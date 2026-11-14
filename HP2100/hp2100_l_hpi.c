/* HP 12009A L-Series HP-IB interface.
   12009-90001 (December 1988), chapter 3. The HP-IB bus and hard-disc
   protocols are shared with the existing 12821A/DA implementation. */
#include <string.h>
#include "hp2100_defs.h"
#include "hp2100_cpu.h"
#include "hp2100_cpu_dmm.h"
#include "hp2100_di.h"
#include "hp2100_l_iop.h"

extern DEVICE hpi_dev;
#include "hp2100_l_amigo.h"
t_stat l_hpi_service (UNIT *);
static t_stat hpi_reset (DEVICE *);
static t_stat hpi_backend (UNIT *, int32, CONST char *, void *);
static L_IOP chip;
static HP_WORD control, mask_word, hold, read_data, phi[8], byte_latch, status_word;
static HP_WORD in_fifo[8], out_fifo[8];
static uint32 in_head, in_count, out_head, out_count;
static uint32 backend = lh, registered, input_left, input_active, input_lf;
static uint32 talking, listening, controller, end_input, dma_byte, configuring;
static uint32 transfers, handshakes, errors, dma_started;
static t_bool dma_fifo_wait, dma_input_wait, input_hold;
static unsigned primary_address, poll_line = 7;
static t_bool poll_enabled = TRUE, poll_sense = TRUE, poll_configure;
static HP_WORD dma_fifo_word;
static t_bool poll_timing;
static double poll_started;
#define hpi_event l_amigo_units[2]
static REG hpi_reg[] = {
    { FLDATA (INHOLD, input_hold, 0) },
    { FLDATA (COUNTSTART, chip.count_started, 0) },
    { ORDATA (STATUS, status_word, 16) }, { ORDATA (CONTROL, control, 16) }, { ORDATA (MASK, mask_word, 16) },
    { ORDATA (BYTELATCH, byte_latch, 16) }, { ORDATA (HOLD, hold, 16) }, { ORDATA (DATA, read_data, 16) },
    { BRDATA (PHI, phi, 8, 10, 8) },
    { BRDATA (INPUT, in_fifo, 8, 10, 8) }, { BRDATA (OUTPUT, out_fifo, 8, 10, 8) },
    { DRDATA (INHEAD, in_head, 4) }, { DRDATA (INCOUNT, in_count, 4) },
    { DRDATA (OUTHEAD, out_head, 4) }, { DRDATA (OUTCOUNT, out_count, 4) },
    { DRDATA (BACKEND, backend, 3), REG_RO },
    { DRDATA (REMAIN, input_left, 9) }, { FLDATA (RECEIVING, input_active, 0) },
    { FLDATA (LF, input_lf, 0) }, { FLDATA (TALK, talking, 0) },
    { FLDATA (LISTEN, listening, 0) }, { FLDATA (CIC, controller, 0) },
    { FLDATA (ENDINPUT, end_input, 0) }, { FLDATA (DMABYTE, dma_byte, 0) },
    { FLDATA (CONFIGURING, configuring, 0) },
    { ORDATA (FLAGS, chip.flags, 4) }, { ORDATA (CONTROLS, chip.controls, 4) },
    { FLDATA (DMAEN, chip.dma_enabled, 0) }, { FLDATA (SRQMASK, chip.srq_mask, 0) },
    { FLDATA (IRQ, chip.irq_pending, 0) }, { BRDATA (REGS, chip.reg, 8, 16, 32) },
    { BRDATA (FDCYL, l_amigo_state.cylinder, 10, 16, 2) },
    { BRDATA (FDHEAD, l_amigo_state.head, 10, 8, 2) },
    { BRDATA (FDSECTOR, l_amigo_state.sector, 10, 8, 2) },
    { DRDATA (FDOFFSET, l_amigo_state.offset, 9) },
    { DRDATA (FDUNIT, l_amigo_state.selected, 2) },
    { ORDATA (FDSECONDARY, l_amigo_state.secondary, 5) },
    { BRDATA (FDPACKET, l_amigo_state.packet, 8, 8, 16) },
    { DRDATA (FDPACKETCOUNT, l_amigo_state.packet_count, 5) },
    { DRDATA (FDREPLYCOUNT, l_amigo_state.reply_count, 9) },
    { DRDATA (FDREPLYPOS, l_amigo_state.reply_pos, 9) },
    { FLDATA (FDREAD, l_amigo_state.read_active, 0) },
    { FLDATA (FDWRITE, l_amigo_state.write_active, 0) },
    { FLDATA (FDUNTALK, l_amigo_state.untalk, 0) },
    { FLDATA (FDIDENTIFY, l_amigo_state.identified, 0) },
    { ORDATA (FDDSJ, l_amigo_state.dsj, 3) },
    { BRDATA (FDBUFFER, l_amigo_state.reply, 8, 8, 256) },
    { BRDATA (FDSTATUS, l_amigo_state.disk_status, 8, 8, 2) },
    { GRDATA (BUSCTL, di[lh].bus_cntl, 2, 8, 0) },
    { GRDATA (ACCEPTORS, di[lh].acceptors, 2, 2, 0) },
    { GRDATA (LISTENERS, di[lh].listeners, 2, 2, 0) },
    { GRDATA (TALKERS, di[lh].talker, 2, 2, 0) },
    { GRDATA (POLL, di[lh].poll_response, 2, 8, 0) },
    { ORDATA (BUSLISTEN, di[lh].cntl_register, 16) },
    { FLDATA (DMASTARTED, dma_started, 0) },
    { DRDATA (TRANSFERS, transfers, 32) }, { DRDATA (HANDSHAKES, handshakes, 32) },
    { DRDATA (ERRORS, errors, 32) }, { NULL }
};
static MTAB hpi_mod[] = {
    { MTAB_XTD | MTAB_VDV, lh, NULL, "FLOPPY", &hpi_backend, NULL, NULL },
    { MTAB_XTD | MTAB_VDV, da, NULL, "HARDDISK", &hpi_backend, NULL, NULL },
    { 0 }
};
DEVICE hpi_dev = {
    "HPI", l_amigo_units, hpi_reg, hpi_mod, 3, 10, 24, 1, 8, 8,
    NULL, NULL, &hpi_reset, NULL, &l_amigo_attach, &l_amigo_detach, NULL,
    DEV_DISABLE | DEV_DIS | DEV_DEBUG, 0, di_deb, NULL, NULL
};
t_bool l_hpi_active (void)
{ return (cpu_configuration & CPU_1000_L) && !(hpi_dev.flags & DEV_DIS); }
t_bool l_hpi_owns (CARD_ID card)
{ return l_hpi_active() && card == (CARD_ID)backend; }
static t_stat hpi_backend (UNIT *unit, int32 value, CONST char *text, void *desc)
{
    (void)unit; (void)text; (void)desc;
    if (chip.dma_enabled || in_count || out_count || input_active) return SCPE_INCOMP;
    l_hpi_crs(); backend = value; l_hpi_crs(); return SCPE_OK;
}
void l_hpi_sync (void)
{
    uint32 active = l_hpi_active();
    if (registered != active) {
        cpu_l_diag_configure(1, active, 04027); /* 02103-90005 table 4-6 */
        registered = active;
    }
}
void l_hpi_mask (HP_WORD value) { mask_word = value; }
HP_WORD l_hpi_mask_read (void) { return (mask_word & 0177776) | ((mask_word >> 5) & 1); }
HP_WORD l_hpi_mode2 (HP_WORD global, t_bool disabled)
{
    return (global & 077) | (!disabled ? 0100 : 0) | (global == 027 ? 0200 : 0)
        | ((chip.controls & 8) ? 0400 : 0) | ((chip.flags & 8) ? 01000 : 0)
        | ((chip.flags & 7) ? 02000 : 0)
        /* ASI precedes HPI in the installed physical priority chain.
           An unmasked higher request blocks PI even with CPU interrupts off. */
        | (l_asi_higher_irq(1) ? 0 : 04000);
}
t_bool l_hpi_irq (void) { return l_hpi_active() && !(mask_word & 040) && l_iop_irq(&chip); }
void l_hpi_ack (void) { chip.irq_pending = FALSE; }
void l_hpi_diagnose (uint32 mode)
{
    if (l_hpi_active()) {
        l_iop_diagnose(&chip, mode, &hpi_dev);
        if (l_iop_diagnose_pending(&chip) && !sim_is_active(&hpi_event)) sim_activate(&hpi_event, 1);
    }
}
void l_hpi_crs (void)
{
    mask_word = 0;
    l_iop_reset(&chip); memset(phi, 0, sizeof phi);
    control = hold = read_data = byte_latch = status_word = 0;
    dma_fifo_wait = dma_input_wait = input_hold = FALSE; primary_address = 0;
    poll_line = 7; poll_enabled = poll_sense = TRUE; poll_configure = poll_timing = FALSE;
    in_head = in_count = out_head = out_count = 0;
    input_left = input_active = input_lf = end_input = 0;
    talking = listening = controller = dma_byte = configuring = dma_started = 0;
    sim_cancel(&hpi_event);
    if (l_hpi_active()) {
        di_bus_control((CARD_ID)backend, 31, BUS_IFC, 0);
        di_bus_control((CARD_ID)backend, 31, 0, 0377);
        di[backend].cntl_register = 0;
    }
}
static t_stat hpi_reset (DEVICE *device)
{
    (void)device;
    hpi_event.dptr = &hpi_dev;
    l_hpi_crs(); mask_word = transfers = handshakes = errors = 0;
    l_amigo_reset(); l_hpi_sync(); return SCPE_OK;
}
/* PHI poll data settles after 2us; the card's PPDONE timer requires 7us.
   Use the L CPU's functional 50ns clock, not host wall time. */
