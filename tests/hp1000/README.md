# L-Series development checks

Run from the repository root with Python 3. No third-party Python modules are needed.

```sh
make -W HP2100/hp2100_cpu.c hp2100 > build/hp1000-build.log 2>&1
python3 -m unittest discover -s tests/hp1000 -v
python3 tests/hp1000/inventory.py
python3 tests/hp1000/run_baseline.py
python3 tests/hp1000/run_l_series.py
python3 tests/hp1000/absolute_binary.py hp1000-references/software/diagnostics/archives/type-7/24397-16002_Rev-2001.abin
```

Create `build/` before redirecting the build log on a fresh checkout. The inventory
CSV contains paths, sizes, SHA-256 hashes, filename part/revision fields, source
headers, and absolute-record validation results. Filename revisions are leads,
not verified source revisions. Search the CSV for `24397`, `24612`, or `24613`.

The baseline checks load/add/store on all seven existing CPU models, then deposits
and asserts every decoded kernel word in an existing 1000-E memory container.
It independently loads the unchanged image through the existing 1000-E PTR ROM
loader and compares 6,237 words (excluding loader scratch registers A/B).
It does **not** execute the L-Series kernel. JSON and per-check logs go to
`build/hp1000/`. Each emulator process has a 30-second timeout, configurable via
`--timeout`. Missing originals report BLOCKED; L-Series execution reports
NOT_IMPLEMENTED. The process fails for failed, blocked, unknown, or timed-out
checks; the explicit future execution row is informational.

`absolute_binary.py --deposits FILE` writes load commands for independent inspection.
Unlike the existing simulator's `LOAD` command, it accepts general absolute images;
HP2100's current `LOAD` accepts only binary-loader images. No HP originals are
included with these scripts. The optional original-image unit test skips when the
private reference image is unavailable.

The L-series runner uses no historical binaries. It exercises all fourteen
memory-reference operations, flags, register aliases, addressing/page boundaries,
NXM semantics, breakpoints, indirect-loop handling, unsupported-instruction
stops, rejected options/foreign boot ROMs, and model switching. It writes
`l-series.ini`, `l-series.log`, and `l-series-results.json` under `build/hp1000/`.
Each case must emit its own success marker after its assertions. These are
independent instruction checks, not original kernel diagnostic tests.

To select the initial subset interactively:

```text
SET CPU 1000-L
SHOW CPU
```

The display identifies this as experimental CPU/processor-ROM support.

Original processor ROM investigation and bounded execution:

```sh
python3 tests/hp1000/firmware.py
python3 tests/hp1000/firmware_source.py
python3 tests/hp1000/run_firmware.py
```

The firmware runner separates synthetic overlay tests from the authentic CPU
pretest prefix. Full power-on pretest, VCP, serial, slave-mode/single-step, and
bootstrap gates remain NOT_IMPLEMENTED. Use `--require-vcp` for a strict full
milestone gate, which currently fails. See `docs/hp1000/firmware.md` for commands,
provenance, hardware citations, source comparison, and the current stopping point.

Direct KERN absolute-load and execution probe:

```sh
python3 tests/hp1000/run_kernel.py
```

Loads and asserts all original Rev.2001 words in L RAM with ROM disabled, then
probes octal entries 2, 3000, and 4 in separate simulator processes. Execution
is bounded to 10,000 instructions and 30 seconds per entry. Logs, register
snapshots, and traces go to `build/hp1000/kernel/`. Probe completion is distinct
from a diagnostic pass; no diagnostic success criterion is fabricated.

To run the complete KERN word-memory phase and then probe the parity phase:

```sh
python3 tests/hp1000/run_kernel_memory.py
```

This runner checks the source-derived PEIT completion boundary and final memory
range, guards original/relocated error-handler entries, and uses a 50-million
instruction budget plus a 30-second wall limit. Long-phase tracing is disabled;
the following parity-phase entry is traced. JSON distinguishes the memory subset
pass from full KERN success. Artifacts go to `build/hp1000/kernel-memory/`.

To verify software parity and the original KERN parity-interrupt phase:

