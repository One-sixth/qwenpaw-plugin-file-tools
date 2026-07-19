"""历史回滚工具。

包含：
- file_tools_undo: 恢复文件到历史版本
"""

import logging
import os
from datetime import datetime
from typing import Optional

try:
    from ..backup.manager import get_history_count, list_history, restore_file
    from ..utils import format_error, resolve_path
except ImportError:
    from backup.manager import get_history_count, list_history, restore_file
    from utils import format_error, resolve_path

logger = logging.getLogger(__name__)


# ── 20. file_tools_undo ───────────────────────────────────


def file_tools_undo(
    path: str,
    history_number: int,
) -> str:
    """恢复文件到历史版本。

    从 `_file_tools/history/{编码目录}/{history_number}` 读回备份覆盖写回。
    不触发新的备份。

    Args:
        path: 文件路径
        history_number: 历史版本号（1=最旧，数字越大越新）

    Returns:
        纯文本结果
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return format_error("恢复", f"文件「{resolved}」不存在")

    # 检查历史版本是否存在
    total = get_history_count(resolved)
    if total == 0:
        return (
            f"恢复失败，因为文件「{resolved}」没有历史版本。"
            f"修改类工具（如 file_tools_append、file_tools_replace_lines 等）"
            f"会自动创建备份。"
        )

    if history_number < 1 or history_number > total:
        return (
            f"恢复失败，因为历史版本 #{history_number} 不存在，"
            f"文件「{resolved}」共有 {total} 个历史版本。"
            f"请先用 file_tools_history(path=\"{path}\") 查看可用的历史版本号。"
        )

    # 获取时间
    history = list_history(resolved)
    created_at = ""
    for h in history:
        if h["number"] == history_number:
            created_at = h["created_at"]
            break

    # 恢复
    if not restore_file(resolved, history_number):
        return format_error("恢复", f"历史版本 #{history_number} 文件损坏或不可读")

    time_str = f"（创建于 {created_at}）" if created_at else ""
    return f"已恢复「{resolved}」到历史版本 #{history_number}{time_str}。"
