# RTE-L boots from the generated 7902 image

The original RTLGN completes with **0 errors** under the supplied RTE-IVB host.
The L-Series runs the original VCP and BOOTX, loads SYSTEM from the emulated 7902
through the 12009A, and prints:

```
*RTE-L SYSTEM READY*
COMND:
   0: 0:11   JAN  1,1976  THUR
```

The final line is the real response to a typed `TM` command. The test verifies
normal return to the kernel's idle state. The displayed time varies with execution;
it is the guest clock, not a host-generated response.

This is a **working memory-based RTE-L configuration with COMND**, not an
installed disk-based FMGR system. It has 32KW, ASI SC20/console LU1, 12009A SC27,
7902 units 0/1 at LU2/3, four ID segments, sixteen class entries and a 1024-word
SAM pool. `%COMND` is scheduled at startup. HP's memory-based COMND deliberately
terminates after one interactive command (92070-18076, CALR/EX); a second prompt
is not required to prove that command completed. Repeated attention/rescheduling
and broader operator-command coverage remain separate acceptance work.

## Reproduce

```
make hp2100
python3 tests/hp1000/run_rte_l_generation.py
python3 tests/hp1000/run_rte_l_boot.py
```

Generation creates `build/hp1000/rte-l-generated/` with the 7902 image, SYSTEM,
SNAP, SYLIST, command input, source hashes and simulator logs. The boot runner
creates `build/hp1000/rte-l-boot/` with console capture, script/log and results.
It verifies all **31,742 words** at 00002..75777 before executing the kernel at
02003. The missing-SYSTEM HLT2 is no longer reached.

Current SYSTEM SHA256:
`2c84d3a32e8572b715e230c8bdf19973445ab7756f0a2e3abf499b47a3d3cc2a`.
Current generated 7902 image SHA256:
`5be6aa743260b2307ea3320c76e1abe0dd1076ca90f01f5d8429ef0e101120f4`.

Both original source disks and all original file payloads remain unchanged.
Target boot and tests attach the generated image read-only. Every executable
word is produced by HP's original generator and relocatables; neither firmware
nor target software is patched.

## Terminal and generation requirements

The M2645 console configuration uses ENQ/ACK. The boot runner responds with ACK
only when the real driver emits ENQ, using a SimH EXPECT terminal-peer rule.
DD.00 source 92070-18083 Rev.1941 explicitly implements this handshake. This
supplies terminal behavior, not an alternate bootstrap or synthetic OS output.
Host receive data now wakes an active serial DMA request. A focused ASI test
checks that a received ACK is packed into memory and completes that request.

`tests/hp1000/config/rte-l-7902.gen` includes `%CLASS`, `CL,16`, and `SA,1024`.
These are needed by COMND's buffered/class I/O. Earlier minimal builds reached
the kernel but aborted COMND with OP17 (optional class service absent), then
IO04 when CLASS was added but SAM still had only 16 words. RTLG4 source
92070-18081 explicitly defines SA as a **word count**. The corrected input links
normally; no program binary is edited.

LOADR needs `SZ,24` for RTLGN's working storage; its default eleven pages cause
OV FIX before target linking. `$LDRLB` and `$MXLB` provide matching original
loader support. READR restores/verifies all 55 unchanged type-5 files plus the
encoded type-3 GENCMD input. The generation phases keep the kernel/drivers and
background COMND separate; `ST` marks the latter for startup.

The host-side file transport, `rte_disk.append_files`, appends generated SYSTEM
and SNAP to a packed master copy using the original D.RTR directory/allocation
format. It rejects unsupported fragmented or multiple-directory-track layouts
and checks every existing file's hash. Original BOOTEX/BOOTX and 7902 geometry
remain unchanged. SYSTEM starts at track82/FMP sector36; SNAP at track91/sector8.

## Diagnostic gates and limits

Before this OS continuation, full original disk KRNL passed with three cards;
original HPIB passed its offline/online checks and 7902 controller loopback; and
authentic ASIC Rev.2040 passed with the documented hood. The older disk ASIC
Rev.2001 still exposes its DDL interrupt-restore bug. HP's later runtime fixes
that path; it was not patched in the emulator. See diagnostic-results.md.

Disk-based `%FMGR` and `%START` are separate supplied programs. Their installation
is not claimed. Disk-file management, repeated console sessions, broader I/O,
application execution and long-duration stability still require validation.
