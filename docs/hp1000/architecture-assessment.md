# L-Series integration assessment

Initial target: HP 2103L / HP 1000 L-Series. A-Series is deferred. All emulator
changes belong in `HP2100/` and the existing `hp2100` executable, as requested.
No separate HP1000 simulator or build target is planned.

The existing CPU model encodings in `hp2100_defs.h` and `hp2100_cpu.c` cover
2114/2115/2116, 2100, and 1000 M/E/F. `CPU_1000` currently means M/E/F;
blindly adding L to this mask would enable incompatible code paths. The model
table, option masks, dispatch, reset, and memory configuration need a coordinated
extension. `SET CPU 1000-L` now selects experimental CPU/processor-ROM support,
with a distinct configuration bit and no M/E/F firmware options. Existing model
and option encodings are preserved; the L unit model code is 7, and its separate
configuration bit is 19. `CPU_1000` continues to mean M/E/F only.

Reuse candidates are the simulator device, register/debug interface, SCP stepping
and breakpoints, symbolic instruction decoding, and documented common integer
instruction operations. Audit indirect addressing and micro-operation combinations
before sharing execution. Existing memory helpers in `hp2100_mem.c` include
M/E/F-specific mapping/protection assumptions; L protection and XL expansion
must be checked independently.

The L-Series architecture has CPU and distributed I/O processor chips, with DMA
handled on individual cards: 02103-90007, October 1980, §1-1, printed 1-1
(PDF 11), and §1-7, printed 1-2 (PDF 12). It is not sufficient to reuse the
centralized channels in `hp2100_dma.c` or the current device signal interfaces
unchanged. Keep compatible peripheral mechanics separate from card protocols.

Global-register selection changes the meaning of I/O instruction bits 5:0 from
select code to card register number: §3-19, printed 3-12 (PDF 42), and §5-4
(PDF 56). Existing `hp2100_io.h` and CPU I/O dispatch need a model-specific
route before conventional M/E/F devices see L instructions.

Interrupt vector assignments include power fail 04, parity 05, internal TBG 06,
protection 07, and unimplemented instruction 10: §4, table 4-1 (PDF 48).
These cannot be assumed to match existing device assignments. The internal
TBG is described as a 10 ms source in §1-5, printed 1-1 (PDF 11).

First implementation sequence: finish the instruction/protection audit; add L
model capabilities and CPU state without enabling M/E/F options; test common
integer instruction classes; implement CPU-resident I/O and interrupt/trap
semantics; then distributed I/O, 12005A console, and per-card DMA. Use the
24397 kernel as an incremental execution target. ROM/VCP calls need original
ROMs or a documented boot path that avoids them, never diagnostic-specific stubs.

## First implemented CPU subset

The fourteen memory-reference operations in 02103-90007 §3-15, printed 3-5
through 3-7 (PDF 35–37), use the existing executor: AND, XOR, IOR, JSB, JMP,
ISZ, ADA/ADB, CPA/CPB, LDA/LDB, and STA/STB. Addressing follows §3-3/3-4,
printed 3-1 (PDF 31): current page means the page of the instruction, including
when the following instruction crosses a page boundary. Register aliases at
addresses 0/1 are retained. Appendix A, printed A-9 (PDF 73), documents sticky
extend/overflow on addition.

L nonexistent-memory reads return 177777 and writes are ignored (§3-7,
printed 3-3, PDF 33). M/E/F and 21xx read behavior remains unchanged. The
experimental model allows up to 32K words; smaller configurations support
memory-boundary checks. XL expansion is not implemented.

