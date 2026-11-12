# Original processor firmware investigation

The authentic firmware now completes power-on pretests and reaches interactive
VCP through the optional 12005A console. Register changes, single-step and
run/halt return pass automated checks. Diagnostic bootstrap remains unfinished.
See [12005a.md](12005a.md) for current results and reproduction; earlier bounded
prefix results below describe intermediate bring-up stages.

## Artifacts and reconstruction

All three files exist under
`hp1000-references/software/diagnostics/archives/type-4/`. A search of the local
software tree found no additional `12001-*` components or revisions.

| File | Actual size | Role | SHA-256 |
|---|---:|---|---|
| `12001-18001_Rev-2150.src` | 118,716 bytes | Assembly source, header dated 811204; four logical pages | `a364f90c8a065444de82edbe63238ca1c796d30228afdf136a5da3ee7944a040` |
| `12001-16001_Rev-2140.src` | 12,836 bytes | Hex container holding 4,096 low-lane bytes | `420550eabffce21d1ce2c323d8dffaa2f19b4f99c60c944d2e1085daa7b4b39d` |
| `12001-16002_Rev-2150.src` | 12,836 bytes | Hex container holding 4,096 high-lane bytes | `f6c54e58fe8d0aecba0a6d462f254257f02dff016bdefb6c35d0e3e1c7909228` |

Observed container syntax: STX, `$A0000,`, whitespace-separated hex byte pairs,
ETX, `$S` followed by a four-digit hex checksum, then whitespace. The checksums
are the low 16 bits of the byte sum: E7A6 and 23FF respectively. This identifies
the actual framing; a specific programmer/vendor format name has not been verified.

The files are byte lanes, not sequential ROM halves. Each word is
`(16002[i] << 8) | 16001[i]`. In this order the opening words are 000000,
004002, and 024100 octal, matching source lines 85–89. Reversing or concatenating
the lanes does not reproduce those anchors.

`firmware_source.py` resolves the directives in this particular unchanged
source, then uses HP2100's existing symbolic assembler to encode instructions.
All **3,675 source-emitted words match** the reconstructed image with zero
differences. The 421 words in unassigned source gaps are not source-verified;
their authentic PROM bytes are retained. This establishes that the supplied
pair implements the supplied Rev.2150 source despite different lane labels.
It does not establish how HP assigned or released individual PROM revisions.
No missing byte lane is currently indicated, and no original file was patched.

Reconstructed 8,192-byte image SHA-256:
`a9e036d1731eb1e6c1d6c4357d9b0d265a462a560d715addc2bac76655d490f8`.

The ERD Appendix A listing is an earlier example, identified there as source
24397-18001, while the archive source identifies 12001-18001 Rev.2150. The
manual explicitly allows later firmware differences. We use it to verify
organization and hardware rules, not as a byte-identical release reference.

## Hardware mapping evidence

Local specification: `02103-90009_L-Series_ERD_Sep80.pdf`:

- Printed A-1/PDF 321: four 1K-word pages overlay the same RAM address space;
  assembly origins start at 04000, but execution can be on any 1K page. Common
  RAM storage occupies the last 64 words of the execution page. Standard memory
  uses the last page; expanded memory uses page zero.
- Printed A-2/PDF 322, figure A-1: processor output bits 8:7 select page 0
  (pretest), page 1 (VCP), or pages 2–3 (loaders). The manual identifies physical
  low/high PROM parts 5180-0123/5180-0124, versus obsolete 2K parts 5090-1624/1625.
  Equivalence between those physical part numbers and archive filenames has not
  been independently verified.
- Printed A-3/PDF 323 and source lines 26–48: instruction fetches and A-side
  reads use ROM; B-side reads use RAM. JSB return writes and stores use RAM;
  JMP indirect reads RAM. EAU address words and operands use ROM. The gating
  expression is FETCH or (READ and not IR11) or EAU.
- §2.5.1.4–2.5.1.6, printed 2-42–2-44/PDF 65–67: CPU-internal A/B fetches
  and ROM read/fetch bus behavior. A/B aliases remain CPU-internal, and DMA
  reads do not pass through the ROM overlay.
- §2.5.4, printed 2-55/PDF 78: slave transfers occur between instructions,
  through SLAVE-/SCHOD-/IORQ-/IOGO-, and the one slave-capable card must use
  select code 20. Figure 2-23, printed 2-57/PDF 80, supplies the handshake.
- §2.5.5, printed 2-56/PDF 79: the CPU chip's electrical bus integrity test
  precedes software self-tests. Source lines 85–90 identify offset 2 as the
  software entry after that test. The emulator begins there and does not
  claim to execute the CPU chip's internal electrical test.

02103-90007 §4-10/4-12, table 4-3, printed 4-4–4-5/PDF 50–51, distinguishes
the processor input switches from its output/page register and specifies
CLC 2/STC 2 ROM control. Source reset at logical 00002 fetches page 0 offset
2 and jumps to logical 00100; source START at 04100 is an assembly address,
not the hardware reset PC.

## Implementation and repeatable checks

ROM loading and execution live inside the existing HP2100 simulator. The
`CPU_1000` mask remains M/E/F only. No HP firmware is embedded in C or committed.

```sh
make hp2100
python3 tests/hp1000/firmware.py
python3 tests/hp1000/firmware_source.py
python3 tests/hp1000/run_firmware.py
python3 tests/hp1000/run_l_series.py
python3 tests/hp1000/run_baseline.py
python3 -m unittest discover -s tests/hp1000 -v
```

