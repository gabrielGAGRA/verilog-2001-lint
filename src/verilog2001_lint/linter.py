from pathlib import Path
import shutil
from typing import Dict, List, Optional, Set

from verilog2001_lint.integrations import (
    run_iverilog_check,
    run_verilator_check,
)
from verilog2001_lint.rules.file_structure import check_file_structure
from verilog2001_lint.rules.formatting import check_formatting_and_style
from verilog2001_lint.rules.fpga import check_cyclone_v_invariants
from verilog2001_lint.rules.naming import (
    check_naming_and_types,
    check_sv_keywords,
)
from verilog2001_lint.rules.procedural import (
    check_case_default,
    check_instantiations_and_generate,
    check_procedural_blocks,
)
from verilog2001_lint.rules.testbench import check_testbench_structure
from verilog2001_lint.violation import LintViolation, Severity
from verilog2001_lint.waivers import mask_comments_and_strings, parse_waivers


class VerilogLinter:
  """Linter for Verilog-2001 and FPGA RTL, aligned with Google Style Guide."""

  def __init__(
      self,
      run_iverilog: bool = True,
      run_verilator: bool = True,
      max_line_length: int = 100,
      disabled_rules: Optional[Set[str]] = None,
  ):
    self.run_iverilog = run_iverilog and (shutil.which("iverilog") is not None)
    self.run_verilator = run_verilator and (
        shutil.which("verilator") is not None
    )
    self.max_line_length = max_line_length
    self.disabled_rules = disabled_rules or set()

  def _add(
      self,
      violations: List[LintViolation],
      waivers: Dict[int, Set[str]],
      rule_id: str,
      path: Path,
      line: int,
      col: int,
      msg: str,
      snippet: str = "",
      severity: Severity = Severity.ERROR,
  ) -> None:
    if rule_id in self.disabled_rules:
      return
    if line in waivers and rule_id in waivers[line]:
      return
    violations.append(
        LintViolation(rule_id, severity, path, line, col, msg, snippet)
    )

  def lint_file(self, file_path: Path) -> List[LintViolation]:
    violations: List[LintViolation] = []

    if file_path.suffix in [".sv", ".svh"]:
      violations.append(
          LintViolation(
              "FILE_EXT_SYSTEMVERILOG",
              Severity.ERROR,
              file_path,
              1,
              1,
              f"SystemVerilog extension ({file_path.suffix}) prohibited. Use .v or .vh for Verilog-2001.",
          )
      )
      return violations

    if file_path.suffix not in [".v", ".vh"]:
      return violations

    try:
      raw_source = file_path.read_bytes().decode("utf-8", errors="replace")
    except Exception as e:
      violations.append(
          LintViolation(
              "FILE_READ_ERROR",
              Severity.ERROR,
              file_path,
              0,
              0,
              f"Failed to read file: {e}",
          )
      )
      return violations

    waivers = parse_waivers(raw_source)
    lines = raw_source.splitlines()

    def add_v(
        rule_id: str,
        path: Path,
        line: int,
        col: int,
        msg: str,
        snippet: str = "",
        severity: Severity = Severity.ERROR,
    ) -> None:
      self._add(
          violations,
          waivers,
          rule_id,
          path,
          line,
          col,
          msg,
          snippet,
          severity,
      )

    if "\r\n" in raw_source:
      add_v(
          "LINE_ENDING_CRLF",
          file_path,
          1,
          1,
          "CRLF line endings (\\r\\n) found. Use POSIX LF (\\n).",
          severity=Severity.WARNING,
      )

    masked_source = mask_comments_and_strings(raw_source)
    masked_lines = masked_source.splitlines()
    is_tb = (
        file_path.stem.lower().startswith("tb_")
        or file_path.stem.lower().endswith("_tb")
        or file_path.stem.lower().endswith("_test")
    )

    # 1. File Structure
    check_file_structure(file_path, masked_lines, lines, waivers, add_v)

    # 2. Formatting & Style
    check_formatting_and_style(
        file_path,
        masked_lines,
        lines,
        waivers,
        add_v,
        max_line_length=self.max_line_length,
    )

    # 3. SystemVerilog Keyword Bans
    check_sv_keywords(file_path, masked_lines, lines, waivers, add_v)

    # 4. Naming & Port Conventions
    check_naming_and_types(
        file_path, masked_lines, lines, waivers, add_v, is_tb=is_tb
    )

    # 5. Procedural Logic & Generate
    check_procedural_blocks(
        file_path, masked_lines, lines, waivers, add_v, is_tb=is_tb
    )
    check_instantiations_and_generate(
        file_path, masked_lines, lines, waivers, add_v, is_tb=is_tb
    )

    # 6. Cyclone V / FPGA Invariants
    check_cyclone_v_invariants(file_path, masked_lines, lines, waivers, add_v)
    check_case_default(file_path, masked_lines, lines, waivers, add_v)

    # 7. Testbench Rules
    if is_tb:
      check_testbench_structure(file_path, masked_lines, lines, waivers, add_v)

    # 8. External Integrations (iverilog & verilator)
    if file_path.suffix == ".v":
      if self.run_iverilog:
        run_iverilog_check(file_path, waivers, add_v)
      if self.run_verilator and not is_tb:
        run_verilator_check(file_path, waivers, add_v)

    return violations
