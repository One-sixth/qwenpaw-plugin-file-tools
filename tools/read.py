"""文本读取类工具。

包含：
- file_tools_read_lines: 按行读取（纯文本格式）
- file_tools_read_block: 读取矩形块（CSV）
- file_tools_regex: 正则匹配（CSV）
"""

import bisect
import csv
import io
import json
import logging
import os
import re as re_module
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from ..utils import (
        format_error,
        make_error,
        make_success,
        parse_int,
        read_file_lines,
        resolve_path,
        truncate_line,
    )
except ImportError:
    from utils import (
        format_error,
        make_error,
        make_success,
        parse_int,
        read_file_lines,
        resolve_path,
        truncate_line,
    )

logger = logging.getLogger(__name__)


# ── 6. file_tools_read_lines ──────────────────────────────


def file_tools_read_lines(
    path: str,
    start_line: Union[int, str] = 1,
    line_count: Union[int, str] = 20,
    max_chars: Union[int, str] = 5000,
    encoding: str = "auto",
    show_line_number: bool = True,
) -> str:
    """按行读取文本文件，返回纯文本格式。支持指定起始行和读取行数，超过 max_chars 时自动截断并提示从哪行继续读取。空文件视为 0 行。show_line_number=True 时输出顶部有图例行 `行号 > 行内容`，每行格式为 `行号 > 内容`；False 时直接输出原文。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        start_line: 起始行号，1-based，默认 1。最小值为 1，超出文件总行数时报错。支持整数或十进制数字字符串。
        line_count: 读取行数。正数=读取指定行数，-1=读取到文件末尾，0=报错（无意义）。支持整数或十进制数字字符串。
        max_chars: 返回内容总字符上限，默认 5000。超过时截断并提示从截断位置继续读取。支持整数或十进制数字字符串。
        encoding: 文件编码。auto=自动检测（默认），也可指定 utf-8、gbk 等 Python 支持的编码名称。
        show_line_number: 行号显示模式。True=顶部带图例、每行带行号前缀（默认），False=直接输出原文。
    """
    resolved = resolve_path(path)

    start_line, err = parse_int(start_line, "start_line")
    if err:
        return make_error("按行读取", err)
    line_count, err = parse_int(line_count, "line_count")
    if err:
        return make_error("按行读取", err)
    max_chars, err = parse_int(max_chars, "max_chars")
    if err:
        return make_error("按行读取", err)

    if line_count == 0:
        return make_error("按行读取失败，因为 line_count=0 没有意义。请设置 line_count=-1 读取到末尾，或设为一个正整数。")
    if start_line < 1:
        return make_error(f"按行读取失败，因为起始行号 {start_line} 不合法。行号从 1 开始。")

    if not os.path.isfile(resolved):
        return make_error(f"按行读取失败，因为文件「{resolved}」不存在。")

    try:
        lines, resolved_encoding = read_file_lines(resolved, encoding)
    except Exception as e:
        return make_error(f"按行读取失败，因为读取文件时出错：{e}。")

    # 空文件（[""]）视为0行
    if len(lines) == 1 and lines[0] == "":
        lines = []

    total_lines = len(lines)
    if start_line > total_lines + 1:
        return make_error(format_error("按行读取", f"文件共 {total_lines} 行，起始行号 {start_line} 超出范围"))

    actual_start = start_line - 1
    if line_count == -1:
        actual_count = total_lines - actual_start
    else:
        actual_count = line_count

    actual_end = min(actual_start + actual_count, total_lines)
    selected_lines = lines[actual_start:actual_end]

    output_lines: List[str] = []
    char_count = 0
    truncated = False

    for i, line in enumerate(selected_lines):
        row_num = start_line + i
        content = line

        if len(content) > 4096:
            content = content[:4096] + "<<<TRUNCATED>>>"

        char_count += len(content)
        if char_count > max_chars:
            truncated = True
            content = content[:max_chars - (char_count - len(content))] + "<<<TRUNCATED>>>"
            if show_line_number:
                output_lines.append(f"{row_num} > {content}")
            else:
                output_lines.append(content)
            break

        if show_line_number:
            output_lines.append(f"{row_num} > {content}")
        else:
            output_lines.append(content)

    result = "\n".join(output_lines)

    if truncated:
        next_line = row_num
        result += f"\n\n<<<TRUNCATED>>>内容已超出 max_chars={max_chars} 限制。如需继续阅读，请从第 {next_line} 行开始读取（该行内容不完整，会重新返回完整内容）。\n"

    if show_line_number and output_lines:
        result = "行号 > 行内容\n\n" + result

    return make_success(result)