```sh
python3 tests/hp1000/run_parity.py
python3 tests/hp1000/run_kernel_memory.py --parity --output build/hp1000/kernel-parity-verified
```

The latter verifies TST01 completion, 513 parity faults including one inhibited
fetch, final address/sense/control state, and guarded error handlers. See
`docs/hp1000/parity.md` for scope and limitations.

To skip memory/parity and run KERN instruction tests from octal 03777:

```sh
python3 tests/hp1000/run_kernel_instructions.py
```

The unchanged absolute image is loaded and checked before execution. Source
checkpoints guard progress through TST02/TST03/TST04/TSTJL toward TST05, with
error-handler breakpoints active. Current result: PASS through TSTJL, including the original JLA/JLB checks
and subsequent ASG tests, reaching TST05 (13777). Full KERN remains unfinished. See `docs/hp1000/diagnostic-results.md` for scope.

To check processor I/O and compare original KERN entry points:

```sh
python3 tests/hp1000/run_io.py
python3 tests/hp1000/run_kernel_io.py
```

The independent runner checks 47 register, flag, timer and interrupt behaviors.
The KERN runner compares direct octal 13777 with 03777, using source-derived
checkpoints and diagnostic error guards. Both pass the processor-I/O prefix,
including sixteen UI traps, and stop at 14246/STC 7 (protection enforcement is
unfinished). Full TST05/KERN are not passed. See `docs/hp1000/io.md` for manual
coverage and timer accuracy limits. Artifacts go under `build/hp1000/io/` and
`build/hp1000/kernel-io-verified/`.

To test standard L memory protection:

```sh
python3 tests/hp1000/run_protection.py
```

This checks the exclusive fence, accumulator exceptions, indirect targets,
store and I/O suppression, violation-address capture and Type 2 delivery.
`run_kernel_io.py` now verifies two original protection violations and matching
entry paths through the next stop at 14311/LIA 3,C (ROM-P register), replacing
its earlier STC 7 boundary. Full KERN protection coverage remains incomplete.

SC 3 ROM-P/P-SAVE transfers are covered by `run_io.py` (74 checks, including
27 SC 3 cases). `run_kernel_io.py` now expects LIA 10,C at 14311: the SC 3 read
has passed and the select-code sweep has advanced. `run_firmware.py` also
checks a longer bounded original reset run ending at 00710/STC 11, separately
from its 164-instruction prefix. Neither is a full VCP startup pass; see
`docs/hp1000/sc3.md` for the remaining slave/serial work.

Unassigned L inputs now use the owner's provisional 177777 assumption.
`run_io.py` covers 40 new input cases (114 total). `run_kernel_io.py` verifies
the completed select-code sweep and matching direct entries at 14324/MPT03.
It stops before the relocating test can overwrite fixed error-breakpoint code.
For the subsequent fully initialized exploratory run and the MPT09 interrupt
failure, see `docs/hp1000/unassigned-io.md`. This does not claim full KERN success.

To test L interrupt recognition inside indirect chains:

```sh
python3 tests/hp1000/run_indirect.py
python3 tests/hp1000/run_kernel_indirect.py
```

The first checks 17 L cases plus two 2116 board-presence regressions. The second
runs original startup and verifies KERN MPT09's three/four-level return checks,
using signature-aware handling of its relocating test checkpoint. MPT09 passes;
the next stop is 15212/OTA 2, diagnose mode 1. See
`docs/hp1000/indirect-interrupts.md` for semantics and limits.

To check diagnose mode 1:

```sh
python3 tests/hp1000/run_diagnose.py
python3 -m unittest discover -s tests/hp1000 -v
python3 tests/hp1000/run_kernel_indirect.py
```

The first passes 57 instruction checks for the actual empty backplane. The unit
suite compiles the shared mode-1 controller with synthetic descriptions to test
priority enumeration and direct/scoped queries; no test card is installed into
the simulator. KERN's initialized run now reaches its genuine no-I/O-chip
error, verified at IOERR entry. Its JSON distinguishes that expected empty
configuration from a full KERN pass. See `docs/hp1000/diagnose-mode-1.md`.

