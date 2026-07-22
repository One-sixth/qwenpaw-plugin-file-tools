"""文件修改类工具。

所有修改工具在执行前自动备份原文件，成功修改后返回附带备份提示。

包含：
- file_tools_append: 追加内容
- file_tools_replace_lines: 替换行区间
- file_tools_insert_lines: 行前插入
- file_tools_delete_lines: 删除行区间
- file_tools_replace: 查找替换（子串）
- file_tools_regex_replace: 正则替换

文件 I/O 使用 Python 文本模式，统一用 \\\\n 换行。
Windows 上读写时 \\\\n ↔ \\\\r\\\\n 由 Python 自动处理。
"""

import logging
import os
import re as re_module
from typing import Any, Dict, List, Literal, Optional, Tuple

try:
    from ..backup.manager import backup_file
    from ..utils import (
        LINE_CONTENT_TRUNCATE,
        detect_encoding,
        format_backup_info,
        format_error,
        normalize_newlines,
        read_file_lines,
        resolve_path,
        truncate_line,
    )
except ImportError:
    from backup.manager import backup_file
    from utils import (
        LINE_CONTENT_TRUNCATE,
        detect_encoding,
        format_backup_info,
        format_error,
        normalize_newlines,
        read_file_lines,
        resolve_path,
        truncate_line,
    )

logger = logging.getLogger(__name__)


def _write_file(path: str, content: str, encoding: str, newline: Optional[str] = None) -> None:
    """文本模式写入文件。

    newline 参数与 open() 的 newline 参数语义一致：
    None=Python自动处理，\\n=LF，\\r\\n=CRLF。
    """
    with open(path, "w", encoding=encoding, newline=newline) as f:
        f.write(content)


# ── 9. file_tools_append ──────────────────────────────────


