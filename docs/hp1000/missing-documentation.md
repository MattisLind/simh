# Documentation and ROM requests

The supplied CPU manuals and original kernel binary allow useful work now.
The most valuable additional manuals, verified against 02103-90007's
documentation map (printed iii, PDF 5), are:

The owner reports that **24397-90002**, **02103-90005**, and **24397-90003**
cannot currently be found. These remain optional acquisition leads, not
prerequisites for initial CPU development; do not repeatedly request them.
Continue with the supplied ERD, reference manual, and unchanged diagnostic sources.

Reconstruct kernel setup, entry paths, dependencies, error reporting, and repeat/
completion conditions from `24397-18002`; inspect `24397-18003` for DDL runtime
and loading behavior. Cross-check any inferred behavior against the manuals and
original binaries. Record source revision and line references, distinguishing
documented hardware behavior from diagnostic expectations and unresolved details.
I/O register, interrupt, or DMA details that remain ambiguous need explicit
tracking rather than guessed implementations. Diagnostic success must have
verified criteria; an unexplained halt, loop, or timeout is not a pass.

| Priority | Part number | Manual / purpose |
|---|---|---|
| First | **24397-90002** | Kernel Diagnostic Operating Manual: setup, modes, pass/error indications, fixtures, ROM prerequisites |
| First | **02103-90005** | L-Series Computer I/O Interfacing Guide: distributed I/O chip, register, interrupt, and DMA details |
| Next | **24397-90003** | Diagnostic Design Language Operating and Programming Manual: L-Series DDL runtime and loading |
| Next | **12005-90001** | 12005A Asynchronous Serial Interface Reference Manual: first console card |
| Next | **24397-90005** | 12005A diagnostic operation and loopback requirements |
| Helpful | **24397-90001** | L-Series Hardware Troubleshooting Guide |

Original processor firmware was found locally: 12001-18001 Rev.2150 and
the PROM lanes 12001-16001 Rev.2140 / 16002 Rev.2150. All source-emitted
words match their reconstructed image. Additional ROM dumps are no longer an
initial prerequisite. See `firmware.md` for provenance and remaining hardware
gates. The kernel's VCP dependencies still require working ROM/VCP execution.

A-Series manuals, SCSI, LAN, and later interfaces are deferred. Original assembler
and loader executables plus their operating instructions would help rebuild the
sources, but the original L kernel binary avoids making that a prerequisite for
initial CPU work. No additional download has been claimed.

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