static t_bool poll_elapsed (unsigned ticks)
{
    t_bool active = controller && (phi[3] & 040) && !out_count && !input_active;
    if (!active) poll_timing = FALSE;
    else if (!poll_timing) { poll_started = cpu_l_io_time(); poll_timing = TRUE; }
    return active && cpu_l_io_time() - poll_started >= ticks;
}
static HP_WORD poll_value (void)
{
    HP_WORD response;
    if (phi[7] & 0200) response = di[backend].poll_response;
    else response = poll_enabled && (((phi[6] & 010) != 0) == poll_sense)
        ? 1u << poll_line : 0;
    return (response ^ phi[5]) & phi[4];
}
static HP_WORD conditions (void)
{
    HP_WORD value = phi[2] & 0701; /* latched parity, status change, abort, clear */
    if (out_count < 8) value |= 010;
    if (in_count) value |= 4;
    if (!out_count && !input_active) value |= 2;
    if (di[backend].bus_cntl & BUS_SRQ) value |= 020;
    if (!in_count && poll_elapsed(40) && poll_value()) value |= 040;
    value &= phi[3] & 0777;
    if (value && (phi[3] & 01000)) value |= 01000;
    return value;
}
static t_bool interrupt_condition (void)
{
    return (conditions() & 01000) || (status_word & 040000)
        || ((control & 0200) && (status_word & 010000))
        || ((control & 020) && (di[backend].bus_cntl & BUS_SRQ));
}
static void update_irq (void)
{
    if ((control & 4) && interrupt_condition()) l_iop_flag(&chip, 030, TRUE);
}
/* The shared bus stores a combined NRFD level. Deny it only when this
   listener asserted it; never release a disk's seek holdoff. */
