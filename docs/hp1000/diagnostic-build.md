# Diagnostic build and load path

Host: Darwin arm64, Apple clang 21.0.0, GNU make and Python 3 available.
Baseline commit: `87eb7d5e96f9ce0ee6ac183e20160e5c486b0712`.

```sh
mkdir -p build/hp1000
make -W HP2100/hp2100_cpu.c hp2100 > build/hp1000/baseline-build.log 2>&1
python3 tests/hp1000/inventory.py
python3 -m unittest discover -s tests/hp1000 -v
python3 tests/hp1000/run_baseline.py
```

The forced rebuild passed with the makefile's warnings-as-errors settings and
automatic RegisterSanityCheck. The linker warned that an optional libpng found
in `/usr/local` was x86_64 rather than arm64; the HP2100 executable linked and
all checks ran successfully. No dependencies were installed.

Recovered original executable: `24397-16002_Rev-2001.abin`. Its 114 records
load 6,239 unique words, and each record's additive checksum is valid. The first
four words agree with source declarations/instructions: 160002, 000002,
124003, 003000 (octal). The source specifies start address 4; the harness
does not execute it. SHA-256 is recorded in `build/hp1000/results.json`.

`absolute_binary.py` decodes count byte, unused byte, big-endian address, data
words, and additive checksum, allowing NUL leader/trailer. The format reference
is the current HP2100 `sim_load` and PTR binary-loader implementation. The
existing `LOAD` command is deliberately limited to loader images near a 4K
boundary; it is not a general executable loader. The harness uses SCP deposits
and asserts all recovered words without changing that established command.

An independent load check also attaches the unchanged binary to PTR and runs the
existing 1000-E 12992K paper-tape loader. It must stop at HLT 77, P=77712;
all 6,237 image words above address 1 must match the Python decoder. Addresses
0 and 1 alias A/B, which the loader uses as scratch registers, and are explicitly
excluded from this native-loader comparison. This verifies the decode path
against an existing emulated loader without executing the L-Series diagnostic.

Sources show ASMB directives for the L kernel/DDL. Several 24612 components are
relocatable and reference DCS/runtime externals; later sources require MACRO.
A complete assembler/linker/runtime environment has not been identified, and no
source rebuild is claimed. Use the original L kernel absolute executable for
the initial CPU work while investigating the source toolchain separately.