def file_tools_append(
    path: str,
    content: str,
    encoding: str = "auto",
    line_separator: Literal["auto", "\\n", "\\r\\n"] = "auto",
) -> str:
    """追加内容到文件末尾。修改前自动备份。不会自动在文件末尾补换行符——如果文件末尾没有换行符，新增内容会直接接到最后一行后面。返回时显示文件末尾 3 行作为预览。写回时 \\r\\n/\\r 自动统一为 \\n。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。文件不存在时报错（请先用 QwenPaw 的 write_file 创建文件）。
        content: 要追加的文本内容。\\r\\n 和 \\r 写入前自动统一为 \\n，避免文本模式二次转换导致 \\r\\r\\n。追加前不会自动补换行符——如需换行需在 content 开头加 \\n。
        encoding: 文件编码。auto=自动检测（默认），也可指定编码名称。
        line_separator: 行结束符控制。auto=按操作系统自动处理（Windows 上 \\n→\\r\\n），\\n=Unix 风格（强制 LF），\\r\\n=Windows 风格（强制 CRLF）。
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return format_error(
            "追加",
            f"文件「{resolved}」不存在",
            "请确认路径是否正确。文件不存在时请先用 QwenPaw 的 write_file 工具创建文件。",
        )

    history_number = backup_file(resolved)
    if history_number is None:
        return format_error("追加", "备份原文件失败。因为获取会话文件路径失败。")

    resolved_encoding = detect_encoding(resolved, encoding)

    # 统一换行符后再写入，避免文本模式二次转换 \\r\\n → \\r\\r\\n
    normalized = normalize_newlines(content)

    # 解析 line_separator
    newline_map = {"auto": None, "\\n": "\n", "\\r\\n": "\r\n"}
    nl = newline_map.get(line_separator, None)

    try:
        with open(resolved, "a", encoding=resolved_encoding, newline=nl) as f:
            f.write(normalized)
    except Exception as e:
        return format_error("追加", f"写入文件时出错：{e}")

    lines, _ = read_file_lines(resolved, resolved_encoding)
    total_lines = len(lines)

    summary = f"成功追加：已在文件末尾追加了内容。文件共 {total_lines} 行。{format_backup_info(resolved, history_number)}"

    result_parts: List[str] = [summary, ""]
    preview_start = max(0, total_lines - 3)
    for i in range(preview_start, total_lines):
        result_parts.append(f"{i + 1}\t{truncate_line(lines[i])}")

    return "\n".join(result_parts)


# ── 10. file_tools_replace_lines ──────────────────────────


def file_tools_replace_lines(
    path: str,
    start_line: int,
    end_line: int,
    content: str,
    encoding: str = "auto",
    line_separator: Literal["auto", "\\n", "\\r\\n"] = "auto",
) -> str:
    """整段替换文件中的指定行区间，替换内容可以比原区间行数多或少。修改前自动备份。返回时显示 +/- diff 格式预览（先 - 旧行再 + 新行，带行号）。写回时 \\r\\n/\\r 自动统一为 \\n。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。文件不存在时报错。
        start_line: 起始行号，1-based，包含。最小值为 1。超出文件总行数+1 时报错。
        end_line: 结束行号，1-based，包含。必须 >= start_line。超出文件总行数时取到文件末尾。
        content: 替换内容。用 \\n 拆成多行，因此可以增加或减少行数。\\r\\n/\\r 写入前自动统一为 \\n。
        encoding: 文件编码。auto=自动检测（默认），也可指定编码名称。
        line_separator: 行结束符控制。auto=按操作系统自动处理（默认），\\n=Unix 风格 LF，\\r\\n=Windows 风格 CRLF。
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return format_error("替换行", f"文件「{resolved}」不存在")
    if start_line < 1 or end_line < 1:
        return format_error("替换行", f"行号必须 >= 1，收到 start_line={start_line}, end_line={end_line}")
    if start_line > end_line:
        return format_error("替换行", f"起始行号 {start_line} 大于结束行号 {end_line}")

    history_number = backup_file(resolved)
    if history_number is None:
        return format_error("替换行", "备份原文件失败。因为获取会话文件路径失败。")

    try:
        lines, resolved_encoding = read_file_lines(resolved, encoding)
    except Exception as e:
        return format_error("替换行", f"读取文件时出错：{e}")

    total_lines = len(lines)
    if start_line > total_lines + 1:
        return format_error("替换行", f"起始行号 {start_line} 超出文件范围（共 {total_lines} 行）")

    old_lines = lines.copy()
    actual_start = max(0, start_line - 1)
    actual_end = min(end_line, total_lines)

    new_lines_content = normalize_newlines(content).split("\n")
    lines[actual_start:actual_end] = new_lines_content

    # 解析 line_separator
    newline_map = {"auto": None, "\\n": "\n", "\\r\\n": "\r\n"}
    nl = newline_map.get(line_separator, None)

    try:
        _write_file(resolved, "\n".join(lines), resolved_encoding, newline=nl)
    except Exception as e:
        return format_error("替换行", f"写入文件时出错：{e}")

    new_total = len(lines)

    # 构建 +/- diff 预览
    diff_parts = []
    # - 组：旧内容（按旧行号）
    for i in range(actual_start, actual_end):
        diff_parts.append(f"- {i + 1} > {truncate_line(old_lines[i])}")
    # + 组：新内容（按新行号，从 start_line 开始）
    for i in range(actual_start, actual_start + len(new_lines_content)):
        diff_parts.append(f"+ {i + 1} > {truncate_line(lines[i])}")
    diff_text = "\n".join(diff_parts)

    summary = f"成功替换：已将第 {start_line}~{end_line} 行替换为 {len(new_lines_content)} 行新内容。文件共 {new_total} 行。{format_backup_info(resolved, history_number)}"
    return "\n".join([summary, "", diff_text])