static void hold_input (t_bool holdoff)
{
    if (input_hold != holdoff) {
        input_hold = holdoff;
        di_bus_control((CARD_ID)backend, 31, holdoff ? BUS_NRFD : 0,
                       holdoff ? 0 : BUS_NRFD);
    }
}
static void schedule (void)
{ if (l_hpi_active() && !sim_is_active(&hpi_event)) sim_activate(&hpi_event, l_iop_diagnose_pending(&chip) ? (chip.dma_wait ? chip.dma_wait : 1) : 5); }
void l_hpi_bus_update (void) { schedule(); }
/* Called by the shared bus before a device advances to its next byte. */
t_bool l_hpi_bus_accept (uint8 data)
{
    HP_WORD word = data;
    if (!input_active || !listening || (di[backend].bus_cntl & BUS_ATN) || in_count == 8)
        return FALSE;
    if (di[backend].bus_cntl & BUS_EOI) word |= 01400;
    else if (input_lf && data == 012) word |= 01400;
    else if (input_left == 1) word |= 01000;
    in_fifo[(in_head + in_count) & 7] = word; in_count++;
    if (input_left) input_left--;
    if ((word & 01400) == 01400 || (!input_left && input_active == 1)) {
        input_active = 0; end_input = 1;
    }
    if (in_count == 8 || !input_active)
        hold_input(TRUE);
    update_irq();
    schedule(); return TRUE;
}
/* DIO8 parity is generated by the PHI for command-tagged outbound words,
   independently of the device's right to drive ATN (3-35). */
