from pathlib import Path
import re
from typing import Callable, Dict, List, Optional, Set, Tuple

from verilog2001_lint.violation import Severity

RE_ALWAYS = re.compile(r"\balways\s*@\s*(\([^)]*\)|\*)")
RE_ASSIGN = re.compile(r"^\s*assign\b")
RE_DELAY = re.compile(r"#[0-9]+")
RE_REDUNDANT_CLK = re.compile(r"\belse\s+if\s*\(\s*(?:clk|clock)\s*\)")
RE_BLOCKING = re.compile(r"(?<![=!<>])=(?![=])")

RESERVED_KEYWORDS = {
    "module", "endmodule", "input", "output", "inout", "wire", "reg",
    "integer", "genvar", "real", "time", "parameter", "localparam",
    "assign", "generate", "endgenerate", "defparam", "begin", "end",
    "if", "else", "case", "casex", "casez", "initial", "always",
    "task", "endtask", "function", "endfunction", "repeat", "while",
    "for", "forever", "fork", "join", "disable", "posedge", "negedge",
}

PRIMITIVE_GATES = {
    "and", "nand", "or", "nor", "xor", "xnor",
    "buf", "not", "bufif0", "bufif1", "notif0", "notif1",
}


def check_procedural_blocks(
    file_path: Path,
    masked_lines: List[str],
    raw_lines: List[str],
    waivers: Dict[int, Set[str]],
    add_violation: Callable[..., None],
    is_tb: bool,
) -> None:
  """Enforces rules inside always/initial blocks and assignments."""
  current_block: Optional[str] = None
  block_depth = 0
  in_always = False
  in_always_header = False
  always_header_buf = ""
  always_header_line = 1

  signed_signals: Set[str] = set()
  for l in masked_lines:
    m_sig = re.findall(r"\bsigned\b\s+(?:\[[^\]]+\]\s+)?([A-Za-z0-9_]+)", l)
    signed_signals.update(m_sig)

  for idx, line in enumerate(masked_lines):
    line_num = idx + 1
    is_assign = bool(RE_ASSIGN.search(line))

    # casex prohibited
    if re.search(r"\bcasex\b", line):
      add_violation(
          "CASEX_PROHIBITED",
          file_path,
          line_num,
          line.find("casex") + 1,
          "'casex' is strictly prohibited. Use 'case' or 'casez'.",
          raw_lines[idx],
      )

    # casez using 'z' or 'Z' in literal
    if re.search(r"\b\d+'[bB][01_]*[zZ][01_zZ]*\b", line):
      add_violation(
          "CASEZ_Z_LITERAL",
          file_path,
          line_num,
          1,
          "Wildcard literal uses 'z'/'Z'. Use '?' instead (e.g. 4'b??01).",
          raw_lines[idx],
      )

    # Task in RTL prohibited
    if not is_tb and re.match(r"^\s*task\b", line):
      add_violation(
          "TASK_IN_RTL_PROHIBITED",
          file_path,
          line_num,
          1,
          "Tasks are prohibited in synthesizable RTL. Use submodules instead.",
          raw_lines[idx],
      )

    # Function automatic in RTL
    if not is_tb and re.match(r"^\s*function\b", line):
      if not re.search(r"\bfunction\s+automatic\b", line):
        add_violation(
            "FUNCTION_NOT_AUTOMATIC",
            file_path,
            line_num,
            1,
            "Functions in synthesizable RTL must be declared 'function automatic'.",
            raw_lines[idx],
        )

    # Delay prohibited in RTL
    if not is_tb:
      delay_match = RE_DELAY.search(line)
      if delay_match:
        add_violation(
            "DELAY_PROHIBITED",
            file_path,
            line_num,
            delay_match.start() + 1,
            "#delay statements are prohibited in synthesizable RTL.",
            raw_lines[idx],
        )

    # Testbench plusarg test check
    if is_tb and "$test$plusargs" in line:
      add_violation(
          "TESTBENCH_PLUSARG_TEST",
          file_path,
          line_num,
          line.find("$test$plusargs") + 1,
          "$test$plusargs is prohibited; use $value$plusargs.",
          raw_lines[idx],
          severity=Severity.WARNING,
      )

    # Logical shift >> on signed signal
    if ">>" in line and ">>>" not in line:
      for s in signed_signals:
        if re.search(rf"\b{s}\s*>>", line):
          add_violation(
              "SIGNED_LOGICAL_RIGHT_SHIFT",
              file_path,
              line_num,
              line.find(">>") + 1,
              f"Logical right shift '>>' used on signed signal '{s}'. Use '>>>' to preserve sign.",
              raw_lines[idx],
          )

    # Parentheses around reduction operators preceded by another operator
    m_red = re.search(r"(?:~|!)\s*([&|^]|~[&|^])(?![&|=~^])\s*[a-zA-Z_]", line)
    if m_red:
      add_violation(
          "REDUCTION_OPERATOR_PARENS",
          file_path,
          line_num,
          m_red.start() + 1,
          "Parentheses are required to isolate reduction operations preceded by another operator (e.g. '~(&foo)').",
          raw_lines[idx],
          severity=Severity.WARNING,
      )

    # Nested ternary without parentheses
    m_tern = re.search(r"\?[^:?]+:\s*([^;()?]+)\?", line)
    if m_tern:
      add_violation(
          "NESTED_TERNARY_PARENS",
          file_path,
          line_num,
          1,
          "Nested ternary expressions must be enclosed in parentheses.",
          raw_lines[idx],
          severity=Severity.WARNING,
      )

    # Always header detection
    if not in_always_header:
      always_match = RE_ALWAYS.search(line)
      if always_match:
        sens = always_match.group(1).strip()
        in_always = True
        if "*" in sens:
          current_block = "combinational"
        elif "posedge" in sens or "negedge" in sens:
          current_block = "sequential"
        else:
          current_block = "combinational"
          add_violation(
              "MANUAL_SENSITIVITY_LIST",
              file_path,
              line_num,
              always_match.start() + 1,
              "Manual sensitivity list in combinational block. Use 'always @*'.",
              raw_lines[idx],
          )
      elif re.search(r"\balways\s*@", line):
        in_always_header = True
        always_header_buf = line
        always_header_line = line_num
    else:
      always_header_buf += " " + line
      if ")" in line:
        in_always_header = False
        in_always = True
        m_sens = re.search(r"\balways\s*@\s*(\([^)]*\)|\*)", always_header_buf)
        if m_sens:
          sens = m_sens.group(1).strip()
          if "*" in sens:
            current_block = "combinational"
          elif "posedge" in sens or "negedge" in sens:
            current_block = "sequential"
          else:
            current_block = "combinational"
            add_violation(
                "MANUAL_SENSITIVITY_LIST",
                file_path,
                always_header_line,
                1,
                "Manual sensitivity list in combinational block. Use 'always @*'.",
                raw_lines[always_header_line - 1],
            )

    begins = len(re.findall(r"\bbegin\b", line))
    ends = len(re.findall(r"\bend\b", line))
    if in_always:
      block_depth += begins - ends

    if current_block == "sequential" and not is_assign:
      red_clk = RE_REDUNDANT_CLK.search(line)
      if red_clk:
        add_violation(
            "ANTI_PATTERN_REDUNDANT_CLOCK_CHECK",
            file_path,
            line_num,
            red_clk.start() + 1,
            "Redundant 'else if (clk)' check inside edge-triggered always block.",
            raw_lines[idx],
        )

      if not re.search(r"\bfor\s*\(", line):
        blk = RE_BLOCKING.search(line)
        if blk and not re.search(r"\b(?:if|while)\s*\(.*=", line):
          if re.search(
              r"(?:^\s*|\b(?:begin|else)\s+)(?:[a-zA-Z_0-9]+(?:\s*\[[^\]]+\])?|\{[^}]+\})\s*=(?![=])",
              line,
          ):
            add_violation(
                "SEQUENTIAL_BLOCKING_ASSIGNMENT",
                file_path,
                line_num,
                blk.start() + 1,
                "Blocking assignment (=) inside sequential always block. Use non-blocking (<=).",
                raw_lines[idx],
            )

    elif current_block == "combinational" and not is_assign:
      if not re.search(r"\b(?:if|while)\s*\(.*<=", line):
        nonblk = re.search(
            r"(?:^\s*|\b(?:begin|else)\s+)(?:[a-zA-Z_0-9]+(?:\s*\[[^\]]+\])?|\{[^}]+\})\s*<=(?![=])",
            line,
        )
        if nonblk:
          add_violation(
              "COMBINATIONAL_NONBLOCKING_ASSIGNMENT",
              file_path,
              line_num,
              nonblk.start() + 1,
              "Non-blocking assignment (<=) inside combinational always block. Use blocking (=).",
              raw_lines[idx],
          )

    if in_always:
      if block_depth <= 0 and (
          ends > 0 or (block_depth == 0 and begins == 0 and ";" in line)
      ):
        in_always = False
        current_block = None
        block_depth = 0

    if "endmodule" in line:
      current_block = None
      in_always = False
      in_always_header = False
      block_depth = 0


