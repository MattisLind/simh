# L-Series interrupts within indirect chains

The L resolver now recognizes a permitted TBG request within an indirect chain.
The facility is built into the L CPU and does not depend on the legacy MP device
or on LMPEN. This is the counterpart of the 2116 facility supplied by its
optional memory-protect board; the 2116 board-dependent behavior is preserved.

Evidence: 02103-90007 section 4-7 (printed 4-4, PDF 50) states that indirect
JMP/JSB instructions defer I/O service through the succeeding instruction, but
allow a pending I/O interrupt after three successive indirect levels. The
original KERN MPT09 source checks both the level threshold and saved P values.

## Behavior

- One/two-level indirect jumps keep Type 3 interrupts deferred.
- A pending, permitted request enables service at the third level. If that
  level supplies a direct destination, the jump completes and interrupt service
  sees the destination as the return address.
- If resolution must continue past that point, the resolver returns NOTE_INDINT
  before the next pointer read. The CPU backs P up to the original instruction,
  services the request, and can retry the instruction after the handler returns.
  A partially resolved JSB does not store its return address.
- Requests arriving later in a long chain are also recognized. Each pointer read
  advances the functional L timer by the documented 1.8 us, so a timer event can
  interrupt a looping chain even when no request was pending at its start.
- Type 3 master enable, SC 4 gating and mask bit 1 still apply. Masked or absent
  requests do not interrupt resolution. The configured simulator indirect limit
  remains effective; hardware-style indefinite CPU freezing is not simulated.

The existing L Type 1/Type 2 service paths and simulator timing limitations are
unchanged. TBG is currently the implemented Type 3 source; future L interface
cards must join its request selection. No legacy interface is acknowledged for
an L request, and the non-L pending-request and optional-board rules remain in
place.

## Verification

```sh
python3 tests/hp1000/run_indirect.py
python3 tests/hp1000/run_kernel_indirect.py
```

Nineteen directed checks cover one through five levels, return/restart P, JSB
write inhibition, three gating conditions, operation without L protection
enabled, requests arriving early and late within a looping chain, no-request
resolution/limit, and 2116 with its MP board present versus absent.

The original KERN runner loads and checks the unchanged absolute image, starts
at entry 2, verifies completion of original memory/parity initialization (EOM
77777, 513 parity faults including one instruction-fetch fault), and continues
through MPT09. The PRIPR completion checkpoint is matched against its original
opcode; temporary relocating test code at the same address is stepped over.
Error guards lie below the relocated range. EXITM and EXITN must hold the
source-derived expected return addresses, and CPERR must remain zero.

**MPT09 passes.** The next bounded probe stops at **15212: OTA 2**, A=1, selecting
unimplemented diagnose mode 1. Full KERN, interface/DMA diagnose modes and VCP
are not passed. Original source/image hashes and exact scripts/logs/results are
under `build/hp1000/kernel-indirect/`; directed results are under
`build/hp1000/indirect/`.

## Diagnose-mode follow-up

The previous OTA 2 stop is resolved by mode-1 support. The initialized runner
now verifies KERN's genuine no-I/O-chips error with the current empty L
backplane. See `diagnose-mode-1.md`; MPT09 remains PASS.
