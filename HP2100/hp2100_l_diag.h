/* HP 1000 L-Series diagnose mode 1 (02103-90007 sections 5-23/5-24).
   A small controller shared by the CPU path and independent protocol tests.
   Each entry represents an I/O chip in physical priority order, not SC order.
   No entries are installed by default; real L card drivers must supply them. */
#ifndef HP2100_L_DIAG_H
#define HP2100_L_DIAG_H

#include <stdint.h>
#include <string.h>

#define L_DIAG_SLOTS 48

typedef struct {
    uint16_t identity[L_DIAG_SLOTS];
    uint8_t present[L_DIAG_SLOTS];
    uint8_t participant[L_DIAG_SLOTS];
    uint8_t responded[L_DIAG_SLOTS];
    uint8_t active;
} L_DIAG;

static inline int l_diag_configure (L_DIAG *bus, unsigned slot, int present, uint16_t identity)
{
    if (slot >= L_DIAG_SLOTS || (present && (identity & 077) < 020))
        return 0;
    bus->identity[slot] = identity;
    bus->present[slot] = present != 0;
    bus->participant[slot] = bus->responded[slot] = 0;
    return 1;
}

static inline void l_diag_reset (L_DIAG *bus)
{
    memset(bus->participant, 0, sizeof bus->participant);
    memset(bus->responded, 0, sizeof bus->responded);
    bus->active = 0;
}

static inline void l_diag_begin (L_DIAG *bus, int global_disabled, uint16_t global)
{
    unsigned slot;
    for (slot = 0; slot < L_DIAG_SLOTS; slot++) {
        if (bus->present[slot]
          && (global_disabled || (bus->identity[slot] & 077) == global)) {
            bus->participant[slot] = 1;
            bus->responded[slot] = 0;
        }
    }
    bus->active = 1;
}

static inline void l_diag_end (L_DIAG *bus, int global_disabled, uint16_t global)
{
    unsigned slot;
    bus->active = 0;
    for (slot = 0; slot < L_DIAG_SLOTS; slot++) {
        if (global_disabled || (bus->identity[slot] & 077) == global)
            bus->participant[slot] = bus->responded[slot] = 0;
        if (bus->present[slot] && bus->participant[slot])
            bus->active = 1;
    }
}

/* Return zero for no responder without touching *value. Direct queries do not
   consume priority; enumerated queries consume each participating chip once. */
static inline int l_diag_read (L_DIAG *bus, unsigned select_code,
                              int global_disabled, uint16_t global, uint16_t *value)
{
    unsigned slot;
    if (!bus->active)
        return 0;
    for (slot = 0; slot < L_DIAG_SLOTS; slot++) {
        if (!bus->present[slot] || !bus->participant[slot])
            continue;
        if (select_code == 2) {
            if (bus->responded[slot]
              || (!global_disabled && (bus->identity[slot] & 077) != global))
                continue;
            bus->responded[slot] = 1;
        }
        else if ((bus->identity[slot] & 077) != select_code)
            continue;
        *value = bus->identity[slot];
        return 1;
    }
    return 0;
}
#endif
