/* HP 12005A serial interfaces. ASI is the VCP card; ASI1 is an optional
   independent card. Both share this implementation and hp2100_l_iop.c. */
#include "hp2100_defs.h"
#include "hp2100_cpu.h"
#include "hp2100_l_iop.h"
#include "hp2100_cpu_dmm.h"

#define UNIT_LOOPBACK (1u << UNIT_V_UF)
#define UNIT_HOOD (1u << (UNIT_V_UF + 1))
#define ASI_CARDS 2
extern DEVICE asi_dev, asi1_dev;
static t_stat asi_service (UNIT *unit);
static t_stat asi_reset (DEVICE *device);
static t_stat asi_set_sc (UNIT *, int32, CONST char *, void *);
static t_stat asi_show_sc (FILE *, UNIT *, int32, CONST void *);
typedef struct {
    L_IOP chip;
    HP_WORD control, status_word, mask_word;
    uint32 rx, tx, rx_ready, rx_wait, tx_wait, uart_diag, slave_pending;
    HP_WORD select_code, tx_latch;
    uint32 baud_code, dma_byte;
    double tx_due, tx_started, break_start, baud_reset;
    t_bool parity_corrupt;
    t_bool break_low;
    t_bool registered;
} ASI_CARD;
static ASI_CARD cards[ASI_CARDS] = {{ .select_code = 020, .baud_code = 15 },
                                     { .select_code = 021, .baud_code = 15 }};
static UNIT asi_units[ASI_CARDS] = {
    { UDATA(&asi_service, UNIT_ATTABLE | UNIT_SEQ | UNIT_TEXT, 0) },
    { UDATA(&asi_service, UNIT_ATTABLE | UNIT_SEQ | UNIT_TEXT, 0) }
};
#define ASI_REGS(n) \
    { ORDATA (CONTROL, cards[n].control, 16) }, \
    { ORDATA (STATUS, cards[n].status_word, 16) }, \
    { ORDATA (MASK, cards[n].mask_word, 16) }, \
    { ORDATA (SC, cards[n].select_code, 6), REG_RO }, \
    { ORDATA (RX, cards[n].rx, 8) }, { ORDATA (TX, cards[n].tx, 8) }, \
    { FLDATA (RXREADY, cards[n].rx_ready, 0) }, { FLDATA (RXWAIT, cards[n].rx_wait, 0) }, \
    { FLDATA (TXWAIT, cards[n].tx_wait, 0) }, { FLDATA (UARTDIAG, cards[n].uart_diag, 0) }, \
    { FLDATA (SLAVE, cards[n].slave_pending, 0) }, \
    { ORDATA (FLAGS, cards[n].chip.flags, 4) }, { ORDATA (CONTROLS, cards[n].chip.controls, 4) }, \
    { FLDATA (DMAEN, cards[n].chip.dma_enabled, 0) }, { FLDATA (SRQMASK, cards[n].chip.srq_mask, 0) }, \
    { FLDATA (IRQ, cards[n].chip.irq_pending, 0) }, \
    { BRDATA (REGS, cards[n].chip.reg, 8, 16, 32) }
static REG asi_reg[] = { ASI_REGS(0), { NULL } };
static REG asi1_reg[] = { ASI_REGS(1), { NULL } };
static MTAB asi_mod[] = {
    { UNIT_LOOPBACK, UNIT_LOOPBACK, "loopback", "LOOPBACK", NULL },
    { UNIT_LOOPBACK, 0, "no loopback", "NOLOOPBACK", NULL },
    { UNIT_HOOD, UNIT_HOOD, "24397-60003 test hood", "HOOD", NULL },
    { UNIT_HOOD, 0, "no test hood", "NOHOOD", NULL },
    { MTAB_XTD | MTAB_VDV, 0, "SC", "SC", &asi_set_sc, &asi_show_sc, NULL },
    { 0 }
};
DEVICE asi_dev = {
    "ASI", &asi_units[0], asi_reg, asi_mod, 1, 8, 16, 1, 8, 8,
    NULL, NULL, &asi_reset, NULL, &attach_unit, &detach_unit, NULL,
    DEV_DISABLE | DEV_DIS, 0, NULL, NULL, NULL
};
DEVICE asi1_dev = {
    "ASI1", &asi_units[1], asi1_reg, asi_mod, 1, 8, 16, 1, 8, 8,
    NULL, NULL, &asi_reset, NULL, &attach_unit, &detach_unit, NULL,
    DEV_DISABLE | DEV_DIS, 0, NULL, NULL, NULL
};
static DEVICE *card_device (unsigned index) { return index ? &asi1_dev : &asi_dev; }
static unsigned card_position (unsigned index) { return index ? 2 : 0; } /* HPI is slot 1 */
static t_bool card_active (unsigned index)
{ return (cpu_configuration & CPU_1000_L) && !(card_device(index)->flags & DEV_DIS); }
static ASI_CARD *find_card (HP_WORD sc)
{
    unsigned i;
    for (i = 0; i < ASI_CARDS; i++)
        if (card_active(i) && cards[i].select_code == sc) return &cards[i];
    return NULL;
}
/* UART timings use the same instruction-time scale as the functional L TBG
   (50 ns per timing unit). No host sleeps or diagnostic command matching. */
