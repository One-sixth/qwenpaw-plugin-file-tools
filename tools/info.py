"""信息读取类工具。

包含：
- file_tools_listdir: 列出目录内容（纯文本/Markdown）
- file_tools_info: 查看文件元数据（JSON）
- file_tools_guess: 猜测文件类型（JSON）
- file_tools_diff: 文件差异对比（unified diff）
- file_tools_history: 查看文件历史版本（JSON）
"""

import csv
import difflib
import io
import json
import logging
import os
import stat
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

try:
    from ..backup.manager import list_history as _list_history
    from ..utils import (
        CSV_FIELD_TRUNCATE,
        DEFAULT_MAX_CHARS,
        format_csv,
        format_error,
        guess_file_type,
        make_error,
        make_result,
        make_success,
        parse_int,
        read_file_content,
        resolve_path,
    )
except ImportError:
    from backup.manager import list_history as _list_history
    from utils import (
        CSV_FIELD_TRUNCATE,
        DEFAULT_MAX_CHARS,
        format_csv,
        format_error,
        guess_file_type,
        make_error,
        make_result,
        make_success,
        parse_int,
        read_file_content,
        resolve_path,
    )

logger = logging.getLogger(__name__)


# ── 1. file_tools_listdir ─────────────────────────────────


def file_tools_listdir(
    path: str,
    recursive: Union[int, str] = 1,
    columns: Optional[List[str]] = None,
    absolute: bool = False,
    start: Union[int, str] = 1,
    count: Union[int, str] = 500,
    sort_by: str = "name",
    ascending: bool = True,
) -> str:
    """列出目录内容。支持递归遍历、自定义属性列、排序和分页。无 columns 时返回纯文本列表（一行一文件），有 columns 时返回 Markdown 表格。如果发现文件超过 10000条，将只能看到前10000条文件，更多文件条目需要用其他方法获取。

    Args:
        path: 目录路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        recursive: 递归深度。1=仅当前目录（默认），2=包含一层子目录，-1=无限递归。如果发现文件超过 10000条，将只能看到前10000条文件，更多文件条目需要用其他方法获取。支持整数或十进制数字字符串。
        columns: 额外属性列的列表。可选值：size（字节数）、permissions（Unix 风格权限字符串）、type（file/directory/symlink）、modified_at（最后修改时间）、created_at（创建时间）、extension（小写扩展名）。为空时不显示属性列。
        absolute: 路径显示模式。False=相对路径（默认，以目标目录为根），True=绝对路径。
        start: 起始序号，1-based。从第几个文件开始显示，默认 1。超出文件总数时返回「没有更多文件」提示。支持整数或十进制数字字符串。
        count: 最多返回的文件数，默认 500。范围 1~500，超出时报错。支持整数或十进制数字字符串。
        sort_by: 排序字段。name=按文件名排序（默认，大小写不敏感），也可按 size、permissions、type、modified_at、created_at、extension 排序。
        ascending: 排序方向。True=升序排列（默认），False=降序排列。
    """
    # ── 参数校验 ──
    recursive, err = parse_int(recursive, "recursive")
    if err:
        return make_error("列出目录", err)
    start, err = parse_int(start, "start")
    if err:
        return make_error("列出目录", err)
    count, err = parse_int(count, "count")
    if err:
        return make_error("列出目录", err)

    if recursive not in (1, 2, -1):
        return make_error(
            f"列出目录失败，因为 recursive 参数值 {recursive} 不合法。"
            f"合法值为：1（当前目录）、2（包含一层子目录）、-1（递归）。"
        )

    resolved = resolve_path(path)
    if not os.path.isdir(resolved):
        return make_error(
            f"列出目录失败，因为路径「{resolved}」不存在或不是一个目录。"
        )

    if start < 1:
        return make_error(
            f"列出目录失败，因为 start 参数值 {start} 不合法。"
            f"start 表示「从第几个文件开始显示」，最小值为 1。"
        )

    if count < 1 or count > 500:
        return make_error(
            f"列出目录失败，因为 count 参数值 {count} 不合法。"
            f"count 范围为 1~500。"
        )

    valid_sort = {"name", "size", "permissions", "type", "modified_at", "created_at", "extension"}
    if sort_by not in valid_sort:
        return make_error(
            f"列出目录失败，因为 sort_by 参数值「{sort_by}」不合法。"
            f"合法值为：{', '.join(sorted(valid_sort))}。"
        )

    # ── 确定需要收集的列 ──
    columns = columns or []
    valid_columns = {"size", "permissions", "type", "modified_at", "created_at", "extension"}
    extra_columns = [c for c in columns if c in valid_columns]

    # 排序所需的列（sort_by 不是 name 时，需要在 scan 时额外收集）
    gather_set = set(extra_columns)
    if sort_by != "name" and sort_by in valid_columns:
        gather_set.add(sort_by)

    # ── 扫描 ──
    rows: List[Dict[str, Any]] = []
    file_count = 0
    max_files = 10000

    def _scan(dir_path: str, current_depth: int, max_depth: int):
        nonlocal file_count
        try:
            items = os.listdir(dir_path)
        except PermissionError:
            return

        for item in items:
            if file_count >= max_files:
                return

            full_path = os.path.join(dir_path, item)

            if absolute:
                name = full_path
            else:
                name = os.path.relpath(full_path, resolved)

            row: Dict[str, Any] = {"name": name}

            try:
                st = os.stat(full_path)
            except OSError:
                continue

            for col in gather_set:
                if col == "size":
                    try:
                        row["size"] = st.st_size
                    except OSError:
                        row["size"] = 0
                elif col == "permissions":
                    row["permissions"] = stat.filemode(st.st_mode)
                elif col == "type":
                    if os.path.isdir(full_path):
                        row["type"] = "directory"
                    elif os.path.islink(full_path):
                        row["type"] = "symlink"
                    else:
                        row["type"] = "file"
                elif col == "modified_at":
                    row["modified_at"] = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                elif col == "created_at":
                    row["created_at"] = datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                elif col == "extension":
                    _, ext = os.path.splitext(item)
                    row["extension"] = ext.lower() if ext else ""

            rows.append(row)
            file_count += 1

            if current_depth < max_depth and os.path.isdir(full_path):
                _scan(full_path, current_depth + 1, max_depth)

    if recursive == 1:
        _scan(resolved, 1, 1)
    elif recursive == 2:
        _scan(resolved, 1, 2)
    elif recursive == -1:
        _scan(resolved, 1, 99999)

    if not rows:
        return make_success("（空目录，无文件）")

    # ── 排序 ──
    if sort_by == "name":
        rows.sort(key=lambda r: r["name"].lower(), reverse=not ascending)
    else:
        rows.sort(key=lambda r: r.get(sort_by, ""), reverse=not ascending)

    # ── 分页 ──
    total = len(rows)
    start_idx = start - 1
    if start_idx >= total:
        return make_success(f"（没有更多文件，共 {total} 个文件，当前从第 {start} 个开始）")

    end_idx = min(start_idx + count, total)
    page = rows[start_idx:end_idx]

    # ── 输出格式 ──
    if not extra_columns:
        # 纯文本列表
        output = "\n".join(row["name"] for row in page)
    else:
        # Markdown 表格
        fieldnames = ["name"] + extra_columns
        header = "| " + " | ".join(fieldnames) + " |"
        separator = "|" + "|".join("---" for _ in fieldnames) + "|"
        data_lines = []
        for row in page:
            data_lines.append("| " + " | ".join(str(row.get(col, "")) for col in fieldnames) + " |")
        output = header + "\n" + separator + "\n" + "\n".join(data_lines)

    # ── 尾部信息 ──
    end_display = start + len(page) - 1
    remaining = total - end_display
    if remaining > 0:
        output += f"\n\n当前列出的文件 {start}~{end_display}，后面还有 {remaining} 个文件。"

    if file_count >= max_files:
        output += "\n目标文件夹搜索文件超过10000条，当前可以通过翻页 获取前10000条文件信息。如需获取更多的文件条目，请尝试其他方法。\n"

    return make_success(output)