Shift/rotate, alter/skip, and documented EAU encodings now use the common integer
executors, supported by manual descriptions and the authentic firmware pretest
prefix. Plain HLT remains a simulator stop without VCP entry. A limited
processor-card I/O handler implements overflow operations, processor output/page
selection, CLC 2/STC 2 overlay control, global controls, SC 7 register transfers,
and the SC 6 TBG. The processor holds mask bit 1; interface-card mask bits and
routing remain unfinished. Unrecognized CPU encodings now take the hardware
Type 1 trap at octal 10. Standard protection and its Type 2 trap are implemented (see `protection.md`).
Unfinished simulator features, including CLC 3 delayed slave requests, still stop with P preserved and cannot be bypassed via RUN -B/NOSTOP.
See `io.md` for current scope and timer limitations.

Conventional DMA channels are disabled for L; their service and interrupt paths
are excluded. Existing bootstrap ROMs, protected-loader commands, and binary
LOAD/DUMP are refused for L. SCP deposits remain available for image inspection.
User-supplied original processor ROMs can now be loaded and executed with the
four-page overlay and instruction-dependent read gating. BOOT CPU/RESET -P
start the software pretest at offset 2. Complete VCP behavior, protection,
interrupts, DMA, timing fidelity, and devices remain unfinished. A direct KERN
run now completes the original word-memory phase for 32KW and reaches the
separate parity-interrupt test, which also passes using software RAM parity.
These are subset passes; CPU tests and full KERN remain unfinished. See `diagnostic-results.md` and `firmware.md`.

## L-Series processor select code 4

Implemented separately in the L I/O handler using 02103-90007 §§4-9, 4-11,
4-12 and table 4-3, printed 4-4/4-5 (PDF 50/51):

- SFS 4 skips for power up; SFC 4 skips for power down. This is the reverse
  sense of the existing M/E/F power-fail interface.
- LIA/LIB 4 load the six-bit CIR; MIA/MIB 4 merge it; OTA/OTB 4 write only
  bits 5:0. KERN's IREGC routine independently expects this mask (source
  Rev.2001 lines 633–645).
- STC 4/CLC 4 set/clear a separate Type 2/3 interrupt-enable latch. STF/CLF 4
  are NOPs, so the C modifier does not change the power input or CIR.

LPFAIL exposes the power-warning input (0 for normal/up, 1 for failing), and
LINT23 exposes the enable latch. Model selection/power-on reset initialize
normal power, CIR zero and the enable latch set. The initial enable state
matches the original ROM's early TBG test before its first CLC 4/STC 4 pair.
The future L interrupt arbiter must consume this latch: actual power-failure
interrupt generation and delivery remain unfinished. No M/E/F I/O dispatch
or interrupt behavior was changed by this implementation.

## L-Series select code 0 control reset and Type 3 master flag

CLC 0 generates CRS for the L interface cards; CLC 0,C additionally clears
the Type 3 master interrupt flag. This is the same broad CRS operation as on
the earlier models, whose existing `cpu_iog`/`cpu_interface` already implement
both forms via ioCLC and optional ioCLF. The L handler previously intercepted
these instructions and stopped before reaching that legacy path.

The legacy broadcast iterates occupied select codes 06–77; L interface cards
start at 20 octal (02103-90007 §3-19, printed 3-12). There are currently no L
interface cards, so the implemented broadcast has no recipients and reports
that fact in the data trace. Future L card reset handlers must receive CRS.
The existing M/E/F devices are not reset through the L handler.

The CPU-side operations use 02103-90007 §§4-11/4-12, table 4-3 (PDF 50/51):
STF/CLF 0 set/clear Type 3 enable (INTSYS), SFS/SFC 0 test it before optional
clear, and STC 0 is a NOP apart from an optional C modifier. CLC 0 without C
preserves INTSYS. These operations preserve the independent SC 4 gate LINT23,
CIR, registers, RAM, and ROM/page state. They are not a CPU/power-on reset.
SC 0 mask-register data operations remain unfinished, as does actual L interrupt
delivery; the Type 3 flag is retained for the future L interrupt arbiter.

SC 5 RAM parity and Type 1 trap delivery are now implemented independently of
the legacy dispatcher. See `parity.md` for the model, tests and limitations.
