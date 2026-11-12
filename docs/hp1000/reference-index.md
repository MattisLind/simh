# Local reference index

Originals are in `hp1000-references/`; `tests/hp1000/inventory.py` generates
`build/hp1000/inventory.csv` with SHA-256 hashes and local filenames. Acquisition
URLs and provenance were not supplied and have not been reconstructed.

| Publication | Local file under `manuals/architecture/` | Verification |
|---|---|---|
| HP 1000 L-Series Computer Reference Manual, 02103-90007, second edition October 1980 | `1000_L-Series_ReferenceManual_02103-90007_78pages_Oct80.pdf` | Title/number/date visually verified on PDF 3; printing history on PDF 4; 78 PDF pages |
| L-Series Engineering and Reference Documentation, 02103-90009, September 1980 | `1000_L-Series_EngineeringAndReference_02103-90009_461pages_Sep80.pdf` | 461 PDF pages; title/date currently taken from supplied filename, detailed review pending |

The added `02103-90009_L-Series_ERD_Sep80.pdf` was checked on 10 November
2026. It has 461 pages and is byte-for-byte identical to the longer-named ERD
file above (SHA-256 `df199abb8214ad92e4c339dc5b302c5564aec55ecb806d044ca5606b6d828e9d`).
PDFKit found no extractable text on any page of this added copy; the reported
OCR layer is not present in the saved file as read by this tool. Keep both
original files unchanged; treat them as duplicate copies of one publication.

The supplied PDFs currently yield no searchable text through local PDFKit extraction.
OCR of the reference manual is available locally at `build/hp1000/reference-ocr.txt`;
OCR is a search aid, and exact encodings must be checked against the scans.

Key references in 02103-90007: documentation map printed iii/PDF 5; architecture
§1-1 printed 1-1/PDF 11; distributed I/O §1-7 printed 1-2/PDF 12; I/O
instruction addressing §3-19 printed 3-12/PDF 42; interrupt assignments table
4-1/PDF 48; global register §5-4/PDF 56. The documentation map is the source
for the L-specific manual numbers in `missing-documentation.md`.

The first CPU subset additionally uses 02103-90007 §3-3/3-4 (addressing),
printed 3-1/PDF 31; §3-7 (nonexistent memory), printed 3-3/PDF 33; §3-15
(memory-reference operations), printed 3-5–3-7/PDF 35–37; and Appendix A
extend/overflow examples, printed A-9/PDF 73.

Processor firmware: ERD Appendix A-1–A-4/PDF 321–324 and §2.5.1.4–2.5.1.6,
printed 2-42–2-44/PDF 65–67, establish overlay, read gating and organization.
Slave mode is §2.5.4, printed 2-55/PDF 78, with figure 2-23 at PDF 80;
power-on sequencing is §2.5.5, printed 2-56/PDF 79. These pages were visually
inspected. See `firmware.md` for archive components, checksums, and comparison.

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

## ASIC hood and diagnostic revision validation

The supplied `24612-90011_HP1000A-SeriesComputerInterfaceDiagnosticsReferenceManual_238pages_Feb92.pdf`
contains the ASIC hood jumper table and schematics at printed 2-9/2-10
(PDF29/30), plus the program listing in Appendix B. Its embedded text is extracted
in `build/hp1000/manuals/24612-90011.txt`. The physical 12005A pin definitions and
schematic are in 12005-90001, Table 2-5/Figure 7-4.

Full disk KRNL and original HPIB (including 7902 controller loopback) now pass.
Authentic ASIC Rev.2040 also passes; the older disk ASIC's DDL no-entry interrupt
return does not restore interrupts. HP's Rev.2040 source/binary supplies the fix
without an emulator workaround. See [12005a.md](12005a.md) and
[12009a.md](12009a.md); older prefix-only statements above are superseded.