def _build_replace_preview(lines_before, lines_after, start_line, end_line, old_count):
    """构建替换预览：─── 替换前 ─── / ─── 替换后 ─── 对称显示。

    正文区域（被替换/新替换的行）超过 6 行时，只显示前 2 + 后 2 行。
    """
    _MAX_BODY = 6
    total_before = len(lines_before)
    total_after = len(lines_after)
    new_section_end = total_after - total_before + end_line
    parts = []

    def _section(lines, total, s_start, s_end, label, mark_replaced=False):
        nonlocal parts
        parts.append(label)
        body_count = s_end - s_start

        # 正文前上下文
        show_start = max(0, s_start - 2)
        if show_start > 0:
            parts.append("  <<省略>>")
        for i in range(show_start, s_start):
            if i < total:
                parts.append(f"{i + 1}\t{truncate_line(lines[i])}")

        # 正文（超过 _MAX_BODY 行时截断）
        if body_count > _MAX_BODY:
            # 前 2 行
            for i in range(s_start, s_start + 2):
                if i < total:
                    suffix = "（被替换）" if mark_replaced else ""
                    parts.append(f"{i + 1}\t{truncate_line(lines[i])}{suffix}")
            parts.append("  <<省略>>")
            # 后 2 行
            for i in range(s_end - 2, s_end):
                if i < total:
                    suffix = "（被替换）" if mark_replaced else ""
                    parts.append(f"{i + 1}\t{truncate_line(lines[i])}{suffix}")
        else:
            for i in range(s_start, s_end):
                if i < total:
                    suffix = "（被替换）" if mark_replaced else ""
                    parts.append(f"{i + 1}\t{truncate_line(lines[i])}{suffix}")

        # 正文后上下文
        show_end = min(total, s_end + 2)
        for i in range(s_end, show_end):
            if i < total:
                parts.append(f"{i + 1}\t{truncate_line(lines[i])}")
        if show_end < total:
            parts.append("  <<省略>>")

    _section(lines_before, total_before, start_line, end_line, "─── 替换前 ───", mark_replaced=True)
    parts.append("")
    _section(lines_after, total_after, start_line, new_section_end, "─── 替换后 ───")

    return "\n".join(parts)


# ── 11. file_tools_insert_lines ───────────────────────────


