from enum import Enum
from pathlib import Path


class Severity(Enum):
  ERROR = "ERROR"
  WARNING = "WARNING"
  INFO = "INFO"


class LintViolation:
  """Represents a single rule violation in a Verilog file."""

  def __init__(
      self,
      rule_id: str,
      severity: Severity,
      file_path: Path,
      line_num: int,
      col_num: int,
      message: str,
      snippet: str = "",
  ):
    self.rule_id = rule_id
    self.severity = severity
    self.file_path = file_path
    self.line_num = line_num
    self.col_num = col_num
    self.message = message
    self.snippet = snippet

  def __str__(self) -> str:
    color_map = {
        Severity.ERROR: "\033[91m",
        Severity.WARNING: "\033[93m",
        Severity.INFO: "\033[94m",
    }
    sev = f"{color_map.get(self.severity, '')}{self.severity.value}\033[0m"
    loc = (
        f"{self.file_path}:{self.line_num}:{self.col_num}"
        if self.line_num > 0
        else str(self.file_path)
    )
    out = (
        f"\033[1m{loc}:\033[0m [{sev}] \033[1m({self.rule_id})\033[0m:"
        f" {self.message}"
    )
    if self.snippet:
      out += f"\n    \033[90m{self.line_num} | \033[0m{self.snippet.strip()}"
    return out
