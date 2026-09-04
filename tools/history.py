"""历史回滚工具。

包含：
- file_tools_undo: 恢复文件到历史版本
"""

import logging
import os
from datetime import datetime
from typing import Optional, Union

try:
    from ..backup.manager import get_history_count, list_history, restore_file
    from ..utils import format_error, make_error, make_success, parse_int, resolve_path
except ImportError:
    from backup.manager import get_history_count, list_history, restore_file
    from utils import format_error, make_error, make_success, parse_int, resolve_path

logger = logging.getLogger(__name__)


# ── 20. file_tools_undo ───────────────────────────────────


def file_tools_undo(
    path: str,
    history_number: Union[int, str],
) -> str:
    """将文件恢复到指定历史版本。从 workspace 的 file_tools_data/history 备份目录中读取备份覆盖写回。不触发新的备份（即恢复操作本身不会产生新的历史版本）。恢复前建议先用 file_tools_history 查看可用版本列表。history_number=1 为最旧版本，数字越大越新。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。文件不存在或该文件没有历史版本时返回提示。
        history_number: 历史版本号。1=最旧版本，数字越大版本越新。建议先用 file_tools_history 查看可用的版本列表。超出范围时报错提示。支持整数或十进制数字字符串。
    """
    resolved = resolve_path(path)

    history_number, err = parse_int(history_number, "history_number")
    if err:
        return make_error("恢复", err)

    if not os.path.isfile(resolved):
        return make_error("恢复", f"文件「{resolved}」不存在")

    # 检查历史版本是否存在
    total = get_history_count(resolved)
    if total == 0:
        return make_error(
            f"恢复失败，因为文件「{resolved}」没有历史版本。"
            f"修改类工具（如 file_tools_append、file_tools_replace_lines 等）"
            f"会自动创建备份。"
        )

    if history_number < 1 or history_number > total:
        return make_error(
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
        return make_error("恢复", f"历史版本 #{history_number} 文件损坏或不可读")

    time_str = f"（创建于 {created_at}）" if created_at else ""
    return make_success(f"已恢复「{resolved}」到历史版本 #{history_number}{time_str}。")
