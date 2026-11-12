# Authentic RTE-L generation investigation

The supplied RTE-IVB host now boots, and the original RTE-L RTLGN links and
starts successfully. Full system generation remains unfinished. See
[rte-ivb-host.md](rte-ivb-host.md) for the repeatable test and evidence.

This workstream concerns original HP software and media. Hardware development
continues independently in [12009a.md](12009a.md). No SYSTEM file has been
fabricated, no relocatable has been treated as an operating-system image, and
no A-Series image has been used as an L-Series system.

## Inspected media

`tests/hp1000/rte_disk.py` reads BOOTX/FMP directory structures without writing
media. Offsets and sizes use 64-word FMP sectors, distinct from the 256-byte
hardware sectors. The decoder follows the supplied BOOTX source's
CONT/TCONV/DIREC/FOUND routines. For later masters without a sector-zero BOOTX,
it locates a header using the geometry and directory self-address; ambiguous
headers are rejected.

| Image | Directory findings |
|---|---|
| 92070-13401.hpi | BOOTEX, %RTLGN, %LOADR, %EXEC, %INSTL, $SYSLB, $LDRLB, $SYS.., interface/device modules and other software; no SYSTEM |
| 92071-13401 RTE-XL master 1 Rev.2340 | 64 entries, including BOOTEX, %RTLGN, %LOADR, %BUILD and %PFORM; no SYSTEM; sector zero is not the older BOOTX header |
| 92071-13415 RTE-XL master 2 Rev.2340 | 40 entries, including development libraries, %MACRO and %LOADR; no SYSTEM |
| 24397A.hpi | BOOTEX plus original diagnostics, including bootable KRNL and HPIB files; no RTE-L system |

Directory JSON files include image and individual file SHA-256 hashes under
`build/hp1000/12009a/`. The RTE-L master hash is
`1d1e1a901fcd3a2a605cca206b5e51ca2e32b9cf31cf2bdeb0ceca1f55112d90`.
KRNL.bin and the 24397 absolute binaries are diagnostics, not RTE-L systems.

## Verified software relationships

