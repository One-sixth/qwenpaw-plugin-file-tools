"""全量写入工具。

替代默认 write_file 的安全写入工具，支持自动备份和原子写入。
"""

import logging
import os
import shutil

try:
    from ..backup.manager import backup_file
    from ..utils import (
        format_backup_info,
        format_error,
        normalize_newlines,
        resolve_path,
    )
except ImportError:
    from backup.manager import backup_file
    from utils import (
        format_backup_info,
        format_error,
        normalize_newlines,
        resolve_path,
    )

logger = logging.getLogger(__name__)


def file_tools_write(
    path: str,
    content: str,
    encoding: str = "utf-8",
    line_separator: str = "auto",
) -> str:
    """写入文件内容。如果文件已存在，自动备份后覆盖写入。
    如果文件不存在，直接创建新文件。

    使用原子写入（先写临时文件再 os.replace 替换），
    避免写入中断导致文件损坏。

    Args:
        path: 文件路径
        content: 写入内容，\\r\\n/\\r 自动统一为 \\n
        encoding: 编码，默认 utf-8
        line_separator: 行结束符，auto=按平台自动处理，\\n=Unix风格，\\r\\n=Windows风格
    """
    resolved = resolve_path(path)

    # 统一换行符 \\r\\n/\\r → \\n
    normalized = normalize_newlines(content)

    # 统计字符数和行数
    if not normalized:
        char_count = 0
        line_count = 0
    else:
        char_count = len(normalized)
        line_count = len(normalized.split("\n"))

    # 文件已存在时先备份（备份失败不阻塞写入，仅警告）
    history_number = None
    backup_warning = ""
    if os.path.isfile(resolved):
        history_number = backup_file(resolved)
        if history_number is None:
            backup_warning = "\n⚠️ 警告：备份原文件失败，但已直接覆盖写入。请手动确认是否需要备份。"

    # 解析 line_separator
    newline: str | None = None  # auto → Python 默认行为（按平台转换）
    if line_separator in ("\\n", "\n", "lf", "unix"):
        newline = "\n"
    elif line_separator in ("\\r\\n", "\r\n", "crlf", "windows"):
        newline = "\r\n"
    elif line_separator not in ("auto", None):
        supported = "auto | \\n | \\r\\n"
        return format_error(
            "写入",
            f"不支持的 line_separator 参数值「{line_separator}」",
            f" 支持的值：{supported}",
        )

    # 原子写入：先写 .temp 文件，再 shutil.move 替换
    tmp_path = resolved + ".temp_file"
    try:
        with open(tmp_path, "w", encoding=encoding, newline=newline) as f:
            f.write(normalized)
        shutil.move(tmp_path, resolved)
    except Exception as e:
        # 写入失败时清理临时文件
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return format_error("写入", f"写入文件时出错：{e}")

    # 构建返回消息
    if history_number is not None:
        return (
            f"成功写入文件，共 {char_count} 个字符（{line_count} 行）。\n"
            f"{format_backup_info(resolved, history_number)}"
        )
    else:
        msg = f"成功写入文件，共 {char_count} 个字符（{line_count} 行）。"
        if backup_warning:
            msg += backup_warning
        return msg