static HP_WORD command_byte (HP_WORD word)
{
    HP_WORD value = word & 0177, bits = value;
    unsigned odd = 0;
    while (bits) { odd ^= bits & 1; bits >>= 1; }
    if (odd == ((phi[7] & 0400) ? 1u : 0u)) value |= 0200;
    return value;
}
static HP_WORD phi_read_raw (uint32 reg)
{
    HP_WORD value;
    switch (reg) {
        case 0:
            status_word &= ~020000u;
            if (in_count) {
                value = in_fifo[in_head];
                status_word = (status_word & ~020000u) | ((value & 01400) == 01400 ? 020000 : 0);
                if ((value & 01400) == 0400) status_word |= 010000;
                in_head = (in_head + 1) & 7; in_count--;
                if (input_active) hold_input(FALSE);
                return value;
            }
            if (poll_elapsed(40))
                return poll_value();
            phi[2] |= 0100; errors++; return 0;
        case 1: return (phi[1] & 0301) | (controller ? 020 : 0) | 010 | (talking ? 4 : 0) | (listening ? 2 : 0);
        case 2: return conditions();
        case 6: return phi[6] & ~1u;
        default: return phi[reg];
    }
}
static HP_WORD phi_read (uint32 reg)
{
    HP_WORD value = phi_read_raw(reg);
    /* Register 1 retains DO/D1 in D8/D9 for eight-bit hosts (3-40). */
    if (reg != 1) phi[1] = (phi[1] & ~0300u) | ((value >> 2) & 0300);
    return value;
}
static void phi_write (uint32 reg, HP_WORD data)
{
    if (reg != 1 && (phi[6] & 0200)) data = (data & 0377) | ((phi[1] & 0300) << 2);
    switch (reg) {
        case 0:
            poll_timing = FALSE;
            if (out_count == 8) {
                if (chip.dma_enabled) {
                    /* The word is already fetched from memory, but FIFO+
                       holds off its PHI handshake until DMARQ returns. */
                    dma_fifo_word = data; dma_fifo_wait = TRUE;
                }
                else { phi[2] |= 0100; errors++; }
            }
            else { out_fifo[(out_head + out_count) & 7] = data; out_count++; }
            break;
        case 1:
            phi[1] = (phi[1] & ~0300u) | (data & 0300);
            if ((data & 1) && !in_count) phi[1] &= ~1u;
            break;
        case 2: phi[2] &= ~(data & 0701); break;
        case 6:
            phi[6] = data & ~1u;
            if (data & 1) { out_count = out_head = input_active = end_input = 0; }
            if (data & 020) { if (!controller) phi[2] |= 0200; controller = 1; talking = listening = primary_address = 0; }
            if (phi[7] & 0200) di_bus_control((CARD_ID)backend, 31,
                           ((data & 020) ? BUS_IFC : 0) | ((data & 040) ? BUS_REN : 0) | ((data & 4) ? BUS_SRQ : 0),
                           ((data & 020) ? 0 : BUS_IFC) | ((data & 040) ? 0 : BUS_REN) | ((data & 4) ? 0 : BUS_SRQ));
            break;
        case 7:
            /* Going online supplies the interface-function PON message;
               its initial controller state is not an IFC status-change event. */
            if ((data & 0200) && !(phi[7] & 0200)) {
                controller = talking = listening = primary_address = 0;
                phi[2] &= ~0200u;
            }
            phi[7] = data;
            /* TA/LA are latches: clearing ALWAYS does not unaddress the
               chip (12009-90001, 3-51). IFC and address commands do. */
            if (!(phi[6] & 020)) {
                if (data & 0100) talking = 1;
                if (data & 040) listening = 1;
            }
            break;
        default: phi[reg] = data; break;
    }
    schedule();
}
static void handshake (HP_WORD word)
{
    uint32 reg = word >> 12 & 7;
    hold = word;
    control = (control & 07777) | (word & 0170000);
    handshakes++;
    tprintf(hpi_dev, DEB_XFER, "PHI handshake %06o input %u output %u control %06o\n", word, in_count, out_count, control);
    if (word & 0100000) {
        read_data = (word & 0170000) | phi_read(reg);
        if (reg != 0) status_word &= ~020000u; /* EOR decoder is FIFO-only. */
    }
    else { phi_write(reg, word & 01777); read_data = word; }
}
static void configure (void)
{
    l_iop_configure(&chip, &hpi_dev);
    if (chip.reg[021] & 01000) {
        control = chip.reg[031];
        hold = (hold & 01777) | (control & 0170000);
    }
    dma_byte = dma_started = 0;
    dma_fifo_wait = dma_input_wait = FALSE;
}
static void dma_complete (void)
{
    chip.dma_enabled = FALSE;
    if (configuring && (chip.reg[021] & 010000))
        mem_l_dma_write(&hpi_dev, (chip.reg[020] - 1) & 077777, chip.reg[023], chip.reg[021], TRUE);
    if (configuring && (chip.reg[021] & 0100000)) configure();
    else {
        t_bool pending = chip.irq_pending;
        l_iop_flag(&chip, configuring ? 020 : 021, TRUE);
        if (chip.reg[021] & 04000) chip.irq_pending = pending;
        configuring = 0;
        chip.self_configured = chip.auto_pending = FALSE;
    }
}
static void dma_transfer (void)
{
    HP_WORD value, word;
    uint32 address = chip.reg[022] & 077777;
    t_bool input = (chip.reg[021] & 0200) != 0, byte = (chip.reg[021] & 020000) != 0;
    t_bool last = FALSE;
    /* PPOLL holds N+1 SRQ until the outgoing FIFO drains. Memory count
       rollover can precede that last device handshake (4-11/4-12). */
    if (!chip.reg[023] && chip.count_started) {
        if (!input && (control & 2) && !poll_elapsed(140)) return;
        dma_complete(); return;
    }
    if (input) {
        if (control & 0100000) {
            /* PHI DMARQ follows register 6's FIFO selector, independently
               of IOP transfer direction (12009-90001, 3-49). ID.37 selects
               the outbound FIFO before draining up to eight inbound bytes;
               its ready output FIFO therefore clocks even empty input reads. */
            if ((control & 070000) == 0 && !in_count
              && !(control & 04000) && !(phi[6] & 2)) {
                if (!(control & 02000) && !dma_input_wait) {
                    phi_read(0); dma_input_wait = TRUE;
                }
                return;
            }
            dma_input_wait = FALSE;
            value = phi_read(control >> 12 & 7);
        }
        else value = byte ? (dma_byte ? byte_latch & 0377 : byte_latch >> 8) : hold;
        last = ((control & 01000) && (value & 01400) == 01400)
            || ((control & 0400) && (value & 01400) == 0400);
        if (byte) {
            word = mem_l_dma_read(&hpi_dev, address, chip.reg[021], chip.diagnose_mode == 3);
            value = dma_byte ? (word & 0177400) | (value & 0377) : ((value & 0377) << 8) | (word & 0377);
        }
        if (!byte) value |= control & 0170000;
        mem_l_dma_write(&hpi_dev, address, value, chip.reg[021], chip.diagnose_mode == 3);
    }
    else {
        if (dma_fifo_wait && out_count == 8) return;
        dma_fifo_wait = FALSE;
        if ((control & 02000) && out_count == 8) return;
        value = mem_l_dma_read(&hpi_dev, address, chip.reg[021], chip.diagnose_mode == 3);
        byte_latch = value;
        if (byte) {
            value = (control & 01700) | (dma_byte ? value & 0377 : value >> 8);
            if ((control & 01000) && chip.reg[023] != 0177777) value &= ~01000u;
            phi_write(control >> 12 & 7, value);
        }
        else {
            hold = value;
            if (chip.reg[021] & 040000) handshake(value);
        }
    }
    transfers++;
    chip.reg[023] = (chip.reg[023] + 1) & 0177777;
    chip.count_started = TRUE;
    if (!byte || dma_byte) chip.reg[022] = (address + 1) & 077777;
    if (byte) dma_byte ^= 1;
    if ((!chip.reg[023] || last) && (input || !(control & 2) || poll_elapsed(140))) dma_complete();
}
/* An offline PHI uses the same address and FIFO protocol on a private bus
   (12009-90001 3-52). No external drive sees these transfers. */
