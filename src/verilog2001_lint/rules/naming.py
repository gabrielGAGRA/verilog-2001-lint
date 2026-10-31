from pathlib import Path
import re
from typing import Callable, Dict, List, Pattern, Set, Tuple

from verilog2001_lint.violation import Severity

RE_UPPER_CAMEL = re.compile(r"^[A-Z][a-zA-Z0-9]*$")
RE_K_CAMEL = re.compile(r"^k[A-Z][a-zA-Z0-9]*$")
RE_SIGNAL_UNDERSCORE_NUM = re.compile(r"\b([a-zA-Z][a-zA-Z0-9_]*?_([0-9]+))\b")
RE_BINARY_LITERAL = re.compile(r"\b(\d+)'[bB]([01_]+)\b")

SV_KEYWORDS: Tuple[Tuple[str, Pattern], ...] = (
    ("logic", re.compile(r"\blogic\b")),
    ("always_ff", re.compile(r"\balways_ff\b")),
    ("always_comb", re.compile(r"\balways_comb\b")),
    ("always_latch", re.compile(r"\balways_latch\b")),
    ("typedef", re.compile(r"\btypedef\b")),
    ("enum", re.compile(r"\benum\b")),
    ("package", re.compile(r"\bpackage\b")),
    ("interface", re.compile(r"\binterface\b")),
    ("struct", re.compile(r"\bstruct\b")),
    ("union", re.compile(r"\bunion\b")),
    ("unique case", re.compile(r"\bunique\s+case\b")),
    ("priority case", re.compile(r"\bpriority\s+case\b")),
    ("wildcard port (.*)", re.compile(r"\(\s*\.\*\s*\)")),
    ("'0 or '1", re.compile(r"(?<!\d)'[01]\b")),
)


def check_sv_keywords(
    file_path: Path,
    masked_lines: List[str],
    raw_lines: List[str],
    waivers: Dict[int, Set[str]],
    add_violation: Callable[..., None],
) -> None:
  """Detects and rejects SystemVerilog constructs in Verilog-2001 code."""
  for idx, line in enumerate(masked_lines):
    for name, pattern in SV_KEYWORDS:
      match = pattern.search(line)
      if match:
        add_violation(
            "SV_KEYWORD_BANNED",
            file_path,
            idx + 1,
            match.start() + 1,
            f"SystemVerilog construct '{name}' is not allowed in Verilog-2001 RTL.",
            raw_lines[idx],
        )