12005A and authentic interactive VCP: `python3 tests/hp1000/run_asi.py`.
Use `python3 tests/hp1000/run_firmware.py --require-vcp` to require the
power-on, console and single-step gates. See `docs/hp1000/12005a.md`.

12009A register/interrupt/DMA/disk and original disk-bootstrap checks:
`python3 tests/hp1000/run_hpi.py`. Its missing-SYSTEM checkpoint is explicitly
not an RTE-L operating-system pass. Inspect FMP masters without altering them
with `python3 tests/hp1000/rte_disk.py path/to/disc.hpi`.

Original RTE-IVB host + RTE-L relocatable import/link/start:
`python3 tests/hp1000/run_rte_ivb.py`. This uses a fresh working disk and HP's
READR/LOADR utilities; its PASS means generator startup, not a generated SYSTEM.

Generate and boot the genuine RTE-L memory-based 7902 validation image:

```
python3 tests/hp1000/run_rte_l_generation.py
```

Requires the supplied IVB kit and L master. This runs HP READR/LOADR/RTLGN,
requires zero generator errors, installs unchanged SYSTEM/SNAP on a separate
7902 copy, and verifies 31,742 loaded words at the kernel entry. It does not
claim installed disk-based FMGR or diagnostic passes. See
`docs/hp1000/rte-l-built.md` for the required diagnostic-first sequence.

Run the complete original disk KRNL through VCP with both interfaces installed:

```
python3 tests/hp1000/run_krnl_disk.py
```

The runner requires original TST09 at 17770 and its success status 177777,
checks the original disk hash, and never patches diagnostic instructions/data.
Artifacts are under `build/hp1000/krnl-disk/`.

Original disk diagnostics in the required order:

```
python3 tests/hp1000/run_krnl_disk.py --second-asi
python3 tests/hp1000/run_asic.py --instructions 120000000
```

KRNL passes fully with ASI/HPI/ASI1. ASIC currently reports a full-pass failure:
it reaches the 1200-baud test after passing the preceding internal/DMA checks and
baud checks through 900. See `docs/hp1000/diagnostic-results.md` for the observed
DDL interrupt-state stall and provisional virtual-hood wiring. Do not interpret
a simulator-script PASS marker as a full ASIC pass.

`python3 tests/hp1000/run_hpib.py --instructions 30000000` now passes the original
HPIB's offline and online interface checks plus its 7902 controller loopback.
It requires both PASS COMPLETE and actual disc loopback; interface-only completion
with NO HP-IB DISCS FOUND is not counted as a full pass. Optional two-card testing
is not run with the single HPI configuration. All original media stay read-only.

ASIC hood validation now uses the authentic later HP binary:

```
python3 tests/hp1000/run_asic.py --revision 2040
```

This passes all 15 baud settings, the external clock test and PASS COMPLETE.
The runner appends the unmodified Rev.2040 memory image as ASIC40 to a working
copy of the original disk, then uses the original VCP bootstrap. Original disk
files remain unchanged. The default `--revision 2001` deliberately retains the
old disk diagnostic's failing runtime case: HP's later DDL source fixes its
PINT no-entry return to restore interrupts. See docs/hp1000/12005a.md.
`run_asi.py` now also checks the documented HOOD behavior and host-input DMA.

Genuine generated RTE-L boot and one operator command:

```
python3 tests/hp1000/run_rte_l_generation.py
python3 tests/hp1000/run_rte_l_boot.py
```

The CLASS-enabled, 1KW-SAM generation boots to SYSTEM READY and COMND. The boot
test supplies HP2645 ACK only in response to ENQ, types TM, checks its guest-clock
response and normal kernel-idle return. Memory-based COMND intentionally exits
after one interactive command. This does not claim installed disk-based FMGR.

Disk-based RTE-L/FMGR and native assembly validation:

```
python3 tests/hp1000/run_rte_l_fmgr.py
```

