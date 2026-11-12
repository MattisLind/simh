# Diagnostic inventory

Local inventory on 10 November 2026: 53,486 `.src`, 1,148 `.abin`, four `.hpi`,
two HTML files, two other files without suffix, two manuals, and the handoff plan.
The complete searchable path/size/checksum index is reproducible with
`python3 tests/hp1000/inventory.py`. Source headers are indexed; CPU support and
buildability are not inferred from filenames or the source/binary directories.

| Family | Actual evidence | Current status |
|---|---|---|
| 24397-18002 / 16002 | Rev.2001 L kernel assembly and original absolute image; Rev.2040 header identifies L/XL | Rev.2001 word-memory and parity-interrupt phases PASS at 32KW; full KERN unfinished |
| 24397-18003 / 16003 | L DDL assembly Rev.2010; L/XL DDL Rev.2040; binary images present | Runtime/build/load requirements UNKNOWN |
| 24397-18004 | Header identifies 12002A/B XL memory diagnostic | Source present; not baseline L coverage |
| 24397-18005 / 06 / 08 / 09 | Numbered DDL for 12005A serial, 12006A parallel, 12008A PROM, 12009A HP-IB | Source and corresponding 160xx files present; execution NOT_IMPLEMENTED |
| 24612-18018 | ASMB Master I/O, IOM; declares relocatable 24612-16018 | Source present; matching binary absent; compatibility unverified |
| 24612-18036 | Numbered DDL; header identifies 12009A HP-IB | Source present; filename Rev.2213 says service Rev.2301 internally, so revision requires care |
| 24612-18042 | BCM assembly, later revisions use MACRO; declares object 16042 | Source and some binaries present; complete linked runtime unverified |
| 24612-18010 | Assembly implementation of DDL, not a host DDL compiler; declares DCS dependency and external symbols | Source present; tool/runtime requirements unresolved |
| 24398 / 24613 | Files indexed in the full CSV | Detailed interface/revision/dependency audit pending |

1,147 of 1,148 `.abin` files validate under the absolute-record decoder.
`24999-16133_Rev-1730.abin` contains six NUL bytes and no load records; it is
UNKNOWN, not a runnable program. A valid absolute container does not prove that
its contents are a linked executable or that it runs on L hardware.

The kernel Rev.2001 describes itself as standalone and lists CPU, memory, I/O,
interrupt, TBG, protection, and DMA coverage. Its source states entry address 4.
It also references ROM/VCP error reporting. The complete word-memory phase has
now executed and passed, as has the parity-interrupt phase; later sections remain unfinished.
HPI images, including `24397A.hpi` and the supplied RTE-XL images, are hashed
but their internal filesystems and bootability have not been decoded or verified.