- **12009A interface:** HP application note AN 401-1L, printed page 1, specifies
  interface driver **10.37**, used with disc device driver **00.30**. These are
  distinct layers. Sources supplied locally identify `ID.37` as
  `92070-16095` and `DD.30` as `92070-16085`.
  [Original HP application note](https://hpwiki.org/_media/application_notes%3Aan-401-1l.pdf)
- `92070-18085 Rev.1941`, lines 19..27, supplies two 7902 logical-unit defaults:
  units 0/1, 30 hardware sectors per track, two heads and 134 logical tracks.
  These are generation records, not a claim that a particular system is generated.
- `92070-18077 Rev.2026` identifies RTLGN as `92070-16077` and declares segmented
  execution through EXEC plus file-management/library calls. Default file names
  in its source are `COMMAD`, `SYSTEM`, `SNAP`, and `SYLIST`. Thus a host runtime,
  resolved external symbols and command/configuration inputs are required.
- `92070-18108 Rev.2026`, printed source lines 18..29, describes the genuine
  RTE-L relocating loader and explicitly says it may run on RTE-L or an
  **RTE-IVC** system. This is the literal historical comment. The empirical IVB startup check
  below now establishes boot/import/link/start compatibility, while complete
  generation remains unverified.
- `92070-18119 Rev.2026` contains RTE-IV output-format compatibility changes.
  This supports investigating a cross-host route, but is not a completed test.

## Candidate host and exact outstanding requirements

The simulator's own guide documents a preinstalled **RTE-IVB Rev.5010** host
on a **7920H** image, available from HP Computer Museum. Its description includes
a simulator command file, the relocating loader, assembler, file manager and
archive utilities. The supplied image is big-endian; existing DA simulation
requires a separate byte-swapped copy. Its documented minimum includes an M/E/F
CPU, 96KW, DMS, memory protection, TBG, 12821A and terminal.
[Simulator guide](https://opensimh.org/simdocs/hp2100_doc.html),
[Host kit description](https://www.hpmuseum.net/display_item.php?sw=565)

The user supplied the complete kit locally. Its original 50,565,120-byte image
has been preserved; a separate swapped working copy boots. All 55 original
RTE-L relocatable files restore and verify through READR. RTLGN links with its
original `$LDRLB` and `$MXLB`, and executes its no-command-file startup path.
No completed target SYSTEM or cross-generation success is claimed.

Current requirements and status:

1. DONE: original RTE-IVB kit and packaged startup configuration boot successfully.
2. Original RTE-L %RTLGN (main/segments), the appropriate relocating loader,
   host runtime libraries and the complete matching target libraries/modules
   from 92070A. DONE for the startup trial: original RTLGN and both support
   libraries and all four segments link, and generator startup executes. Full
   generation/revision compatibility still requires target-output validation.
3. DONE for all 55 type-5 files: a documented SAVER/READR transport preserves
   source file extents and metadata; the real guest READR verifies every file.
   ASCII and boot files are not imported by that runner. The floppy is not
   attached as a DA hard disk.
4. A genuine generator command/answer file for a minimal standard-memory L:
   32KW, ASI at SC20, 12009A at SC27, ID.37 plus DD.30 and the chosen disc units.
   No known matching answer file is supplied. Exact syntax, ordering, partition,
   runtime and file-management requirements need verification.
5. Correct output installation and boot-file format. SYSTEM, SNAP and listings
   must be produced by HP's actual generator/loader workflow, then installed on
   a writable copy using genuine file-management procedures. A raw concatenation
   of relocatables is not a valid replacement.

Useful original documentation is **92070-90016** (RTE-L/XL Generator Reference),
**92070-90014** (Generation Planning), **92070-90018** (Software Installation),
and the corresponding RTE-IVB loader/file/archive manuals. The earlier
92070-90001 is known unavailable and is not a prerequisite for further hardware
work. The precise generator host/version requirements remain unresolved.

## Shortest practical path

The IVB boot, import and RTLGN startup steps are complete. Next establish a
validated minimal generator command file and target relocation/library sequence.
Run HP's generator, require clean completion, and retain SYSTEM, SNAP, SYLIST,
input answers and hashes. Install that output using genuine file-management
procedures, then boot it through the L-Series VCP/12009A and require real console
and file-system operation.

If later generation phases expose host incompatibilities, investigate those
against the original sources; startup alone is not proof of complete compatibility. Meanwhile, the original 12009A diagnostic and the
master's genuine BOOTX are available hardware-validation workloads. RTE-XL also
requires the unfinished expanded-memory hardware, so its distribution discs do
not offer a shorter demonstrated route to standard-memory RTE-L.

## Required validation order (user direction, 2026-11-11)

1. Produce an authentic RTE-L SYSTEM with HP's generator, install it on a
   working 7902/7906 image, and demonstrate that the original bootstrap loads
   SYSTEM instead of reporting it missing. This is a boot checkpoint, not an
   operating-system acceptance test.
2. Pause further OS bring-up and run the original KRNL from `24397A.hpi` to a
   complete pass. Existing instruction-level tests do not substitute for this.
3. Add a second 12005A ASI and a virtual serial loopback, then run the original
   ASIC diagnostic from that disk to a complete pass.
4. Run the original HPIB diagnostic to a complete pass, resolving the known
   PHI test failures rather than bypassing them.
5. Resume RTE-L boot debugging once the relevant diagnostics pass.

Generated files from an aborted RTLGN run are incomplete scratch outputs and
must not be installed or counted as a successful SYSTEM generation.

## Successful generated boot checkpoint (supersedes missing-SYSTEM status)

RTLGN now completes with zero errors and its genuine SYSTEM boots from a 7902
working copy to kernel entry 02003. The low 31KW matches the generated image.
This is a memory-based COMND validation system, not an installed disk-based
FMGR system. See [rte-l-built.md](rte-l-built.md) for reproduction, hashes,
source-derived installation details, limitations, and the diagnostic gates.

## Current result: generated and running memory-based RTE-L

The workflow is now verified through zero-error generation, original 7902 boot,
SYSTEM READY, COMND and an actual TM command with normal idle return. The final
input includes `%CLASS`, `CL,16` and `SA,1024`; SA is a word count. Earlier
minimal inputs exposed missing optional class I/O and insufficient SAM, now
resolved by ordinary RTLGN configuration. See [rte-l-built.md](rte-l-built.md).
Installed disk-based FMGR remains separate work. Diagnostics passed before this
continuation: full disk KRNL, original HPIB with 7902 loopback, authentic ASIC
Rev.2040. The original older ASIC's DDL interrupt-restore defect remains recorded.