This runs original RTLGN and loaders on an IVB working copy, installs generated
SYSTEM/SNAP plus native FMGR/ASMB/LOADR on a writable 7902 working image, then
boots through original VCP/BOOTX. Real FMGR stores a source file; real ASMB and
LOADR build HELLO; the CPU calculates 41+1 and prints ASSEMBLY TEST PASSED.
A fresh boot executes HELLO and reads COPY again. A third boot exercises
create/rename/read/purge. Original-media and distribution-file hashes must stay
unchanged. --reuse-build repeats installation/tests using recorded build hashes.
The output working image is recreated; preserve personal files separately.

The buffered-transfer HPI regression also checks a shortened buffered read and
a short buffered write against every byte of a synthetic disk image. See
docs/hp1000/rte-l-fmgr.md and the XL follow-on plan in xl-memory.md.

### XL memory and authentic RTE-XL

`run_xl_memory.py` tests CPU translation, shadow-map writes, XLD/XST and the SC13
override. `run_xl_diagnostic.py --memory 64` and `--memory 256` execute the complete
unchanged HP XL diagnostic through VCP/BOOTX, with ASI/HPI/ASI1 DMA coverage.

After `run_rte_l_fmgr.py`, run `run_rte_xl_generation.py`,
`run_rte_xl_programs.py`, and `run_rte_xl_boot.py` to generate and test the native
7902 XL/FMGR system. See [HP 1000 guide](../../docs/README.md) for
provenance, the separate D.RTR requirement and current 7920 limits.

7920 XL generation and verified file/reboot tests:

```sh
python3 tests/hp1000/run_rte_xl_generation.py --commands tests/hp1000/config/rte-xl-7920.gen --output build/hp1000/rte-xl-7920-generated
python3 tests/hp1000/run_rte_xl_boot.py --disk 7920 --generated build/hp1000/rte-xl-7920-generated --output build/hp1000/rte-xl-7920
python3 tests/hp1000/run_rte_xl_loader.py
```

`run_rte_xl_software.py` is an installation investigation, with strict failure
reporting. It uses a separate image and does not establish that the language
tools are usable until linking and compilation/execution have passed.

Interactive RTE-XL and the tested BASIC/MACRO examples are documented in
[the user guide](../../docs/README.md). Start a persistent
working copy with:

```sh
python3 tests/hp1000/run_rte_xl.py
```

`run_rte_xl.py --check --image build/hp1000/rte-xl-console-check/disk.disc`
checks the real pseudo-terminal path, host-text import, MACRO assembly, native
linking, executable output, BASIC arithmetic and return to FMGR. The text
importer has preservation and reference/binary-protection unit tests.

## Type-5 RTE-XL application installation

See [the consolidated HP 1000 guide](../../docs/README.md).
Earlier development notes are backed up in `build/hp1000/docs-before-consolidation/`.
The archive importer validates relocatable checksums and FMP envelopes; its
records are independently compared with original XL master files. All online
LOADR and application checks retain console logs under `build/hp1000/rte-xl-archive/`.

`run_rte_xl_archive_smoke.py` tests EDIT save/reopen/help, FTN4X compile/link/run
and OPEN/MAXREC with reboot persistence, and plain/macro assembly execution.
`check_rte_xl_archive_console.py` also tests EDIT through the public PTY launcher
with `--hp264x-status`. `run_rte_xl_image_schema.py` and
`run_rte_xl_image_records.py` separately gate database creation and API persistence.
Pascal generation/link success must not be reported as a boot or compiler pass.

## Local terminal responses and standard SimH startup

`SET ASI LOCALSTATUS` (also ASI1) answers the HP264x ESC/^/DC1 primary-status
query through the UART receiver. `REMOTESTATUS` restores pass-through. The
response describes 4KB display memory with block mode and auto-LF disabled;
this is not screen emulation. `run_asi.py` tests both modes on both cards.
`run_asi_status.py` boots XL and tests authentic EDIT save/reopen/help with
LOCALACK/LOCALSTATUS and no host terminal responders. It requires the existing
combined software image and EDIT smoke-test artifacts.

Normal user startup uses the standard SimH file `HP2100/hp1000-xl.ini`, as
explained in `docs/README.md`. Python scripts remain development/test tools.
