# L-Series diagnose mode 1

Mode 1 identifies external I/O chips in physical priority order. It does not
identify CPU processor registers as I/O cards and does not synthesize a console
card. The running simulator currently has **zero L-Series interface cards**.

## Documentation and source

02103-90007 sections 5-23/5-24, printed 5-10, PDF 62, specify:

- OTA/B 2 with data 1 establishes mode 1 without changing the global address.
  With GR disabled all chips accept the command; with GR enabled only the
  selected chip accepts it. Data 0 terminates the diagnose sequence.
- LIA/B 2 returns one chip's complete select-code/identification word, highest
  physical priority first, then advances priority to the next chip. A chip
  responds once until mode 1 is re-established.
- After the last responder, another LIA/B 2 leaves the accumulator unchanged.
  This no-response rule is explicitly documented, independent of the provisional
  177777 value used for ordinary unassigned input.
- A direct LIA/B at a participating chip's select code returns its identity
  without consuming the enumeration sequence. Table 5-2 specifies the identity
  word; the controller preserves all sixteen bits supplied by the card driver.

Original KERN CHIPS/GETSC/NOSC (24397-18002 Rev.2001 source lines 5729–5770)
clears A before each LIA 2. An unchanged zero ends enumeration. KERN then
requires at least one table entry; zero cards deliberately takes IOERR with the
comment **"NO I/O CHIPS RESPONDED. ERROR"**. Returning a fabricated card ID would
conceal the absent interface implementation.

## Implementation

The existing L CPU handler sends mode-1 commands and reads to the controller in
`HP2100/hp2100_l_diag.h`. No separate emulator or fake device is created.
`cpu_l_diag_configure(position, present, identity)` lets future real L card
drivers supply a chip description. Position expresses physical priority, not
numeric select-code order. Duplicate select codes remain observable so the
original diagnostic can detect misconfiguration.

Controller state records configured chips, participating chips and chips that
have already responded. GR-scoped commands preserve other chips' mode state;
CRS and power reset clear the sequence while preserving physical configuration.
Data 0 terminates mode 1 without loading an invalid external address into GR.
Changing the global address does not terminate the sequence. State is exposed
as LDIAG1 and hidden LDID/LDINST/LDPART/LDSEEN arrays and is included in simulator
save state. The CPU registration API installs descriptions only; ordinary card
I/O, interrupts and DMA still require actual interface drivers.

Documented LIA/B enumeration and direct queries are supported. MIA/B while mode
1 is active stops explicitly because section 5-24 does not specify mode-1 merge
semantics. Diagnose modes 2–7 also remain unsupported. Other CPU models keep
their existing I/O paths.

## Verification and current outcome

```sh
python3 tests/hp1000/run_diagnose.py
python3 -m unittest discover -s tests/hp1000 -v
python3 tests/hp1000/run_kernel_indirect.py
```

The instruction runner passes 57 cases: A/B command forms, unchanged sentinel
values for empty enumerations/direct queries, C-modifier flag behavior, restart,
termination, CRS, global-address preservation and explicit unsupported cases.
The unit suite compiles the exact shared controller with synthetic chip
*descriptions*, testing physical priority versus SC/registration order, complete
identity values, one response per chip, exhaustion, restart, direct queries,
GR selection, scoped termination, duplicate SCs and configuration removal. Those
synthetic descriptions never appear as devices in the running simulator.

The original fully initialized KERN continues past OTA 2 and reaches its real
NOSC error. The runner stops at IOERR executable entry (17710) and verifies the
source-derived call return, empty select-code table, unchanged A=0 and active
mode 1. Its JSON reports `NO_IO_CHIPS_RESPONDED`, **not** a full diagnostic pass.
MPT09 remains PASS. At least one real L interface implementation—preferably the
12005A console—is needed before KERN's I/O-chip tests can proceed meaningfully.
Full VCP and full KERN remain unfinished.

Artifacts: `build/hp1000/diagnose/` and `build/hp1000/kernel-indirect/`.
