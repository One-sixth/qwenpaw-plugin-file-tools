"""全量写入工具。

替代默认 write_file 的安全写入工具，支持自动备份和原子写入。
"""

import logging
import os
import shutil
from typing import Literal

try:
    from ..backup.manager import backup_file, get_last_backup_error
    from ..utils import (
        format_backup_info,
        format_error,
        normalize_newlines,
        resolve_path,
    )
except ImportError:
    from backup.manager import backup_file, get_last_backup_error
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
    line_separator: Literal["auto", "\\n", "\\r\\n"] = "auto",
) -> str:
    """写入文件内容，替代默认的 write_file。文件已存在时自动备份并覆盖（备份失败不阻塞写入），文件不存在时直接创建新文件。使用原子写入——先写 .temp_file 再 shutil.move 替换，避免写入中断导致文件损坏。备份后的文件可通过 file_tools_undo 恢复。返回字符数和行数统计。

    Args:
        path: 要写入的文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。文件已存在时自动备份，不存在时直接创建。
        content: 要写入的文本内容。\\r\\n 和 \\r 写入前自动统一为 \\n，避免文本模式二次转换。
        encoding: 文件编码，默认 utf-8。支持 utf-8、gbk 等 Python open() 支持的编码。
        line_separator: 行结束符控制。auto=按操作系统自动处理（Windows 上 \\n→\\r\\n），\\n=Unix 风格 LF，\\r\\n=Windows 风格 CRLF。
    """
    resolved = resolve_path(path)

    # line_separator 运行时校验（schema 层已拦截，此处双重保障）
    if line_separator not in ("auto", "\\n", "\\r\\n"):
        return format_error("写入", f"line_separator 参数值 {line_separator} 不合法，仅支持 auto、\\n、\\r\\n")

    # 统一换行符 \\r\\n/\\r → \\n
    normalized = normalize_newlines(content)

    # 统计字符数和行数
    if not normalized:
        char_count = 0
        line_count = 0
    else:
        char_count = len(normalized)
        line_count = len(normalized.split("\n"))

    # 文件已存在时先备份（备份失败则拒绝修改）
    history_number = None
    if os.path.isfile(resolved):
        history_number = backup_file(resolved)
        if history_number is None:
            error_detail = get_last_backup_error() or "未知原因"
            return format_error(
                "写入",
                f"备份原文件失败（{error_detail}）",
            )

    # 解析 line_separator（Literal 约束确保只传 auto / \\n / \\r\\n）
    newline: str | None = None  # auto → Python 默认行为（按平台转换）
    if line_separator == "\\n":
        newline = "\n"
    elif line_separator == "\\r\\n":
        newline = "\r\n"
    # else: auto → newline=None，Python 自动处理

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
        return f"成功写入文件，共 {char_count} 个字符（{line_count} 行）。"