def file_tools_insert_lines(
    path: str,
    line: int,
    content: str,
    encoding: str = "auto",
    line_separator: Literal["auto", "\\n", "\\r\\n"] = "auto",
) -> str:
    """在指定行号之前插入新内容，可一次插入多行。修改前自动备份。返回时显示「─── 插入前/后 ───」预览，前后各一行上下文，插入行超过 6 行时只显示前 2 + 后 2 行。写回时 \\r\\n/\\r 自动统一为 \\n。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。文件不存在时报错。
        line: 插入位置，1-based。在第 line 行之前插入，line 大于文件总行数时追加到文件末尾。最小值为 1。
        content: 要插入的文本内容。用 \\n 拆成多行，因此可以一次插入多行。\\r\\n/\\r 写入前自动统一为 \\n。
        encoding: 文件编码。auto=自动检测（默认），也可指定编码名称。
        line_separator: 行结束符控制。auto=按操作系统自动处理（默认），\\n=Unix 风格 LF，\\r\\n=Windows 风格 CRLF。
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return format_error("插入行", f"文件「{resolved}」不存在")
    if line < 1:
        return format_error("插入行", f"行号 {line} 不合法，行号从 1 开始")

    history_number = backup_file(resolved)
    if history_number is None:
        return format_error("插入行", "备份原文件失败。因为获取会话文件路径失败。")

    try:
        lines, resolved_encoding = read_file_lines(resolved, encoding)
    except Exception as e:
        return format_error("插入行", f"读取文件时出错：{e}")

    total_lines = len(lines)
    insert_pos = min(line - 1, total_lines)
    insert_lines = normalize_newlines(content).split("\n")
    insert_count = len(insert_lines)

    old_lines = lines.copy()
    lines[insert_pos:insert_pos] = insert_lines

    # 解析 line_separator
    newline_map = {"auto": None, "\\n": "\n", "\\r\\n": "\r\n"}
    nl = newline_map.get(line_separator, None)

    try:
        _write_file(resolved, "\n".join(lines), resolved_encoding, newline=nl)
    except Exception as e:
        return format_error("插入行", f"写入文件时出错：{e}")

    new_total = len(lines)

    # 构建 +/- diff 预览
    diff_parts = []
    # 前一行上下文（按旧行号）
    if insert_pos > 0:
        diff_parts.append(f"  {insert_pos} > {truncate_line(old_lines[insert_pos - 1])}")
    # + 组：新插入的行（按新行号）
    for i in range(insert_pos, insert_pos + insert_count):
        diff_parts.append(f"+ {i + 1} > {truncate_line(lines[i])}")
    # 后一行上下文（按新行号，即原第 line 行被后移后的新位置）
    next_line = insert_pos + insert_count
    if next_line < new_total:
        diff_parts.append(f"  {next_line + 1} > {truncate_line(lines[next_line])}")
    diff_text = "\n".join(diff_parts)

    return (
        f"成功插入：已在第 {line} 行前插入了 {insert_count} 行内容。"
        f"文件从 {total_lines} 行变为 {new_total} 行。"
        f"{format_backup_info(resolved, history_number)}\n\n"
        f"{diff_text}"
    )


# ── 12. file_tools_delete_lines ───────────────────────────


def file_tools_delete_lines(
    path: str,
    start_line: int,
    end_line: int,
    encoding: str = "auto",
    line_separator: Literal["auto", "\\n", "\\r\\n"] = "auto",
) -> str:
    """删除文件中指定行区间的文本。修改前自动备份。返回时显示 +/- diff 格式预览（前一行上下文 + 被删行 + 后一行上下文），不带 + 组。写回时 \\r\\n/\\r 自动统一为 \\n。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。文件不存在时报错。
        start_line: 起始行号，1-based，包含。最小值为 1。超出文件总行数时报错。
        end_line: 结束行号，1-based，包含。必须 >= start_line。超出文件总行数时取到文件末尾。
        encoding: 文件编码。auto=自动检测（默认），也可指定编码名称。
        line_separator: 行结束符控制。auto=按操作系统自动处理（默认），\\n=Unix 风格 LF，\\r\\n=Windows 风格 CRLF。
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return format_error("删除行", f"文件「{resolved}」不存在")
    if start_line < 1 or end_line < 1:
        return format_error("删除行", f"行号必须 >= 1")
    if start_line > end_line:
        return format_error("删除行", f"起始行号 {start_line} 大于结束行号 {end_line}")

    history_number = backup_file(resolved)
    if history_number is None:
        return format_error("删除行", "备份原文件失败。因为获取会话文件路径失败。")

    try:
        lines, resolved_encoding = read_file_lines(resolved, encoding)
    except Exception as e:
        return format_error("删除行", f"读取文件时出错：{e}")

    total_lines = len(lines)
    if start_line > total_lines:
        return format_error("删除行", f"起始行号 {start_line} 超出文件范围（共 {total_lines} 行）")

    old_lines = lines.copy()
    actual_start = max(0, start_line - 1)
    actual_end = min(end_line, total_lines)
    del lines[actual_start:actual_end]

    # 解析 line_separator
    newline_map = {"auto": None, "\\n": "\n", "\\r\\n": "\r\n"}
    nl = newline_map.get(line_separator, None)

    try:
        _write_file(resolved, "\n".join(lines), resolved_encoding, newline=nl)
    except Exception as e:
        return format_error("删除行", f"写入文件时出错：{e}")

    new_total = len(lines)

    # 构建 +/- diff 预览
    diff_parts = []
    # 前一行上下文（按旧行号）
    if actual_start > 0:
        diff_parts.append(f"  {actual_start} > {truncate_line(old_lines[actual_start - 1])}")
    # - 组：被删除的行（按旧行号）
    for i in range(actual_start, actual_end):
        diff_parts.append(f"- {i + 1} > {truncate_line(old_lines[i])}")
    # 后一行上下文（按新行号，即删除后该位置的行）
    if actual_start < new_total:
        diff_parts.append(f"  {actual_start + 1} > {truncate_line(lines[actual_start])}")
    diff_text = "\n".join(diff_parts)

    summary = f"成功删除：已删除第 {start_line}~{end_line} 行（共 {actual_end - actual_start} 行）。文件从 {total_lines} 行变为 {new_total} 行。{format_backup_info(resolved, history_number)}"
    return "\n".join([summary, "", diff_text])