def extract_instantiations(
    source_text: str, raw_lines: List[str]
) -> List[Tuple[str, Optional[str], str, str, int, str]]:
  """Extracts submodule instantiations safely outside procedural blocks."""
  chars = list(source_text)
  n = len(chars)
  i = 0
  while i < n:
    m_task = re.match(r"\b(task|function)\b", source_text[i:])
    if m_task:
      kw = m_task.group(1)
      m_end = re.search(r"\bend" + kw + r"\b", source_text[i:])
      if m_end:
        end_pos = i + m_end.end()
        for j in range(i, end_pos):
          if chars[j] != "\n":
            chars[j] = " "
        i = end_pos
        continue
    m_proc = re.match(r"\b(always|initial)\b", source_text[i:])
    if m_proc:
      start_pos = i
      j = i + m_proc.end()
      while j < n and source_text[j] in " \t\r\n":
        j += 1
      if j < n and source_text[j] == "@":
        while j < n and source_text[j] != "(":
          j += 1
        depth = 1
        j += 1
        while j < n and depth > 0:
          if source_text[j] == "(":
            depth += 1
          elif source_text[j] == ")":
            depth -= 1
          j += 1
      while j < n and source_text[j] in " \t\r\n":
        j += 1
      if j < n and source_text[j : j + 5] == "begin":
        depth = 1
        j += 5
        while j < n and depth > 0:
          if re.match(r"\bbegin\b", source_text[j:]):
            depth += 1
            j += 5
          elif re.match(r"\bend\b", source_text[j:]):
            depth -= 1
            j += 3
          else:
            j += 1
      else:
        while j < n and source_text[j] != ";":
          j += 1
        if j < n:
          j += 1
      for k in range(start_pos, min(j, n)):
        if chars[k] != "\n":
          chars[k] = " "
      i = j
      continue
    i += 1
  src = "".join(chars)

  # Mask compiler directives
  src = re.sub(r"^\s*`[^\n]*", lambda m: " " * len(m.group(0)), src, flags=re.MULTILINE)
  # Mask module header
  src = re.sub(
      r"\bmodule\s+[a-zA-Z_0-9]+(?:\s*#\s*\([\s\S]*?\))?\s*\([\s\S]*?\)\s*;",
      lambda m: re.sub(r"[^\n]", " ", m.group(0)),
      src,
  )
  # Mask assigns and declarations
  src = re.sub(r"\bassign\s+[^;]+;", lambda m: re.sub(r"[^\n]", " ", m.group(0)), src)
  src = re.sub(
      r"\b(?:wire|reg|input|output|inout|integer|genvar|real|time)\b[^;]+;",
      lambda m: re.sub(r"[^\n]", " ", m.group(0)),
      src,
  )
  src = re.sub(
      r"\b(?:parameter|localparam)\b[^;]+;",
      lambda m: re.sub(r"[^\n]", " ", m.group(0)),
      src,
  )

  def extract_balanced_paren(text: str, start_idx: int) -> Tuple[Optional[str], int]:
    depth = 0
    for idx in range(start_idx, len(text)):
      if text[idx] == "(":
        depth += 1
      elif text[idx] == ")":
        depth -= 1
        if depth == 0:
          return text[start_idx + 1 : idx], idx + 1
    return None, len(text)

  instantiations = []
  pattern = re.compile(r"\b([a-zA-Z_0-9]+)\s*(#|\b[a-zA-Z_0-9]+\s*\()")
  pos = 0
  while pos < len(src):
    m = pattern.search(src, pos)
    if not m:
      break
    mod_type = m.group(1)
    if mod_type in RESERVED_KEYWORDS or mod_type.startswith("$"):
      pos = m.end()
      continue

    curr_idx = m.start() + len(mod_type)
    while curr_idx < len(src) and src[curr_idx] in " \t\r\n":
      curr_idx += 1

    param_overrides = None
    if curr_idx < len(src) and src[curr_idx] == "#":
      curr_idx += 1
      while curr_idx < len(src) and src[curr_idx] in " \t\r\n":
        curr_idx += 1
      if curr_idx < len(src) and src[curr_idx] == "(":
        param_overrides, curr_idx = extract_balanced_paren(src, curr_idx)

    m_inst = re.match(r"\s*([a-zA-Z_0-9]+)\s*\(", src[curr_idx:])
    if not m_inst:
      pos = m.end()
      continue

    inst_name = m_inst.group(1)
    if inst_name in RESERVED_KEYWORDS or inst_name.startswith("$"):
      pos = m.end()
      continue

    paren_start = curr_idx + m_inst.end() - 1
    port_list, end_idx = extract_balanced_paren(src, paren_start)
    if port_list is None:
      port_list = ""

    line_num = source_text[: m.start()].count("\n") + 1
    snippet = raw_lines[line_num - 1] if line_num <= len(raw_lines) else ""
    instantiations.append((mod_type, param_overrides, inst_name, port_list, line_num, snippet))
    pos = end_idx

  return instantiations


