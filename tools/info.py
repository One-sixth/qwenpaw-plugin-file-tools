"""信息读取类工具。

包含：
- file_tools_listdir: 列出目录内容（CSV）
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
from typing import Any, Dict, List, Optional

try:
    from ..backup.manager import list_history as _list_history
    from ..utils import (
        CSV_FIELD_TRUNCATE,
        DEFAULT_MAX_CHARS,
        format_csv,
        format_error,
        guess_file_type,
        make_result,
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
        make_result,
        read_file_content,
        resolve_path,
    )

logger = logging.getLogger(__name__)


# ── 1. file_tools_listdir ─────────────────────────────────


def file_tools_listdir(
    path: str,
    recursive: int = 1,
    columns: Optional[List[str]] = None,
) -> str:
    """列出目录内容，返回 CSV。

    Args:
        path: 目录路径
        recursive: 1=当前目录，2=当前+一层子目录，-1=无限递归
        columns: 额外属性列（size, permissions, type, modified_at, created_at, extension）

    Returns:
        CSV 格式字符串
    """
    # 参数校验
    if recursive not in (1, 2, -1):
        return (
            f"列出目录失败，因为 recursive 参数值 {recursive} 不合法。"
            f"合法值为：1（当前目录）、2（包含一层子目录）、-1（递归）。"
        )

    resolved = resolve_path(path)
    if not os.path.isdir(resolved):
        return (
            f"列出目录失败，因为路径「{resolved}」不存在或不是一个目录。"
            f"请使用 file_tools_info(path=\"{path}\") 确认路径是否正确。"
        )

    columns = columns or []

    # 支持的列名
    valid_columns = {"size", "permissions", "type", "modified_at", "created_at", "extension"}
    extra_columns = [c for c in columns if c in valid_columns]
    fieldnames = ["name"] + extra_columns

    rows: List[Dict[str, Any]] = []
    file_count = 0
    max_files = 10000

    def _scan(dir_path: str, current_depth: int, max_depth: int):
        nonlocal file_count
        try:
            items = sorted(os.listdir(dir_path), key=lambda x: (not os.path.isdir(os.path.join(dir_path, x)), x.lower()))
        except PermissionError:
            return

        for item in items:
            if file_count >= max_files:
                return

            full_path = os.path.join(dir_path, item)
            row: Dict[str, Any] = {"name": item}

            try:
                st = os.stat(full_path)
            except OSError:
                continue

            for col in extra_columns:
                if col == "size":
                    try:
                        row["size"] = st.st_size
                    except OSError:
                        row["size"] = 0
                elif col == "permissions":
                    row["permissions"] = stat.filemode(st.st_mode)
                elif col == "type":
                    if os.path.isdir(full_path):
                        row["type"] = "文件夹"
                    elif os.path.islink(full_path):
                        row["type"] = "链接"
                    else:
                        row["type"] = "文件"
                elif col == "modified_at":
                    row["modified_at"] = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                elif col == "created_at":
                    row["created_at"] = datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                elif col == "extension":
                    _, ext = os.path.splitext(item)
                    row["extension"] = ext.lower() if ext else ""

            rows.append(row)
            file_count += 1

            # 递归处理子目录
            if current_depth < max_depth and os.path.isdir(full_path):
                _scan(full_path, current_depth + 1, max_depth)

    if recursive == 1:
        _scan(resolved, 1, 1)
    elif recursive == 2:
        _scan(resolved, 1, 2)
    elif recursive == -1:
        _scan(resolved, 1, 99999)

    csv_output = format_csv(rows, fieldnames=fieldnames)

    if file_count >= max_files:
        csv_output += "\n结果过多，仅返回前 10000 条。如需缩小范围，请指定更具体的目录路径。\n"

    return csv_output


# ── 2. file_tools_info ────────────────────────────────────


def file_tools_info(
    path: str,
) -> str:
    """查看文件/目录元数据，返回 JSON。

    Args:
        path: 文件或目录路径

    Returns:
        JSON 字符串
    """
    resolved = resolve_path(path)
    exists = os.path.exists(resolved)

    info: Dict[str, Any] = {
        "path": resolved,
        "exists": exists,
    }

    if exists:
        try:
            st = os.stat(resolved)
            info["size"] = st.st_size
            info["is_dir"] = os.path.isdir(resolved)
            info["is_file"] = os.path.isfile(resolved)
            info["is_link"] = os.path.islink(resolved)
            info["permissions"] = stat.filemode(st.st_mode)
            info["created_at"] = datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            info["modified_at"] = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except OSError as e:
            return json.dumps({
                "path": resolved,
                "error": f"无法读取文件元数据: {e}",
            }, ensure_ascii=False)

    return json.dumps(info, ensure_ascii=False, indent=2)


# ── 3. file_tools_guess ───────────────────────────────────


def file_tools_guess(
    path: str,
) -> str:
    """猜测文件类型，返回 JSON。

    Args:
        path: 文件路径

    Returns:
        JSON 字符串
    """
    resolved = resolve_path(path)

    if not os.path.exists(resolved):
        return json.dumps({
            "path": resolved,
            "error": "文件不存在",
        }, ensure_ascii=False)

    if os.path.isdir(resolved):
        return json.dumps({
            "path": resolved,
            "type": "directory",
            "subtype": "directory",
            "encoding": None,
            "confidence": 1.0,
        }, ensure_ascii=False)

    result = guess_file_type(resolved)
    result["path"] = resolved
    return json.dumps(result, ensure_ascii=False, indent=2)


# ── 4. file_tools_diff ────────────────────────────────────


def file_tools_diff(
    path_a: str,
    path_b: str,
    start: int = 1,
    count: int = 10,
    max_chars: int = 2048,
) -> str:
    """文件差异对比，返回 unified diff 格式。

    Args:
        path_a: 旧文件路径
        path_b: 新文件路径
        start: 从第几个 hunk 开始（1-based）
        count: 最多显示多少个 hunk
        max_chars: 返回内容总字符上限

    Returns:
        unified diff 字符串
    """
    resolved_a = resolve_path(path_a)
    resolved_b = resolve_path(path_b)

    if not os.path.isfile(resolved_a):
        return f"对比失败，因为找不到旧文件「{resolved_a}」。请确认路径是否正确。"
    if not os.path.isfile(resolved_b):
        return f"对比失败，因为找不到新文件「{resolved_b}」。请确认路径是否正确。"

    try:
        content_a, _ = read_file_content(resolved_a)
        content_b, _ = read_file_content(resolved_b)
    except Exception as e:
        return f"对比失败，因为读取文件时出错：{e}。"

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
        return "文件相同，没有差异。"

    # 分页
    total_hunks = len(hunks)
    if start < 1:
        return format_error("对比", f"start 参数值 {start} 不合法。start 表示「从第几个 hunk 开始显示」，最小值为 1。")
    end_idx = min(start - 1 + count, total_hunks)
    selected = hunks[start - 1 : end_idx]

    output_lines = [f"共有 {total_hunks} 个差异块，显示第 {start}~{end_idx} 个：\n"]
    for hunk in selected:
        output_lines.extend(hunk)
        output_lines.append("")

    result = "".join(output_lines)
    return make_result(result, max_chars)


# ── 5. file_tools_history ─────────────────────────────────


def file_tools_history(
    path: str,
) -> str:
    """查看文件历史版本，返回 JSON。

    Args:
        path: 文件路径

    Returns:
        JSON 字符串
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return json.dumps({
            "path": resolved,
            "error": "文件不存在",
        }, ensure_ascii=False)

    history = _list_history(resolved)

    return json.dumps({
        "path": resolved,
        "history": history,
    }, ensure_ascii=False, indent=2)