# ── 13. file_tools_replace ────────────────────────────────


def file_tools_replace(
    path: str,
    old_text: str,
    new_text: str,
    start_line: int = 1,
    end_line: Optional[int] = None,
    count: int = 1,
    encoding: str = "auto",
    dry_run: bool = False,
    line_separator: Literal["auto", "\\n", "\\r\\n"] = "auto",
) -> str:
    """精确子串查找替换（str.replace），支持跨行匹配。修改前自动备份。old_text 和 new_text 均不做转义处理——传入真实换行符即可跨行匹配。提供 dry_run 模式预览替换结果而不实际修改。返回时附带 unified diff 格式的差异预览。写回时 \\r\\n/\\r 自动统一为 \\n。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。文件不存在时报错。
        old_text: 要查找的文本，精确字串匹配。不做正则转义，传入真实换行符 \\n 即可跨行匹配。不能为空。
        new_text: 替换成的文本。不做转义处理，与 old_text 的匹配方式一致。
        start_line: 搜索起始行号，1-based，包含。默认 1。最小值为 1，超出文件行数时报错。
        end_line: 搜索结束行号，1-based，包含。默认 None=文件末尾。必须 >= start_line。
        count: 替换次数，默认 1。每次调用只替换第一个匹配，避免意外替换过多。必须 >= 1。
        encoding: 文件编码。auto=自动检测（默认），也可指定编码名称。
        dry_run: 预览模式。true=只统计匹配数量并显示模拟结果，不实际修改文件。false=实际执行替换（默认）。
        line_separator: 行结束符控制。auto=按操作系统自动处理（默认），\\n=Unix 风格 LF，\\r\\n=Windows 风格 CRLF。
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return format_error("替换", f"文件「{resolved}」不存在")

    if not old_text:
        return format_error("替换", "old_text 不能为空字符串")

    if count == 0:
        return format_error("替换", f"count 参数值 {count} 不合法。count=-1 表示替换所有匹配，count>=1 表示替换指定数量。")
    if count < -1:
        return format_error("替换", f"count 参数值 {count} 不合法。负数值仅支持 -1（替换所有匹配）。")

    try:
        lines, resolved_encoding = read_file_lines(resolved, encoding)
    except Exception as e:
        return format_error("替换", f"读取文件时出错：{e}")

    total_lines = len(lines)
    if start_line < 1:
        return format_error("替换", f"起始行号 {start_line} 不合法")

    actual_start = start_line - 1
    if actual_start >= total_lines:
        return format_error("替换", f"起始行号 {start_line} 超出文件范围（共 {total_lines} 行）")

    actual_end = end_line if end_line is not None else total_lines
    actual_end = min(actual_end, total_lines)
    if actual_end < actual_start:
        actual_end = actual_start

    # 拼接搜索范围（跨行匹配）
    range_lines = lines[actual_start:actual_end]
    range_content = "\n".join(range_lines)

    # 统计匹配次数
    match_count = range_content.count(old_text)
    if match_count == 0:
        return (
            f"替换失败，因为在「{resolved}」第 {start_line}~{actual_end} 行范围内"
            f"未找到匹配「{old_text}」的内容。"
        )

    if count == -1:
        effective_count = match_count
    else:
        effective_count = min(count, match_count)

    if dry_run:
        return (
            f"⚠️ dry_run 模式 — 以下为模拟修改结果，未实际修改文件。\n\n"
            f"模拟替换：在「{resolved}」第 {start_line}~{actual_end} 行范围内"
            f"将替换 {effective_count} 处（共匹配到 {match_count} 处）。"
        )

    # 备份
    history_number = backup_file(resolved)
    if history_number is None:
        return format_error("替换", "备份原文件失败。因为获取会话文件路径失败。")

    # 执行替换（跨行匹配）
    new_range = range_content.replace(old_text, new_text, effective_count)

    # 替换回 lines
    new_lines = lines.copy()
    new_range_lines = new_range.split("\n")
    new_lines[actual_start:actual_end] = new_range_lines

    # 解析 line_separator
    newline_map = {"auto": None, "\\n": "\n", "\\r\\n": "\r\n"}
    nl = newline_map.get(line_separator, None)

    # 写入文件
    try:
        _write_file(resolved, "\n".join(new_lines), resolved_encoding, newline=nl)
    except Exception as e:
        return format_error("替换", f"写入文件时出错：{e}")

    # 生成 diff 预览（difflib.unified_diff, n=1）
    import difflib

    original_with_nl = [l + '\n' for l in lines]
    modified_with_nl = [l + '\n' for l in new_lines]

    diff = difflib.unified_diff(
        original_with_nl,
        modified_with_nl,
        fromfile='original',
        tofile='modified',
        n=1,
    )
    diff_text = ''.join(diff)

    new_total = len(new_lines)
    return (
        f"成功替换：在「{resolved}」第 {start_line}~{actual_end} 行范围内"
        f"替换了 {effective_count} 处。文件从 {total_lines} 行变为 {new_total} 行。"
        f"{format_backup_info(resolved, history_number)}\n\n"
        f"{diff_text}"
    )


# ── 14. file_tools_regex_replace ──────────────────────────


def file_tools_regex_replace(
    path: str,
    pattern: str,
    replacement: str,
    start_line: int = 1,
    end_line: Optional[int] = None,
    start: int = 1,
    count: int = 1,
    encoding: str = "auto",
    dry_run: bool = False,
    line_separator: Literal["auto", "\\n", "\\r\\n"] = "auto",
) -> str:
    """正则替换文件内容（re.finditer + 从后往前替换），支持跨行匹配。修改前自动备份。从后往前逐个替换，避免偏移漂移。支持 \\1、\\g<name> 等反向引用。提供 dry_run 模式预览。返回时附带 unified diff 格式的差异预览。写回时 \\r\\n/\\r 自动统一为 \\n。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。文件不存在时报错。
        pattern: 正则表达式，Python re 语法。拼接行范围后整体匹配，支持跨行匹配。不能为空字符串。
        replacement: 替换字符串，支持 \\1、\\g<name> 等反向引用。Python re.sub 的 expand 语义。
        start_line: 搜索起始行号，1-based，包含。默认 1。最小值为 1，超出文件行数时报错。
        end_line: 搜索结束行号，1-based，包含。默认 None=文件末尾。必须 >= start_line。
        start: 从第几个匹配开始替换，1-based。默认 1。最小值为 1，超出匹配总数时报错。
        count: 替换次数。1=只替换第 1 个（默认），-1=替换全部匹配。传 0 报错。
        encoding: 文件编码。auto=自动检测（默认），也可指定编码名称。
        dry_run: 预览模式。true=只统计匹配数量并显示模拟结果，不实际修改文件。false=实际执行替换（默认）。
        line_separator: 行结束符控制。auto=按操作系统自动处理（默认），\\n=Unix 风格 LF，\\r\\n=Windows 风格 CRLF。
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return format_error("正则替换", f"文件「{resolved}」不存在")

    if not pattern:
        return format_error("正则替换", "pattern 不能为空字符串。请传入有效的正则表达式。")

    try:
        compiled = re_module.compile(pattern)
    except re_module.error as e:
        return format_error("正则替换", f"正则表达式语法错误：{e}")

    try:
        lines, resolved_encoding = read_file_lines(resolved, encoding)
    except Exception as e:
        return format_error("正则替换", f"读取文件时出错：{e}")

    # ── 参数校验 ──────────────────────────────────────────

    total_lines = len(lines)

    if start < 1:
        return format_error("正则替换", f"start 参数值 {start} 不合法。start 表示「从第几个匹配开始替换」，最小值为 1。")

    if count == 0:
        return format_error("正则替换", "count 参数值 0 不合法。count=-1 表示替换所有匹配，count>=1 表示替换指定数量。")
    if count < -1:
        return format_error("正则替换", f"count 参数值 {count} 不合法。负数值仅支持 -1（替换所有匹配）。")

    if start_line < 1:
        return format_error("正则替换", f"start_line 参数值 {start_line} 不合法。行号从 1 开始，最小值为 1。")
    if end_line is not None and end_line < 1:
        return format_error("正则替换", f"end_line 参数值 {end_line} 不合法。行号从 1 开始，最小值为 1。")
    if end_line is not None and end_line < start_line:
        return format_error("正则替换", f"end_line ({end_line}) 小于 start_line ({start_line})，参数矛盾。")
    if start_line > total_lines:
        return format_error("正则替换", f"start_line 参数值 {start_line} 超出文件范围。文件共 {total_lines} 行。")

    actual_start = start_line - 1
    actual_end = min(end_line or total_lines, total_lines)

    # 拼接行范围（跨行匹配）
    range_lines = lines[actual_start:actual_end]
    range_content = "\n".join(range_lines)

    # 收集所有匹配
    all_matches = list(compiled.finditer(range_content))
    total_matches = len(all_matches)

    if total_matches == 0:
        return (
            f"正则替换失败，因为在「{resolved}」第 {start_line}~{actual_end} 行范围内"
            f"未找到匹配「{pattern}」的内容。"
        )

    # 计算要替换的范围（从后往前）
    skip = start - 1
    if skip >= total_matches:
        return format_error("正则替换", f"start 参数值 {start} 超出匹配总数（共 {total_matches} 个匹配）。")

    if count == -1:
        effective_matches = all_matches[skip:]
    else:
        effective_matches = all_matches[skip:skip + count]

    if not effective_matches:
        return f"正则替换失败，因为从第 {start} 个匹配开始，剩余匹配数不足。"

    replace_count = len(effective_matches)

    if dry_run:
        return (
            f"⚠️ dry_run 模式 — 以下为模拟修改结果，未实际修改文件。\n\n"
            f"模拟替换：\n"
            f"  匹配到 {total_matches} 处，将替换 {replace_count} 处。"
        )

    history_number = backup_file(resolved)
    if history_number is None:
        return format_error("正则替换", "备份原文件失败。因为获取会话文件路径失败。")

    # 从后往前替换，避免偏移漂移
    old_range = range_content
    for m in reversed(effective_matches):
        range_content = range_content[:m.start()] + m.expand(replacement) + range_content[m.end():]

    # 替换回 lines
    new_lines = lines.copy()
    new_lines[actual_start:actual_end] = range_content.split("\n")

    # 解析 line_separator
    newline_map = {"auto": None, "\\n": "\n", "\\r\\n": "\r\n"}
    nl = newline_map.get(line_separator, None)

    try:
        _write_file(resolved, "\n".join(new_lines), resolved_encoding, newline=nl)
    except Exception as e:
        return format_error("正则替换", f"写入文件时出错：{e}")

    # 生成 unified diff 预览
    import difflib
    original_with_nl = [l + '\n' for l in lines]
    modified_with_nl = [l + '\n' for l in new_lines]
    diff = difflib.unified_diff(
        original_with_nl,
        modified_with_nl,
        fromfile='original',
        tofile='modified',
        n=1,
    )
    diff_text = ''.join(diff)

    new_total = len(new_lines)
    return (
        f"成功替换了 {replace_count} 处。文件从 {total_lines} 行变为 {new_total} 行。"
        f"{format_backup_info(resolved, history_number)}\n\n"
        f"{diff_text}"
    )