def check_naming_and_types(
    file_path: Path,
    masked_lines: List[str],
    raw_lines: List[str],
    waivers: Dict[int, Set[str]],
    add_violation: Callable[..., None],
    is_tb: bool,
) -> None:
  """Enforces naming conventions, port declarations, and literal sizing."""
  source_text = "\n".join(masked_lines)

  # Macro naming and local macro undef
  defined_local_macros: Dict[str, int] = {}
  undefed_macros: Set[str] = set()

  for idx, line in enumerate(masked_lines):
    line_num = idx + 1
    m_def = re.match(r"^\s*`define\s+([A-Za-z0-9_]+)", line)
    if m_def:
      m_name = m_def.group(1)
      if not m_name.isupper():
        add_violation(
            "MACRO_NAMING_AND_UNDEF",
            file_path,
            line_num,
            1,
            f"Macro name '{m_name}' must be ALL_CAPS.",
            raw_lines[idx],
        )
      if file_path.suffix == ".v" and not is_tb:
        if not m_name.startswith("_"):
          add_violation(
              "MACRO_NAMING_AND_UNDEF",
              file_path,
              line_num,
              1,
              f"File-local macro '{m_name}' in .v file must start with a single underscore (e.g. '_{m_name}').",
              raw_lines[idx],
          )
        defined_local_macros[m_name] = line_num

    m_undef = re.match(r"^\s*`undef\s+([A-Za-z0-9_]+)", line)
    if m_undef:
      undefed_macros.add(m_undef.group(1))

  for m_name, l_num in defined_local_macros.items():
    if m_name not in undefed_macros:
      add_violation(
          "MACRO_NAMING_AND_UNDEF",
          file_path,
          l_num,
          1,
          f"Local macro '{m_name}' must be explicitly `undef'd before end of file.",
          raw_lines[l_num - 1],
      )

  # Parameters & Localparams casing
  re_param_block = re.compile(
      r"\b(parameter|localparam)\s+(?:(?:signed\s+)?\[[^\]]+\]\s+)?([^;]+);",
      re.DOTALL,
  )
  for m_block in re_param_block.finditer(source_text):
    kw = m_block.group(1)
    block_body = m_block.group(2)
    block_start = m_block.start()
    is_fsm_block = (kw == "localparam") and (
        any(
            s in block_body.upper()
            for s in ("STATE", "IDLE", "WAIT", "READ", "WRITE", "DONE")
        )
        or any(
            RE_K_CAMEL.match(m.group(1))
            for m in re.finditer(r"\b([A-Za-z0-9_]+)\s*=", block_body)
        )
    )
    for m_assign in re.finditer(r"\b([A-Za-z0-9_]+)\s*=", block_body):
      p_name = m_assign.group(1)
      abs_pos = block_start + m_assign.start(1)
      line_num = source_text[:abs_pos].count("\n") + 1
      snippet = raw_lines[line_num - 1] if line_num <= len(raw_lines) else ""
      col_num = abs_pos - source_text.rfind("\n", 0, abs_pos)

      is_fsm_candidate = (
          is_fsm_block
          or RE_K_CAMEL.match(p_name)
          or any(
              s in p_name.upper()
              for s in ("STATE", "IDLE", "WAIT", "READ", "WRITE", "DONE")
          )
      )
      if is_fsm_candidate:
        if kw == "parameter":
          add_violation(
              "FSM_STATE_NAMING_STYLE",
              file_path,
              line_num,
              col_num,
              f"FSM state constant '{p_name}' declared with 'parameter'. Use 'localparam [WIDTH-1:0]'.",
              snippet,
          )
        if not RE_K_CAMEL.match(p_name):
          add_violation(
              "FSM_STATE_NAMING_STYLE",
              file_path,
              line_num,
              col_num,
              f"FSM state constant '{p_name}' must use kUpperCamelCase (e.g. 'k{p_name.capitalize()}').",
              snippet,
          )
      else:
        if not RE_UPPER_CAMEL.match(p_name):
          add_violation(
              "PARAM_NAMING_STYLE",
              file_path,
              line_num,
              col_num,
              f"Parameter/localparam '{p_name}' must use UpperCamelCase.",
              snippet,
          )

  # Signal names ending with underscore-number
  re_sig_decl = re.compile(
      r"\b(?:wire|reg|input|output|inout)(?:\s+(?:wire|reg))?\s+(?:signed\s+)?(?:\[[^\]]+\]\s+)?([A-Za-z0-9_,\s]+?)(?:;|,|\)|$)"
  )
  for idx, line in enumerate(masked_lines):
    line_num = idx + 1
    for m_decl in re_sig_decl.finditer(line):
      sig_list = m_decl.group(1).split(",")
      for sig in sig_list:
        sig_clean = sig.strip()
        m_num = RE_SIGNAL_UNDERSCORE_NUM.match(sig_clean)
        if m_num:
          if not re.search(r"_d\d+$", sig_clean):
            add_violation(
                "SIGNAL_UNDERSCORE_NUMBER",
                file_path,
                line_num,
                line.find(sig_clean) + 1,
                f"Signal '{sig_clean}' ends with '_<number>'. Use '_d<N>', '_ch<N>' or array indexing instead.",
                raw_lines[idx],
            )

  # Module port list checks
  re_port_list = re.compile(
      r"\bmodule\s+\w+\s*(?:#\([^)]*\)\s*)?\((.*?)\);", re.DOTALL
  )
  m_ports = re_port_list.search(source_text)
  if m_ports and not is_tb:
    ports_str = m_ports.group(1)
    ports_start_line = source_text[: m_ports.start(1)].count("\n") + 1
    port_entries = [p.strip() for p in ports_str.split(",") if p.strip()]

    for p_idx, p_entry in enumerate(port_entries):
      # Default port value in header
      if re.search(r"\binput\b.*=", p_entry):
        add_violation(
            "DEFAULT_PORT_VALUE_PROHIBITED",
            file_path,
            ports_start_line,
            1,
            f"Default input port value prohibited: '{p_entry}'.",
        )

      # Clock & reset naming
      m_clk_rst = re.search(
          r"\binput\s+(?:wire\s+)?([A-Za-z0-9_]+)", p_entry
      )
      if m_clk_rst:
        name = m_clk_rst.group(1)
        if name in ("clock", "clk_in"):
          add_violation(
              "CLOCK_RESET_NAMING",
              file_path,
              ports_start_line,
              1,
              f"Clock port '{name}' must be named 'clk' (or '<domain>_clk').",
          )
        if name in ("reset", "rst_in"):
          add_violation(
              "CLOCK_RESET_NAMING",
              file_path,
              ports_start_line,
              1,
              f"Reset port '{name}' must be named 'rst' (sync) or 'arst' (async).",
          )

      # Port ordering (clk must be first)
      if p_idx == 0 and "clk" not in p_entry.lower() and len(port_entries) > 1:
        if any("clk" in p.lower() for p in port_entries):
          add_violation(
              "PORT_ORDER_CLK_RST",
              file_path,
              ports_start_line,
              1,
              "Clock port ('clk') must be the first port in the module port list.",
              severity=Severity.WARNING,
          )

  # Binary literals full-digit sizing
  for idx, line in enumerate(masked_lines):
    line_num = idx + 1
    for m_bin in RE_BINARY_LITERAL.finditer(line):
      declared_w = int(m_bin.group(1))
      digits = m_bin.group(2).replace("_", "")
      if declared_w != len(digits):
        add_violation(
            "BINARY_LITERAL_WIDTH_MISMATCH",
            file_path,
            line_num,
            m_bin.start() + 1,
            f"Binary literal '{m_bin.group(0)}' width mismatch: declared {declared_w} bits, but specified {len(digits)} digits. Explicitly write all bits.",
            raw_lines[idx],
        )

  # Endianness: packed little-endian [MSB:LSB], unpacked big-endian [0:N-1]
  for idx, line in enumerate(masked_lines):
    line_num = idx + 1
    m_decl = re.search(
        r"\b(?:wire|reg|input|output)\s+(?:signed\s+)?\[\s*(\d+)\s*:\s*(\d+)\s*\]",
        line,
    )
    if m_decl:
      left, right = int(m_decl.group(1)), int(m_decl.group(2))
      if left < right:
        add_violation(
            "PACKED_UNPACKED_ENDIANNESS",
            file_path,
            line_num,
            m_decl.start() + 1,
            f"Packed vector range '[{left}:{right}]' must be little-endian '[{right}:{left}]'.",
            raw_lines[idx],
        )
    if "=" not in line:
      m_unp = re.search(
          r"\b(?:reg|wire)\s+(?:\[[^\]]+\]\s+)?[a-zA-Z_0-9]+\s*\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*;",
          line,
      )
      if m_unp:
        left, right = int(m_unp.group(1)), int(m_unp.group(2))
        if left > right:
          add_violation(
              "PACKED_UNPACKED_ENDIANNESS",
              file_path,
              line_num,
              m_unp.start() + 1,
              f"Unpacked array range '[{left}:{right}]' must be big-endian '[{right}:{left}]'.",
              raw_lines[idx],
          )
