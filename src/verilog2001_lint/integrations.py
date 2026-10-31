from pathlib import Path
import re
import subprocess
from typing import Callable, Dict, List, Set

from verilog2001_lint.violation import LintViolation, Severity

FATAL_VERILATOR_RULES = {
    "LATCH",
    "WIDTH",
    "CASEINCOMPLETE",
    "COMBDLY",
    "UNDRIVEN",
    "MULTIDRIVEN",
    "ALWCOMBORDER",
}


def run_iverilog_check(
    file_path: Path,
    waivers: Dict[int, Set[str]],
    add_violation: Callable[..., None],
) -> None:
  """Runs Icarus Verilog elaboration pre-flight syntax and binding check."""
  file_dir = str(file_path.parent)
  cmd = [
      "iverilog",
      "-Wall",
      "-g2001",
      "-tnull",
      "-y",
      file_dir,
      "-I",
      file_dir,
      str(file_path),
  ]
  try:
    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    if res.returncode != 0 or res.stderr:
      for err_line in res.stderr.splitlines():
        err_line = err_line.strip()
        if not err_line:
          continue
        m = re.match(
            r"^([^:]+):(\d+):\s*(error|warning)?\s*(.*)$",
            err_line,
            re.IGNORECASE,
        )
        if m:
          _, line_str, err_type, msg = m.groups()
          is_note = msg.startswith("...") or (err_type or "").startswith("...")
          is_warn = (err_type or "").lower() == "warning" or is_note
          add_violation(
              (
                  "IVERILOG_COMPILER_WARNING"
                  if is_warn
                  else "IVERILOG_COMPILER_ERROR"
              ),
              file_path,
              int(line_str),
              1,
              f"[iverilog] {msg or err_line}",
              severity=Severity.WARNING if is_warn else Severity.ERROR,
          )
        else:
          is_note = (
              err_line.startswith("...") or "timescale" in err_line.lower()
          )
          add_violation(
              (
                  "IVERILOG_COMPILER_WARNING"
                  if is_note
                  else "IVERILOG_COMPILER_ERROR"
              ),
              file_path,
              0,
              0,
              f"[iverilog] {err_line}",
              severity=Severity.WARNING if is_note else Severity.ERROR,
          )
  except Exception as e:
    add_violation(
        "IVERILOG_EXEC_ERROR",
        file_path,
        0,
        0,
        f"Could not execute iverilog: {e}",
        severity=Severity.WARNING,
    )


def run_verilator_check(
    file_path: Path,
    waivers: Dict[int, Set[str]],
    add_violation: Callable[..., None],
) -> None:
  """Runs Verilator static RTL analysis pass."""
  file_dir = str(file_path.parent)
  cmd = [
      "verilator",
      "--lint-only",
      "-Wall",
      "+1364-2001ext+v",
      "-I" + file_dir,
      "-y",
      file_dir,
      "-Wno-PINCONNECTEMPTY",
      "-Wno-UNUSEDSIGNAL",
      "-Wno-EOFNEWLINE",
      "-Werror-LATCH",
      "-Werror-CASEINCOMPLETE",
      "-Werror-COMBDLY",
      str(file_path),
  ]
  try:
    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    if res.stderr:
      for line in res.stderr.splitlines():
        line = line.strip()
        if not line or line.startswith("%"):
          m = re.match(
              r"^%(Error|Warning)(?:-([A-Z0-9_]+))?:\s*([^:]+):(\d+):(?:\d+:)?\s*(.*)$",
              line,
          )
          if m:
            sev, rule, _, line_no, msg = m.groups()
            rule_name = rule or "LINT"
            is_err = sev == "Error" or rule_name in FATAL_VERILATOR_RULES
            add_violation(
                f"VERILATOR_{rule_name}",
                file_path,
                int(line_no),
                1,
                f"[verilator] {msg}",
                severity=Severity.ERROR if is_err else Severity.WARNING,
            )
  except Exception:
    pass
