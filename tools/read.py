"""文本读取类工具。

包含：
- file_tools_read_lines: 按行读取（CSV）
- file_tools_read_block: 读取矩形块（CSV）
- file_tools_regex: 正则匹配（CSV）
"""

import csv
import io
import logging
import os
import re as re_module
from typing import Any, Dict, List, Optional, Tuple

try:
    from ..utils import (
        DEFAULT_MAX_CHARS,
        format_csv,
        format_error,
        read_file_lines,
        resolve_path,
        truncate_line,
    )
except ImportError:
    from utils import (
        DEFAULT_MAX_CHARS,
        format_csv,
        format_error,
        read_file_lines,
        resolve_path,
        truncate_line,
    )

logger = logging.getLogger(__name__)


# ── 6. file_tools_read_lines ──────────────────────────────


def file_tools_read_lines(
    path: str,
    start_line: int = 1,
    line_count: int = 20,
    max_chars: int = 2048,
    encoding: str = "auto",
) -> str:
    """按行读取文本文件，返回 CSV。

    Args:
        path: 文件路径
        start_line: 起始行号（1-based）
        line_count: 读取行数，-1=到末尾，0=报错
        max_chars: 返回内容总字符上限
        encoding: 编码

    Returns:
        CSV 字符串
    """
    resolved = resolve_path(path)

    if line_count == 0:
        return "按行读取失败，因为 line_count=0 没有意义。请设置 line_count=-1 读取到末尾，或设为一个正整数。"
    if start_line < 1:
        return f"按行读取失败，因为起始行号 {start_line} 不合法。行号从 1 开始。"

    if not os.path.isfile(resolved):
        return (
            f"按行读取失败，因为文件「{resolved}」不存在。"
            f"请使用 file_tools_info(path=\"{path}\") 确认文件是否存在。"
        )

    try:
        lines, resolved_encoding = read_file_lines(resolved, encoding)
    except Exception as e:
        return f"按行读取失败，因为读取文件时出错：{e}。"

    # 空文件（[""]）视为0行，只返回表头
    if len(lines) == 1 and lines[0] == "":
        lines = []

    total_lines = len(lines)
    if start_line > total_lines + 1:
        return f"按行读取失败，因为文件共 {total_lines} 行，起始行号 {start_line} 超出范围。"

    actual_start = start_line - 1
    if line_count == -1:
        actual_count = total_lines - actual_start
    else:
        actual_count = line_count

    actual_end = min(actual_start + actual_count, total_lines)
    selected_lines = lines[actual_start:actual_end]

    rows: List[Dict[str, Any]] = []
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
            rows.append({"line_number": str(row_num), "content": content})
            break

        rows.append({"line_number": str(row_num), "content": content})

    if rows:
        max_num = max(int(r["line_number"]) for r in rows)
        width = len(str(max_num))
        for r in rows:
            r["line_number"] = str(int(r["line_number"])).zfill(width)

    csv_output = format_csv(rows, fieldnames=["line_number", "content"])

    if truncated:
        # 被截断的行内容不完整，建议从该行重新读取
        next_line = int(rows[-1]["line_number"])
        csv_output += f"\n`<<truncated>>` 内容已超出 max_chars={max_chars} 限制。如需继续阅读，请从第 {next_line} 行开始读取（该行内容不完整，会重新返回完整内容）。\n"

    return csv_output


# ── 7. file_tools_read_block ──────────────────────────────


