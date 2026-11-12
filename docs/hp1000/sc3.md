# SC 3: ROM-P and P-SAVE

SC 3 register transfers are implemented in the L-only processor-I/O handler of
the existing HP2100 simulator. They do not change the existing 21xx/M/E/F path.

02103-90007 section 2-27 (printed 2-9/2-10, PDF 29) describes registers on the
slave-capable I/O chip: P-SAVE stores the interrupted program's P at VCP entry;
ROM-P stores the entry address to place in CPU P. Table 4-3 (PDF 51) specifies
load, merge and output operations. C selects a different register here; it does
not clear either register after transfer.

| Instruction | Register/action |
|---|---|
| LIA/B 3 | Load P-SAVE |
| MIA/B 3 | Merge P-SAVE |
| OTA/B 3 | Write P-SAVE |
| LIA/B 3,C | Load ROM-P |
| MIA/B 3,C | Merge ROM-P |
| OTA/B 3,C | Write ROM-P |
| STF/CLF/SFS/SFC 3 | NOP, no skip |
| STC 3 | NOP |

Both registers retain **all 16 bits**, independently of the CPU's 15-bit P.
Original firmware 12001-18001 lines 1113–1127 explicitly tests ROM-P's high bit
as the single-cycle flag, clears it, then sets it again with IOR .100K before
OTA 3,C. Masking these registers to 15 bits would break the original VCP.
P-SAVE also carries firmware flags (for example the comments around lines
1132–1142 and the loader continuation logic).

The simulator exposes LPSAVE and LROMP as 16-bit registers, so their values are
included in simulator save state. Power reset and L model selection clear them.
They are not overwritten on ordinary CPU instruction fetches: P-SAVE belongs to
the slave I/O chip, not the CPU's internal instruction-address save mechanism.

## What this enables, and what remains

The register operations are necessary for authentic VCP execution. They do not
implement the slave handshake itself. CLC 3 delayed requests, HLT-to-VCP entry,
P capture/restore at slave transitions and the 12005A serial interface remain
unfinished. CLC 3 continues to stop explicitly; interactive VCP is not claimed.

Unchanged KERN now reads SC 3 successfully and reaches **14311: LIA 10,C** in
the select-code sweep. This is the same instruction location as the previous
stop because the diagnostic modifies its select-code field in place. The opcode
has advanced from 103503 to 103510. Both entry points, 13777 and 03777, still
match, with the previous two protection violations passing.

The original firmware's checked 164-instruction prefix remains valid. A new,
longer bounded probe from reset, with tracing disabled during memory loops,
reaches **00710: STC 11** (102711), a mapping control not implemented by the
standard-L subset. The opcode is checked against the reconstructed original
PROM. This is a known stop, not a completed pretest or proof that ROM-P has
already been initialized by the firmware. Full VCP startup remains unfinished.

```sh
python3 tests/hp1000/run_io.py
python3 tests/hp1000/run_kernel_io.py
python3 tests/hp1000/run_firmware.py
```

The I/O runner now has 74 checks, including 27 SC 3 cases: A/B and C selection,
load/merge/output, zero/full/high-bit patterns, independent register contents,
NOP controls, a complete four-instruction round trip with E/O preserved, and
power reset. Firmware-prefix and extended-probe results are under
`build/hp1000/firmware/`; KERN entry comparison remains under
`build/hp1000/kernel-io-verified/`.
