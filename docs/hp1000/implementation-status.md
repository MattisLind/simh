# Implementation status

Target: HP 2103L / HP 1000 L-Series integrated into HP2100. A-Series deferred.

| Milestone | Status | Evidence / remaining work |
|---|---|---|
| 0A baseline | PASS | Rebuilt existing emulator, internal register check, seven model smoke checks |
| 0B inventory | PARTIAL | Complete hashed file index; L family and named 24612 leads examined; full dependencies/media audit pending |
| 0C usable original binary | PARTIAL | Original L kernel load-verified; word-memory and parity-interrupt phases pass at 32KW; instruction/I-O prefix plus first two MP checks pass; select-code sweep and initialized MPT09 pass; mode 1 implemented; KERN enumerates enabled L interfaces; original HPIB diagnostic boots to DDL READY; no full KERN pass |
| 0D harness | PARTIAL | Bounded memory-phase runner checks source-derived completion and error entries; later diagnostic success criteria still needed |
| 1 model integration | PARTIAL | Experimental 1000-L in HP2100; separate capabilities; user-supplied processor ROM loading, software reset entry, stepping, breakpoints, and ROM-aware traces |
| 2 CPU/memory | PARTIAL | Memory-reference, shift/alter, documented EAU encodings, JLA/JLB, simulator HLT, L NXM semantics, and four-page ROM overlay and standard protection; XL unfinished |
| 3 interrupt/I/O/DMA | PARTIAL | SC 0/4 controls, SC 3 ROM-P/P-SAVE transfers, SC 5 parity, SC 6 TBG, Type 1 UI trap and SC 7 register transfers; standard protection/Type 2 and third-level Type 3 recognition implemented; mode-1 enumeration implemented; interface drivers and distributed DMA unfinished |
| 5 first interface | PARTIAL | 12005A programmed I/O and shared chip implemented; authentic power-on pretests, interactive VCP, single-step and run/halt pass; full DMA and diagnostic bootstrap pending |
| 6 operating system | NOT RUN | RTE-L BOOTX executes through 12009A; supplied L/XL masters have no SYSTEM; cross-generation investigation is separate |

Early firmware milestone achieved: authentic power-on pretests → interactive
original VCP on the 12005A console, including single-step and run/halt return.
Original diagnostic bootstrap remains open. All 3,675 emitted source words
match the reconstructed ROM. See [12005a.md](12005a.md) for reproduction and
implementation limits. With ASI enabled, initialized KERN enumerates SC 20
and reaches TST06; this does not establish a full kernel pass.

The Phase 0 gate is only partially met: decode/load automation works, but actual
diagnostic execution/pass detection and detailed source build reconstruction do
not. Continue the architecture audit and CPU work against the supplied manuals;
reconstruct kernel operating instructions and success criteria from the supplied
sources and binaries before claiming original diagnostic passes. The owner could
not locate 24397-90002 or 24397-90003; continue unblocked CPU work
and evidence-based diagnostic analysis without waiting for these manuals.

12009A update: optional HPI at SC27 now shares the HP-IB bus and existing DA
hard-disc endpoint, with a new 7902/9895 floppy subset. Seven directed/integration
checks pass, including interrupts, DMA, scratch-media writes, the authentic
RTE-L BOOTX missing-SYSTEM checkpoint and original HPIB diagnostic startup.
The full PHI diagnostic remains incomplete. See [12009a.md](12009a.md) and
[rte-l-generation.md](rte-l-generation.md).

## RTE-IVB generation-host checkpoint (2026-11-11)

The user-supplied original RTE-IVB image boots in the existing 1000-E simulation
using a separate byte-swapped copy. All 55 RTE-L relocatable files restore and
verify through the original READR. The original RTLGN links with `$LDRLB` and
`$MXLB`, including all four segments, and starts through its initial command-file
check. `run_rte_ivb.py` automates these checks and confirms that the source disk
is unchanged. No complete RTE-L generation or running L-Series OS is claimed.
See [rte-ivb-host.md](rte-ivb-host.md) for exact inputs, commands and remaining work.


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

### Current validation milestone (2026-11-12)

- Full original disk KRNL passes with ASI/HPI/ASI1 installed.
- Original disk HPIB passes offline/online interface checks and 7902 controller
  loopback, ending with PASS COMPLETE. Optional two-card test was not run.
- Authentic ASIC Rev.2040 passes all baud settings, the external-clock test and
  PASS COMPLETE using the documented hood. Rev.2001's no-entry DDL PINT path
  remains defective; HP's later source/binary restores interrupts correctly.
- Original RTLGN generates the CLASS-enabled RTE-L SYSTEM with zero errors.
  Original VCP/BOOTX boots it from the read-only 7902 image to SYSTEM READY and
  COMND; a real TM command prints time/date and returns to kernel idle.

Reproduce with run_krnl_disk.py --second-asi, run_hpib.py,
run_asic.py --revision 2040, run_rte_l_generation.py and run_rte_l_boot.py.
This supersedes the earlier diagnostic pause and loader-only checkpoint.
Disk-based FMGR installation and full hardware conformance remain open.