# ── 2. file_tools_info ────────────────────────────────────


def file_tools_info(
    path: str,
) -> str:
    """查看文件或目录的元数据，返回 JSON 格式。包含路径、大小、权限、创建时间和修改时间等信息。路径不存在时返回错误提示。

    Args:
        path: 文件或目录路径。相对路径相对于 workspace 目录，支持 ~ 展开。路径不存在时返回提示，请检查路径拼写。
    """
    resolved = resolve_path(path)
    if not os.path.exists(resolved):
        return make_error(format_error(
            "查看文件信息",
            f"路径「{resolved}」不存在",
            "请使用 file_tools_listdir 确认文件是否存在，或检查路径拼写是否正确。",
        ))

    try:
        st = os.stat(resolved)
    except OSError as e:
        return make_success(json.dumps({
            "path": resolved,
            "error": f"无法读取文件元数据: {e}",
        }, ensure_ascii=False))

    info: Dict[str, Any] = {
        "path": resolved,
        "exists": True,
        "size": st.st_size,
        "is_dir": os.path.isdir(resolved),
        "is_file": os.path.isfile(resolved),
        "is_link": os.path.islink(resolved),
        "permissions": stat.filemode(st.st_mode),
        "created_at": datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
        "modified_at": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }

    return make_success(json.dumps(info, ensure_ascii=False, indent=2))


# ── 3. file_tools_guess ───────────────────────────────────


