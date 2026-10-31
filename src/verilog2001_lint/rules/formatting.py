from pathlib import Path
import re
from typing import Callable, Dict, List, Set

from verilog2001_lint.violation import Severity

SYNTHESIS_PRAGMAS = (
    "full_case",
    "parallel_case",
    "translate_off",
    "translate_on",
    "synthesis_off",
    "synthesis_on",
)


def check_formatting_and_style(
    file_path: Path,
    masked_lines: List[str],
    raw_lines: List[str],
    waivers: Dict[int, Set[str]],
    add_violation: Callable[..., None],
    max_line_length: int = 100,
) -> None:
  """Enforces formatting, indentation, whitespace, and prohibits synthesis pragmas."""
  for idx, raw_line in enumerate(raw_lines):
    line_num = idx + 1
    m_line = masked_lines[idx] if idx < len(masked_lines) else ""

    # Tab characters
    if "\t" in raw_line:
      add_violation(
          "TAB_CHARACTER",
          file_path,
          line_num,
          raw_line.find("\t") + 1,
          "Tab character found. Use spaces (2 spaces per indent level).",
          raw_line,
          severity=Severity.WARNING,
      )

    # Trailing whitespace
    if raw_line.rstrip("\r\n") != raw_line.rstrip():
      add_violation(
          "TRAILING_WHITESPACE",
          file_path,
          line_num,
          len(raw_line.rstrip()) + 1,
          "Trailing whitespace at end of line.",
          raw_line,
          severity=Severity.WARNING,
      )

    # Line length limit
    clean_line = raw_line.rstrip("\r\n")
    if len(clean_line) > max_line_length and not (
        "`include" in clean_line
        or "http://" in clean_line
        or "https://" in clean_line
    ):
      add_violation(
          "LINE_TOO_LONG",
          file_path,
          line_num,
          max_line_length + 1,
          f"Line exceeds {max_line_length} characters ({len(clean_line)} chars).",
          clean_line[: max_line_length + 5] + "...",
          severity=Severity.WARNING,
      )

    # Indentation step (multiples of 2 spaces)
    stripped = raw_line.lstrip()
    if (
        stripped
        and not stripped.startswith("//")
        and not stripped.startswith("/*")
        and not stripped.startswith("*")
    ):
      if not stripped.startswith("`"):
        indent = len(raw_line) - len(stripped)
        if indent % 2 != 0:
          add_violation(
              "INDENTATION_STEP",
              file_path,
              line_num,
              1,
              f"Indentation is {indent} spaces (must be a multiple of 2).",
              raw_line,
              severity=Severity.WARNING,
          )

    # Redundant semicolons
    if ";;" in m_line:
      add_violation(
          "REDUNDANT_SEMICOLON",
          file_path,
          line_num,
          m_line.find(";;") + 1,
          "Redundant semicolon (;;).",
          raw_line,
          severity=Severity.WARNING,
      )

    # Preprocessor column 0 alignment
    if re.match(r"^\s+`(?:ifdef|ifndef|else|elsif|endif)\b", m_line):
      add_violation(
          "PREPROCESSOR_INDENT",
          file_path,
          line_num,
          1,
          "Branching preprocessor directives (`ifdef, `else, `endif) must be left-aligned at column 0.",
          raw_line,
          severity=Severity.WARNING,
      )

    # Space after control keywords
    kw_spacing_match = re.search(r"\b(if|for|while|case)\(", m_line)
    if kw_spacing_match:
      add_violation(
          "SPACING_STYLE",
          file_path,
          line_num,
          kw_spacing_match.start() + 1,
          f"Missing space after keyword '{kw_spacing_match.group(1)}' before '('.",
          raw_line,
          severity=Severity.WARNING,
      )

    # Begin / End placement
    if re.match(r"^\s*begin\b", m_line) and idx > 0:
      prev_m = masked_lines[idx - 1].strip()
      if re.search(
          r"\b(if|else|for|while|case|casex|casez|always)\s*(\([^)]*\))?$",
          prev_m,
      ):
        add_violation(
            "BEGIN_END_STYLE",
            file_path,
            line_num,
            1,
            "'begin' should be placed on the same line as the preceding keyword.",
            raw_line,
            severity=Severity.WARNING,
        )

    # 'end else begin' on one line
    if (
        re.match(r"^\s*else\s+begin\b", m_line)
        and idx > 0
        and masked_lines[idx - 1].strip() == "end"
    ):
      add_violation(
          "BEGIN_END_STYLE",
          file_path,
          line_num,
          1,
          "Use 'end else begin' on a single line instead of 'end' followed by 'else begin'.",
          raw_line,
          severity=Severity.WARNING,
      )

    # Synthesis pragmas
    for pragma in SYNTHESIS_PRAGMAS:
      if pragma in raw_line.lower():
        add_violation(
            "SYNTHESIS_PRAGMA_PROHIBITED",
            file_path,
            line_num,
            1,
            f"Synthesis pragma '{pragma}' is prohibited (causes simulation-synthesis mismatches).",
            raw_line,
        )