static uint32 character_ticks (const ASI_CARD *card)
{
    static const double baud[16] = {62500,50,75,110,134.5,150,300,600,900,1200,1800,2400,3600,4800,7200,9600};
    uint32 bits = 1 + ((card->control & 0400) ? 8 : 7) + 2 + ((card->control & 020000) ? 1 : 0);
    return (uint32)(20000000.0 * bits / baud[(asi_units[card - cards].flags & UNIT_HOOD) ? (card->control >> 3) & 15 : card->baud_code & 15] + 0.999);
}
static t_bool special_character (const ASI_CARD *card)
{
    uint32 value = card->rx & 0177;
    switch (card->control >> 14 & 3) {
        case 1: return value == 004 || value == 010 || value == 015 || value == 022 || value == 0177;
        case 2: return value == 036;
        case 3: return value == 015;
        default: return FALSE;
    }
}
static t_bool serial_mark (const ASI_CARD *card)
{
    uint32 bits = (card->control & 0400) ? 8 : 7;
    double frame_bit;
    unsigned at;
    if (!card->tx_wait) return TRUE;
    frame_bit = character_ticks(card) / (double)(1 + bits + 2 + ((card->control & 020000) ? 1 : 0));
    at = (unsigned)((cpu_l_io_time() - card->tx_started) / frame_bit);
    if (!at) return FALSE;
    if (at <= bits) return (card->tx >> (at - 1)) & 1;
    return TRUE;
}
static HP_WORD serial_status (ASI_CARD *card)
{
    unsigned index = (unsigned)(card - cards);
    HP_WORD status = card->status_word & 074000;
    HP_WORD modem = 0;
    t_bool mark = !(card->uart_diag && !(card->control & 4));
    if (asi_units[index].flags & UNIT_HOOD) {
        /* 24612-90011 table 2-1: M-V is TR->RR; W-Z is SD(U)->DM;
           B-2/F-3 and X-E wrap RS to IC/CS; 9-15/10-17 wrap SD to SRD. */
        if (card->control & 1) modem |= 01000;
        if (card->control & 2) modem |= 020 | 040;
        if (serial_mark(card)) modem |= 010 | 02000;
    }
    else if (asi_units[index].flags & UNIT_LOOPBACK) {
        if (card->control & 1) modem |= 010 | 01000;
        if (card->control & 2) modem |= 020 | 040;
        if (serial_mark(card)) modem |= 02000;
    }
    else modem = 02000;
    status |= modem;
    if (!(card->control & 0200)
      || ((card->control & 0170) == ((modem & 070) | ((modem & 01000) >> 3)))) status |= 0100;
    if (!status || !(status & 074000)) status |= 0100000;
    if (!special_character(card)) status |= 0200;
    if (card->uart_diag && (card->control & 1)) status |= 0400;
    if (mark && !card->tx_wait) status |= 4;
    if (!card->tx_wait) status |= 2;
    if (card->rx_ready) status |= 1;
    return status;
}
static void start_tx (ASI_CARD *card, UNIT *unit, HP_WORD value)
{
    card->tx = value & ((card->control & 0400) ? 0377 : 0177);
    card->tx_wait = 1;
    card->tx_started = cpu_l_io_time();
    card->parity_corrupt = FALSE;
    card->tx_due = card->tx_started + character_ticks(card);
    if ((card->control & 0200) && !(serial_status(card) & 0100))
        l_iop_flag(&card->chip, 030, TRUE);
    sim_activate(unit, (character_ticks(card) + 127) / 128);
}
static void serial_reset (ASI_CARD *card, uint32 diagnose)
{
    card->control = card->status_word = 0;
    card->rx_wait = card->tx_wait = card->rx_ready = 0;
    card->uart_diag = diagnose;
    card->break_low = card->parity_corrupt = FALSE;
    card->tx_latch = 0; /* UART reset does not erase the received data latch. */
}
static void control_write (ASI_CARD *card, HP_WORD value)
{
    unsigned index = (unsigned)(card - cards);
    HP_WORD old = card->control;
    card->control = value;
    /* 24612-90011 table 2-1 and 12005-90001 figure 7-4: RDM/RCS/RIC/RRR
       drive the BRG selects. ECHOM->DRST pulses its reset, rather than
       latching the select word. U1 supplies 1MHz to EXTCLK (16x baud). */
    if (asi_units[index].flags & UNIT_HOOD) {
        if (!(old & 04000) && (value & 04000)) card->baud_reset = cpu_l_io_time();
        if ((old & 04000) && !(value & 04000) && card->tx_wait) {
            double since = card->baud_reset > card->tx_started ? card->baud_reset : card->tx_started;
            double held = cpu_l_io_time() - since;
            card->tx_started += held; card->tx_due += held;
        }
    }
    if ((asi_units[index].flags & UNIT_HOOD) && card->tx_wait && (old & 4) && !(value & 4))
        card->parity_corrupt = TRUE;
    if (card->uart_diag) {
        if (!(value & 4) && !card->break_low) {
            card->break_start = cpu_l_io_time(); card->break_low = TRUE;
        }
        else if ((value & 4) && card->break_low) {
            if (cpu_l_io_time() - card->break_start >= character_ticks(card)) {
                card->status_word |= 040000;
                if (!index) card->slave_pending = 1;
                else l_iop_flag(&card->chip, 030, TRUE);
            }
            card->break_low = FALSE;
        }
    }
    if ((value & 0200) && !(serial_status(card) & 0100)) l_iop_flag(&card->chip, 030, TRUE);
}
static void receive_byte (ASI_CARD *card, uint32 value)
{
    if (card->rx_ready) card->status_word |= 04000;
    card->rx = value & 0377;
    card->rx_ready = 1;
    card->chip.reg[030] = card->rx;
}
t_bool l_asi_active (void) { return card_active(0); } /* only the VCP card owns the keyboard */
t_bool l_asi_any_active (void) { return card_active(0) || card_active(1); }
t_bool l_asi_present (HP_WORD sc) { return find_card(sc) != NULL; }
void l_asi_sync (void)
{
    unsigned i;
    for (i = 0; i < ASI_CARDS; i++) {
        t_bool active = card_active(i);
        if (cards[i].registered != active) {
            cpu_l_diag_configure(card_position(i), active, cards[i].select_code);
            cards[i].registered = active;
        }
    }
}
static void card_crs (unsigned index)
{
    ASI_CARD *card = &cards[index];
    card->mask_word = 0;
    l_iop_reset(&card->chip);
    serial_reset(card, 0);
    card->baud_code = 15;
    sim_cancel(&asi_units[index]);
}
void l_asi_crs (void) { unsigned i; for (i = 0; i < ASI_CARDS; i++) card_crs(i); }
static t_stat asi_reset (DEVICE *device)
{
    unsigned i = device == &asi1_dev;
    card_crs(i);
    cards[i].rx_ready = cards[i].slave_pending = 0;
    l_asi_sync();
    return SCPE_OK;
}
static t_stat asi_set_sc (UNIT *unit, int32 value, CONST char *text, void *desc)
{
    t_stat status;
    uint32 sc;
    unsigned i = (unsigned)(unit - asi_units);
    (void)value; (void)desc;
    if (!text) return SCPE_ARG;
    sc = (uint32)get_uint(text, 8, 077, &status);
    if (status != SCPE_OK || sc < 020 || sc == 027 || sc == cards[1-i].select_code) return SCPE_ARG;
    if (cards[i].chip.dma_enabled || cards[i].tx_wait || cards[i].rx_wait) return SCPE_INCOMP;
    cpu_l_diag_configure(card_position(i), FALSE, cards[i].select_code);
    cards[i].registered = FALSE; cards[i].select_code = sc; l_asi_sync();
    return SCPE_OK;
}
static t_stat asi_show_sc (FILE *stream, UNIT *unit, int32 value, CONST void *desc)
{
    (void)value; (void)desc;
    fprintf(stream, "SC=%02o", cards[unit - asi_units].select_code);
    return SCPE_OK;
}
void l_asi_mask (HP_WORD value)
{ unsigned i; for (i = 0; i < ASI_CARDS; i++) cards[i].mask_word = value; }
HP_WORD l_asi_mask_read (HP_WORD sc)
{
    ASI_CARD *card = find_card(sc);
    return card ? (card->mask_word & 0177776) | ((card->mask_word >> (sc >> 2)) & 1) : 0;
}
static t_bool card_irq (unsigned i)
{
    return card_active(i) && !(cards[i].mask_word & (1u << (cards[i].select_code >> 2)))
        && l_iop_irq(&cards[i].chip);
}
t_bool l_asi_higher_irq (unsigned position)
{
    unsigned i;
    for (i = 0; i < ASI_CARDS; i++) if (card_position(i) < position && card_irq(i)) return TRUE;
    return FALSE;
}
HP_WORD l_asi_mode2 (HP_WORD sc, HP_WORD global, t_bool disabled)
{
    ASI_CARD *card = find_card(sc);
    unsigned index;
    t_bool priority;
    if (!card) return 0;
    index = (unsigned)(card - cards);
    priority = !l_asi_higher_irq(card_position(index)) && (!index || !l_hpi_irq());
    return (global & 077) | (!disabled ? 0100 : 0) | (global == sc ? 0200 : 0)
        | ((card->chip.controls & 8) ? 0400 : 0) | ((card->chip.flags & 8) ? 01000 : 0)
        | ((card->chip.flags & 7) ? 02000 : 0) | (priority ? 04000 : 0) | (!index ? 010000 : 0);
}
void l_asi_diagnose (uint32 mode, HP_WORD global, t_bool disabled)
{
    unsigned i;
    for (i = 0; i < ASI_CARDS; i++) if (card_active(i) && (disabled || global == cards[i].select_code)) {
        l_iop_diagnose(&cards[i].chip, mode, card_device(i));
        if (l_iop_diagnose_pending(&cards[i].chip) && !sim_is_active(&asi_units[i])) sim_activate(&asi_units[i], 1);
    }
}
t_bool l_asi_irq (void) { return card_irq(0) || card_irq(1); }
HP_WORD l_asi_irq_sc (void) { return card_irq(0) ? cards[0].select_code : card_irq(1) ? cards[1].select_code : 0; }
void l_asi_ack (HP_WORD sc) { ASI_CARD *card = find_card(sc); if (card) card->chip.irq_pending = FALSE; }
t_bool l_asi_slave (void) { return card_active(0) && cards[0].slave_pending; }
void l_asi_slave_ack (void) { cards[0].slave_pending = 0; }

