# Development log

## 10 November 2026

Applied owner decisions: L-Series first, integrated into the existing HP2100
emulator; other series deferred. Updated the handoff to make these controlling
decisions explicit. Historical originals remain unchanged and are ignored by git.

Recorded baseline 87eb7d5e96f9ce0ee6ac183e20160e5c486b0712; forced a successful
build and register sanity check. Added bounded load/add/store regressions for all
seven existing CPU models. No prior HP2100 regression scripts were present.

Indexed and hashed local references. Found original L-specific 24397 sources and
binaries, making the generic 24612 Master I/O source a secondary starting point.
Recovered the Rev.2001 kernel, checked all 114 records, verified source anchors,
and asserted all 6,239 loaded words in an existing CPU memory container. Added
five decoder tests including corruption/truncation rejection. Independently boot-loaded
the unchanged image via the existing PTR loader and checked 6,237 memory words
against the Python decoder, excluding loader scratch registers A/B. No L instructions
were executed and no original diagnostic pass was claimed.

Read/OCRed 02103-90007 and visually confirmed its title and documentation map.
Identified exact L-specific manual numbers to request and documented distributed
I/O, global-register addressing, and interrupt-vector differences from M/E/F.
Next work is the detailed CPU/engineering-manual audit and model capability
integration; kernel execution validation also needs operating instructions.

Checked the added `02103-90009_L-Series_ERD_Sep80.pdf`: 461 pages, identical
SHA-256 and bytes to the existing long-named ERD. Text extraction returned no
page text across all 461 pages. Recorded the duplicate and extraction limitation
in the reference index; originals were not modified.

The owner reports 24397-90002 (kernel operation), 02103-90005 (I/O interfacing),
and 24397-90003 (DDL operation/programming) cannot be found. Recorded all three
as unavailable acquisition leads. Initial CPU work continues from the supplied
architecture manuals; diagnostic operation and DDL behavior will be reconstructed
from the L-specific sources and binaries with uncertainties recorded explicitly.
No additional diagnostic coverage or hardware behavior is claimed by this update.

Implemented the first L-Series CPU subset in HP2100: `SET CPU 1000-L`, a
distinct model configuration bit with existing encodings preserved, all fourteen
memory-reference operations through the common executor, NOP, simulator HLT,
and L-specific all-ones nonexistent-memory reads. Writes to absent memory remain
ignored. Legacy protected-loader commands and boot ROMs are refused for L;
conventional DMA channels are disabled and their interrupt/DMA execution paths
excluded. Other instruction groups stop explicitly with P preserved, regardless
of RUN -B or NOSTOP. SHOW CPU identifies the experimental scope.

Validated 48 independent L-Series checks, including unsupported paths, memory
boundaries, and model transitions. Rebuilt with warnings-as-errors and passed
RegisterSanityCheck, the seven existing-model smoke checks, both original-image
load checks, and five decoder tests. No original diagnostic instructions were
executed. The next implementation increment is shift/rotate and alter/skip,
then extended arithmetic and CPU-resident I/O/trap behavior, using the manuals
and kernel source to resolve L-specific semantics.

Investigated the original processor firmware files identified by the owner.
Both 4,096-byte hex payloads validate their stored byte-sum checksums. They
are low/high byte lanes, not consecutive ROM halves. A narrow directive resolver
plus the existing HP2100 symbolic assembler reproduces all 3,675 emitted source
words exactly from unchanged Rev.2150 source. No additional 12001 revisions
were found locally; unused PROM padding remains unchanged.

Visually checked ERD Appendix A and processor memory/slave-mode sections.
Implemented user-supplied processor ROM loading, four 1K pages selected by
processor output bits 8:7, instruction-dependent ROM/RAM reads, RAM stores,
CPU A/B aliases, software reset entry at offset 2, and ROM-aware stop output.
Extended the L integer executor to shift/alter and documented EAU encodings;
added the small processor I/O subset needed for the initial instruction tests.

