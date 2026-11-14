/* Shared HP 1000 L/A I/O-chip programmed-I/O and diagnostic DMA subset.
   02103-90005 sections II/IV; 12006-90001 table 3-1. */
#ifndef HP2100_L_IOP_H
#define HP2100_L_IOP_H
/* Include hp2100_defs.h before this header, as for hp2100_cpu.h. */

typedef struct {
    HP_WORD reg[32];
    uint32 flags, controls, diagnose_mode, dma_wait;
    t_bool dma_enabled, srq_mask, irq_pending, self_configured, auto_pending, count_started;
} L_IOP;
#define L_IOP_CONFIG 1
#define L_IOP_START  2
#define L_IOP_ABORT  4
void l_iop_reset (L_IOP *chip);
void l_iop_flag (L_IOP *chip, uint32 reg, t_bool set);
t_bool l_iop_irq (const L_IOP *chip);
uint32 l_iop_io (L_IOP *chip, uint32 reg, uint32 op, t_bool clear,
                 HP_WORD *data, t_bool *skip);
void l_iop_configure (L_IOP *chip, DEVICE *device);
void l_iop_complete (L_IOP *chip, DEVICE *device);
void l_iop_abort (L_IOP *chip, DEVICE *device);
t_bool l_iop_diagnose_pending (const L_IOP *chip);
t_bool l_iop_diagnose_step (L_IOP *chip, DEVICE *device);
void l_iop_diagnose (L_IOP *chip, uint32 mode, DEVICE *device);
#endif
