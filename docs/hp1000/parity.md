# L-Series software parity

Implemented functional RAM parity and SC 5 inside HP2100. The model stores a
seventeenth bit per standard L RAM word, generates parity on writes using the
selected odd/even sense, and detects mismatches on reads when enabled. There
are no KERN-specific shortcuts or changes to the original diagnostic. This
models software-injected faults, not random electrical failures or bus timing.

Specification: 02103-90007 §4-2, printed 4-1/4-2 (PDF 47/48), and table 4-3,
printed 4-5 (PDF 51). KERN Rev.2001 lines 1160–1220 independently exercise
data-read completion, fetched-instruction inhibition and interrupt acknowledgement.

STF/CLF 5 select even/odd generation and checking; SFS/SFC test this sense
before optional clear. STC/CLC enable/disable detection. Writes generate parity
even when detection is disabled. LI/MI read/merge the parity-address register;
output writes its address portion. Faults record the address and set bit 15 for
an instruction fetch. Console deposits create valid odd-parity words.

A detected error latches a Type 1 request, independent of Type 3 and SC 4
gates. At the instruction boundary CIR becomes 5, detection is disabled, and
the trap-cell instruction executes without using the M/E/F dispatcher. A bad
data read still supplies its data; a bad fetched instruction is inhibited.
Its following P value is available to the trap-cell instruction. CPU A/B
aliases, ROM reads and nonexistent RAM do not trigger RAM parity faults.

LPAREN, LPAREVEN and LPAR expose state; LPARIRQ reports a pending request.
LPFAULT and LPFETCH count real detected faults/fetch faults and do not control
diagnostic progress. Per-word bits and controller state are included in the
simulator register state. DMA parity, XL mapping, full interrupt priorities
and physical fault timing remain outside this implementation.

## Verified execution

```sh
python3 tests/hp1000/run_parity.py
python3 tests/hp1000/run_kernel_memory.py --parity --output build/hp1000/kernel-parity-verified
```

The independent suite passes **18/18**, covering sense/C modifiers, register
transfers, enable/disable, valid data, bad data, delayed detection, unmaskable
delivery, CIR/address reporting, return addresses and suppression of a fetched
store instruction. All prior **99 L checks**, seven legacy-model smoke checks,
both image-load checks, eleven unit tests and firmware-prefix checks pass.

Unchanged KERN Rev.2001 completes word-memory and parity-interrupt phases and
reaches **03777: TST01**. It injects **512 data faults and one fetch fault**,
verified by LPFAULT=513, LPFETCH=1 and final LPAR=103710. Error-handler
breakpoints remain active until completion. This is a subset pass, not full KERN.
The next 10,000-step CPU-test probe expires at 04367 and remains UNKNOWN.

Original ROM startup now advances past CLC 5 and stops at **00425: OTB 7,C**,
the unfinished SC 7 violation-register output. Its checked prefix is now 164
attempts (163 completed). This is not full power-on pretest or VCP success.

Artifacts are under `build/hp1000/parity/`, `build/hp1000/kernel-parity-verified/`
and `build/hp1000/firmware/`.