Authentic startup now traverses 156 instructions of the CPU pretest and stops
on unfinished CLC 5 at logical 00416/source 04416. This is a partial startup
result, not full pretest or VCP success. Full processor I/O, parity, timers,
interrupts, the actual 12005A card, slave mode, and diagnostic bootstrap remain
unimplemented. Recorded authentic VCP startup as an early milestone before RTE.

At the owner's request, directly loaded and executed the unchanged KERN
Rev.2001 absolute binary in L RAM with ROM disabled. Added a bounded probe
for source/binary entry points 2, 3000, and 4. Entry 2 boots through location
3 into START at octal 3000; START rewrites both 2 and 4 with restart jumps.
Both initial-entry paths stop at 03003/SFS 4, the first unsupported power-status
operation. Entry 4 before initialization enters the illegal-interrupt path and
stops at 03254/LIA 4. All 6,239 image words were verified before each execution.
Recorded traces/registers and clarified the misleading source comment naming 4.
No diagnostic test section or suite pass is claimed.

Implemented the L-Series processor SC 4 functions from 02103-90007 table 4-3:
power-up/down skips, six-bit CIR load/merge/output, Type 2/3 enable state and
STF/CLF NOPs, including C modifiers. The L sense of SFS/SFC is distinct from
M/E/F and uses its own handler. LPFAIL and LINT23 expose the modeled state;
full power-fail interrupt generation/delivery remains future work.

Added 26 directed checks; all 81 L CPU checks pass. KERN now passes SFS 4
at 03003 and stops on CLC 0,C at 03005 from either initial entry. The address-4
error path also progresses past LIA 4 and reaches its CLC 0,C at 03265.

Implemented SC 0 control/flag operations in the L handler: CLC 0 broadcasts
CRS to L cards (none installed), its C modifier clears Type 3 enable, STF/CLF
and SFS/SFC operate on that flag, and STC 0 is NOP except optional clear.
The existing earlier-model path already implements both CLC forms; L dispatch
had previously stopped them. Retained the shared CRS concept while avoiding
broadcasts to incompatible legacy devices. Added 18 checks, all 99 now pass.

KERN now executes memory-test code. The 10,000-step probes stop by budget;
an additional entry-2 run reaches 100,000 instruction attempts and expires in
the address-parity pattern code at 03520. These remain UNKNOWN; no diagnostic
section pass is claimed. Existing-model, firmware-prefix, and unit regressions
also pass. SC 0 mask transfers, real L card reset recipients, and interrupt
delivery remain future work.

Ran KERN's complete word-memory phase at the owner's request. Located PEIT in
the source at 03641 and verified its entry signature against the binary. The
unchanged image completes the phase and reaches PEIT without entering guarded
memory/error-display handlers. Final FADD/LADD are 020000/077777 and EOM is
077777 for the 32KW model. Added a reproducible runner with source/image hashes,
original and relocated error breakpoints, completion assertions, and bounded
execution. The formal run completed in about 1.8 seconds without a large trace.

Continued with tracing into the parity-error interrupt phase: it stops at
03647, CLC 5, the unimplemented parity-system control. Recorded the first
original KERN subset pass (word-memory phase), keeping the full diagnostic
and hardware parity tests explicitly unfinished. No emulator or HP artifact
was patched for this run.

Implemented software RAM parity at the owner's request: one stored parity bit
per standard L word, odd/even generation/checking, SC 5 control/registers,
bad-data completion, bad-fetch suppression and unmaskable Type 1 delivery.
No diagnostic-specific branches or source/binary patches were added.

Unchanged KERN now passes word-memory and parity-interrupt phases and reaches
TST01 at 03777. Fault instrumentation verifies 512 bad-data reads plus one
bad fetch; final LPAR is 103710. Independent tests pass 18/18, prior L tests
99/99, and existing-model, image-load, unit and firmware-prefix regressions pass.
The following CPU-test probe remains UNKNOWN by instruction budget. Original
ROM startup advances to OTB 7,C at 00425. Limits and repeatable commands are
in `parity.md`.