def file_tools_guess(
    path: str,
) -> str:
    """猜测文件类型和编码，返回 JSON 格式。根据文件魔数（magic number）检测类型，文本自动检测编码。目录直接返回 type 为 directory。检测库未安装时降级处理。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。如果是目录直接返回 type=directory，不执行魔数检测。
    """
    resolved = resolve_path(path)

    if not os.path.exists(resolved):
        return make_success(json.dumps({
            "path": resolved,
            "error": "文件不存在",
        }, ensure_ascii=False))

    if os.path.isdir(resolved):
        return make_success(json.dumps({
            "path": resolved,
            "type": "directory",
            "subtype": "directory",
            "encoding": None,
            "confidence": 1.0,
        }, ensure_ascii=False))

    result = guess_file_type(resolved)
    result["path"] = resolved
    return make_success(json.dumps(result, ensure_ascii=False, indent=2))


# ── 4. file_tools_diff ────────────────────────────────────


def file_tools_diff(
    path_a: str,
    path_b: str,
    start: Union[int, str] = 1,
    count: Union[int, str] = 10,
    max_chars: Union[int, str] = 2048,
) -> str:
    """对比两个文件的差异，返回 unified diff 格式。支持 hunk 分页，可指定从第几个差异块开始显示。文件相同时返回「文件相同，没有差异。」

    Args:
        path_a: 旧文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        path_b: 新文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        start: 起始 hunk 序号，1-based。从第几个差异块开始显示，最小值为 1。支持整数或十进制数字字符串。
        count: 最多显示多少个差异块，默认 10。支持整数或十进制数字字符串。
        max_chars: 返回内容总字符上限，默认 2048。超过时自动截断。支持整数或十进制数字字符串。
    """
    resolved_a = resolve_path(path_a)
    resolved_b = resolve_path(path_b)

    start, err = parse_int(start, "start")
    if err:
        return make_error("对比", err)
    count, err = parse_int(count, "count")
    if err:
        return make_error("对比", err)
    max_chars, err = parse_int(max_chars, "max_chars")
    if err:
        return make_error("对比", err)

    if not os.path.isfile(resolved_a):
        return make_error(f"对比失败，因为找不到旧文件「{resolved_a}」。请确认路径是否正确。")
    if not os.path.isfile(resolved_b):
        return make_error(f"对比失败，因为找不到新文件「{resolved_b}」。请确认路径是否正确。")

    try:
        content_a, _ = read_file_content(resolved_a)
        content_b, _ = read_file_content(resolved_b)
    except Exception as e:
        return make_error(f"对比失败，因为读取文件时出错：{e}。")

    lines_a = content_a.splitlines(keepends=True)
    lines_b = content_b.splitlines(keepends=True)

    # 生成 unified diff
    diff_lines = list(
        difflib.unified_diff(
            lines_a,
            lines_b,
            fromfile=resolved_a,
            tofile=resolved_b,
            lineterm="",
        )
    )

    # 按 hunk 分组
    hunks: List[List[str]] = []
    current_hunk: List[str] = []

    for line in diff_lines:
        if line.startswith("@@"):
            if current_hunk:
                hunks.append(current_hunk)
            current_hunk = [line]
        elif current_hunk:
            current_hunk.append(line)

    if current_hunk:
        hunks.append(current_hunk)

    if not hunks:
        return make_success("文件相同，没有差异。")

    # 分页
    total_hunks = len(hunks)
    if start < 1:
        return make_error("对比", f"start 参数值 {start} 不合法。start 表示「从第几个 hunk 开始显示」，最小值为 1")
    if count < 1:
        return make_error("对比", f"count 参数值 {count} 不合法。count 表示「最多显示多少个差异块」，最小值为 1")
    if start > total_hunks:
        return make_error("对比", f"start 参数值 {start} 超出差异块总数（共 {total_hunks} 个）。start 取值范围 1~{total_hunks}")
    end_idx = min(start - 1 + count, total_hunks)
    selected = hunks[start - 1 : end_idx]

    output_lines = [f"共有 {total_hunks} 个差异块，显示第 {start}~{end_idx} 个：\n"]
    for hunk in selected:
        output_lines.extend(hunk)
        output_lines.append("")

    result = "".join(output_lines)
    return make_success(make_result(result, max_chars))


# ── 5. file_tools_history ─────────────────────────────────


def file_tools_history(
    path: str,
) -> str:
    """查看文件的历史备份版本列表，返回 JSON 格式。包含每个历史版本的编号（history_number）和创建时间。文件没有历史版本时返回空列表。历史版本由修改类工具（append、replace_lines 等）在修改前自动创建。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。文件不存在时返回对应的错误信息。
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return make_success(json.dumps({
            "path": resolved,
            "error": "文件不存在",
        }, ensure_ascii=False))

    history = _list_history(resolved)

    return make_success(json.dumps({
        "path": resolved,
        "history": history,
    }, ensure_ascii=False, indent=2))
