from pathlib import Path
import re
from typing import Callable, Dict, List, Set

from verilog2001_lint.violation import Severity


def check_testbench_structure(
    file_path: Path,
    masked_lines: List[str],
    raw_lines: List[str],
    waivers: Dict[int, Set[str]],
    add_violation: Callable[..., None],
) -> None:
  """Enforces testbench architecture, portless declaration, and termination rules."""
  source_text = "\n".join(masked_lines)

  # Testbench module must not declare ports
  re_tb_ports = re.compile(r"\bmodule\s+[a-zA-Z0-9_]+\s*\(([^)]+)\)\s*;")
  m_ports = re_tb_ports.search(source_text)
  if m_ports and m_ports.group(1).strip():
    line_num = source_text[: m_ports.start(1)].count("\n") + 1
    add_violation(
        "TESTBENCH_HAS_PORTS",
        file_path,
        line_num,
        1,
        "Testbench modules must not declare input/output ports (use 'module <name>;').",
        raw_lines[line_num - 1] if line_num <= len(raw_lines) else "",
    )

  # Testbench must contain $finish
  if not re.search(r"\$finish\b", source_text):
    add_violation(
        "TESTBENCH_MISSING_FINISH",
        file_path,
        1,
        1,
        "Testbench must contain $finish to ensure deterministic termination.",
    )

  # $stop prohibited in automated testbenches
  for idx, line in enumerate(masked_lines):
    if "$stop" in line:
      add_violation(
          "TESTBENCH_STOP_PROHIBITED",
          file_path,
          idx + 1,
          line.find("$stop") + 1,
          "$stop is prohibited in automated testbenches (causes batch runs to hang); use $finish.",
          raw_lines[idx],
          severity=Severity.WARNING,
      )