### Direct KERN instruction-test execution

Ran unchanged KERN from 03777 and compared with execution after complete memory
and parity phases. Both stop identically at 06366/100600 (JLA). Added a bounded
checkpoint runner; TST02, TST03, TST04 and TSTJL are reached without guarded
error-handler entry. TST05 remains unreached; full instruction tests and full
KERN remain incomplete. No CPU implementation changes in this investigation.

### L-Series JLA/JLB

Implemented canonical JLA/JLB in the existing CPU's L-only decoder and added
L-only symbolic assembly/disassembly. Verified ERD figure 2-8 sheets 1/2 and
KERN return-link constants: selected accumulator receives P after the inline
operand; resolved operand supplies jump destination. Flags/other accumulator
are preserved. Added eight directed checks plus ROM operand/indirect checks.
Unmodified KERN instruction tests now reach TST05 at 13777 without guarded
error entry. Existing-model, parity, firmware-prefix and unit regressions pass.

### Processor-I/O prefix and direct TST05 entry

Compared original KERN at 13777 and 03777. Initial blocker was OTA 7,C at 00720.
Added processor mask/status/global controls, fence/violation registers, SC 6
functional timer and Type 3 service, and unconditional UI Type 1 service. Checked
reference tables 3-5/4-3 and ERD table 2-1 and interrupt descriptions. Both entries
now pass the processor-I/O prefix and sixteen UI traps, then stop identically at
14246/STC 7; protection enforcement is the next boundary. Added 47 independent
I/O checks and a guarded entry-comparison runner. Timer limitations and missing
interface/DMA coverage are documented in io.md. Existing regressions pass;
firmware prefix now checks completion of OTB 7,C rather than unsupported stop.

### Standard L protection enforcement

Added L-only protection enable/request state, resolved-target checks for MRG
writes/jumps and JL*, per-word DST checks, HLT/I/O inhibition, violation capture,
and SC 4-gated Type 2 service. Interrupt acknowledgement retains protection only
for an I/O trap instruction. ERD 2.4.12 confirms that violating JMP/JSB still
load P; writes remain inhibited. Added an independent protection runner and
extended the original KERN entry comparison through its first two violations.
Both entries now stop at 14311/LIA 3,C, separate unfinished ROM-P register work.
Full KERN protection tests remain unverified; no diagnostic patch/bypass used.

### SC 3 ROM-P/P-SAVE register transfers

Added L-only 16-bit register load/merge/output with C selecting ROM-P, without C
selecting P-SAVE. Verified reference section 2-27/table 4-3 and original VCP's
bit-15 single-cycle flag. Added 27 directed SC 3 checks, bringing I/O checks to
74. KERN advances from LIA 3,C to LIA 10,C at its self-modifying 14311 location;
both entries match. Extended original reset probe reaches 00710/STC 11.
Full pretest, CLC 3 slave transitions, serial and interactive VCP remain open.

### Provisional idle input for unassigned L select codes

Implemented the owner's chosen 177777 input assumption for unassigned SC 10–77,
LI/MI A/B with or without C, with existing processor handlers and all other
models unchanged. Added 40 directed cases (114 total I/O checks). KERN's
select-code sweep now completes at MPT03/14324 from either direct entry.
Relocating fence test exposed an error-breakpoint collision, not a diagnostic
failure; bounded direct-entry verification now ends before relocation. A
separate original startup continuation catches the real MPT09 indirect-chain
interrupt error at 15101 via CPERR entry. Documented EOM initialization needs
for later tests and left indirect-chain behavior unchanged in this update.

### L built-in indirect-chain interrupt recognition

Implemented the L counterpart of the 2116 optional-MP facility: permit Type 3
service at the third indirect level, preserve a completed jump's destination,
and restart longer chains without partial JSB stores. TBG pointer-read timing
now permits requests to arrive inside a long chain. Master/mask/SC 4 gates stay
in force; LMPEN is not required. Added 17 L checks and two 2116 board-presence
regressions, plus a source-verified original KERN MPT09 runner. All pass. KERN
now stops at 15212/OTA 2, diagnose mode 1; the 15101 error is resolved.

