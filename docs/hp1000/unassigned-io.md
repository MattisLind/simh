# Provisional unassigned L-Series input

By the owner's explicit choice, an input from an unassigned L-Series select
code returns **177777 octal** until hardware evidence establishes the idle-bus
value. This is a simulator assumption, not a verified electrical property of
the L backplane. It must not be inferred from the similar nonexistent-memory
read value, which has separate documentation.

The existing L processor handler implements LI/MI A/B, with and without C, for
otherwise unhandled select codes 10–77. LI loads all ones; MI ORs with all ones,
also producing all ones. No card flag exists to clear. No L interface cards are
currently installed. A future card dispatcher must take precedence over this
fallback for populated select codes.

Documented processor operations at SC 0–7 still go through their individual
handlers; an unfinished operation there is not hidden by this assumption.
Output/control/flag operations on unassigned codes retain the explicit
unsupported-feature stop. L protection checks execute before the input handler,
and existing 21xx/M/E/F input behavior is unchanged.

## Diagnostic results

The unchanged KERN select-code sweep now completes. `run_kernel_io.py` checks
**14324/MPT03** as its new completion boundary instead of expecting an unsupported
input stop. Both 13777 and 03777 entries match, including A=177777 and the two
preceding protection violations. This runner deliberately stops before the
relocating fence test; its error breakpoints are not valid throughout that test
because KERN temporarily replaces code at their addresses with its test module.

A separate bounded continuation through the complete original memory/parity
initialization reaches a real diagnostic error at **15101**, source MPT09:
`JSB CPUER,I` after the comment "NO I/O INTERRUPT IN INDIRECT CHAIN". A breakpoint
at CPERR executable entry (13636), outside the relocating test range, captures
the call with CPERR=15102. The L three-level indirect-chain interrupt behavior
remains unfinished. This is not an idle-bus input failure or a full KERN pass.
The earlier stop at 17666 was a breakpoint collision with legitimate relocated
test code and must not be interpreted as a diagnostic error.

The direct-entry shortcut also leaves EOM at its image default (zero): later
relocating-memory tests require the EOM value established by startup. The longer
probe therefore runs the original memory phase rather than inventing a value
or patching the diagnostic. Direct 13777/03777 equivalence is established only
through the checked MPT03 boundary.

```sh
python3 tests/hp1000/run_io.py
python3 tests/hp1000/run_kernel_io.py
```

The independent I/O runner now passes 114 checks, including 40 unassigned-input
cases for select codes 10, 11, 17, 20 and 77, A/B, LI/MI and hold/clear forms.
They also check that the other accumulator and violation register are unchanged.
The fully initialized continuation script, stop log and classified result are
under `build/hp1000/unassigned/initialized-*`; its harness completion marker does
not indicate diagnostic success.

## Indirect-interrupt follow-up

The MPT09 failure described above is now resolved. The initialized
`run_kernel_indirect.py` runner verifies MPT09 return addresses and next stops
at 15212/OTA 2 selecting diagnose mode 1. See `indirect-interrupts.md`.