def file_tools_read_block(
    path: str,
    start_line: int,
    end_line: int,
    start_offset: int = 0,
    end_offset: int = 2048,
    max_chars: int = 2048,
    encoding: str = "auto",
) -> str:
    """读取矩形块，返回 CSV。

    像一个可以上下左右移动的"观察窗口"，从文本中截取一个矩形区域。

    Args:
        path: 文件路径
        start_line: 起始行号（包含，1-based）
        end_line: 结束行号（包含，1-based）
        start_offset: 行内起始字符偏移
        end_offset: 行内结束字符偏移
        max_chars: 返回内容总字符上限
        encoding: 编码

    Returns:
        CSV 字符串
    """
    resolved = resolve_path(path)

    if start_offset > end_offset:
        return f"读取矩形块失败，因为 start_offset ({start_offset}) 大于 end_offset ({end_offset})。"
    if start_line < 1 or end_line < 1:
        return f"读取矩形块失败，因为行号必须 >= 1。"
    if start_line > end_line:
        return f"读取矩形块失败，因为起始行号 {start_line} 大于结束行号 {end_line}。"

    if not os.path.isfile(resolved):
        return (
            f"读取矩形块失败，因为文件「{resolved}」不存在。"
            f"请使用 file_tools_info(path=\"{path}\") 确认文件是否存在。"
        )

    try:
        lines, resolved_encoding = read_file_lines(resolved, encoding)
    except Exception as e:
        return f"读取矩形块失败，因为读取文件时出错：{e}。"

    total_lines = len(lines)
    if start_line > total_lines:
        return f"读取矩形块失败，因为文件共 {total_lines} 行，起始行号 {start_line} 超出范围。"

    actual_start = max(0, start_line - 1)
    actual_end = min(end_line, total_lines)

    rows: List[Dict[str, Any]] = []
    char_count = 0
    is_truncated = False

    for i in range(actual_start, actual_end):
        line = lines[i]
        row_num = i + 1

        if start_offset >= len(line):
            content = ""
        else:
            content = line[start_offset:end_offset]

        char_count += len(content)
        if char_count > max_chars:
            is_truncated = True
            remaining = max_chars - (char_count - len(content))
            content = content[:remaining] + "<<truncated>>"
            rows.append({"line_number": str(row_num), "content": content})
            break

        rows.append({"line_number": str(row_num), "content": content})

    if rows:
        max_num = max(int(r["line_number"]) for r in rows)
        width = len(str(max_num))
        for r in rows:
            r["line_number"] = str(int(r["line_number"])).zfill(width)

    csv_output = format_csv(rows, fieldnames=["line_number", "content"])

    if is_truncated:
        next_line = int(rows[-1]["line_number"])
        csv_output += f"\n`<<truncated>>` 内容已超出 max_chars={max_chars} 限制。如需继续阅读，请从第 {next_line} 行开始读取（该行内容不完整，会重新返回完整内容）。\n"

    return csv_output


# ── 8. file_tools_regex ───────────────────────────────────


def file_tools_regex(
    path: str,
    pattern: str,
    start_line: int = 1,
    end_line: Optional[int] = None,
    start: int = 1,
    count: int = 10,
    max_chars: int = 2048,
    encoding: str = "auto",
) -> str:
    """正则匹配文件内容，返回 CSV。

    Args:
        path: 文件路径
        pattern: 正则表达式
        start_line: 起始行号（包含，1-based）
        end_line: 结束行号（包含，1-based，None=文件末尾）
        start: 从第几个匹配开始（1-based）
        count: 最多返回多少个匹配
        max_chars: 返回内容总字符上限
        encoding: 编码

    Returns:
        CSV 字符串（列名: match_number,line_number,line_content,matched_text）
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return (
            f"正则匹配失败，因为文件「{resolved}」不存在。"
            f"请使用 file_tools_info(path=\"{path}\") 确认文件是否存在。"
        )

    try:
        compiled = re_module.compile(pattern)
    except re_module.error as e:
        return f"正则匹配失败，因为正则表达式语法错误：{e}。"

    try:
        lines, resolved_encoding = read_file_lines(resolved, encoding)
    except Exception as e:
        return f"正则匹配失败，因为读取文件时出错：{e}。"

    total_lines = len(lines)
    actual_start = max(0, start_line - 1)
    actual_end = min(end_line or total_lines, total_lines)

    if actual_start >= total_lines:
        return format_csv([], fieldnames=["match_number", "line_number", "line_content", "matched_text"])

    all_matches: List[Dict[str, Any]] = []

    for i in range(actual_start, actual_end):
        line = lines[i]
        match = compiled.search(line)
        if match:
            line_content = truncate_line(line)
            all_matches.append({
                "match_number": len(all_matches) + 1,
                "line_number": i + 1,
                "line_content": line_content,
                "matched_text": match.group(0),
            })

    if not all_matches:
        return format_csv([], fieldnames=["match_number", "line_number", "line_content", "matched_text"])

    if start < 1:
        return format_error("正则匹配", f"start 参数值 {start} 不合法。start 表示「从第几个匹配开始显示」，最小值为 1。")
    if count < 1:
        count = 10

    page_start = start - 1
    page_end = min(page_start + count, len(all_matches))
    page = all_matches[page_start:page_end]

    csv_output = format_csv(page, fieldnames=["match_number", "line_number", "line_content", "matched_text"])

    total_matches = len(all_matches)
    if page_end < total_matches:
        csv_output += f"\n`<<truncated>>` 共 {total_matches} 个匹配，只显示了第 {start}~{page_end} 个。\n"

    return csv_output
