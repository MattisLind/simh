# Known issues

- L-Series supports the common integer groups and documented EAU encodings,
  with a four-page processor ROM overlay and a small processor I/O subset.
  KERN Rev.2001's word-memory and parity-interrupt phases pass at 32KW;
  instruction tests from 03777 also reach TST05 (13777), including JLA/JLB;
  the full kernel diagnostic remains unfinished.
- Full processor I/O, remaining trap details, XL expansion, distributed DMA, VCP
  entry/return, serial card, and slave mode are unfinished. Unsupported features
  stop with P preserved. HLT returns to SCP without invoking VCP.
- Original firmware prefix now completes OTB 7,C and reaches checked boundary
  00426. This is not completion of the full power-on test.
- The internal electrical bus test is not simulated. RESET -P/BOOT CPU start
  at the original software entry, offset 2, when a processor ROM is loaded.
- Direct KERN Rev.2001 execution confirms boot entry 2 and START at octal 3000.
  Address 4 becomes a restart only after initialization. The first execution
  entry now passes SC 4 and CLC 0,C and completes the word-memory phase. The
  following parity-interrupt test now passes and reaches CPU tests at 03777.
  Direct 13777 and 03777 runs match through the processor-I/O prefix and stop
  at 14311/LIA 10,C after two protection violations pass. SC 3 transfers now
  work; the select-code sweep next encounters unsupported SC 10 input. Full diagnostic success
  criteria still need investigation from the available sources.
- SC 4 register/skip/control operations are implemented. Actual power-fail
  interrupt generation/delivery and the full L interrupt arbiter remain
  unfinished; LINT23 retains the interrupt-enable state for that work.
- SC 0 control reset and Type 3 flag operations are implemented. The CRS
  broadcast currently has no L interface-card recipients. The processor holds
  TBG mask bit 1; interface-card mask bits and full L arbitration remain unfinished.
- Source filename revision may disagree with its own service header. The CSV
  preserves both; do not automatically pair files solely by revision filename.
- Absolute-record validation proves container integrity only. Full source/binary
  equivalence has not been established beyond the kernel's initial words.
- HPI filesystems, bootstrap paths, and original build-tool executables have not
  been audited. Presence of RTE media is not proof of a runnable toolchain.
- M/E/F memory-map, interrupt, DMA, and device interfaces are not an L backplane.
  Existing masks called CPU_1000 specifically cover M/E/F.
- Optional libpng from `/usr/local` has the wrong host architecture; build passed.
- OCR can misread bit diagrams and numbers. Check scan images before implementing
  encodings. Local OCR uses Apple's Vision service, which required sandbox approval.

- Functional RAM parity and Type 1 delivery are implemented. DMA/XL parity,
  full interrupt priorities and electrical fault timing remain unvalidated.

- The 10 ms TBG uses instruction-time accounting during CPU execution, not host
  wall time. Table 3-5 integer times are used; data-dependent EAU timing, DMA
  delays and board-level divider phase are not cycle-accurate. See `io.md`.

- Standard L protection is implemented and independently tested; KERN MPT03–09
  remain unverified behind the processor/I-O select-code sweep. Reference manual/ERD disagree
  on SC 3 protection exemption. See `protection.md`.

- SC 3 ROM-P/P-SAVE transfers work, but CLC 3 delayed slave requests, actual
  P capture/restore and serial VCP operation remain unfinished. A longer
  authentic firmware probe stops at 00710/STC 11. See `sc3.md`.

- Unassigned L inputs provisionally return 177777 by owner choice, not verified
  bus documentation. Direct KERN entry comparison now passes to MPT03/14324.
  The MPT09 indirect-chain interrupt error is now resolved; initialized KERN
  now reaches the real no-I/O-chips error after mode-1 enumeration. Full KERN remains incomplete. See `unassigned-io.md`.

- L third-level indirect-chain TBG interrupt recognition now passes MPT09;
  2116 board-dependent behavior is regression-tested unchanged. See
  `indirect-interrupts.md`. Mode 1 is implemented; other diagnose modes and real L cards remain unfinished.

- Diagnose mode 1 is implemented, with no real L chips installed by default.
  KERN now reports its genuine no-I/O-chip error. Modes 2–7, mode-1 merge
  semantics, and real interface drivers remain unfinished. See `diagnose-mode-1.md`.

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
