"""历史备份管理。

在修改类工具执行前自动备份原文件，支持按版本恢复和查询历史。
"""

import json
import logging
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from ..utils import encode_path, get_session_dir
except ImportError:
    from utils import encode_path, get_session_dir

logger = logging.getLogger(__name__)

# 记录最后一次备份失败的原因（供工具函数输出具体错误信息）
_last_backup_error: str | None = None


def get_last_backup_error() -> str | None:
    """获取最后一次备份失败的原因。"""
    return _last_backup_error


def _get_backup_root() -> str:
    """获取备份根目录。

    通过 get_session_dir() 获取 QwenPaw 工作区中的会话路径。
    如果无法获取（如 QwenPaw 配置异常），get_session_dir() 会抛出
    RuntimeError 说明无法获取会话文件路径，由 backup_file() 捕获后
    返回 None，工具函数将显示错误提示。
    """
    return get_session_dir()


def _get_history_dir(path: str) -> str:
    """获取指定文件的历史备份目录。"""
    backup_root = _get_backup_root()
    encoded = encode_path(path)
    return os.path.join(backup_root, "history", encoded)


def _get_next_number(history_dir: str) -> int:
    """找到下一个可用的备份文件号。"""
    number = 1
    while os.path.exists(os.path.join(history_dir, str(number))):
        number += 1
    return number


def _update_files_json(backup_root: str, path: str, encoded: str) -> None:
    """更新 files.json 映射（仅用于人工查阅）。"""
    files_json = os.path.join(backup_root, "history", "files.json")
    try:
        mapping: Dict[str, str] = {}
        if os.path.exists(files_json):
            with open(files_json, "r", encoding="utf-8") as f:
                mapping = json.load(f)

        if encoded not in mapping:
            mapping[encoded] = path
            os.makedirs(os.path.dirname(files_json), exist_ok=True)
            with open(files_json, "w", encoding="utf-8") as f:
                json.dump(mapping, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("更新 files.json 失败: %s", e)


# ── 公开 API ──────────────────────────────────────────────


def backup_file(path: str) -> Optional[int]:
    """备份指定文件。"""
    global _last_backup_error
    _last_backup_error = None

    if not os.path.isfile(path):
        _last_backup_error = f"文件不存在: {path}"
        logger.warning("尝试备份不存在的文件: %s", path)
        return None

    try:
        history_dir = _get_history_dir(path)
    except RuntimeError as e:
        _last_backup_error = f"无法获取备份目录: {e}"
        logger.error("备份失败，无法获取备份目录: %s", e)
        return None

    os.makedirs(history_dir, exist_ok=True)

    number = _get_next_number(history_dir)
    dest = os.path.join(history_dir, str(number))

    try:
        shutil.copy2(path, dest)
    except Exception as e:
        _last_backup_error = f"复制文件失败: {e}"
        logger.error("备份文件失败 %s → %s: %s", path, dest, e)
        return None

    backup_root = _get_backup_root()
    encoded = encode_path(path)
    _update_files_json(backup_root, path, encoded)

    logger.info("已备份 %s → #%d", path, number)
    return number


def restore_file(path: str, history_number: int) -> bool:
    """将文件恢复到指定的历史版本。"""
    history_dir = _get_history_dir(path)
    backup_file = os.path.join(history_dir, str(history_number))

    if not os.path.isfile(backup_file):
        return False

    try:
        shutil.copy2(backup_file, path)
        logger.info("已恢复 %s ← #%d", path, history_number)
        return True
    except Exception as e:
        logger.error("恢复文件失败 %s ← #%d: %s", path, history_number, e)
        return False


def list_history(path: str) -> List[Dict[str, Any]]:
    """查询文件的历史版本列表。"""
    history_dir = _get_history_dir(path)
    if not os.path.isdir(history_dir):
        return []

    history: List[Dict[str, Any]] = []
    for entry in sorted(os.listdir(history_dir), key=lambda x: int(x)):
        backup_path = os.path.join(history_dir, entry)
        if os.path.isfile(backup_path):
            try:
                mtime = os.path.getmtime(backup_path)
                created_at = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                history.append({"number": int(entry), "created_at": created_at})
            except Exception:
                continue

    return history


def get_history_count(path: str) -> int:
    """获取文件历史版本总数。"""
    return len(list_history(path))
