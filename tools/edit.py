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
from typing import Any, Dict, List, Optional, Tuple

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


def _write_file(path: str, content: str, encoding: str) -> None:
    """文本模式写入文件。"""
    with open(path, "w", encoding=encoding) as f:
        f.write(content)


# ── 9. file_tools_append ──────────────────────────────────


def file_tools_append(
    path: str,
    content: str,
    encoding: str = "auto",
) -> str:
    """追加内容到文件末尾。修改前自动备份。

    Args:
        path: 文件路径
        content: 追加内容，\\r\\n/\\r 自动统一为 \\n
        encoding: 编码，auto=自动检测
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

    try:
        with open(resolved, "a", encoding=resolved_encoding) as f:
            f.write(normalized)
    except Exception as e:
        return format_error("追加", f"写入文件时出错：{e}")

    lines, _ = read_file_lines(resolved, resolved_encoding)
    total_lines = len(lines)

    result_parts: List[str] = []
    preview_start = max(0, total_lines - 3)
    for i in range(preview_start, total_lines):
        result_parts.append(f"{i + 1}\t{truncate_line(lines[i])}")

    if result_parts:
        result_parts.append("")

    result_parts.append(f"成功追加：已在文件末尾追加了内容。文件共 {total_lines} 行。")
    result_parts.append(format_backup_info(resolved, history_number))
    return "\n".join(result_parts)


# ── 10. file_tools_replace_lines ──────────────────────────


def file_tools_replace_lines(
    path: str,
    start_line: int,
    end_line: int,
    content: str,
    encoding: str = "auto",
) -> str:
    """整段替换文件中的指定行区间（行数可增减）。修改前自动备份。

    Args:
        path: 文件路径
        start_line: 起始行号，1-based，范围 [1, EOF]
        end_line: 结束行号，1-based，范围 [start, EOF]
        content: 替换内容，含 \\n 拆成多行
        encoding: 编码，auto=自动检测
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

    try:
        _write_file(resolved, "\n".join(lines), resolved_encoding)
    except Exception as e:
        return format_error("替换行", f"写入文件时出错：{e}")

    new_total = len(lines)
    preview = _build_replace_preview(old_lines, lines, start_line - 1, actual_end, actual_end - actual_start)

    return "\n".join([
        preview,
        "",
        f"成功替换：已将第 {start_line}~{end_line} 行替换为 {len(new_lines_content)} 行新内容。文件共 {new_total} 行。",
        format_backup_info(resolved, history_number),
    ])


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
) -> str:
    """在指定行号前插入新内容。修改前自动备份。

    Args:
        path: 文件路径
        line: 插入位置（在 line 行之前插入），1-based
        content: 插入内容，含 \\n 拆成多行
        encoding: 编码，auto=自动检测
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
    lines[insert_pos:insert_pos] = insert_lines

    try:
        _write_file(resolved, "\n".join(lines), resolved_encoding)
    except Exception as e:
        return format_error("插入行", f"写入文件时出错：{e}")

    new_total = len(lines)
    return (
        f"成功插入：已在第 {line} 行前插入了 {insert_count} 行内容。"
        f"文件从 {total_lines} 行变为 {new_total} 行。"
        f"\n{format_backup_info(resolved, history_number)}"
    )


# ── 12. file_tools_delete_lines ───────────────────────────


def file_tools_delete_lines(
    path: str,
    start_line: int,
    end_line: int,
    encoding: str = "auto",
) -> str:
    """删除文件中的指定行区间。修改前自动备份。

    Args:
        path: 文件路径
        start_line: 起始行号，1-based，范围 [1, EOF]
        end_line: 结束行号，1-based，范围 [start, EOF]
        encoding: 编码，auto=自动检测
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

    try:
        _write_file(resolved, "\n".join(lines), resolved_encoding)
    except Exception as e:
        return format_error("删除行", f"写入文件时出错：{e}")

    # 预览
    parts = []
    show_start = max(0, actual_start - 2)
    show_end = min(total_lines, actual_end + 2)

    parts.append("─── 删除前 ───")
    for i in range(show_start, show_end):
        line_num = i + 1
        if actual_start <= i < actual_end:
            parts.append(f"{line_num}\t{truncate_line(old_lines[i])}（被删除）")
        else:
            parts.append(f"{line_num}\t{truncate_line(old_lines[i])}")

    if actual_start > show_start + 2:
        parts.insert(show_end - show_start, "<<省略>>")  # 修正插入位置

    parts.append("")
    parts.append("─── 删除后 ───")

    new_total = len(lines)
    for i in range(max(0, actual_start - 2), min(new_total, actual_start + (show_end - show_start) - 2)):
        new_line_num = start_line + (i - actual_start)
        parts.append(f"{new_line_num}\t{truncate_line(lines[i])}")

    if new_total > actual_start + (show_end - show_start) - 2:
        parts.append("<<省略>>")

    parts.append("")
    parts.append(
        f"成功删除：已删除第 {start_line}~{end_line} 行（共 {actual_end - actual_start} 行）。"
        f"文件从 {total_lines} 行变为 {new_total} 行。"
    )
    parts.append(format_backup_info(resolved, history_number))
    return "\n".join(parts)


