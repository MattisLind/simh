#include <string.h>
#include "hp2100_defs.h"
#include "hp2100_cpu.h"
#include "hp2100_cpu_dmm.h"
#include "hp2100_l_iop.h"

static uint32 flag_bit (uint32 reg)
{
    if (reg >= 020 && reg <= 022) return 1u << (reg - 020);
    return reg == 030 ? 8u : 0;
}
void l_iop_reset (L_IOP *chip) { memset(chip, 0, sizeof *chip); }
void l_iop_flag (L_IOP *chip, uint32 reg, t_bool set)
{
    uint32 bit = reg == 023 ? 7u : flag_bit(reg);
    if (!set && reg == 020) bit = 3;
    if (set) { chip->flags |= bit; chip->irq_pending = TRUE; }
    else chip->flags &= ~bit;
}
t_bool l_iop_irq (const L_IOP *chip)
{
    /* DMA parity (FLG22) requests service independently of CNTRL30.
       02103-90005 section 2-32; KERN INT.4 forces it with STF22. */
    return chip->irq_pending && ((chip->flags & 4u) != 0
                                || (chip->flags & chip->controls & 013u) != 0);
}
uint32 l_iop_io (L_IOP *chip, uint32 reg, uint32 op, t_bool clear,
                 HP_WORD *data, t_bool *skip)
{
    uint32 action = 0, bit = flag_bit(reg);
    t_bool flag = reg == 023 ? (chip->flags & 7) != 0 : (chip->flags & bit) != 0;
    if (reg == 024) flag = chip->dma_enabled;
    *skip = FALSE;
    switch (op) {
        case 1: l_iop_flag(chip, reg, !clear); return 0;
        case 2: case 3: *skip = flag == (op == 3); break;
        case 4: case 5: {
            HP_WORD value = chip->reg[reg & 037];
            /* IOP readback: configuration bit 15 is tied high. The DMA
               address's bit 15 reports the complement of CW1 IN (bit 7).
               Both are also checked by original KERN REGCK. */
            if (reg == 020) value |= 0100000;
            if (reg == 022)
                value = (value & 077777) | ((chip->reg[021] & 0200) ? 0 : 0100000);
            if (op == 5) *data = 0;
            *data |= value;
            break;
        }
        case 6: chip->reg[reg & 037] = *data & 0177777u; break;
        case 7:
            /* The caller supplies CLC via bit 3 of op, then normalizes here. */
            break;
        case 017:
            chip->controls &= ~bit;
            if (reg == 020) chip->self_configured = FALSE;
            if (reg == 021 || reg == 023) chip->dma_enabled = FALSE;
            if (reg == 023) chip->self_configured = FALSE;
            if (reg == 022) action = L_IOP_ABORT;
            break;
    }
    if (op == 7) {
        chip->controls |= bit;
        if (chip->flags & bit) chip->irq_pending = TRUE;
        if (reg == 020) action = L_IOP_CONFIG;
        if (reg == 021) { chip->dma_enabled = TRUE; chip->self_configured = FALSE; chip->dma_wait = 1; }
        if (reg == 030) action = L_IOP_START;
    }
    if (clear) l_iop_flag(chip, reg, FALSE);
    return action;
}
static void parity_abort (L_IOP *chip)
{
    chip->dma_enabled = chip->self_configured = chip->auto_pending = FALSE;
    l_iop_flag(chip, 022, TRUE);
}
static t_bool config_word (L_IOP *chip, DEVICE *device, HP_WORD *value)
{
    HP_WORD address = chip->reg[020] & 077777;
    *value = mem_read(device, DMA_Channel_1, address);
    chip->reg[020] = (address + 1) & 077777;
    if (cpu_l_dma_parity_error(address, *value)) {
        parity_abort(chip);
        return FALSE;
    }
    return TRUE;
}
void l_iop_configure (L_IOP *chip, DEVICE *device)
{
    HP_WORD value;
    chip->dma_enabled = chip->self_configured = chip->auto_pending = FALSE;
    if (!config_word(chip, device, &chip->reg[021])) return;
    /* Figure 2-3, 02103-90005: optional interface CW31 precedes address/count.
       Each fetch advances CONAD, including a word that fails parity. */
    if ((chip->reg[021] & 01000) && !config_word(chip, device, &chip->reg[031])) return;
    if (!config_word(chip, device, &value)) return;
    chip->reg[022] = value & 077777;
    if (!config_word(chip, device, &chip->reg[023])) return;
    chip->dma_enabled = chip->self_configured = TRUE;
    chip->dma_wait = 1;
    chip->auto_pending = (chip->reg[021] & 0600) == 0400;
}
/* 02103-90005 section 2-23: CLC22 aborts without an interrupt and
   advances a running self-configuration sequence. CLC23 stops it. */