`firmware.py` writes an 8,192-byte big-endian image and provenance manifest under
`build/hp1000/firmware/`. Source comparison does not execute the firmware.
`run_firmware.py` checks all four ROM pages, A/B aliases, ROM versus RAM reads,
indirect chains, stores, EAU address/operand reads, page output, ROM disabling,
high-address mirroring, atomic rejection of a truncated replacement, and M/E/F
isolation. Its synthetic ROM is test data, distinct from the original image.

For the authentic image it executes RESET -P, checks PC=2, enables tracing,
and bounds execution at 5,000 instructions and 30 seconds. The expected current
result is 157 instruction attempts: 156 complete and the last stops at
`CLC 5`, logical 00416/source 04416. CPU self-test failure loops do not reach
this checkpoint. A timeout, unexpected loop, or different stopping point fails
this test. This validates only the instruction-pretest prefix.

Interactive setup is:

```text
SET CPU 1000-L
SET CPU LROM=build/hp1000/firmware/processor-rom.bin
RESET -P
GO
```

`BOOT CPU` also starts the loaded original image at offset 2; without a loaded
L image it is refused. Other models' boot ROMs remain refused for L. Plain
RESET does not substitute for a power-on reset. Loading a ROM does not start it.
LROMEN and LSTATUS expose overlay/page state, while LROMLD reports image presence.
SCP memory deposits/assertions still access RAM; instruction traces show actual
ROM fetches. Stop messages identify ROM PC and opcode rather than a RAM mnemonic.

`firmware-results.json`, `source-report.json`, and `power-on.trace` preserve
results and context. `--require-vcp` now runs the original pretest and interactive VCP checks through
`run_asi.py`; a prefix alone cannot satisfy that gate. The disk diagnostic
bootstrap is tested separately by `run_hpi.py`.

## Remaining execution gates

| Target | Status | Specific remaining work |
|---|---|---|
| Source/binary discovery and lane validation | PASS | All emitted source words match; unused gaps are retained |
| Processor ROM overlay | PASS for tested paths | XL and complete trap/interrupt interactions remain unfinished |
| Original CPU instruction-pretest prefix | PASS | 156 instructions complete before first unfinished I/O operation |
| Complete power-on pretest | PASS | Original ROM completes CPU, memory and I/O tests with ASI enabled; see `12005a.md` |
| Interactive original VCP | PASS | Register display and A/P changes verified; see `12005a.md` |
| 12005A console | PASS | Programmed I/O, receive/echo and UART loopback verified; see `12005a.md` |
| Slave mode / VCP single-step | PASS | INA single-step and run-to-HLT return verified; see `12005a.md` |
| VCP diagnostic bootstrap | PASS for tested disk path | Original VCP → HP-IB loader → BOOTX → HPIB diagnostic reaches DDL READY; full diagnostic pass remains open |

Source evidence for the serial path is available at lines 1724–1795 and
1850–1861: console discovery selects SC 20, uses global addressing, card
registers 30/31/32, and serial control words 001010/006412. That evidence is
not a complete card specification. The 12005A hardware manual remains a useful
optional reference; its absence is not grounds for fabricating register or
slave-mode behavior. No console prompt or firmware bootstrap pass is claimed.
Separately, directly loaded KERN now passes its word-memory phase; that result
does not exercise the VCP bootstrap. See `diagnostic-results.md`.

A promising bootstrap path is the HP 264x mini-cartridge protocol over the
12005A, rather than pretending the existing PTR is an L-Series card.
02103-90007 figure 2-1, printed 2-4/PDF 24, says that this loader reads absolute
binary files. Source lines 2849–2896 implement terminal command framing, count,
address, data and checksum handling; lines 2983–3020 show big-endian byte/word
transfers and serial control words. This agrees with the decoded 24397 absolute
record structure, but terminal record framing and the complete load path remain
unverified. A terminal/media backend must respond to the actual emitted commands
and deliver unchanged records through the card; no diagnostic-load shortcut is
implemented.

## Parity implementation update

SC 5 parity is now implemented (see `parity.md`). The authentic startup-prefix
checker now observes 164 attempts, with 163 completed before OTB 7,C at logical
00425/source 04425. The former CLC 5 checkpoint above describes the earlier
implementation. Full power-on pretest, VCP and bootstrap still remain unfinished.
The directly loaded KERN parity-interrupt phase now passes independently.

## Processor-I/O update

SC 7 violation-register transfers are now implemented. The reproducible authentic
prefix checker executes all 164 instructions through OTB 7,C and stops at a
breakpoint at 00426, rather than expecting that transfer to be unsupported.
BOOT CPU reaches the same checked boundary. Longer startup is still unverified;
this checkpoint is not a claim that the complete pretest or VCP has passed.

## SC 3 update

ROM-P and P-SAVE transfers are implemented with all sixteen bits preserved;
see `sc3.md`. Slave transitions, CLC 3 delayed requests and serial operation
remain unfinished. A longer authentic reset probe now checks the next stop at
00710/STC 11, separately from the stable 164-instruction prefix checkpoint.
Neither probe claims full power-on pretest or interactive VCP completion.

## 12009A disk bootstrap update

The original VCP/HP-IB/BOOTX path now loads and executes HPIB from 24397A.hpi.
Its title and READY prompt are verified by `run_hpi.py`. The RTE-L master also
executes its own BOOTX and reaches its documented HLT 2 when SYSTEM is missing.
These results supersede earlier statements that no firmware bootstrap had run.
See [12009a.md](12009a.md) for the exact workload, evidence and remaining gaps.
