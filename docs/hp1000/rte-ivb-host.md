# RTE-IVB host and original RTE-L generator startup

The supplied RTE-IVB Rev.5010 package now boots on the existing HP2100
1000-E model. HP's READR restores and verifies the RTE-L relocatables, and
HP's LOADR links the original RTLGN main and all four segments. RTLGN executes
its startup and checks its command-file argument. This establishes a working
host/import/link/start path; a complete target generation has not been run.

## Reproduce

From the repository root:

```
make hp2100
python3 tests/hp1000/run_rte_ivb.py
```

Inputs are the supplied `RTE-IVB/` directory and `92070-13401.hpi` in
`hp1000-references/software/operating-systems/`. The runner uses the packaged
configuration with optimized execution and creates a fresh little-endian copy
of the big-endian 7920H image. All guest writes target this copy under
`build/hp1000/rte-ivb-validation/`; the supplied image is hash-checked afterward.

Original image, 50,565,120 bytes:
`3a3a06b9a619ed56f0b02b2f1368ea57250dbaa5ef14b2d950e7e2c9e99bde63`.

Initial byte-swapped copy:
`75e8418b2d57a5740f1d7941c576122e2c9183959841daf213f776a4e37b1a24`.

The generated SCP script, transcript, file manifest, provenance and results are
retained in the output directory. The working image changes during import and
linking; its initial swapped hash is therefore not its final hash.

## Import mechanism

`rte_archive.py` creates an interchange tape using the SAVER/READR format
specified by original HP sources `92068-18053 Rev.5010` (header/directory) and
`92068-18054 Rev.2241` (JREAD's raw file access). This is a newly packaged
transport containing unchanged original data, not an original HP-produced tape.

The source master has 55 type-5 relocatable files. Their complete allocated
extents, names and types are preserved; each source extent is hashed. FMP's
64-word sector sizes are converted to READR's 128-word block counts. Tape data
records contain the same big-endian words, wrapped in SimH tape records. The
remaining ASCII and boot files are not imported by this runner.

The real guest READR restores them to cartridge SC with verification enabled.
All **55 restores and 55 verifies** complete. This includes `%RTLGN`, `$LDRLB`,
`$MXLB`, the target system libraries, and the original interface/device modules.
The host system cartridge and the source master remain separate.

## Verified linking and startup

At the real host file manager, the successful loader sequence is:

```
RU,LOADR
LI,$LDRLB::SC
LI,$MXLB::SC
RE,%RTLGN::SC
EN
```

The libraries matter: `$LDRLB` supplies loader globals such as `CPL.L` and
relocation algorithms; `$MXLB` supplies the original `.X.Y.` support module,
including `.X.` and `.Y.`. The host's own system library resolves EXEC, file
management and other host calls. The RTE-L target `$SYSLB` is not substituted
for the host runtime in this link.

The transcript identifies RTLGN Rev.2026 and RTLG1..RTLG4, then reports:

```
11 PAGES RELOCATED
/LOADR:RTLGN READY AT ...
```

`RU,RTLGN` subsequently prints:

```
FMGR -6 ON FILE COMAND
```

That is the expected no-command-file path in `92070-18078`; it demonstrates
actual execution of RTLGN and its initial segment using the IVB runtime. It is
not a successful system-generation message. No executable or guest firmware was
patched, and no replacement loader or synthetic RTE-L system was used.

## Next stage

Prepare and verify a generator command file for the intended standard-memory
L-Series configuration. The original sources specify initial `LI,CP`/`LI,BP`
and `MS,16`/`MS,32` records, followed by target relocation, I/O tables and memory
allocation phases. Their complete sequence and target-module dependencies must
be checked before a generated output can be called bootable.

Generation must retain its input, SYSTEM, SNAP and SYLIST, and require clean
source-defined completion. Then install a writable target disk copy and boot
through the original VCP/12009A. Full PHI behavior, disk-controller conformance
and normal 12005A console DMA remain independent hardware work.

## Subsequent generation checkpoint

Full target generation now completes with zero errors using `SZ,24` for the
host generator's workspace. The generated memory-based RTE-L SYSTEM reaches
02003 through original VCP/BOOTX on a 7902 copy. See [rte-l-built.md](rte-l-built.md).
The startup-only runner above remains a separate host regression.

## Completed target generation and runtime validation

The original host READR/LOADR/RTLGN workflow now produces the target SYSTEM with
zero errors. The canonical generation includes CLASS, sixteen class entries and
1024 SAM words. The 7902 image boots through original VCP/BOOTX on the L CPU,
prints SYSTEM READY and COMND, executes TM and returns to kernel idle. See
[rte-l-built.md](rte-l-built.md) for reproduction, hashes and installed-FMGR limits.
KRNL, HPIB including disk loopback, and genuine ASIC Rev.2040 have passed before
this OS continuation. No original media or HP program is patched.