void l_iop_abort (L_IOP *chip, DEVICE *device)
{
    chip->dma_enabled = FALSE;
    if (chip->self_configured) l_iop_configure(chip, device);
}
void l_iop_complete (L_IOP *chip, DEVICE *device)
{
    t_bool pending = chip->irq_pending;
    uint32 flag = chip->self_configured ? 020 : 021;
    chip->dma_enabled = FALSE;
    if (chip->self_configured && (chip->reg[021] & 010000))
        mem_write(device, DMA_Channel_1, (chip->reg[020] - 1) & 077777, chip->reg[023]);
    if (chip->self_configured && (chip->reg[021] & 0100000))
        l_iop_configure(chip, device);
    else {
        chip->self_configured = chip->auto_pending = FALSE;
        l_iop_flag(chip, flag, TRUE);
        if (chip->reg[021] & 04000) chip->irq_pending = pending;
    }
}
void l_iop_diagnose (L_IOP *chip, uint32 mode, DEVICE *device)
{
    chip->diagnose_mode = mode;
    if (mode == 7) chip->srq_mask = TRUE; /* latched until CRS */
    /* AUTO starts the first output without an external SRQ. A continuation
       may configure another AUTO block. Internal mode-3 input words are
       scheduled separately, so the CPU runs while DMA steals cycles. */
    if (chip->srq_mask && chip->dma_enabled) {
        uint32 budget = 65536;
        while (chip->dma_enabled && budget--) {
            if (!chip->reg[023]) { l_iop_complete(chip, device); continue; }
            if (!chip->auto_pending) break;
            {
                HP_WORD address = chip->reg[022] & 077777;
                chip->reg[030] = mem_read(device, DMA_Channel_1, address);
                chip->auto_pending = FALSE;
                chip->reg[022] = (address + 1) & 077777;
                chip->reg[023] = (chip->reg[023] + 1) & 0177777;
                if (cpu_l_dma_parity_error(address, chip->reg[030])) {
                    parity_abort(chip);
                    break;
                }
            }
            if (!chip->reg[023]) l_iop_complete(chip, device);
        }
    }
}
t_bool l_iop_diagnose_pending (const L_IOP *chip)
{
    return chip->dma_enabled && chip->diagnose_mode == 3 && (chip->reg[021] & 0200);
}
t_bool l_iop_diagnose_step (L_IOP *chip, DEVICE *device)
{
    uint32 words = 0;
    if (!l_iop_diagnose_pending(chip)) return FALSE;
    /* Bounded backplane grants: the L CPU's CPUTURN limits holdoff to
       32 memory cycles (02103-90005 section 2-17). Instruction-event
       pacing is a functional approximation, not a microcycle model. */
    while (l_iop_diagnose_pending(chip) && words < 32) {
        if (chip->reg[023]) {
            mem_write(device, DMA_Channel_1, chip->reg[022] & 077777, chip->reg[020]);
            chip->reg[020] = (chip->reg[020] + 1) & 077777;
            chip->reg[022] = (chip->reg[022] + 1) & 077777;
            chip->reg[023] = (chip->reg[023] + 1) & 0177777;
            words++;
        }
        if (!chip->reg[023]) l_iop_complete(chip, device);
    }
    chip->dma_wait = words ? words : 1;
    return l_iop_diagnose_pending(chip);
}
