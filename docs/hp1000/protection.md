# L-Series memory protection

Standard 32KW L protection is implemented inside the existing HP2100 CPU.
It is independent of the legacy M/E/F memory-protect device and is inactive for
all other CPU models. No HP diagnostic source or absolute image is patched.

## Implemented behavior

STC 7 enables protection; CLC 7 is NOP. OTA/B 7 loads the 15-bit exclusive
upper fence, while OTA/B 7,C writes the 15-bit violation register. LI/MI 7,C
reads/merges the violation address. LMPEN, LMPIRQ and LMPFLT expose enable,
pending request and observed violation count; LFENCE and LVIO expose addresses.
Power reset and L model selection clear the protection state.

Locations 2 through fence-1 are protected from ISZ, STA, STB, JSB, DST and jumps.
A/B aliases at 0/1 are writable; JMP to those locations is prohibited even with
fence zero. Reads and arithmetic operands below the fence are legal. Indirect
pointers can reside below the fence: the ultimate target determines protection.
DST checks each destination, including address wrap; if the second destination
violates, an already completed first store is not rolled back.

A violation suppresses the offending write or I/O operation, records the
instruction's address and requests trap cell 7. All HLTs and I/O operations
except SC 1 are prohibited. The Type 2 request ignores STF/CLF 0 and temporary
I/O deferral, but is gated by SC 4. Parity and UI retain higher priority.
Interrupt acknowledgement disables protection before a non-I/O trap instruction
executes. An I/O trap instruction executes without this disable and without
being rejected by protection.

Violating JMP/JSB instructions still load P with the new jump address; JSB
suppresses the return-address store and uses target+1. The violation register
therefore remains necessary to identify the original instruction. JLA/JLB also
check their resolved target before changing the link accumulator.

## Evidence and limits

The primary programmer specification is 02103-90007 (October 1980), section 4-3,
printed 4-2, PDF 48. ERD 02103-90009 section 2.4.12, printed 2-36/2-37,
PDF 59–60, supplies the jump-P and write-inhibition details. Its I/O exceptions
are inconsistent: paragraph text mentions SC 1/3, and its CPU-chip MPV account
excludes select codes below 10. The implementation follows the later reference
manual's processor-system rule, SC 1 only. KERN's original HLT and LIB CIR
violation checks agree; SC 3 under protection remains a documentation conflict,
not a separately validated behavior.

```sh
python3 tests/hp1000/run_protection.py
python3 tests/hp1000/run_kernel_io.py
```

The independent runner checks fence boundaries across thirteen address-bit
patterns, protected/allowed stores and jumps, A/B exceptions, legal reads,
indirect pointers, double stores, HLT and I/O suppression, enable semantics,
SC 4 gating, JSB trap return and the I/O-trap exception.

Both unchanged KERN entries (13777 and 03777) pass the prior I/O prefix plus
its first two protection violations, with two requests and final LVIO=14270
(TH003). They match at the next explicit simulator stop:
**14311: LIA 10,C**, the next unsupported select code in the decoding sweep.
SC 3 register transfers now work (see `sc3.md`). No select-code response is
faked to advance KERN. Full MPT03–MPT09, the exhaustive relocating fence test, and full
KERN are consequently not claimed to pass. Third-level Type 3 interruption is now implemented and verified by original
MPT09; see `indirect-interrupts.md`. Distributed DMA,
XL protection and electrical timing are not established by these checks.

Artifacts are under `build/hp1000/protection/` and
`build/hp1000/kernel-io-verified/`. The latter records original hashes, diagnostic
checkpoints, matching final CPU/protection state and error-handler guards.

## Unassigned-input update

The SC 10 input blocker is resolved by the explicit provisional 177777 input
assumption. Direct entries now match through MPT03/14324. A fully initialized
continuation reaches the MPT09 three-level indirect interrupt error at 15101.
See `unassigned-io.md` for scope, relocation breakpoints and EOM prerequisites.

## Indirect-interrupt update

The original MPT09 error is resolved; the fully initialized runner passes its
return-address checks and reaches diagnose mode 1 at 15212/OTA 2. See
`indirect-interrupts.md` for reproducible validation and remaining scope.
