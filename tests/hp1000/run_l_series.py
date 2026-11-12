"""Exercise the experimental L-Series subset inside the existing hp2100 binary.

Expected results come from 02103-90007, October 1980, sections 3-7/3-15,
not from running another CPU model. No original diagnostic pass is claimed.
"""
import argparse
import json
from pathlib import Path

from run_baseline import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulator", type=Path, default=Path("BIN/hp2100"))
    parser.add_argument("--output", type=Path, default=Path("build/hp1000"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    commands = ["set on", "on error exit 1", "set cpu 1000-L", "set cpu 32K"]
    tests = []

    def case(name, instruction, deposits, expected, address=0o100):
        tests.append(name)
        commands.extend(["reset", "deposit A 0", "deposit B 0",
                         "deposit E 0", "deposit O 0"])
        commands.extend(f"deposit {a} {v}" for a, v in deposits.items())
        commands.extend([f"deposit {address:o} {instruction}",
                         f"deposit P {address:o}", "on error ignore", "step",
                         "on error exit 1"])
        commands.extend(f"assert {a}={v}" for a, v in expected.items())
        commands.append(f"echo L_CASE_PASS_{name}")

    case("LDA", "LDA 200", {"200": "12345"}, {"A": "12345", "P": "101"})
    case("LDB", "LDB 200", {"200": "12345"}, {"B": "12345", "P": "101"})
    case("STA", "STA 200", {"A": "76543"}, {"200": "76543", "A": "76543"})
    case("STB", "STB 200", {"B": "76543"}, {"200": "76543", "B": "76543"})
    for name, value in [("AND", 0o12345 & 0o777), ("IOR", 0o12345 | 0o777),
                        ("XOR", 0o12345 ^ 0o777)]:
        case(name, f"{name} 200", {"A": "12345", "200": "777"},
             {"A": f"{value:o}", "200": "777"})
    case("ADA_carry", "ADA 200", {"A": "177777", "200": "1"},
         {"A": "0", "E": "1", "O": "0"})
    case("ADB_overflow", "ADB 200", {"B": "77777", "200": "1"},
         {"B": "100000", "E": "0", "O": "1"})
    case("ADA_sticky", "ADA 200", {"A": "1", "200": "1", "E": "1", "O": "1"},
         {"A": "2", "E": "1", "O": "1"})
    for name, reg in [("CPA", "A"), ("CPB", "B")]:
        for equal in [True, False]:
            case(f"{name}_{'equal' if equal else 'unequal'}", f"{name} 200",
                 {reg: "10", "200": "10" if equal else "11"},
                 {"P": "101" if equal else "102", reg: "10"})
    case("ISZ_wrap", "ISZ 200", {"200": "177777", "E": "1", "O": "1"},
         {"200": "0", "P": "102", "E": "1", "O": "1"})
    case("ISZ_nonzero", "ISZ 200", {"200": "10"}, {"200": "11", "P": "101"})
    case("JMP", "JMP 200", {}, {"P": "200"})
    case("JSB", "JSB 200", {}, {"P": "201", "200": "101"})
    case("JMP_indirect", "JMP 200,I", {"200": "300"}, {"P": "300"})
    case("JSB_indirect", "JSB 200,I", {"200": "300"}, {"P": "301", "300": "101"})
    # ERD figure 2-8 (2/34A-B): link is P+2, with E/O preserved.
    for op, reg, other in [("JLA 2345", "A", "B"), ("JLB 2345", "B", "A")]:
        for flags in [0, 1]:
            case(f"JL_{reg}_{flags}", op,
                 {"101": "2345", reg: "125252", other: "77777",
                  "E": str(flags), "O": str(flags)},
                 {reg: "102", other: "77777", "P": "2345",
                  "E": str(flags), "O": str(flags), "101": "2345"})
        case(f"JL_{reg}_indirect", "100600" if reg == "A" else "104600",
             {"101": "100200", "200": "100201", "201": "2345", other: "76543"},
             {reg: "102", other: "76543", "P": "2345"})
        case(f"JL_{reg}_wrap", "100600" if reg == "A" else "104600", {"77777": "2345"},
             {reg: "0", "P": "2345"}, address=0o77776)
    case("register_read", "LDA 1", {"B": "12345"}, {"A": "12345", "B": "12345"})
    case("register_write", "STA 1", {"A": "54321"}, {"B": "54321"})
    case("register_ISZ", "ISZ 0", {"A": "177777"},
         {"A": "0", "P": "102", "E": "0", "O": "0"})
    case("indirect_chain", "LDA 200,I",
         {"200": "100201", "201": "202", "202": "65432"}, {"A": "65432"})
    case("current_page", "LDA 2200", {"2200": "1357", "200": "2460"},
         {"A": "1357", "P": "2101"}, address=0o2100)
    case("page_boundary", "062010", {"10": "123", "2010": "456"},
         {"A": "123", "P": "2000"}, address=0o1777)
    case("PC_wrap", "NOP", {}, {"P": "0"}, address=0o77777)
    # High memory stays usable after HLT; there is no 21xx loader shadow window.
    case("HLT", "HLT 77", {"77770": "54321"},
         {"P": "101", "T": "102077", "77770": "54321"})
    case("ASG", "CLA,CCE,RSS", {"A": "123"}, {"A": "0", "E": "1", "P": "102"})
    case("SRG", "ALF,ALF", {"A": "123456"}, {"A": "27247"})
    case("MPY", "MPY 200", {"A": "3", "200": "4"}, {"A": "14", "B": "0", "P": "102"})
    case("DIV", "DIV 200", {"A": "17", "200": "3"}, {"A": "5", "B": "0", "O": "0", "P": "102"})
    case("DLD", "DLD 200", {"200": "12345", "201": "67777"},
         {"A": "12345", "B": "67777", "P": "102"})
    case("DST", "DST 200", {"A": "7654", "B": "1234"},
         {"200": "7654", "201": "1234", "P": "102"})
    case("ASL_16", "ASL 16", {"A": "1", "B": "0", "E": "1"},
         {"A": "0", "B": "1", "E": "1", "O": "0"})
    case("RRR_16", "RRR 16", {"A": "1", "B": "2"}, {"A": "2", "B": "1"})
    case("overflow_skip_clear", "SOS C", {"O": "1"}, {"O": "0", "P": "102"})
    # L SC 4: table 4-3, 02103-90007. Power sense is the reverse of M/E/F.
    for suffix in ["", ",C"]:
        for failing in [0, 1]:
            for op in ["SFS", "SFC"]:
                skip = failing == (op == "SFC")
                case(f"SC4_{op}_{failing}_{suffix or 'hold'}", f"{op} 4{suffix}",
                     {"LPFAIL": str(failing), "CIR": "65", "LINT23": "1"},
                     {"P": "102" if skip else "101", "CIR": "65", "LINT23": "1"})
        for op, register in [("LIA", "A"), ("LIB", "B")]:
            case(f"SC4_{op}_{suffix or 'hold'}", f"{op} 4{suffix}",
                 {"CIR": "65", register: "177777"}, {register: "65", "CIR": "65"})
        for op, register in [("MIA", "A"), ("MIB", "B")]:
            case(f"SC4_{op}_{suffix or 'hold'}", f"{op} 4{suffix}",
                 {"CIR": "65", register: "100002"}, {register: "100067", "CIR": "65"})
        for op, register in [("OTA", "A"), ("OTB", "B")]:
            case(f"SC4_{op}_{suffix or 'hold'}", f"{op} 4{suffix}",
                 {"CIR": "0", register: "125252"}, {register: "125252", "CIR": "52"})
        for op, enabled in [("CLC", 0), ("STC", 1)]:
            case(f"SC4_{op}_{suffix or 'hold'}", f"{op} 4{suffix}",
                 {"LINT23": str(1 - enabled), "CIR": "27", "LPFAIL": "1"},
                 {"LINT23": str(enabled), "CIR": "27", "LPFAIL": "1"})
    for op in ["STF 4", "CLF 4"]:
        case(f"SC4_nop_{op.replace(' ', '_')}", op,
             {"CIR": "27", "LINT23": "0", "LPFAIL": "1"},
             {"P": "101", "CIR": "27", "LINT23": "0", "LPFAIL": "1"})
    # SC 0 control reset is distinct from CPU reset and from the SC 4 gate.
    for op in ["CLC", "STC"]:
        for suffix in ["", ",C"]:
            for enabled in [0, 1]:
                case(f"SC0_{op}_{enabled}_{suffix or 'hold'}", f"{op} 0{suffix}",
                     {"INTSYS": str(enabled), "LINT23": "0", "CIR": "27", "LPFAIL": "1",
                      "A": "123456", "B": "65432", "E": "1", "O": "1",
                      "400": "76543", "LSTATUS": "65"},
                     {"P": "101", "INTSYS": "0" if suffix else str(enabled),
                      "LINT23": "0", "CIR": "27", "LPFAIL": "1", "A": "123456",
                      "B": "65432", "E": "1", "O": "1", "400": "76543", "LSTATUS": "65"})
    for op in ["SFS", "SFC"]:
        for suffix in ["", ",C"]:
            for enabled in [0, 1]:
                skip = enabled == (op == "SFS")
                case(f"SC0_{op}_{enabled}_{suffix or 'hold'}", f"{op} 0{suffix}",
                     {"INTSYS": str(enabled), "LINT23": "0"},
                     {"P": "102" if skip else "101", "LINT23": "0",
                      "INTSYS": "0" if suffix else str(enabled)})
    for op, enabled in [("STF", 1), ("CLF", 0)]:
        case(f"SC0_{op}", f"{op} 0", {"INTSYS": str(1 - enabled), "LINT23": "0"},
             {"P": "101", "INTSYS": str(enabled), "LINT23": "0"})
    commands.append("set -f cpu 16K")
    case("NXM_read", "LDA 200,I", {"200": "40000"}, {"A": "177777"})
    case("NXM_write", "STA 200,I", {"200": "40000", "A": "123"}, {"A": "123"})
    case("NXM_write_ignored", "LDB 200,I", {"200": "40000"}, {"B": "177777"})
    commands.append("set cpu 32K")
    tests.append("NXM_no_hidden_write")
    commands.extend(["assert 40000=0", "echo L_CASE_PASS_NXM_no_hidden_write"])

    tests.append("breakpoint")
    commands.extend(["deposit 100 JMP 101", "break 101", "on error ignore",
                     "run 100", "on error exit 1", "assert P=101", "nobreak 101",
                     "echo L_CASE_PASS_breakpoint"])

    tests.append("indirect_loop")
    commands.extend(["deposit 100 LDA 200,I", "deposit 200 100200", "deposit A 123",
                     "on 4 goto indirect_loop", "run 100", "exit 1",
                     ":indirect_loop", "on 4 exit 1", "assert P=100", "assert A=123",
                     "echo L_CASE_PASS_indirect_loop"])

    # Refuse incomplete instruction groups, including RUN -B and disabled stops.
    for index, (name, opcode) in enumerate([
            ("IO", "102620"), ("HLT_clear", "103000"),
            ("status_clear", "103601"), ("VCP", "106703")]):
        tests.append(f"unsupported_{name}")
        commands.extend(["reset", "set cpu nostop", f"deposit 100 {opcode}",
                         "deposit A 2" if name == "diagnose" else "deposit A 123", "deposit B 456",
                         f"on 11 goto rejected_{index}", "run -b 100", "exit 1",
                         f":rejected_{index}", "on 11 exit 1", "assert P=100",
                         "assert A=2" if name == "diagnose" else "assert A=123", "assert B=456",
                         f"echo L_CASE_PASS_unsupported_{name}"])

    for index, option in enumerate(["EAU", "DMS", "FP", "64K", "LOADERENABLE"]):
        tests.append(f"reject_{option}")
        commands.extend([f"on NOFNC goto option_{index}", f"set cpu {option}",
                         "exit 1", f":option_{index}", "on NOFNC exit 1",
                         f"echo L_CASE_PASS_reject_{option}"])

    tape = args.output / "empty-test-tape.bin"
    tape.write_bytes(b"\0" * 10)
    commands.append(f"attach -r PTR {json.dumps(str(tape.resolve()))}")
    for device in ["CPU", "PTR"]:
        tests.append(f"reject_boot_{device}")
        commands.extend(["deposit P 123", "deposit 77770 65432",
                         f"on NOFNC goto boot_{device}", f"boot {device}", "exit 1",
                         f":boot_{device}", "on NOFNC exit 1", "assert P=123",
                         "assert 77770=65432", f"echo L_CASE_PASS_reject_boot_{device}"])
    commands.append("detach PTR")

    # Existing model capabilities and memory semantics must survive L selection.
    tests.append("model_switch")
    commands.extend(["set cpu 1000-E", "set cpu NODMS", "set cpu DMS", "set cpu 64K",
                     "set -f cpu 16K", "reset", "deposit 100 LDA 200,I",
                     "deposit 200 40000", "on error ignore", "run 100 until 101",
                     "on error exit 1", "assert A=0", "set cpu 1000-L",
                     "set cpu 32K", "show cpu", "echo L_CASE_PASS_model_switch",
                     "echo HP1000_CHECK_PASS", "exit"])
    script = args.output / "l-series.ini"
    script.write_text("\n".join(commands) + "\n")
    log = script.with_suffix(".log")
    result = execute(args.simulator.resolve(), script, log, 30)
    output = log.read_text() if log.exists() else ""
    executed = [name for name in tests if f"L_CASE_PASS_{name}\n" in output]
    if result["status"] == "PASS" and executed != tests:
        result["status"] = "FAIL"
    result.update(model="1000-L", scope="independent subset checks",
                  planned=len(tests), executed=len(executed), cases=executed,
                  diagnostic_tests_executed=0)
    (args.output / "l-series-results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"{result['status']} 1000-L: {len(executed)}/{len(tests)} independent checks")
    return int(result["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
