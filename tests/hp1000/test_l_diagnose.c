/* Synthetic chip descriptions exercise the shared controller, not simulator
   devices. No card or identity is installed in the running HP2100 simulator. */
#include <stdio.h>
#include <stdlib.h>
#include "hp2100_l_diag.h"

static unsigned checks;
#define CHECK(x) do { checks++; if (!(x)) { \
    fprintf(stderr, "line %u: %s\n", (unsigned)__LINE__, #x); return 1; } } while (0)

int main (void)
{
    L_DIAG bus = {0};
    uint16_t value;
    unsigned i;
    const uint16_t identities[] = {002033, 0100070, 0054420};

    /* No-response means unchanged, including the caller's sentinel. */
    l_diag_begin(&bus, 1, 0);
    for (i = 0; i < 3; i++) {
        value = identities[i];
        CHECK(!l_diag_read(&bus, 2, 1, 0, &value));
        CHECK(value == identities[i]);
    }
    CHECK(!l_diag_configure(&bus, L_DIAG_SLOTS, 1, 020));
    CHECK(!l_diag_configure(&bus, 0, 1, 010));

    /* Registration order and numeric SC order must not determine priority. */
    CHECK(l_diag_configure(&bus, 9, 1, identities[2]));
    CHECK(l_diag_configure(&bus, 3, 1, identities[1]));
    CHECK(l_diag_configure(&bus, 1, 1, identities[0]));
    l_diag_begin(&bus, 1, 0);
    value = 0777;
    CHECK(l_diag_read(&bus, 020, 1, 0, &value));
    CHECK(value == identities[2]);                     /* direct query does not consume it */
    for (i = 0; i < 3; i++) {
        CHECK(l_diag_read(&bus, 2, 1, 0, &value));
        CHECK(value == identities[i]);
    }
    value = 0125252;
    CHECK(!l_diag_read(&bus, 2, 1, 0, &value));
    CHECK(value == 0125252);
    CHECK(l_diag_read(&bus, 033, 1, 0, &value));         /* direct query works after enumeration */
    CHECK(value == identities[0]);
    value = 045;
    CHECK(!l_diag_read(&bus, 077, 1, 0, &value));
    CHECK(value == 045);

    /* Re-entering mode 1 starts a new priority sequence. */
    l_diag_begin(&bus, 1, 0);
    CHECK(l_diag_read(&bus, 2, 1, 0, &value));
    CHECK(value == identities[0]);
    /* A GR-selected read leaves unselected participants available. */
    CHECK(l_diag_read(&bus, 2, 0, 020, &value));
    CHECK(value == identities[2]);
    CHECK(l_diag_read(&bus, 2, 1, 0, &value));
    CHECK(value == identities[1]);
    CHECK(!l_diag_read(&bus, 2, 1, 0, &value));

    l_diag_reset(&bus);
    CHECK(!bus.active);
    CHECK(bus.present[1] && bus.present[3] && bus.present[9]);
    value = 0123;
    CHECK(!l_diag_read(&bus, 2, 1, 0, &value));
    CHECK(value == 0123);
    /* Scope mode 1 to one selected card; other chips are not participants. */
    l_diag_begin(&bus, 0, 020);
    CHECK(l_diag_read(&bus, 2, 0, 020, &value));
    CHECK(value == identities[2]);
    CHECK(!l_diag_read(&bus, 2, 0, 020, &value));
    value = 0456;
    CHECK(!l_diag_read(&bus, 070, 1, 0, &value));
    CHECK(value == 0456);
    l_diag_begin(&bus, 0, 077);
    CHECK(!l_diag_read(&bus, 2, 0, 077, &value));
    CHECK(value == 0456);

    /* Duplicate SCs remain observable, allowing KERN to diagnose a conflict. */
    CHECK(l_diag_configure(&bus, 0, 1, 0140033));
    l_diag_begin(&bus, 1, 0);
    CHECK(l_diag_read(&bus, 2, 1, 0, &value));
    CHECK(value == 0140033);
    CHECK(l_diag_read(&bus, 2, 1, 0, &value));
    CHECK(value == identities[0]);
    CHECK(l_diag_configure(&bus, 0, 0, 0));
    l_diag_begin(&bus, 1, 0);
    CHECK(l_diag_read(&bus, 2, 1, 0, &value));
    CHECK(value == identities[0]);
    /* A scoped restart/termination must not reset other chips' mode state. */
    l_diag_begin(&bus, 1, 0);
    CHECK(l_diag_read(&bus, 2, 1, 0, &value));
    CHECK(value == identities[0]);
    l_diag_begin(&bus, 0, 020);
    CHECK(bus.responded[1] == 1 && bus.responded[9] == 0);
    l_diag_end(&bus, 0, 020);
    CHECK(bus.active && !bus.participant[9] && bus.participant[3]);
    CHECK(l_diag_read(&bus, 2, 1, 0, &value));
    CHECK(value == identities[1]);
    l_diag_end(&bus, 1, 0);
    CHECK(!bus.active);
    printf("PASS: %u diagnose-controller checks\n", checks);
    return 0;
}
