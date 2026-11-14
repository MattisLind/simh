# HP 1000 L-Series: starting SimH and using RTE-XL

This setup runs RTE-XL Rev.2340 on the HP 1000 L-Series CPU in the existing
HP2100 simulator, with 256KW memory, a 12005A serial console and a 7920 HP-IB
disk. EDIT, MACRO, FORTRAN 4X and BASIC are installed on the combined image.

## Start and reach the prompt

Run these commands from the repository root in a macOS or Linux terminal:

```sh
make hp2100
mkdir -p build/hp1000/rte-xl-native-user
cp -n build/hp1000/rte-xl-archive/rte-xl-software-7920.disc build/hp1000/rte-xl-native-user/disc.disc
BIN/hp2100 HP2100/hp1000-xl.ini
```

The combined disk and `build/hp1000/rte-xl-7920/rom.bin` must already exist;
these commands use the system built in this workspace. `cp -n` creates your
working disk without overwriting an existing one. Later runs need only the
last command. Files saved on the working disk persist across restarts.

The standard SimH command file configures `1000-L`, runs the original ROM
pretest and boots the disk. It enables `ASI LOCALACK` for ENQ/ACK and
`ASI LOCALSTATUS` for EDIT's HP264x status query. No Python launcher or host
terminal responder is needed. Wait for:

```text
BOOT PROCESS COMPLETE
*RTE-L SYSTEM READY*
FMGR :
```

The original software prints “RTE-L SYSTEM READY” on this XL system too.
Commands below are entered at `FMGR :`, unless another prompt is shown.
Press Return and wait for the prompt after each command.

## Mount the software

After each boot:

```text
MC,3
MC,4
MC,5
MC,6
```

| Cartridge | Software | Directory command |
|---|---|---|
| 32001 | System, FMGR and LOADR; mounted automatically | `DL,::32001` |
| 32002 | MACRO and assembly examples | `DL,::32002` |
| 32003 | BASIC | `DL,::32003` |
| 32004 | EDIT and text files | `DL,::32004` |
| 32005 | FTN4X and Fortran examples | `DL,::32005` |

`MC` takes a logical unit number; `::32002` identifies a cartridge.
Filenames are limited to six characters, including any prefix such as `&`.
`DU,filename::32002,1` displays a text file on the console.

## EDIT: create and reopen a file

Start the editor:

```text
RU,EDIT::32004
```

At EDIT's `/` prompt, insert one line, then save and exit:

```text
IHELLO FROM EDIT
EC,NOTE::32004
```

Reopen it from FMGR:

```text
RU,EDIT::32004,NOTE::32004
```

At `/`, list the file, display insertion help, then exit without saving changes:

```text
1 $ L
H I
A/
```

This verifies ordinary command-based editing. Full-screen operation is not
required by these examples.

## MACRO: assemble, link and run

The installed `&MAC` example defines and invokes a macro to calculate 41+1.
Display its source if desired:

```text
DU,&MAC::32002,1
```

Delete the previous example outputs before rebuilding:

```text
PU,MCLIST::32002
PU,MCREL::32002
PU,MCMAC::32002
```

Then assemble, link using the supplied command file, and run:

```text
RU,MACRO::32002,&MAC::32002,MCLIST::32002,MCREL::32002
RU,LOADR,MCLINK::32002
RU,MCMAC::32002
```

Expected output: `ASSEMBLY TEST PASSED`.
`MCLIST` is the listing, `MCREL` the relocatable object and `MCMAC` the executable.

## Fortran: compile, link and run

`FSRC::32005` contains this working example:

```fortran
FTN4
      PROGRAM FTEST
      INTEGER I
      I=6*7
      WRITE(1,100) I
  100 FORMAT(1X,I5)
      END
```

Delete the previous example outputs, then compile, link and execute:

```text
PU,FLIST::32005
PU,FOBJ::32005
PU,FTEST::32005
RU,FTN4X::32005,FSRC::32005,FLIST::32005,FOBJ::32005
RU,LOADR,FLDCMD::32005
RU,FTEST::32005
```

The compiler should report no errors; the program prints `42`.
`FLIST` is the compiler listing, `FOBJ` the object and `FLDCMD` the supplied
loader command file. To edit the source, use:

```text
RU,EDIT::32004,FSRC::32005
```

For a tested disk-I/O example, display `FIOSRC::32005` or run
`RU,FRTEST::32005` to read the value saved by the OPEN/MAXREC test.
Fortran file-I/O source requires a `$FILES` directive; the example uses
`$FILES(0,1)` before its first Fortran statement.

## BASIC: run a small program

```text
RU,BASIC::32003
```

At BASIC's `>` prompt, enter these lines one at a time:

```basic
10 PRINT 6*7
20 END
RUN
```

The program prints `42`. Return to FMGR with:

```text
BYE
```

This example runs in memory; it does not save the BASIC source to disk.

## Pause, exit and keep your work

Press **Ctrl-E** for the `sim>` prompt. Enter `CONTINUE` to resume or `QUIT` to
exit. Disk files survive restarting. Back up the user disk while SimH is stopped
and use only one running simulator per writable disk image.

The startup file uses these standard SimH settings:

```text
SET ASI LOCALACK
SET ASI LOCALSTATUS
```

LOCALACK answers outgoing ENQ with ACK. LOCALSTATUS recognizes the HP264x
primary-status query (ESC, `^`, XON) and returns a 4KB terminal configuration
with block mode and auto-LF disabled. It implements this status exchange,
not a full-screen terminal. ASI1 supports both settings too.
`REMOTEACK` and `REMOTESTATUS` restore external terminal handling; these are
the driver defaults. Diagnostic loopback and test-hood wiring take precedence.

Pascal is deferred. IMAGE/L utilities load and create a database, but record
insertion is not yet working. The examples above use the verified tools.