# ── 7. file_tools_read_block ──────────────────────────────


def file_tools_read_block(
    path: str,
    start_row: Union[int, str],
    end_row: Union[int, str],
    start_col: Union[int, str] = 1,
    end_col: Union[int, str] = 2048,
    max_chars: Union[int, str] = 5000,
    encoding: str = "auto",
    show_line_number: bool = True,
) -> str:
    """从文本文件中读取一个矩形区域，返回纯文本格式。像一个可以上下左右移动的「观察窗口」——指定起止行列范围，只返回该矩形内的文本切片。超过 max_chars 时自动截断。空文件、行列参数反转等边界情况均有对应提示。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        start_row: 起始行号，1-based，包含。必须 >= 1。超出文件总行数时报错。支持整数或十进制数字字符串。
        end_row: 结束行号，1-based，包含。必须 >= start_row，超出文件总行数时取到文件末尾。支持整数或十进制数字字符串。
        start_col: 行内起始列号，1-based，包含。默认 1。必须 <= end_col。超过该行长度时取空字符串。支持整数或十进制数字字符串。
        end_col: 行内结束列号，1-based，包含。默认 2048。必须 >= start_col。支持整数或十进制数字字符串。
        max_chars: 返回内容总字符上限，默认 5000。超过时截断并提示从截断位置继续读取。支持整数或十进制数字字符串。
        encoding: 文件编码。auto=自动检测（默认），也可指定编码名称。
        show_line_number: 行号显示模式。True=顶部带图例、每行带行号前缀（默认），False=直接输出原文切片。
    """
    resolved = resolve_path(path)

    start_row, err = parse_int(start_row, "start_row")
    if err:
        return make_error("读取矩形块", err)
    end_row, err = parse_int(end_row, "end_row")
    if err:
        return make_error("读取矩形块", err)
    start_col, err = parse_int(start_col, "start_col")
    if err:
        return make_error("读取矩形块", err)
    end_col, err = parse_int(end_col, "end_col")
    if err:
        return make_error("读取矩形块", err)
    max_chars, err = parse_int(max_chars, "max_chars")
    if err:
        return make_error("读取矩形块", err)

    if start_col > end_col:
        return make_error(f"读取矩形块失败，因为 start_col ({start_col}) 大于 end_col ({end_col})。")
    if start_row < 1 or end_row < 1:
        return make_error("读取矩形块失败，因为行号必须 >= 1。")
    if start_row > end_row:
        return make_error(f"读取矩形块失败，因为起始行号 {start_row} 大于结束行号 {end_row}。")
    if start_col < 1 or end_col < 1:
        return make_error("读取矩形块", "起始列号和结束列号必须 >= 1")

    if not os.path.isfile(resolved):
        return make_error(f"读取矩形块失败，因为文件「{resolved}」不存在。")

    try:
        lines, resolved_encoding = read_file_lines(resolved, encoding)
    except Exception as e:
        return make_error(f"读取矩形块失败，因为读取文件时出错：{e}。")

    # 空文件（[""]）视为0行
    if len(lines) == 1 and lines[0] == "":
        lines = []

    total_lines = len(lines)
    if total_lines == 0:
        return make_error("读取矩形块失败，因为文件为空（长度为 0）。")
    if start_row > total_lines:
        return make_error(f"读取矩形块失败，因为文件共 {total_lines} 行，起始行号 {start_row} 超出范围。")

    actual_start = max(0, start_row - 1)
    actual_end = min(end_row, total_lines)

    output_lines: List[str] = []
    char_count = 0
    is_truncated = False

    for i in range(actual_start, actual_end):
        line = lines[i]
        row_num = i + 1

        if start_col > len(line):
            content = ""
        else:
            content = line[start_col - 1 : end_col]

        char_count += len(content)
        if char_count > max_chars:
            is_truncated = True
            remaining = max_chars - (char_count - len(content))
            content = content[:remaining] + "<<<TRUNCATED>>>"
            if show_line_number:
                output_lines.append(f"{row_num} > {content}")
            else:
                output_lines.append(content)
            break

        if show_line_number:
            output_lines.append(f"{row_num} > {content}")
        else:
            output_lines.append(content)

    result = "\n".join(output_lines)

    if is_truncated:
        next_line = row_num
        result += f"\n\n<<<TRUNCATED>>>内容已超出 max_chars={max_chars} 限制。如需继续阅读，请从第 {next_line} 行开始读取（该行内容不完整，会重新返回完整内容）。\n"

    if show_line_number and output_lines:
        result = "行号 > 行内容\n\n" + result

    return make_success(result)