# ── 15. file_tools_indent_lines ──────────────────────────


def file_tools_indent_lines(
    path: str,
    start_line: int = 1,
    end_line: Optional[int] = None,
    mode: str = "expand",
    count: int = 4,
    char: str = " ",
    line_separator: Literal["auto", "\\n", "\\r\\n"] = "auto",
    encoding: str = "auto",
) -> str:
    """调整文件中指定行范围的行首缩进，支持增加（expand）和减少（shrink）两种模式。修改前自动备份。shrink 模式最多删除到行首非空白字符为止，不会删除非空白内容。返回时显示 +/- diff 格式预览（只显示有变化的行）。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。文件不存在时报错。
        start_line: 起始行号，1-based，包含。默认 1。最小值为 1，超出文件行数时报错。
        end_line: 结束行号，1-based，包含。默认 None=文件末尾。必须 >= start_line。
        mode: 缩进模式。expand=增加缩进（默认），shrink=减少缩进。shrink 时最多删除到行首第一个非空白字符。
        count: 添加或删除的空白字符数量。默认 4。必须 >= 0。
        char: 填充字符。默认空格（' '），也可传 '\\t' 使用制表符。仅 expand 模式使用。
        line_separator: 行结束符控制。auto=按操作系统自动处理（默认），\\n=Unix 风格 LF，\\r\\n=Windows 风格 CRLF。
        encoding: 文件编码。auto=自动检测（默认），也可指定编码名称。
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return format_error("缩进调整", f"文件「{resolved}」不存在")
    if start_line < 1:
        return format_error("缩进调整", f"起始行号 {start_line} 不合法")
    if mode not in ("expand", "shrink"):
        return format_error("缩进调整", f"模式 {mode} 不合法，仅支持 expand 和 shrink")
    if count < 0:
        return format_error("缩进调整", f"数量 {count} 不合法，必须 >= 0")
    if not char:
        return format_error("缩进调整", "填充字符不能为空")

    try:
        lines, resolved_encoding = read_file_lines(resolved, encoding)
    except Exception as e:
        return format_error("缩进调整", f"读取文件时出错：{e}")

    total_lines = len(lines)
    if total_lines == 0:
        return "缩进调整失败，因为文件为空。"
    if start_line > total_lines:
        return format_error("缩进调整", f"起始行号 {start_line} 超出文件范围（共 {total_lines} 行）")

    actual_start = start_line - 1
    actual_end = min(end_line or total_lines, total_lines)

    changes: List[Tuple[int, str, str]] = []
    for i in range(actual_start, actual_end):
        old_line = lines[i]
        if mode == "expand":
            lines[i] = char * count + old_line
        else:  # shrink
            stripped = old_line.lstrip()
            leading = len(old_line) - len(stripped)
            remove = min(count, leading)
            lines[i] = old_line[remove:]

        if lines[i] != old_line:
            changes.append((i + 1, old_line, lines[i]))

    if not changes:
        return "缩进调整失败，因为没有行被修改。"

    history_number = backup_file(resolved)
    if history_number is None:
        return format_error("缩进调整", "备份原文件失败。因为获取会话文件路径失败。")

    # 根据 line_separator 选择 newline 参数
    newline_map = {"auto": None, "\\n": "\n", "\\r\\n": "\r\n"}
    nl = newline_map.get(line_separator, None)

    try:
        content = "\n".join(lines)
        with open(resolved, "w", encoding=resolved_encoding, newline=nl) as f:
            f.write(content)
    except Exception as e:
        return format_error("缩进调整", f"写入文件时出错：{e}")

    # 构建 diff 预览（先 - 后 + 分组）
    diff_parts = []
    for row_num, old, _ in changes:
        diff_parts.append(f"- {row_num} > {truncate_line(old)}")
    for row_num, _, new in changes:
        diff_parts.append(f"+ {row_num} > {truncate_line(new)}")
    diff_text = "\n".join(diff_parts)

    mode_text = "增加了" if mode == "expand" else "减少了"
    return (
        f"成功缩进：已对第 {start_line}~{actual_end} 行{mode_text} {count} 个缩进。"
        f"{format_backup_info(resolved, history_number)}\n\n"
        f"{diff_text}\n"
    )       f"{diff_text}\n"
    )