### Diagnose mode 1

Implemented documented mode-1 selection and identity enumeration, using physical
priority order and unchanged accumulators for no response. Added a shared
controller with real-driver registration, scoped GR behavior and saved state.
No L card is installed or fabricated. Added 57 simulator instruction checks and
populated-controller tests using synthetic descriptions confined to a C unit
test. Original KERN now reaches NOSC's genuine no-I/O-chip error at IOERR/17710;
its runner checks that condition explicitly without claiming full KERN passes.
MPT09 remains PASS. Diagnose modes 2–7 and real L interface drivers remain open.

## 12005A / VCP update (2026-11-11)

The supplied 12005-90001 May 1981 reference manual and 02103-90005 November
1984 I/O guide are now available; earlier missing-manual and no-interface
statements above are superseded. The manuals folder currently contains 12 PDFs,
including 12006, 12009A and later A/L diagnostic references; A-only material
remains deferred. Local page counts and hashes are recorded in
`build/hp1000/manuals/index.json`; OCR extracts for 12005, 12006 and the I/O
guide are under the same directory.

Authentic ROM pretests and interactive VCP now pass using the optional ASI
interface, including register changes, single-step and run/halt return.
Initialized KERN with ASI enumerates SC 20 and reaches TST06. Full KERN,
normal serial DMA and diagnostic bootstrap remain unproven. See
[12005a.md](12005a.md) for hardware references, test commands and limitations.

## 12009A and original diagnostic-disc boot (2026-11-11)

`run_hpi.py` passes seven grouped checks: card registers, card IRQ during
indirection, packed DMA chains/residue, existing DA hard-drive identification,
a byte-DMA write checked against the whole synthetic image, authentic RTE-L
BOOTX and authentic HPIB diagnostic startup from 24397A.hpi. The latter prints
its title and READY; running it passes its initial register/DMA checks but stops
in the PHI chip tests, so no full diagnostic pass is claimed.

The RTE-L BOOTX HLT 2 is a documented missing-SYSTEM checkpoint. The two XL
masters likewise have no SYSTEM entry. Hardware bring-up continues separately
from the unverified RTE-IVB/RTLGN generation route. See [12009a.md](12009a.md)
and [rte-l-generation.md](rte-l-generation.md).

## RTE-IVB generation-host checkpoint (2026-11-11)

The user-supplied original RTE-IVB image boots in the existing 1000-E simulation
using a separate byte-swapped copy. All 55 RTE-L relocatable files restore and
verify through the original READR. The original RTLGN links with `$LDRLB` and
`$MXLB`, including all four segments, and starts through its initial command-file
check. `run_rte_ivb.py` automates these checks and confirms that the source disk
is unchanged. No complete RTE-L generation or running L-Series OS is claimed.
See [rte-ivb-host.md](rte-ivb-host.md) for exact inputs, commands and remaining work.

## Genuine RTE-L SYSTEM generated and loaded (2026-11-11)

Original RTLGN completes with 0 errors under IVB after allocating 24 host pages
and correcting the kernel/background generation phases. The 32KW ASI/12009A/
7902 configuration uses HP COMND as its startup background program. Original
VCP/BOOTX loads SYSTEM and reaches 02003; 31,742 words match the generator file.
The repeatable runner preserves both source disks and every original target
file. This is not yet an installed disk-based FMGR system. See `rte-l-built.md`.

Per user direction, pause OS bring-up here: require KRNL, then a second ASI with
virtual loopback and ASIC, then HPIB, before returning to RTE-L boot work.

## Complete disk KRNL pass (2026-11-11)

The original KRNL loaded by VCP from `24397A.hpi` reaches TST09 at 17770 and
writes success status 177777, with ASI SC20 and HPI SC27 installed. No diagnostic
or ROM patches are used. The new `run_krnl_disk.py` requires full source-defined
completion, preserving original disk hashes and recording failures. Shared IOP
fixes cover status/priority, reset, DMA configuration/chaining/residue, timed
mode-3 transfers and card-side parity. See `diagnostic-results.md` for scope and
pacing limitations. Proceed next with the second ASI/virtual loopback and ASIC.