def check_instantiations_and_generate(
    file_path: Path,
    masked_lines: List[str],
    raw_lines: List[str],
    waivers: Dict[int, Set[str]],
    add_violation: Callable[..., None],
    is_tb: bool,
) -> None:
  """Enforces explicit port/parameter binding and generate block labeling."""
  source_text = "\n".join(masked_lines)

  # Defparam prohibited
  for idx, line in enumerate(masked_lines):
    if re.search(r"\bdefparam\b", line):
      add_violation(
          "DEFPARAM_PROHIBITED",
          file_path,
          idx + 1,
          line.find("defparam") + 1,
          "'defparam' is prohibited. Use ANSI parameter port overrides #(.Param(val)).",
          raw_lines[idx],
      )

  # Generate block labels (must start with gen_)
  for idx, line in enumerate(masked_lines):
    line_num = idx + 1
    m_gen_begin = re.search(r"\bbegin\s*(?::\s*([a-zA-Z0-9_]+))?", line)
    if "generate" in source_text:
      if re.search(r"\b(?:for|if|else)\b.*?\bbegin\b", line) or (
          m_gen_begin and idx > 0 and re.search(r"\b(?:for|if|else)\b", masked_lines[idx - 1])
      ):
        m_label = re.search(r"\bbegin\s*:\s*([a-zA-Z0-9_]+)", line)
        if not m_label and idx < len(masked_lines) - 1:
          m_label = re.search(r"^\s*:\s*([a-zA-Z0-9_]+)", masked_lines[idx + 1])
        if m_label:
          lbl = m_label.group(1)
          if not lbl.startswith("gen_"):
            add_violation(
                "GENERATE_BLOCK_LABEL",
                file_path,
                line_num,
                1,
                f"Generate block label '{lbl}' must start with 'gen_' (e.g. 'gen_{lbl}').",
                raw_lines[idx],
            )

  # Submodule instantiations
  instantiations = extract_instantiations(source_text, raw_lines)
  for mod_type, param_overrides, inst_name, port_list, line_num, snippet in instantiations:
    if mod_type in RESERVED_KEYWORDS or inst_name in RESERVED_KEYWORDS:
      continue

    # Recursive instantiation check
    if mod_type == file_path.stem and not is_tb:
      add_violation(
          "RECURSIVE_INSTANTIATION",
          file_path,
          line_num,
          1,
          f"Module '{mod_type}' instantiates itself recursively.",
          snippet,
      )

    # Instance naming convention
    valid_name = inst_name.startswith(mod_type)
    if is_tb:
      valid_name = valid_name or inst_name in (
          "dut", "uut", f"{mod_type}_dut", f"{mod_type}_uut"
      )

    if not valid_name and mod_type not in PRIMITIVE_GATES:
      add_violation(
          "INSTANCE_NAME_CONVENTION",
          file_path,
          line_num,
          1,
          f"Instance name '{inst_name}' must start with module name '{mod_type}' (e.g. '{mod_type}_0' or '{mod_type}_dut').",
          snippet,
      )

    # Positional parameter overrides
    if param_overrides and not re.search(r"\.\s*[a-zA-Z0-9_]+\s*\(", param_overrides):
      add_violation(
          "POSITIONAL_PARAM_INSTANTIATION",
          file_path,
          line_num,
          1,
          f"Positional parameter override '#({param_overrides})' in '{inst_name}'. Named parameter binding (#(.Param(val))) is required.",
          snippet,
      )

    # Positional port binding
    if (
        mod_type not in PRIMITIVE_GATES
        and port_list
        and not re.search(r"\.\s*[a-zA-Z_0-9]+\s*\(", port_list)
    ):
      add_violation(
          "POSITIONAL_INSTANTIATION",
          file_path,
          line_num,
          1,
          f"Positional port instantiation in '{inst_name}'. Named port binding (.port(sig)) is required.",
          snippet,
      )

    # Floating input ports: .in_port()
    for m_conn in re.finditer(r"\.\s*([a-zA-Z0-9_]+)\s*\(\s*\)", port_list):
      p_name = m_conn.group(1)
      if any(
          p_name.startswith(p)
          for p in ("in", "data_in", "clk", "rst", "enable", "req", "valid")
      ):
        add_violation(
            "FLOATING_INPUT_PORT",
            file_path,
            line_num,
            1,
            f"Input port '.{p_name}()' left floating in instance '{inst_name}'. Tie off explicitly.",
            snippet,
        )


def check_case_default(
    file_path: Path,
    masked_lines: List[str],
    raw_lines: List[str],
    waivers: Dict[int, Set[str]],
    add_violation: Callable[..., None],
) -> None:
  """Verifies that all case/casez statements declare a default branch."""
  stack: List[Tuple[int, bool]] = []
  for idx, line in enumerate(masked_lines):
    for m in re.finditer(r"\b(case|casez|endcase|default)\b", line):
      tok = m.group(1)
      if tok in ("case", "casez"):
        stack.append((idx, False))
      elif tok == "default" and stack:
        stack[-1] = (stack[-1][0], True)
      elif tok == "endcase" and stack:
        start_idx, has_default = stack.pop()
        if not has_default:
          add_violation(
              "CASE_MISSING_DEFAULT",
              file_path,
              start_idx + 1,
              1,
              "case statement has no 'default:' branch.",
              raw_lines[start_idx],
          )
