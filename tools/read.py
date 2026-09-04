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
from typing import Any, Dict, List, Optional, Union

try:
    from ..utils import (
        DEFAULT_MAX_CHARS,
        format_csv,
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
        DEFAULT_MAX_CHARS,
        format_csv,
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
    max_chars: Union[int, str] = 2048,
    encoding: str = "auto",
    show_line_number: bool = True,
) -> str:
    """按行读取文本文件，返回纯文本格式。支持指定起始行和读取行数，超过 max_chars 时自动截断并提示从哪行继续读取。空文件视为 0 行。show_line_number=True 时每行格式为 `行号 > 内容`，False 时直接输出原文。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        start_line: 起始行号，1-based，默认 1。最小值为 1，超出文件总行数时报错。支持整数或十进制数字字符串。
        line_count: 读取行数。正数=读取指定行数，-1=读取到文件末尾，0=报错（无意义）。支持整数或十进制数字字符串。
        max_chars: 返回内容总字符上限，默认 2048。超过时截断并提示从截断位置继续读取。支持整数或十进制数字字符串。
        encoding: 文件编码。auto=自动检测（默认），也可指定 utf-8、gbk 等 Python 支持的编码名称。
        show_line_number: 行号显示模式。True=每行带行号前缀（默认），False=直接输出原文。
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
            content = content[:4096] + "<<truncated>>"

        char_count += len(content)
        if char_count > max_chars:
            truncated = True
            content = content[:max_chars - (char_count - len(content))] + "<<truncated>>"
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
        result += f"\n`<<truncated>>` 内容已超出 max_chars={max_chars} 限制。如需继续阅读，请从第 {next_line} 行开始读取（该行内容不完整，会重新返回完整内容）。\n"

    return make_success(result)


# ── 7. file_tools_read_block ──────────────────────────────


def file_tools_read_block(
    path: str,
    start_row: Union[int, str],
    end_row: Union[int, str],
    start_col: Union[int, str] = 1,
    end_col: Union[int, str] = 2048,
    max_chars: Union[int, str] = 2048,
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
        max_chars: 返回内容总字符上限，默认 2048。超过时截断并提示从截断位置继续读取。支持整数或十进制数字字符串。
        encoding: 文件编码。auto=自动检测（默认），也可指定编码名称。
        show_line_number: 行号显示模式。True=每行带行号前缀（默认），False=直接输出原文切片。
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
            content = content[:remaining] + "<<truncated>>"
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
        result += f"\n`<<truncated>>` 内容已超出 max_chars={max_chars} 限制。如需继续阅读，请从第 {next_line} 行开始读取（该行内容不完整，会重新返回完整内容）。\n"

    return make_success(result)


# ── 8. file_tools_regex ───────────────────────────────────


def file_tools_regex(
    path: str,
    pattern: str,
    start_line: Union[int, str] = 1,
    end_line: Optional[Union[int, str]] = None,
    start: Union[int, str] = 1,
    count: Union[int, str] = 10,
    encoding: str = "auto",
) -> str:
    """在文件内容中搜索正则表达式，支持跨行匹配，返回 JSON 格式。拼接指定行范围后整体用 finditer 匹配，因此正则可以跨行。matched 字段自动根据捕获组数量决定：0 组=完整匹配串，1 组=提取内容，2+组=列表。超过 250 字符的匹配内容会被截断并附带 note 字段提示。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        pattern: 正则表达式，Python re 语法。支持跨行匹配（拼接行范围后整体用 finditer 匹配）。不能为空。
        start_line: 搜索起始行号，1-based，包含。默认 1。最小值为 1，超出文件总行数时报错。支持整数或十进制数字字符串。
        end_line: 搜索结束行号，1-based，包含。默认 None=文件末尾。必须 >= start_line。支持整数或十进制数字字符串。
        start: 从第几个匹配开始显示，1-based。默认 1。最小值为 1。支持整数或十进制数字字符串。
        count: 最多返回多少个匹配。默认 10。传 -1 返回所有匹配，传 0 报错。支持整数或十进制数字字符串。
        encoding: 文件编码。auto=自动检测（默认），也可指定编码名称。
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

    if not os.path.isfile(resolved):
        return make_error(
            "正则匹配",
            f"文件「{resolved}」不存在",
        )

    if not pattern:
        return make_error("正则匹配", "pattern 不能为空字符串。请传入有效的正则表达式。")

    try:
        compiled = re_module.compile(pattern)
    except re_module.error as e:
        return make_error("正则匹配", f"正则表达式语法错误：{e}")

    try:
        lines, resolved_encoding = read_file_lines(resolved, encoding)
    except Exception as e:
        return make_error("正则匹配", f"读取文件时出错：{e}")

    # ── 参数校验 ──────────────────────────────────────────

    if start < 1:
        return make_error("正则匹配", f"start 参数值 {start} 不合法。start 表示「从第几个匹配开始显示」，最小值为 1。")

    if count == 0:
        return make_error("正则匹配", "count 参数值 0 不合法。count=-1 表示返回所有匹配，count>=1 表示返回指定数量。")
    if count < -1:
        return make_error("正则匹配", f"count 参数值 {count} 不合法。负数值仅支持 -1（返回所有匹配）。")

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

    if actual_start >= total_lines:
        return make_success(json.dumps({"total_matches": 0, "matches": []}, indent=2, ensure_ascii=False))

    # 拼接行范围（跨行匹配）
    range_lines = lines[actual_start:actual_end]
    range_content = "\n".join(range_lines)

    # 构建行偏移索引：每个 line 在 range_content 中的起始偏移
    line_offsets = [0]
    for l in range_lines:
        line_offsets.append(line_offsets[-1] + len(l) + 1)  # +1 for \n

    def _pos_to_line(pos: int) -> int:
        """将 range_content 中的字符位置映射到原始文件行号。"""
        idx = bisect.bisect_right(line_offsets, pos) - 1
        return actual_start + idx + 1  # 1-based

    MATCHED_MAX = 250

    def _truncate_matched(val):
        """截断 matched 内容到 250 字符，超过加截断符。"""
        if isinstance(val, str):
            if len(val) > MATCHED_MAX:
                return val[:MATCHED_MAX] + "<<truncated>>", True
            return val, False
        if isinstance(val, list):
            truncated = False
            result = []
            for item in val:
                if len(item) > MATCHED_MAX:
                    result.append(item[:MATCHED_MAX] + "<<truncated>>")
                    truncated = True
                else:
                    result.append(item)
            return result, truncated
        return val, False

    # 收集所有匹配
    all_matches: List[Dict[str, Any]] = []
    any_truncated = False

    for match in compiled.finditer(range_content):
        start_pos = match.start()
        end_pos = match.end()
        line_start = _pos_to_line(start_pos)
        line_end = _pos_to_line(end_pos - 1) if end_pos > start_pos else line_start

        if line_start == line_end:
            lines_str = str(line_start)
        else:
            lines_str = f"{line_start}~{line_end}"

        # matched 字段：捕获组决定类型
        group_count = len(match.groups())
        if group_count == 0:
            raw = match.group(0)
        elif group_count == 1:
            raw = match.group(1)
        else:
            raw = list(match.groups())

        matched, truncated = _truncate_matched(raw)
        if truncated:
            any_truncated = True

        all_matches.append({
            "match": len(all_matches) + 1,
            "lines": lines_str,
            "matched": matched,
        })

    if not all_matches:
        return make_success(json.dumps({"total_matches": 0, "matches": []}, indent=2, ensure_ascii=False))

    # 分页
    effective_count = len(all_matches) if count == -1 else count
    page_start = start - 1
    page_end = min(page_start + effective_count, len(all_matches))
    page = all_matches[page_start:page_end]

    result = {
        "total_matches": len(all_matches),
        "matches": page,
    }

    if any_truncated:
        result["note"] = (
            "部分匹配结果因内容过长已被截断（上限 250 字符）。"
            "如需获取完整内容，请使用 file_tools_read_lines 或 file_tools_read_block 读取目标行。"
        )

    return make_success(json.dumps(result, indent=2, ensure_ascii=False))