static void offline_step (void)
{
    HP_WORD word, value;
    unsigned address = controller ? 036 : phi[7] & 037;
    t_bool deliver = FALSE;
    if ((phi[7] & 0200) || !out_count || (phi[6] & 020) || (phi[2] & 1)) return;
    word = out_fifo[out_head];
    value = word & 0377;
    if (controller && (word & 01400) == 0400) {
        unsigned command = word & 0177;
        if (command >= 0140 && command < 0160 && poll_configure) {
            poll_line = command & 7; poll_sense = (command & 010) != 0;
            poll_enabled = TRUE;
        }
        else if (command >= 0140 && primary_address) {
            if (in_count == 8) return;
            value = 0400 | (command & 037) | (primary_address == 1 ? 0200 : 0);
            deliver = TRUE;
        }
        else {
            primary_address = 0; poll_configure = FALSE;
            if (command == (0100 | address)) { talking = 1; primary_address = 1; }
            else if ((command & 0140) == 0100) talking = 0;
            else if (command == (040 | address)) { listening = 1; primary_address = 2; }
            else if (command == 077) listening = 0;
            else if (command == 010) status_word |= 040000;
            else if (command == 005 && listening) poll_configure = TRUE;
        }
    }
    else {
        if (!talking) return;
        if (listening) {
            if (in_count == 8) return;
            value = ((word & 0400) ? command_byte(word) : word & 0377)
                | ((word & 01000) ? 01400 : 0);
            deliver = TRUE;
        }
    }
    if (deliver) { in_fifo[(in_head + in_count) & 7] = value; in_count++; }
    out_head = (out_head + 1) & 7; out_count--;
}
t_stat l_hpi_service (UNIT *unit)
{
    HP_WORD word;
    t_bool accepted;
    (void)unit;
    if (!l_hpi_active()) return SCPE_OK;
    if (l_iop_diagnose_pending(&chip)) {
        l_iop_diagnose_step(&chip, &hpi_dev);
        configuring = chip.self_configured;
    }
    if (end_input) {
        uint8 release = input_hold ? BUS_NRFD : 0;
        end_input = input_hold = 0;
        /* Assert ATN before releasing NRFD: DA may synchronously source
           another byte when NRFD is denied with ATN low. */
        di_bus_control((CARD_ID)backend, 31, BUS_ATN, release);
    }
    offline_step();
    if (out_count && !input_active && (phi[7] & 0200)) {
        word = out_fifo[out_head]; accepted = TRUE;
        if ((word & 01400) == 0400) {
            uint8 release = BUS_EOI | (input_hold ? BUS_NRFD : 0);
            input_active = end_input = input_hold = 0;
            di_bus_control((CARD_ID)backend, 31, BUS_ATN, release);
            if (di[backend].bus_cntl & BUS_NRFD) accepted = FALSE;
            else {
            if ((word & 0377) == (0100 | (controller ? 036 : phi[7] & 037))) talking = 1;
            else if ((word & 0140) == 0100) talking = 0;
            if ((word & 0377) == (040 | (controller ? 036 : phi[7] & 037))) listening = 1;
            else if ((word & 0377) == 077) listening = 0;
            di[backend].cntl_register = listening ? 4 : 0; /* shared bus listener */
            di_bus_source((CARD_ID)backend, word & 0377);
            }
        }
        else if (!talking && controller) {
            input_left = word & 0377; input_lf = !(word & 01000);
            input_active = (word & 01400) == 01400 && !input_left ? 2 : 1;
            if (!input_left && input_active == 1) input_left = 256;
            di_bus_control((CARD_ID)backend, 31, 0, BUS_ATN | BUS_EOI);
        }
        else {
            di_bus_control((CARD_ID)backend, 31, (word & 01000) ? BUS_EOI : 0,
                           BUS_ATN | ((word & 01000) ? 0 : BUS_EOI));
            /* The shared disk backend may hold NRFD throughout a seek.
               Retain this FIFO word until every listener is ready. */
            accepted = !(di[backend].bus_cntl & BUS_NRFD) && di_bus_source((CARD_ID)backend, word & 0377);
        }
        if (accepted) { out_head = (out_head + 1) & 7; out_count--; }
    }
    if (dma_fifo_wait && chip.dma_enabled && out_count < 8) {
        out_fifo[(out_head + out_count) & 7] = dma_fifo_word;
        out_count++; dma_fifo_wait = FALSE;
    }
    if (chip.dma_enabled && !chip.srq_mask && chip.diagnose_mode != 3) {
        /* Advance one DMA/configuration cycle per service. PHI and bus
           handshakes must settle before the next self-configuration word. */
        if (!(control & 010) || interrupt_condition()) dma_started = 1;
        if (dma_started && !((control & 0100) && interrupt_condition()))
            dma_transfer();
    }
    (void)poll_elapsed(0);
    update_irq();
    if (out_count || chip.dma_enabled) schedule();
    return SCPE_OK;
}
t_bool l_hpi_io (HP_WORD instruction, HP_WORD global, t_bool disabled, HP_WORD *data, t_bool *skip)
{
    uint32 reg = instruction & 077, op = instruction >> 6 & 7, action;
    t_bool clear = (instruction & 01000) != 0, clc = op == 7 && (instruction & 04000);
    t_bool dma_before = chip.dma_enabled;
    HP_WORD value;
    if (!l_hpi_active()) return FALSE;
    if (disabled) { if (reg != 027) return FALSE; reg = 030; }
    else if (global != 027 || reg < 020) return FALSE;
    *skip = FALSE;
    if (reg == 031 || reg == 032) {
        if (op == 6 && reg == 031) {
            control = *data;
            hold = (hold & 01777) | (control & 0170000);
            if (control & 1) { control = status_word = 0; hold &= 01777; chip.flags &= ~8u; }
        }
        if (op == 6 && reg == 032) status_word &= ~010000u;
        if (op == 4 || op == 5) {
            value = reg == 031 ? control : 036 | status_word
                | ((control & 2) && poll_elapsed(140) ? 0100000 : 0)
                | ((conditions() & 01000) ? 04000 : 0)
                | ((control & 0100) && interrupt_condition() ? 02000 : 0)
                | ((di[backend].bus_cntl & BUS_SRQ) ? 01000 : 0)
                | (((phi[6] & 2) ? out_count < 8 : in_count != 0) ? 0400 : 0);
            if (op == 5) *data = 0;
            *data |= value;
            if (reg == 032) status_word &= ~040000u;
        }
        schedule(); return TRUE;
    }
    if (reg == 030 && op == 6) { dma_fifo_wait = FALSE; hold = *data; control = (control & 07777) | (hold & 0170000); chip.reg[030] = hold; }
    if (reg == 030 && (op == 4 || op == 5)) chip.reg[030] = (read_data & 01777) | (control & 0170000);
    action = l_iop_io(&chip, reg, clc ? 017 : op, clear, data, skip);
    if (reg == 022 && op == 6) chip.reg[022] &= 077777;
    if (action & L_IOP_CONFIG) {
        if (reg == 020 || configuring) { configuring = 1; configure(); }
        else chip.dma_enabled = FALSE;
    }
    if (action & L_IOP_ABORT) {
        l_iop_abort(&chip, &hpi_dev);
        configuring = chip.self_configured;
    }
    if (reg == 020 && clc) { configuring = 0; chip.self_configured = FALSE; chip.dma_enabled = dma_before; }
    if (reg == 023 && clc) configuring = 0;
    if (reg == 021 && op == 7 && !clc) { dma_byte = dma_started = 0; }
    if (chip.diagnose_mode == 3 || chip.srq_mask) {
        l_iop_diagnose(&chip, chip.diagnose_mode, &hpi_dev);
        configuring = chip.self_configured;
    }
    if (action & L_IOP_START) { handshake(hold); }
    update_irq();
    schedule(); return TRUE;
}
