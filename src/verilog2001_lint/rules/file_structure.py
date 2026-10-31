from pathlib import Path
import re
from typing import Callable, Dict, List, Set, Tuple

from verilog2001_lint.violation import Severity

RE_MODULE = re.compile(r"\bmodule\s+([a-zA-Z_0-9]+)\b")


def check_file_structure(
    file_path: Path,
    masked_lines: List[str],
    raw_lines: List[str],
    waivers: Dict[int, Set[str]],
    add_violation: Callable[..., None],
) -> None:
  """Enforces file structure, header comments, and compiler directives."""
  first_non_empty = next((l for l in raw_lines if l.strip()), "")
  if not (first_non_empty.startswith("//") or first_non_empty.startswith("/*")):
    add_violation(
        "FILE_HEADER_COMMENT_MISSING",
        file_path,
        1,
        1,
        "Missing file header comment describing module and theory of operation.",
        first_non_empty,
        severity=Severity.WARNING,
    )

  has_nettype_none = False
  nettype_none_line = None
  has_nettype_wire = False
  nettype_wire_line = None
  module_lines: List[Tuple[int, str]] = []
  last_endmodule_line = None

  for idx, line in enumerate(masked_lines):
    line_num = idx + 1
    if "`default_nettype" in line:
      if "none" in line:
        has_nettype_none = True
        if nettype_none_line is None:
          nettype_none_line = line_num
      elif "wire" in line:
        has_nettype_wire = True
        nettype_wire_line = line_num

    match = RE_MODULE.search(line)
    if match:
      module_lines.append((line_num, match.group(1)))

    if "endmodule" in line:
      last_endmodule_line = line_num

  first_mod_line = module_lines[0][0] if module_lines else (len(raw_lines) + 1)

  if not has_nettype_none or (
      nettype_none_line and nettype_none_line > first_mod_line
  ):
    add_violation(
        "DIRECTIVE_DEFAULT_NETTYPE_NONE",
        file_path,
        nettype_none_line or 1,
        1,
        "Missing `default_nettype none at top of file (must precede module declarations).",
    )

  if file_path.suffix == ".v":
    if not has_nettype_wire or (
        last_endmodule_line
        and nettype_wire_line
        and nettype_wire_line < last_endmodule_line
    ):
      last_line = len(raw_lines) or 1
      add_violation(
          "DIRECTIVE_DEFAULT_NETTYPE_WIRE",
          file_path,
          nettype_wire_line or last_line,
          1,
          "Missing `default_nettype wire after endmodule.",
      )

    if len(module_lines) > 1:
      mod_names = ", ".join(f"'{m[1]}'" for m in module_lines)
      add_violation(
          "FILE_MULTIPLE_MODULES",
          file_path,
          module_lines[1][0],
          1,
          f"File contains multiple modules ({mod_names}). Exactly one module per file required.",
          raw_lines[module_lines[1][0] - 1],
      )
    elif len(module_lines) == 1:
      mod_line, mod_name = module_lines[0]
      if mod_name != file_path.stem:
        add_violation(
            "FILE_MODULE_NAME_MISMATCH",
            file_path,
            mod_line,
            1,
            f"Module name '{mod_name}' does not match filename stem '{file_path.stem}'.",
            raw_lines[mod_line - 1],
        )

  elif file_path.suffix == ".vh":
    has_ifndef = any(re.match(r"^\s*`ifndef\s+", l) for l in masked_lines)
    has_def = any(re.match(r"^\s*`define\s+", l) for l in masked_lines)
    if not (has_ifndef and has_def):
      add_violation(
          "HEADER_GUARD_MISSING",
          file_path,
          1,
          1,
          "Header file (.vh) must contain standard `ifndef / `define include guards.",
      )
