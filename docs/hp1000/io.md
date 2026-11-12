# L-Series processor I/O

The available manuals are sufficient for the implemented processor-I/O prefix.
They do not yet establish a complete interface-card or distributed DMA model.
All additions are confined to the L path in the existing HP2100 CPU.

| Evidence | Relevant coverage |
|---|---|
| 02103-90007 table 4-3, printed 4-5/4-6, PDF 51 | SC 0–7 transfers, flag and control operations |
| 02103-90007 sections 4-4 through 4-11 | Unconditional UI trap, 10 ms TBG, interrupt deferral, mask bit 1 and SC 4 gating |
| 02103-90007 table 3-5, printed 3-16, PDF 46 | Instruction execution times for the functional timer |
| 02103-90009 table 2-1, printed 2-15 through 2-17, PDF 36–38 | SC 7 violation/fence distinction; CLC 6 stops TBG and clears pending request |
| 02103-90009 section 2.3.2, PDF 29–31 | Processor interrupt levels and service |
| Unchanged KERN Rev.2001 TST05 source | Independent end-to-end register, timer, interrupt and UI checks |

Implemented additions:

- SC 0 load/merge/output of the processor's TBG mask bit (bit 1). Other mask
  bits live on interface cards and are not supplied by this processor register.
- SC 1 status input from S bits 8–13 plus TBG mask in bit 15. MLOST is presently
  assumed clear. Existing output/ROM-page and overflow behavior is retained.
- SC 2 global disable/enable, skips and address-latch transfers, independent of
  boot ROM control. The latch is a functional model of the global-address bus;
  mode-1 priority enumeration is implemented (see `diagnose-mode-1.md`).
  Ordinary interface-card routing and diagnose modes 2–7 remain unfinished.
- SC 7 fence output without C; violation-register output/load/merge with C.
  Input without C is NOP. Registers are 15 bits. STC 7 now enables standard protection; see `protection.md`.
- SC 6 flag operations, skips and transfer NOPs, timer enable/disable, and a
  10 ms periodic request. CLC 6 also clears a pending request without needing C.
- TBG Type 3 service through trap cell 6, with CIR update, request acknowledge,
  mask bit 1, Type 3 enable and SC 4 gating. I/O and indirect jumps defer
  service through the following instruction. No legacy interface is acknowledged.
- Unrecognized CPU instructions take unconditional Type 1 service at octal 10,
  below parity priority and ahead of TBG. A missing simulator implementation of
  a documented feature still stops; it is not presented as an unrecognized CPU
  opcode. KERN verifies all sixteen original UI encodings.

## Timing limits

TBG advances in 50 ns units while the CPU executes, using table 3-5 times for
integer instructions and skips, with indirect-level overhead. The fractional
phase is preserved while stopped/disabled and reset on power reset/model
selection. This is a functional virtual-time model, not a host wall-clock timer
or an electrical CPU-chip model. EAU timing uses a conservative bound rather
than operand-dependent timing; DMA delays, first-tick electrical phase and
interrupt-entry bus timing are not cycle-accurate. KERN's TBG checks pass, but
that does not validate those unmodeled timings.

## Verification and entry comparison

```sh
python3 tests/hp1000/run_io.py
python3 tests/hp1000/run_kernel_io.py
```

The first runner passes 47 independent checks, including the 10 ms boundary
using documented 3.2 us NOPs, request gating, I/O deferral and JSB return address,
register transfers and unconditional UI delivery. The second loads and checks
all original absolute words, guards diagnostic error entries, and compares
entry at 13777 with entry at 03777. Both reach the register-check return,
TBTST, JSBTR, UITST and MPTST; TEMP7 records 20 octal UI traps. Both then stop
at **14246: STC 7**, with matching final CPU state and 260 timer ticks.

Thus 13777 is a usable shortcut for this prefix. Full TST05, memory protection,
interface-card I/O, distributed DMA, VCP and full KERN are not passed. Further
work can continue from this boundary using the available protection sections;
missing 02103-90005 and card-specific documentation matter primarily when
implementing full interface routing/DMA. No further manual is required to
reproduce these runs. Results are under `build/hp1000/io/` and
`build/hp1000/kernel-io-verified/`.

## Protection update

The earlier 14246/STC 7 stop is resolved. Both entries now pass the first two
protection violations and stop at 14311/LIA 3,C, a separate ROM-P register read.
Full protection-section coverage is still pending; see `protection.md`.