# ── 8. file_tools_regex ───────────────────────────────────


def file_tools_regex(
    path: str,
    pattern: str,
    start_line: Union[int, str] = 1,
    end_line: Optional[Union[int, str]] = None,
    start: Union[int, str] = 1,
    count: Union[int, str] = 10,
    max_chars: Union[int, str] = 5000,
    encoding: str = "auto",
) -> str:
    """在文件内容中搜索正则表达式，返回表格（序号 | 行号,列号 | [组 |] 匹配内容）。跨行匹配在 pattern 内写 \\n。有捕获组时匹配内容列显示组内容（单组=组文本，多组=每组一行）。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        pattern: 正则表达式。^/$ 按行（每行首尾），整段绝对首尾用 \\A/\\Z。
        start_line: 搜索起始行号，1-based，包含。
        end_line: 搜索结束行号，1-based，包含。None=文件末尾。
        start: 从第几行结果开始显示（不是第几个匹配），1-based。
        count: 最多返回多少行结果。-1=全部。
        max_chars: 返回内容总字符上限。
        encoding: 文件编码。
    """
    import bisect

    resolved = resolve_path(path)

    start_line, err = parse_int(start_line, "start_line")
    if err:
        return make_error("正则匹配", err)
    end_line, err = parse_int(end_line, "end_line")
    if err:
        return make_error("正则匹配", err)
    start, err = parse_int(start, "start")
    if err:
        return make_error("正则匹配", err)
    count, err = parse_int(count, "count")
    if err:
        return make_error("正则匹配", err)
    max_chars, err = parse_int(max_chars, "max_chars")
    if err:
        return make_error("正则匹配", err)

    if not os.path.isfile(resolved):
        return make_error(
            "正则匹配",
            f"文件「{resolved}」不存在",
        )

    if not pattern:
        return make_error("正则匹配", "pattern 不能为空字符串。请传入有效的正则表达式。")

    try:
        compiled = re_module.compile(pattern, re_module.MULTILINE)
    except re_module.error as e:
        return make_error("正则匹配", f"正则表达式语法错误：{e}")

    try:
        lines, resolved_encoding = read_file_lines(resolved, encoding)
    except Exception as e:
        return make_error("正则匹配", f"读取文件时出错：{e}")

    # ── 参数校验 ──────────────────────────────────────────

    if start < 1:
        return make_error("正则匹配", f"start 参数值 {start} 不合法。start 表示「从第几行结果开始显示」，最小值为 1。")

    if count == 0:
        return make_error("正则匹配", "count 参数值 0 不合法。count=-1 表示返回所有行，count>=1 表示返回指定行数。")
    if count < -1:
        return make_error("正则匹配", f"count 参数值 {count} 不合法。负数值仅支持 -1（返回所有行）。")

    total_lines = len(lines)

    if start_line < 1:
        return make_error("正则匹配", f"start_line 参数值 {start_line} 不合法。行号从 1 开始，最小值为 1。")
    if end_line is not None and end_line < 1:
        return make_error("正则匹配", f"end_line 参数值 {end_line} 不合法。行号从 1 开始，最小值为 1。")
    if end_line is not None and end_line < start_line:
        return make_error("正则匹配", f"end_line ({end_line}) 小于 start_line ({start_line})，参数矛盾。")
    if start_line > total_lines:
        return make_error("正则匹配", f"start_line 参数值 {start_line} 超出文件范围。文件共 {total_lines} 行。")

    actual_start = start_line - 1
    actual_end = min(end_line or total_lines, total_lines)

    # 拼接行范围（跨行匹配）
    range_lines = lines[actual_start:actual_end]
    range_content = "\n".join(range_lines)

    # 构建行偏移索引：每个 line 在 range_content 中的起始偏移
    line_offsets = [0]
    for l in range_lines:
        line_offsets.append(line_offsets[-1] + len(l) + 1)  # +1 for \n

    def _pos_to_line_col(pos: int):
        """将 range_content 中的字符位置映射为 (原始文件行号, 行内列号)，均 1-based。"""
        idx = bisect.bisect_right(line_offsets, pos) - 1
        return actual_start + idx + 1, pos - line_offsets[idx] + 1

    def _escape_cell(s: str) -> str:
        """转义表格单元格：反斜杠/换行/制表符/竖线。多行匹配因此写成一行且不破坏表格。"""
        return (
            s.replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace("\t", "\\t")
            .replace("\r", "\\r")
            .replace("|", "\\|")
        )

    # ── 收集匹配并展平为行 ───────────────────────────────
    # 每行 = (组号, 行号, 列号, 内容)；未参与匹配的组内容为 None
    rows: List[Tuple[int, int, int, Optional[str]]] = []
    for match in compiled.finditer(range_content):
        group_count = len(match.groups())
        if group_count == 0:
            groups = [(0, match.group(0))]
        elif group_count == 1:
            groups = [(1, match.group(1))]
        else:
            groups = [(i, match.group(i)) for i in range(1, group_count + 1)]
        for gno, gval in groups:
            if gval is None:
                rows.append((gno, 0, 0, None))
            else:
                line_no, col = _pos_to_line_col(match.start(gno))
                rows.append((gno, line_no, col, gval))

    # 组列显示策略：0 组或 1 组时隐藏（信息冗余），2+ 组时显示（区分各组）
    # compiled.groups 是 int（捕获组数量，不含组0）
    show_group = compiled.groups >= 2

    total_rows = len(rows)
    if total_rows == 0:
        return make_success("共 0 个匹配。")

    if start > total_rows:
        return make_error("正则匹配", f"start 参数值 {start} 超出总行数（共 {total_rows} 行）。")

    effective_count = total_rows if count == -1 else count
    page_start = start - 1
    page = rows[page_start:page_start + effective_count]

    # ── 格式化结果行 ─────────────────────────────────────
    ROW_MAX = 260  # 每行匹配内容上限（原始字符数）
    MARKER = "<<<TRUNCATED>>>"

    formatted: List[Tuple[str, bool]] = []  # (行文本, 是否内容截断)
    for i, (gno, line_no, col, gval) in enumerate(page):
        no = page_start + i + 1
        if gval is None:
            # 组未参与匹配（如 (a)|(b) 中未命中的组）
            cell = "None"
            pos_str = "-"
            row_truncated = False
        elif gval == "":
            # 零宽匹配（空串）：显式显示 ""
            cell = '""'
            pos_str = f"{line_no},{col}"
            row_truncated = False
        else:
            row_truncated = len(gval) > ROW_MAX
            raw = gval[:ROW_MAX] if row_truncated else gval
            cell = _escape_cell(raw)
            pos_str = f"{line_no},{col}"
        if show_group:
            row_str = f"{no} | {pos_str} | {gno} | {cell}"
        else:
            row_str = f"{no} | {pos_str} | {cell}"
        if row_truncated:
            row_str += MARKER
        formatted.append((row_str, row_truncated))

    # 总字符预算：逐行累计，超出则整行停止（不输出半行，footer 提示用 start 继续）
    out_lines: List[str] = []
    char_count = 0
    emitted = 0
    char_truncated = False
    for row_str, _ in formatted:
        if emitted >= 1 and char_count + len(row_str) > max_chars:
            char_truncated = True
            break
        out_lines.append(row_str)
        char_count += len(row_str)
        emitted += 1

    any_row_truncated = any(t for _, t in formatted[:emitted])
    page_end = page_start + emitted

    # ── 页脚 ─────────────────────────────────────────────
    footer: List[str] = []
    if page_end < total_rows:
        reason = f"，因为总字符超限 {max_chars}" if char_truncated else ""
        footer.append(f"当前展示了 {start} → {page_end} 行（共 {total_rows} 行）{reason}。可以使用 start={page_end + 1} 查看后面的行。")
    else:
        footer.append(f"共 {total_rows} 行，已全部展示。")
    if any_row_truncated:
        footer.append(f"部分行因超过每行 {ROW_MAX} 字符上限被截断。")

    header = "序号 | 行号,列号 | 组 | 匹配内容" if show_group else "序号 | 行号,列号 | 匹配内容"
    result = header + "\n" + "\n".join(out_lines) + "\n\n" + "\n".join(footer)
    return make_success(result)
