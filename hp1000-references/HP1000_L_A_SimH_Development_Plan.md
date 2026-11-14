# HP 1000 L-Series and A-Series emulation in SimH

**Project handoff and Codex implementation prompt**  
**Scope:** HP 1000 L-Series and A-Series CPU, memory, I/O subsystem, devices, diagnostics, and eventual RTE-L/RTE-A support.  
**Audience:** A developer or AI coding agent working on Linux, macOS, Windows, or another supported development environment.

> **Status note:** This document is a project plan, not a claim that an A/L-Series emulator or diagnostic build environment already works. Historical part numbers and archive contents discussed below are leads from earlier investigation; the implementer must verify them against the actual files and HP manuals. The availability of any particular original binary, tool, or manual must also be checked. Do not assume that sources alone are buildable.

## Current implementation decisions — 10 November 2026

The owner's instructions supersede alternatives elsewhere in this original handoff:

- Implement the **HP 2103L / HP 1000 L-Series first**. Defer A-Series and other new models.
- Integrate into the existing **`HP2100/` simulator and `hp2100` executable**. Do not create a separate emulator/code base.
- Keep model-specific CPU, interrupt, memory, and I/O behavior explicit within HP2100. Sharing the executable does not imply compatible backplanes.
- Use the supplied `hp1000-references/` tree. Preserve original software and manuals unchanged.
- Begin with the original **24397 L-Series kernel and DDL** sources/binaries found locally. The 24612 sources remain useful secondary references; model compatibility must be verified.
- Current results and repeatable commands are maintained in `docs/hp1000/` and `tests/hp1000/`.

### Early firmware validation milestone

Execute the original processor firmware before attempting a complete RTE-L boot:
reconstruct and verify the 12001 PROM lanes against unchanged assembly source,
implement the documented four-page ROM overlay and processor modes, complete
original pretest, reach an interactive original VCP through a real 12005A card
model, and use its bootstrap for 24397 diagnostics. Preserve originals, check
revisions, and never replace firmware behavior with simulator-specific success
paths. Current evidence and unresolved gates are in `docs/hp1000/firmware.md`.

## 1. Goal and proposed approach

Develop maintainable support for HP 1000 L-Series and A-Series systems using the existing SimH project as a starting point. Validate the result against original HP documentation and diagnostic software, prioritizing I/O correctness, including interrupt and DMA behavior.

The project should proceed in small, measurable steps:

1. Establish a reproducible **baseline SimH build** and regression tests.
2. Inventory the **documentation, diagnostic sources, original binary media, and build tools**.
3. Establish a **diagnostic build or executable-media workflow** before extensive emulator implementation (**Phase 0**).
4. Integrate model-specific L-Series support within HP2100, reusing behavior verified against the manuals.
5. Run original diagnostics repeatedly and turn each failure into a reproducible test case.
6. Expand from processor and I/O kernel to interfaces, peripheral devices, and eventually RTE operating systems.

The first target is the HP 2103L L-Series. Additional L/XL variants require explicit capability and diagnostic checks; A-Series is deferred.

## 2. Source code and software to gather

### 2.1 Emulator baseline