/* UART SRQ transfers one character. Packed DMA starts with the high byte;
   continuation may change direction while the last transmitted frame is active. */
static void uart_dma (ASI_CARD *card, UNIT *unit, DEVICE *device)
{
    L_IOP *chip = &card->chip;
    HP_WORD word, value, address;
    t_bool input, packed, terminate = FALSE;
    if (!chip->dma_enabled || chip->srq_mask || chip->diagnose_mode == 3) return;
    input = (chip->reg[021] & 0200) != 0;
    packed = (chip->reg[021] & 020000) != 0;
    if (input ? !card->rx_ready : card->tx_wait) return;
    if (!chip->reg[023]) {
        chip->flags |= 2;
        l_iop_complete(chip, device);
        card->dma_byte = 0;
        return;
    }
    address = chip->reg[022] & 077777;
    if (input) {
        value = card->rx;
        terminate = special_character(card);
        if (packed) {
            word = mem_read(device, DMA_Channel_1, address);
            value = card->dma_byte ? (word & 0177400) | (value & 0377)
                                   : ((value & 0377) << 8) | (word & 0377);
        }
        mem_write(device, DMA_Channel_1, address, value);
        card->rx_ready = 0;
    }
    else {
        value = mem_read(device, DMA_Channel_1, address);
        if (cpu_l_dma_parity_error(address, value)) {
            chip->dma_enabled = chip->self_configured = FALSE;
            l_iop_flag(chip, 022, TRUE);
            return;
        }
        if (packed) value = card->dma_byte ? value & 0377 : value >> 8;
        card->tx_latch = value;
        start_tx(card, unit, value);
    }
    if (!packed || card->dma_byte) chip->reg[022] = (address + 1) & 077777;
    if (packed) card->dma_byte ^= 1;
    chip->reg[023] = (chip->reg[023] + 1) & 0177777;
    /* An unchained transmit remains busy until the UART consumes its last
       frame; chained transfers must reconfigure while that frame is active. */
    if ((!chip->reg[023] || terminate)
      && (input || (chip->self_configured && (chip->reg[021] & 0100000)))) {
        if (!(chip->self_configured && (chip->reg[021] & 0100000))) chip->flags |= 2;
        l_iop_complete(chip, device);
        card->dma_byte = 0;
        if (chip->dma_enabled && (chip->reg[021] & 01000)) control_write(card, chip->reg[031]);
    }
    if (chip->dma_enabled || card->tx_wait) sim_activate(unit, 1);
}
static t_stat asi_service (UNIT *unit)
{
    t_stat result;
    unsigned index = (unsigned)(unit - asi_units);
    ASI_CARD *card = &cards[index];
    DEVICE *device = card_device(index);
    if (!card_active(index)) return SCPE_OK;
    l_iop_diagnose_step(&card->chip, device);
    if (card->tx_wait && !((unit->flags & UNIT_HOOD) && (card->control & 04000))
      && cpu_l_io_time() >= card->tx_due) {
        if (card->uart_diag || (unit->flags & (UNIT_LOOPBACK | UNIT_HOOD))) {
            receive_byte(card, card->tx);
            if (card->parity_corrupt && (card->control & 020000)) {
                card->status_word |= 020000;
                if (!card->break_low) l_iop_flag(&card->chip, 030, TRUE);
            }
        }
        else {
            if (index == 0) {
                result = sim_putchar_s(card->tx);
                if (result == SCPE_STALL) { sim_activate(unit, 100); return SCPE_OK; }
                if (result != SCPE_OK) return result;
            }
            if (unit->flags & UNIT_ATT) {
                if (fputc(card->tx, unit->fileref) == EOF) return SCPE_IOERR;
                unit->pos++; fflush(unit->fileref);
            }
        }
        card->tx_wait = 0;
        /* At terminal count the last TRE is the N+1 service request. No
           memory element remains to consume it, so it sets the device flag
           even if CINT suppressed the DMA-completion interrupt. */
        if (!card->break_low && (!card->chip.dma_enabled
          || (!(card->chip.reg[021] & 0200) && !card->chip.reg[023])))
            l_iop_flag(&card->chip, 030, TRUE);
    }
    uart_dma(card, unit, device);
    if (card->rx_wait && card->rx_ready) {
        card->chip.reg[030] = card->rx;
        card->status_word |= 0100001;
        if (card->control & 04000) {
            result = sim_putchar_s(card->rx); if (result != SCPE_OK) return result;
            if (unit->flags & UNIT_ATT) { if (fputc(card->rx, unit->fileref) == EOF) return SCPE_IOERR;
                unit->pos++; fflush(unit->fileref); }
        }
        card->rx_wait = card->rx_ready = 0;
        l_iop_flag(&card->chip, 030, TRUE);
    }
    if (l_iop_diagnose_pending(&card->chip)) sim_activate(unit, card->chip.dma_wait);
    else if (card->tx_wait) {
        double remaining = card->tx_due - cpu_l_io_time();
        sim_activate(unit, remaining > 128 ? (int32)(remaining / 128) : 1);
    }
    return SCPE_OK;
}
t_stat l_asi_poll (void)
{
    t_stat value;
    ASI_CARD *card = &cards[0];
    UNIT *unit = &asi_units[0];
    if (!l_asi_active()) return SCPE_OK;
    value = sim_poll_kbd();
    if (value < SCPE_KFLAG && value != SCPE_OK) return value;
    if (value == SCPE_OK) { /* still service an already buffered byte below */ }
    else if (value & SCPE_BREAK) { card->status_word |= 040000; card->slave_pending = 1; }
    else if (card->rx_ready) { card->status_word |= 04000; if (card->control & 010000) l_iop_flag(&card->chip, 030, TRUE); }
    else { card->rx = value & 0377; card->rx_ready = 1; }
    if (card->rx_ready && (card->rx_wait
      || (card->chip.dma_enabled && (card->chip.reg[021] & 0200)))) sim_activate(unit, 1);
    return SCPE_OK;
}
t_bool l_asi_io (HP_WORD instruction, HP_WORD global, t_bool disabled,
                 HP_WORD *data, t_bool *skip)
{
    uint32 reg = instruction & 077, op = instruction >> 6 & 7, action;
    t_bool clear = (instruction & 01000) != 0;
    ASI_CARD *card = find_card(disabled ? reg : global);
    unsigned index;
    UNIT *unit;
    DEVICE *device;
    if (!card) return FALSE;
    index = (unsigned)(card - cards); unit = &asi_units[index]; device = card_device(index);
    if (disabled) reg = 030;
    else if (reg < 020) return FALSE;
    if (reg == 031 || reg == 032) {
        if (op == 6) {
            if (reg == 031) control_write(card, *data);
            else serial_reset(card, *data & 1);
        }
        else if (op == 4 || op == 5) {
            if (op == 5) *data = 0;
            *data |= reg == 031 ? card->control : serial_status(card);
            if (reg == 032) card->status_word &= ~040000u;
        }
        *skip = FALSE;
        return TRUE;
    }
    if (reg == 030 && op == 6) card->tx_latch = *data;
    if (reg == 030 && (op == 4 || op == 5)) card->chip.reg[030] = card->rx;
    action = l_iop_io(&card->chip, reg, op == 7 && (instruction & 04000) ? 017 : op,
                      clear, data, skip);
    if (action & L_IOP_CONFIG) {
        card->dma_byte = 0;
        l_iop_configure(&card->chip, device);
        if (card->chip.reg[021] & 01000) control_write(card, card->chip.reg[031]);
        /* STC20,C starts the interface with DVCMD (12005-90001 3-36).
           With packed DMA active, BYTEN selects the upper output-buffer byte. */
        if (clear && (card->chip.reg[021] & 0200) && (card->control & 01000)) {
            HP_WORD value = (card->chip.reg[021] & 020000) ? card->tx_latch >> 8 : card->tx_latch;
            start_tx(card, unit, value);
        }
    }
    if (action & L_IOP_ABORT) l_iop_abort(&card->chip, device);
    if ((action & L_IOP_CONFIG) || (reg == 021 && op == 7)) {
        card->dma_byte = 0;
        if (card->chip.dma_enabled) sim_activate(unit, 1);
    }
    /* Mode 3 may precede STC21; masked external SRQ does not inhibit AUTO. */
    if (card->chip.diagnose_mode == 3 || card->chip.srq_mask)
        l_iop_diagnose(&card->chip, card->chip.diagnose_mode, device);
    if (l_iop_diagnose_pending(&card->chip) && !sim_is_active(unit)) sim_activate(unit, 1);
    if (reg == 030 && (op == 4 || op == 5) && (card->control & 02000)) card->rx_ready = 0;
    if (action & L_IOP_START) {
        if ((card->control & 03000) == 03000) card->rx_ready = 0;
        if (card->control & 01000) {
            start_tx(card, unit, card->tx_latch);
        }
        else if (card->control & 02000) { card->rx_wait = 1; card->status_word &= ~1u; sim_activate(unit, 1); }
        if ((card->status_word & 04000) && (card->control & 010000)) l_iop_flag(&card->chip, 030, TRUE);
    }
    return TRUE;
}