# ── 13. file_tools_replace ────────────────────────────────


def file_tools_replace(
    path: str,
    old_text: str,
    new_text: str,
    start_line: int = 1,
    end_line: Optional[int] = None,
    start: int = 1,
    count: int = -1,
    encoding: str = "auto",
    dry_run: bool = False,
) -> str:
    """精确子串查找替换（str.replace，区分大小写）。修改前自动备份。

    Args:
        path: 文件路径
        old_text: 要查找的文本，精确匹配
        new_text: 替换成的文本
        start_line: 搜索起始行，1-based，默认1
        end_line: 搜索结束行，1-based，默认文件末尾
        start: 从第几个匹配开始替换，1-based，默认1
        count: 替换次数，-1=全部替换，默认
        encoding: 编码，auto=自动检测
        dry_run: true=只统计不修改
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return format_error("替换", f"文件「{resolved}」不存在")
    if start_line < 1:
        return format_error("替换", f"起始行号 {start_line} 不合法")

    try:
        lines, resolved_encoding = read_file_lines(resolved, encoding)
    except Exception as e:
        return format_error("替换", f"读取文件时出错：{e}")

    total_lines = len(lines)
    actual_start = max(0, start_line - 1)
    actual_end = min(end_line or total_lines, total_lines)

    if start < 1:
        return format_error("替换", f"start 参数值 {start} 不合法。start 表示「从第几个匹配开始替换」，最小值为 1。")

    total_matches = 0
    for i in range(actual_start, actual_end):
        total_matches += lines[i].count(old_text)

    if total_matches == 0:
        return (
            f"替换失败，因为在「{resolved}」第 {start_line}~{actual_end} 行范围内"
            f"未找到匹配「{old_text}」的内容。"
        )

    effective_start = start
    if count == -1:
        replace_count = total_matches - (effective_start - 1)
    else:
        replace_count = min(count, total_matches - (effective_start - 1))

    if replace_count <= 0:
        return f"替换失败，因为从第 {start} 个匹配开始，剩余匹配数不足。"

    if dry_run:
        return (
            f"⚠️ dry_run 模式 — 以下为模拟修改结果，未实际修改文件。\n\n"
            f"模拟替换：在「{resolved}」第 {start_line}~{actual_end} 行范围内"
            f"将替换 {total_matches} 处。"
        )

    history_number = backup_file(resolved)
    if history_number is None:
        return format_error("替换", "备份原文件失败。因为获取会话文件路径失败。")

    replaced = 0
    skip = effective_start - 1
    for i in range(actual_start, actual_end):
        if count != -1 and replaced >= replace_count:
            break
        line = lines[i]
        line_match_count = line.count(old_text)
        if line_match_count == 0:
            continue

        if skip >= line_match_count:
            skip -= line_match_count
            continue

        if skip > 0:
            pos = 0
            for _ in range(skip):
                pos = line.find(old_text, pos) + len(old_text)
            remaining = line[pos:]
            can_replace = replace_count - replaced
            replaced_in_line = min(can_replace, remaining.count(old_text))
            if replaced_in_line > 0:
                remaining = remaining.replace(old_text, new_text, replaced_in_line)
                replaced += replaced_in_line
            lines[i] = line[:pos] + remaining
            skip = 0
        else:
            need = replace_count - replaced
            lines[i] = line.replace(old_text, new_text, need)
            replaced += min(need, line_match_count)

    try:
        _write_file(resolved, "\n".join(lines), resolved_encoding)
    except Exception as e:
        return format_error("替换", f"写入文件时出错：{e}")

    return (
        f"成功替换：在「{resolved}」第 {start_line}~{actual_end} 行范围内"
        f"替换了 {replaced} 处。"
        f"\n{format_backup_info(resolved, history_number)}"
    )


# ── 14. file_tools_regex_replace ──────────────────────────


def file_tools_regex_replace(
    path: str,
    pattern: str,
    replacement: str,
    start_line: int = 1,
    end_line: Optional[int] = None,
    start: int = 1,
    count: int = -1,
    encoding: str = "auto",
    dry_run: bool = False,
) -> str:
    """正则替换文件内容（re.sub）。修改前自动备份。

    Args:
        path: 文件路径
        pattern: 正则表达式，Python re 语法
        replacement: 替换字符串，支持 \\1 / \\g<name> 等反向引用
        start_line: 搜索起始行，1-based，默认1
        end_line: 搜索结束行，1-based，默认文件末尾
        start: 从第几个匹配开始替换，1-based，默认1
        count: 替换次数，-1=全部替换，默认
        encoding: 编码，auto=自动检测
        dry_run: true=只统计不修改
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return format_error("正则替换", f"文件「{resolved}」不存在")

    try:
        compiled = re_module.compile(pattern)
    except re_module.error as e:
        return format_error("正则替换", f"正则表达式语法错误：{e}")

    try:
        lines, resolved_encoding = read_file_lines(resolved, encoding)
    except Exception as e:
        return format_error("正则替换", f"读取文件时出错：{e}")

    total_lines = len(lines)
    actual_start = max(0, start_line - 1)
    actual_end = min(end_line or total_lines, total_lines)

    if start < 1:
        return format_error("正则替换", f"start 参数值 {start} 不合法。start 表示「从第几个匹配开始替换」，最小值为 1。")

    total_matches = 0
    for i in range(actual_start, actual_end):
        total_matches += len(compiled.findall(lines[i]))

    if total_matches == 0:
        return (
            f"正则替换失败，因为在「{resolved}」第 {start_line}~{actual_end} 行范围内"
            f"未找到匹配「{pattern}」的内容。"
        )

    effective_start = start
    if count == -1:
        replace_count = total_matches - (effective_start - 1)
    else:
        replace_count = min(count, total_matches - (effective_start - 1))

    if replace_count <= 0:
        return f"正则替换失败，因为从第 {start} 个匹配开始，剩余匹配数不足。"

    if dry_run:
        return (
            f"⚠️ dry_run 模式 — 以下为模拟修改结果，未实际修改文件。\n\n"
            f"模拟替换：\n"
            f"  匹配到 {total_matches} 处，将替换 {replace_count} 处。"
        )

    history_number = backup_file(resolved)
    if history_number is None:
        return format_error("正则替换", "备份原文件失败。因为获取会话文件路径失败。")

    replaced = 0
    skip = effective_start - 1
    hit_limit = False

    def _replacer(m):
        nonlocal replaced, skip, hit_limit
        if skip > 0:
            skip -= 1
            return m.group(0)
        if count != -1 and replaced >= replace_count:
            hit_limit = True
            return m.group(0)
        replaced += 1
        return re_module.sub(compiled, replacement, m.group(0))

    for i in range(actual_start, actual_end):
        if hit_limit:
            break
        lines[i] = compiled.sub(_replacer, lines[i])

    try:
        _write_file(resolved, "\n".join(lines), resolved_encoding)
    except Exception as e:
        return format_error("正则替换", f"写入文件时出错：{e}")

    return (
        f"成功替换：\n"
        f"  匹配到 {total_matches} 处，成功替换了 {replaced} 处。"
        f"\n{format_backup_info(resolved, history_number)}"
    )