- [SimH repository](https://github.com/simh/simh), including the existing HP2100 simulator.
- Pin a specific upstream commit and record its build instructions and regression-test results.
- Review SimH's contribution and licensing requirements before submitting or redistributing changes.

The existing HP2100 implementation is a useful reference, but **do not assume L/A-Series I/O is compatible with the 2116/2100/M/E/F backplane**. Implement the L-Series differences within HP2100; do not create a separate HP1000 simulator.

### 2.2 Diagnostic source and media

| Resource | Why it matters | Initial status / action |
|---|---|---|
| `type-4.zip` HP 1000 software collection | Contains leads for 24398, 24612, and 24613 diagnostic sources, including I/O modules | Obtain archive, checksum it, inventory actual files and revisions |
| `24398B.zip` / TeleDisk media | Historical peripheral diagnostic disk images | Inventory and validate images; distribution appears incomplete; avoid assuming every labeled disk is correctly imaged |
| 24612A / 24612B diagnostic distribution | Kernel and combined diagnostic execution | Locate **executable** media and verify target models |
| 24398 peripheral diagnostics | Peripheral exercisers and device testing | Identify self-contained binaries vs OS-dependent programs |
| 24613 measurement/control diagnostics | Analog and digital I/O testing | Match diagnostics to real interface part numbers |
| RTE-L and RTE-A distributions | Eventually boot real systems; may contain development tools or diagnostics | Locate original media and inspect formats |
| Original assembler, linker, DDL tools, loaders | Needed to rebuild diagnostics where possible | Find actual executable tools or reconstruct only minimally necessary pieces |

**Useful source-file leads to verify:**

- `24612-18018`: Master I/O Diagnostic.
- `24612-18036`: HP-IB interface diagnostic.
- `24612-18042`: Basic Control Module (BCM).
- `24612-18010`: Diagnostic Design Language-related component.
- `24612-18003`: disk driver; `24612-18066`: SCSI driver.
- `24613-18001` and nearby files: measurement/control diagnostics.
- `24398-18062`, `24398-18066`: CS/80 exerciser-related sources.

These identifiers are **investigation leads**, not proof of a working toolchain or the presence of all dependencies. Verify every title, platform requirement, and revision against the actual archive.

### 2.3 Original software locations

- [HP Computer Museum documentation collection](https://www.hpmuseum.net/exhibit.php?catdoc=37)
- [HP Computer Museum 24398B listing](https://www.hpmuseum.net/display_item.php?sw=452)
- [Bitsavers HP archive](https://bitsavers.org/pdf/hp/)
- [Bitsavers HP software archive](https://bitsavers.org/bits/HP/)
- [SimH repository](https://github.com/simh/simh)

Check links, mirrors, license conditions, and completeness when obtaining files. Store original archives unchanged with checksums.

## 3. Documentation checklist

Obtain the most relevant available revision and retain a source index including document number, revision, URL, and page number. Some titles/part numbers need confirmation from the scanned cover pages.

### 3.1 Core architecture and I/O

| Priority | Document / lead | Part number | Use |
|---|---|---|---|
| Essential | L-Series Engineering and Reference Documentation | `02103-90009` | CPU, memory, interrupts, I/O behavior |
| Essential | A/L-Series I/O Interfacing Guide | `02103-90005` | Interface programming model, controller operations |
| Essential | A-Series I/O Interfacing Guide | `02103-90055` | A-Series-specific I/O |
| Essential | HP 1000 computer architecture / reference manual | `02103-90007` (verify) | Instruction and CPU model details |
| High | A-Series Computer Handbook | `5954-8590` (verify) | Hardware configurations and model distinctions |
| High | A-Series CE Handbook | `5955-8896` (verify) | Fault diagnosis and hardware details |
| High | System Designer's Guide | `92007-90001` (verify) | System requirements, memory and device selection |

Potential direct source: [L-Series engineering PDF](https://bitsavers.org/pdf/hp/1000/L-series/02103-90009_L-Series_ERD_Sep80.pdf). Confirm the URL and document number before treating it as an authoritative reference.

### 3.2 Diagnostic environment

| Era | Document | Part number |
|---|---|---|
| Earlier | Diagnostic Operating and Troubleshooting | `24612-90001` |
| Earlier | Diagnostic Design Language | `24612-90002` |
| Earlier | Kernel Diagnostics Reference | `24612-90003` |
| Earlier | Interface Diagnostics Reference | `24612-90004` |
| Later | Introduction to A-Series Diagnostics | `24612-90010` |
| Later | Interface Diagnostics Reference | `24612-90011` |
| Later | Diagnostic Operating and Troubleshooting | `24612-90013` |
| Later | Diagnostic Design Language | `24612-90015` |
| Later | Kernel Diagnostics Reference | `24612-90017` |

Collect the older and newer revisions where available; the supported CPUs, interfaces, and build procedures may differ.

### 3.3 Operating-system and interface manuals

- [RTE-A Primary System Software Installation Manual](https://bitsavers.org/pdf/hp/1000/RTE-A/92077-90038_RTE-A_PrimInst.pdf) — useful for bootable media and distribution layout.
- Appropriate RTE-L installation, system generation, and programming manuals.
- Interface programming/service manuals for the **specific** serial, parallel, HP-IB, SCSI, disk, tape, LAN, and measurement/control interfaces chosen for emulation.
- Controller/peripheral command documentation (e.g., HP-IB and CS/80) separately from interface-card programming documentation.

Do not delay the entire project to collect every peripheral manual. Obtain device documentation as each interface enters the implementation roadmap.

## 4. Critical unknowns to resolve in Phase 0

1. **Which exact L/A models are supported by each diagnostic revision?** Do not assume an A-Series diagnostic runs on L-Series hardware.
2. **Can the DDL and assembly sources be built?** Determine whether DDL is translated, interpreted, compiled, or assembled, and what original tools and runtime it requires.
3. **Are original executable binaries available?** Their existence can bypass a missing build environment for early testing.
4. **Can the diagnostic run standalone?** Identify boot loaders, control modules, console requirements, device configuration, and test fixtures/loopback plugs.
5. **How is success defined?** Some diagnostics run repeatedly; a timeout or halt alone is not proof of a passed test.
6. **Are media images genuine and complete?** Decode, enumerate and verify their file systems and content; do not trust labels alone.
7. **What is shared between existing HP2100 and HP1000?** Reuse behavior only when verified in model-specific documentation.
8. **What can legally be redistributed?** Keep original HP software and scans separate from public emulator source until rights are established.

## 5. Suggested repository organization

```text
simh/
  HP2100/                       # Existing simulator plus integrated L-Series support
  tests/hp1000/                 # Unit tests, diagnostic runner, fixtures
  docs/hp1000/                  # Architectural notes, status, test reports
  hp1000-references/            # Local originals, manuals/software ignored by git
    manuals/
      architecture/
      io/
      diagnostics/
      peripherals/
    diagnostics/
      archives/                 # Original archives, immutable + checksums
      extracted/                # Verified unpacked sources
      binaries/
      tools/
    operating-systems/
```

Use `.gitignore` or a separate private repository for historical software unless redistribution is authorized. Record each artifact's provenance, revision, and SHA-256 checksum.

## 6. Target milestones and acceptance criteria

| Milestone | Goal | Evidence required |
|---|---|---|
| **0A** | Reproducible baseline | SimH builds; existing HP2100 tests pass; pinned commit |
| **0B** | Diagnostic inventory | Searchable index with file IDs, revisions, target models, dependencies |
| **0C** | Diagnostic tooling | Rebuilt diagnostic or verified original executable; documented loader |
| **0D** | Automated test harness | One command runs and logs a diagnostic with unambiguous results |
| **1** | Initial HP1000 simulator structure | Model selection, memory, registers, tracing and executable loading |
| **2** | Selected CPU instruction set | Independent opcode tests and documented edge cases |
| **3** | Memory, interrupts and I/O kernel | Master I/O/kernel diagnostics or documented subsets pass |
| **4** | Next supported L/A model | Model-specific tests and diagnostics pass without regression |
| **5** | First external interface | Interface register, interrupt, DMA and loopback tests pass |
| **6** | Peripherals and OS support | Relevant exercisers pass; boot an appropriate RTE distribution |

**Pass discipline:** distinguish `PASS`, `FAIL`, `BLOCKED`, `NOT_IMPLEMENTED`, `TIMEOUT`, and `UNKNOWN`. Report the diagnostic revision, CPU model, hardware configuration, number of tests actually executed, and logs. Do not mark a suite as passing when only a subset was executed.

## 7. Codex handoff prompt (copy in full)

The text below can be pasted into Codex or another code-capable agent operating in the checked-out repository. It is platform-neutral; the agent must discover the actual host environment and select appropriate tools. The agent should not assume it can access resources outside its permitted workspace or network environment.

---

### BEGIN CODEX PROMPT

You are working on a fork of the SimH computer simulator. Your objective is to implement maintainable HP 1000 **L-Series and A-Series** support, with strong emphasis on the **I/O subsystem**, using original Hewlett-Packard documentation and diagnostics for validation.

**Operating principles**

- Start with **Phase 0: diagnostic and build environment**. Do not jump directly into a large emulator implementation.
- Work on the operating system provided by the development environment. Do not assume macOS, Linux, or Windows, a particular compiler, package manager, shell, or CPU architecture. Detect tools and document setup. Prefer portable build and test scripts.
- Inspect the repository's existing source and tests before changing architecture. Record the SimH baseline commit, build instructions, and regression results.
- Preserve existing HP2100 behavior. Integrate L-Series code into HP2100 with explicit model boundaries; share behavior only when documentation confirms compatibility.
- Treat original HP manuals as the reference specification. Identify exact publication, revision, and page for non-obvious hardware behavior.
- Keep historical HP diagnostic sources and media **unchanged**. Maintain their checksums. Do not silently patch diagnostic tests to satisfy the emulator.
- Do not invent hardware behavior or fake diagnostic success. Where documentation is incomplete, flag the uncertainty and isolate it in tests.
- Add explanatory comments to new code, particularly for hardware-specific behavior, register semantics, timing, interrupt priority, DMA, and compatibility decisions.
- Create concise, reviewable commits; keep builds and tests reproducible. Do not commit copyrighted HP source/media to a public repository without permission.
- Continue through tasks that are unblocked. If a dependency prevents a task, document it and continue with a separate, useful task rather than fabricating results.

**Phase 0.1 — Baseline SimH**

1. Identify the host OS, available C compiler, build system, Python/runtime, and dependencies. Provide installation/setup instructions for the detected environment, but keep project scripts portable.
2. Pin the current SimH revision. Compile and run existing HP2100 unit/regression tests, preserving logs.
3. Inspect the HP2100 CPU, instruction handling, memory, DMS/protection, interrupts, DMA, device registration, I/O dispatch, boot loaders, and tracing.
4. Create `docs/hp1000/architecture-assessment.md` describing what is reusable and what differs for L/A-Series.

**Phase 0.2 — Inventory and index reference material**

1. Inspect `hp1000-reference/` if present. Do not assume any named reference file exists until checked.
2. Inventory each manual by title, part number, revision, and location. Start with L-Series engineering, A/L I/O interfacing, A-Series I/O, diagnostic operations, DDL, kernel diagnostics, and interface diagnostics.
3. Identify missing documentation, verify download URLs when network access is available, and record acquisition status; do not claim unavailable documents were downloaded.
4. Build `docs/hp1000/reference-index.md` and `docs/hp1000/missing-documentation.md` with citations to manual pages for key CPU/I/O behaviors.

**Phase 0.3 — Audit diagnostic archives and executable media**

1. Enumerate every archive and disk/tape image. Preserve originals and generate SHA-256 hashes.
2. Search source families 24398, 24612, and 24613. Identify each program, actual source language, revision, supported computer/interface, dependencies, build directives, and expected output.
3. Specifically investigate leads `24612-18018` (Master I/O), `24612-18036` (HP-IB), `24612-18042` (BCM), `24612-18010` (DDL-related), and applicable serial, parallel, SCSI, DMA, storage, and measurement/control tests. **Verify their roles against the actual files**.
4. Decode disk/media formats where possible. Enumerate actual contents; do not rely on archive or volume labels.
5. Write `docs/hp1000/diagnostic-inventory.md`, distinguishing source found, binary found, buildable, loadable, runnable, pass verified, and blocked. Track CPU-model and diagnostic-revision compatibility.

**Phase 0.4 — Reconstruct a usable diagnostic toolchain**

1. Determine how HP built and linked DDL, assembly, and any higher-level diagnostic sources. Trace the dependency graph from test sources through translators/assemblers/linkers/loaders and runtime/control modules.
2. Locate executable original tools and build files where available. Identify whether a host HP system or RTE environment is required.
3. Prefer using an original toolchain or verified original executable image over rewriting a compiler prematurely.
4. Attempt to reproduce one small diagnostic executable from its unchanged sources. If a reference executable exists, compare format and contents where meaningful.
5. If no complete toolchain is recoverable, implement **only** the minimal loader/format tools needed for independently validated diagnostics; document unresolved dependencies. Do not block the rest of the project indefinitely.
6. Record actual commands, tool versions, produced artifacts, and failures in `docs/hp1000/diagnostic-build.md`.

**Phase 0.5 — Establish diagnostic execution and regression automation**

1. Determine each diagnostic's bootstrap method, loader format, required control program, console, configuration, loopback fixture, and expected successful stopping or repeat condition.
2. Write a portable test harness under `tests/hp1000/`, using tools available in the host environment. Keep emulator execution bounded and logs deterministic.
3. The harness must report `PASS`, `FAIL`, `BLOCKED`, `NOT_IMPLEMENTED`, `TIMEOUT`, or `UNKNOWN`, and retain the simulator trace, diagnostic messages, executed test IDs, and hardware configuration.
4. A timeout, unexplained halt, or repeated loop must never count as a pass. Check that the intended tests executed, not just that the process exited.
5. Build a diagnostic loader even before complete CPU emulation, if necessary, so binary headers, checksums, load addresses, and contents can be independently inspected.
6. Where diagnostics depend on missing peripherals or physical test connectors, mark those subsets as blocked and create narrow independent tests instead.

**Phase 0 gate:** Before major emulator coding, show a successful SimH baseline and regression run, a verified diagnostic inventory, a reproducible diagnostic load/decode path, and a working test harness. Preferably demonstrate a rebuilt original diagnostic; if that is impossible, use a verified original executable and document why source reconstruction is blocked.

**Phase 1 — Architecture and initial model selection**

1. Extend `HP2100/` and its existing executable. Preserve existing models and isolate incompatible L-Series behavior within that simulator.
2. Target **HP 2103L / L-Series** first, using the supplied manuals and 24397 diagnostics. Defer A-Series.
3. Implement model selection, CPU/memory state, register inspection, single-step, breakpoints, instruction and I/O tracing, and diagnostic loading.
4. Make model-specific capabilities explicit. Never silently treat all A-Series machines as identical.

**Phase 2 — CPU and memory**

1. Implement documented base instructions and selected-model extensions. Verify encodings, indirect addressing, overflow/extend, arithmetic, shifts, control flow, privileged behavior, and exceptional cases.
2. Implement memory, memory mapping/protection and architectural traps as applicable to the chosen model.
3. Create small independent unit tests for every instruction class. Compare with HP2100 only where semantics are documented as identical.
4. Integrate applicable kernel diagnostics in small increments.

**Phase 3 — I/O, interrupts and DMA**

1. Implement the selected model's actual I/O addressing and device register behavior; do not substitute HP2100 select-code logic where incompatible.
2. Implement interrupts (request, masking, priority, acknowledgement, return), DMA setup/transfers/termination, resets, and protection interactions.
3. Add trace events for register accesses, I/O instructions, interrupt transitions, and DMA transfers.
4. Validate with narrow unit tests and applicable original Master I/O and kernel diagnostics. Record which test sections pass, fail, or remain blocked.

**Phase 4 — Additional L/A model(s)**

1. Add the next model only after the initial model has useful diagnostic coverage.
2. Keep capability tables and model-specific behavior separated and documented.
3. Retain all prior model regression tests.

**Phase 5 — Device interfaces and peripherals**

1. Implement device interfaces in diagnostic-coverage order: typically system console/serial, parallel, HP-IB, storage interface, DMA-capable devices, and then CS/80 disk, tape, SCSI, LAN or measurement/control as documentation and demand permit.
2. For each interface, collect its **specific HP part-number programming manual** and corresponding diagnostic. Do not confuse interface-card diagnostics with tests of an attached peripheral.
3. Test register readback, control/status transitions, reset, interrupt, DMA, invalid commands, and documented error conditions.
4. Run original diagnostics and exercisers where possible, retaining individual test outcomes and traces.

**Phase 6 — Operating systems**

1. Locate, inventory, and identify licensed-to-use RTE-L and RTE-A media and boot instructions.
2. Add exactly the CPU and device capabilities needed for a minimal documented configuration.
3. Boot original systems without patching OS binaries to hide emulator errors.
4. Validate console use, basic file access, interrupt-driven I/O, and reproducible boot sequences.

**Continuous iteration loop**

For every meaningful feature change:

1. Build with appropriate warnings enabled.
2. Run fast independent tests.
3. Run the related original HP diagnostics.
4. Record the first new failure with diagnostic ID/revision, machine configuration, test number, CPU/register state, relevant I/O trace, and source-manual citation.
5. Determine whether the cause is hardware emulation, incorrect diagnostic build/configuration, unsupported interface, bad media, or a genuine source/diagnostic issue.
6. Make the smallest documented behavior correction and add an independent regression case.
7. Rerun the related tests and existing HP2100 regressions.
8. Update the implementation matrix, diagnostic results, and development log.

Do not optimize performance until correctness is established. Do not introduce diagnostic-specific emulator shortcuts. Distinguish a partially passing diagnostic from a fully passing diagnostic.

**Required living project files**

- `docs/hp1000/architecture-assessment.md`
- `docs/hp1000/reference-index.md`
- `docs/hp1000/missing-documentation.md`
- `docs/hp1000/diagnostic-inventory.md`
- `docs/hp1000/diagnostic-build.md`
- `docs/hp1000/diagnostic-results.md`
- `docs/hp1000/implementation-status.md`
- `docs/hp1000/known-issues.md`
- `docs/hp1000/development-log.md`

Maintain a test matrix indexed by exact CPU model, interface part number, diagnostic ID and revision, and test subset. Include evidence for every claimed pass.

**First deliverable**

Begin immediately with Phase 0. Provide a reproducible baseline SimH build, a searchable diagnostic inventory, and a documented diagnostic build/load path. Attempt to produce or recover one usable Master I/O or other small diagnostic executable, with an automated test harness. Then choose the first CPU model using evidence and begin the smallest independently testable implementation. Report precise blockers and continue with unblocked tasks.

### END CODEX PROMPT

---

## 8. Example acceptance-test interface

These are **illustrative commands** for a future harness, not commands that necessarily exist today:

```sh
# Run a named diagnostic on a specific implemented CPU model.
python3 tests/hp1000/run_diagnostic.py --model A600 --diagnostic MASTER_IO --verbose

# Run all eligible diagnostics for the selected model.
python3 tests/hp1000/run_diagnostic.py --model A600 --all

# Run existing simulator regressions using the repository's actual test command.
# Replace the example below after inspecting the SimH build/test system.
make test
```

Prefer structured output (JSON or JUnit XML) alongside human-readable logs. Each test should have bounded execution, a known stopping condition, and artifact paths for traces and failure context.

## 9. Suggested handoff checklist

- [ ] Clone or fork SimH and record the baseline revision.
- [ ] Obtain manuals from Section 3; verify title, part number, revision and provenance.
- [ ] Obtain and checksum diagnostic source archive(s).
- [ ] Obtain original diagnostic binary media where available.
- [ ] Locate any available original DDL/assembler/linker tools and RTE software distributions.
- [ ] Place historical files in an untracked/private reference area.
- [ ] Give the agent the full prompt in Section 7.
- [ ] Require Phase 0 artifacts before accepting substantial emulator feature claims.
- [ ] Review architecture and model selection after Phase 0.
- [ ] Use exact diagnostic test counts, revisions, logs, and regression evidence for progress reporting.

## 10. Risks and success criteria

**Main risks:** incomplete diagnostic distribution, missing DDL build tools, ambiguous model compatibility, insufficient I/O interface documentation, original hardware behavior not described in manuals, and license restrictions on HP historical software.

**A realistic initial success** is not a complete A/L-Series emulator. It is a reproducible test environment that can load one verified original diagnostic image and expose enough CPU/I/O behavior to execute a meaningful test subset. Continued progress is demonstrated by increasing documented diagnostic coverage without breaking existing HP2100 behavior.

## L-Series implementation checkpoint — 2026-11-11

The optional 12009A HPI interface is integrated into HP2100 and shares the
existing HP-IB bus and DA disk backend. Original processor firmware reaches VCP,
boots the RTE-L master into BOOTX (SYSTEM absent), and boots the original HPIB
diagnostic from 24397A.hpi to its DDL READY prompt. Seven new hardware/bootstrap
checks pass; full PHI offline diagnostics and full OS operation remain open.
The added RTE-XL master directories also contain no SYSTEM file.

Keep hardware validation independent of authentic RTE-L system generation.
See `docs/hp1000/12009a.md` and `docs/hp1000/rte-l-generation.md` for confirmed
behavior, remaining hardware gaps, source evidence, and the unverified IVB
cross-generation route. Do not substitute a diagnostic or synthetic image for
an installed RTE-L system.

## Original RTE-L generator host validated — 2026-11-11

The supplied RTE-IVB Rev.5010 kit boots on the existing 1000-E simulation.
A fresh byte-swapped working disk preserves the original. The genuine READR
restores and verifies all 55 RTE-L type-5 files from a documented interchange
tape. The genuine LOADR links RTLGN plus RTLG1..RTLG4 using the matching original
`$LDRLB` and `$MXLB`; RTLGN executes startup and its initial command-file check.

Reproduce with `python3 tests/hp1000/run_rte_ivb.py`. All six acceptance checks
pass. This establishes host/import/link/start compatibility, not complete system
generation. A validated target command/answer file, clean SYSTEM/SNAP/SYLIST
output, installation and genuine L-Series disk boot are still required.
See `docs/hp1000/rte-ivb-host.md` for provenance and exact commands.


### Generated SYSTEM boot checkpoint and diagnostic priority (2026-11-11)

Original RTLGN completes with zero errors and original VCP/BOOTX loads its
32KW ASI/12009A/7902 SYSTEM to kernel entry 02003. The generated low 31KW
is verified word for word. This is a memory-based COMND validation system,
not an installed disk-based FMGR system. Reproduce with
`python3 tests/hp1000/run_rte_l_generation.py`; see
`docs/hp1000/rte-l-built.md` for evidence and limitations.

Further OS bring-up is paused at this checkpoint by user direction. Required
order: full original KRNL pass from `24397A.hpi`, second ASI plus virtual
loopback and full ASIC pass, then full HPIB pass. Resume RTE-L work afterward.

### Current L-Series milestone (2026-11-12)

The diagnostic gates have now been validated: full original disk KRNL with three
cards; original disk HPIB including 7902 controller loopback; authentic ASIC
Rev.2040 with the documented hood and all baud rates. The older disk ASIC's
DDL interrupt-return bug remains recorded; HP's later binary fixes it without
an emulator or program patch.

The original RTLGN now generates a CLASS-enabled memory-based RTE-L SYSTEM
(CL16, SAM1024 words) with zero errors. Original VCP/BOOTX boots it through the
12009A/7902 to SYSTEM READY and COMND. The automated terminal peer performs the
HP2645 ENQ/ACK exchange; a real TM command prints the guest time/date and returns
to kernel idle. No source media or HP executable code is patched.

See docs/hp1000/rte-l-built.md and diagnostic-results.md for reproducible scripts,
hashes and scope. This is a running memory-based COMND system, not yet an
installed disk-based FMGR environment. Further conformance and long-running
system validation remain separate work.

## Current direction and FMGR milestone — 2026-11-12

Disk-based RTE-L now boots through original VCP/BOOTX into authentic FMGR,
initializes four swap areas, and runs native ASMB/LOADR. An assembled arithmetic
program executes and survives a fresh boot. Real guest file creation, writing,
reading, renaming and purging pass. Original media and all original distribution
file payloads remain unchanged. Reproduce with run_rte_l_fmgr.py; details in
docs/hp1000/rte-l-fmgr.md. This supersedes earlier memory-only FMGR limits.

The owner dropped Chess/ALGOL. Next priorities are the L-Series XL mapping
hardware within the existing CPU, authentic RTE-XL generation/boot, then an
HP-IB 7920 installation with space for BASIC, Pascal, Fortran and assembly.
New language packages will be supplied under software/operating-systems.
The existing IVB 7920 host is separate from this target XL installation.