## RTE-L load, full KRNL, second ASI and original ASIC progress

Generated authentic SYSTEM is present and loads to 02003; the boot runner compares
31,742 words. Full disk KRNL passes with all three cards, at 17770/LSTATUS177777.
Added ASI1 and a virtual loopback using the shared ASI and I/O-chip implementation;
added UART frame timing, special-character handling and packed/chained UART DMA.
Four grouped ASI runs include original VCP and direct DMA/residue checks. Processor
I/O now has 116 checks including a disabled-but-running CPU tick divider.

Original ASIC is not complete: it passes its internal/serial DMA checks and baud
checks through 900, then stalls in DDL timer-interrupt dispatch during 1200. Added
an original-disk runner that reports this as failure, and documented the observed
pending-count/table inconsistency. No HP program was patched or bypassed. Full
HPIB diagnostic work and further RTE-L execution remain queued behind ASIC.

## ASIC deferred; original HPIB validation resumed

Per the user's updated instruction, continue HPIB development while leaving the
full ASIC test unfinished. This supersedes the earlier ASIC-before-HPIB gate.
The ASIC timing stall is retained as an open issue, not marked as passed.

Added an original-disk HPIB runner and offline PHI bus behavior, address latches,
command parity, packed/word DMA EOR termination and residue, input/output FIFO
backpressure, delayed/frozen DMA conditions, forced FIFO reads, secondary-address
latching, GET status and internal parallel-poll configuration. Hardware references
and the diagnostic checkpoints are recorded in 12009a.md. No HP binary or original
media is patched. Further RTE-L execution remains behind hardware validation.

## HPIB complete; documented hood and later authentic ASIC complete

Original disk HPIB now identifies the 7902, runs the controller loopback and
prints PASS COMPLETE. Its runner separately requires interface completion and
actual disc loopback. Thirteen focused HP-IB groups pass; the optional two-card
program was not run.

The newly supplied 24612-90011 supplies the actual ASIC hood wiring. Added a
separate HOOD option, 1MHz external clock/reference-selected baud rates, BRG reset
hold, SD-to-DM/SRD status and SSD parity-fault injection. The original ASIC
Rev.2040 absolute binary, loaded by authentic VCP from an appended file in a
working disk copy, passes all baud rates, the external clock test and PASS
COMPLETE. HP's Rev.2040 DDL source/binary fixes the old PINT no-entry path by
restoring interrupts with STF0; the older disk ASIC still exposes that runtime
bug. No HP instructions or original media are patched.

A bounded continuation of the generated RTE-L kernel prints its genuine SYSTEM
READY banner after the documented HP2645 ENQ/ACK exchange. Added host-input DMA
wake-up and a direct regression. COMND then exposes missing optional class-I/O
support in the minimal generation input; a CLASS-enabled RTLGN configuration is
being tested. This is separate from the completed diagnostic milestones.

## RTE-L SYSTEM READY and authentic TM command: PASS

Original RTLGN now generates the canonical memory-based system with CLASS,
CL16 and SA1024 (words), again with zero errors. Original VCP/BOOTX loads the
read-only 7902 image; run_rte_l_boot.py compares 31,742 words and supplies a normal
HP2645 ENQ/ACK terminal peer. The real SYSTEM READY banner and COMND prompt are
followed by the real TM clock/date response and kernel idle state. No HP code is
patched. The memory-based COMND source intentionally terminates after one
interactive command, so a second-prompt criterion was incorrect and was replaced
with actual command-output/idle checks. Installed disk-based FMGR remains open.

The UART final N+1/TRE request at output terminal count is now visible as a device
flag even when CINT inhibits the DMA-completion interrupt. A dedicated regression
covers that distinction; the authentic Rev.2040 ASIC still completes afterward.
