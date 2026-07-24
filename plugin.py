# -*- coding: utf-8 -*-
"""File Tools 插件入口。

注册 25 个文件操作工具到 QwenPaw Agent 工具箱。
"""

import logging

from qwenpaw.plugins.api import PluginApi
from .backup.manager import cleanup_old_backups

from .tools.info import (
    file_tools_listdir,
    file_tools_info,
    file_tools_guess,
    file_tools_diff,
    file_tools_history,
)
from .tools.read import (
    file_tools_read_lines,
    file_tools_read_block,
    file_tools_regex,
)
from .tools.edit import (
    file_tools_append,
    file_tools_replace_lines,
    file_tools_insert_lines,
    file_tools_delete_lines,
    file_tools_replace,
    file_tools_regex_replace,
    file_tools_indent_lines,
)
from .tools.safe import (
    file_tools_copy,
    file_tools_move,
    file_tools_trash,
    file_tools_trash_undo,
    file_tools_mkdir,
)
from .tools.history import file_tools_undo
from .tools.write import file_tools_write
from .tools.bytes import (
    file_tools_read_bytes,
    file_tools_write_bytes,
    file_tools_find_bytes,
    file_tools_replace_bytes,
)

logger = logging.getLogger(__name__)


class FileToolsPlugin:
    """File Tools 插件主类。"""

    def register(self, api: PluginApi):
        logger.info("注册 File Tools 插件（25 个工具）...")

        # ── 信息读取类 ──
        api.register_tool(
            tool_name="file_tools_listdir",
            tool_func=file_tools_listdir,
            description="列出目录内容，支持递归和自定义列。",
            icon="📂",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_info",
            tool_func=file_tools_info,
            description="查看文件/目录的详细元数据（JSON）。",
            icon="ℹ️",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_guess",
            tool_func=file_tools_guess,
            description="猜测文件类型和编码（JSON）。",
            icon="🔍",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_diff",
            tool_func=file_tools_diff,
            description="对比两个文件差异，返回 unified diff。",
            icon="📋",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_history",
            tool_func=file_tools_history,
            description="查看文件的历史版本列表（JSON）。",
            icon="🕐",
            tool_type="file",
            target_param="path",
            enabled=True,
        )

        # ── 文本读取类 ──
        api.register_tool(
            tool_name="file_tools_read_lines",
            tool_func=file_tools_read_lines,
            description="按行读取文本文件，支持行号显示和截断提示。",
            icon="📖",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_read_block",
            tool_func=file_tools_read_block,
            description="读取文本文件的矩形区域（行+列范围）。",
            icon="🔲",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_regex",
            tool_func=file_tools_regex,
            description="正则搜索文件内容，支持跨行匹配，返回 JSON。",
            icon="🔎",
            tool_type="file",
            target_param="path",
            enabled=True,
        )

        # ── 文件修改类（自动备份） ──
        api.register_tool(
            tool_name="file_tools_append",
            tool_func=file_tools_append,
            description="追加内容到文件末尾（自动备份）。",
            icon="➕",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_replace_lines",
            tool_func=file_tools_replace_lines,
            description="整段替换文件中的指定行区间，行数可增减（自动备份）。",
            icon="🔀",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_insert_lines",
            tool_func=file_tools_insert_lines,
            description="在指定行号前插入新内容（自动备份）。",
            icon="📄",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_delete_lines",
            tool_func=file_tools_delete_lines,
            description="删除文件中的指定行区间（自动备份）。",
            icon="✂️",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_replace",
            tool_func=file_tools_replace,
            description="精确子串查找替换，支持跨行（自动备份，支持 dry_run）。",
            icon="🔄",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_regex_replace",
            tool_func=file_tools_regex_replace,
            description="正则替换文件内容，支持跨行匹配（自动备份，支持 dry_run）。",
            icon="✨",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_indent_lines",
            tool_func=file_tools_indent_lines,
            description="调整行首缩进（expand/shrink）。自动备份。",
            icon="📐",
            tool_type="file",
            target_param="path",
            enabled=True,
        )

        # ── 安全文件操作类（不触发备份） ──
        api.register_tool(
            tool_name="file_tools_copy",
            tool_func=file_tools_copy,
            description="复制文件或目录，支持目录融合（源目录→已存在目标目录时合并内容）。目标目录不存在时自动创建。",
            icon="📋",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_move",
            tool_func=file_tools_move,
            description="移动或重命名文件/目录，支持目录融合（源目录→已存在目标目录时合并内容）和文件放入目录。",
            icon="📦",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_trash",
            tool_func=file_tools_trash,
            description="安全删除到回收站（可恢复）。依赖 pytrash。",
            icon="🗑️",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_trash_undo",
            tool_func=file_tools_trash_undo,
            description="从回收站恢复最近删除的文件。依赖 pytrash。",
            icon="♻️",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_mkdir",
            tool_func=file_tools_mkdir,
            description="创建目录，自动创建所有父目录。",
            icon="📁",
            tool_type="file",
            target_param="path",
            enabled=True,
        )

        # ── 历史回滚 ──
        api.register_tool(
            tool_name="file_tools_undo",
            tool_func=file_tools_undo,
            description="恢复文件到历史版本（配合 history 使用）。",
            icon="⏪",
            tool_type="file",
            target_param="path",
            enabled=True,
        )

        # ── 全量写入（替代 write_file） ──
        api.register_tool(
            tool_name="file_tools_write",
            tool_func=file_tools_write,
            description="写入文件内容（原子写入，已存在时自动备份）。",
            icon="✏️",
            tool_type="file",
            target_param="path",
            enabled=True,
        )

        logger.info("✓ File Tools 插件注册完成（25 个工具）")

        # ── 字节级工具 ──
        api.register_tool(
            tool_name="file_tools_read_bytes",
            tool_func=file_tools_read_bytes,
            description="读取二进制文件指定字节范围，返回 hex。",
            icon="🔢",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_write_bytes",
            tool_func=file_tools_write_bytes,
            description="写入二进制文件，支持全量/部分覆盖。",
            icon="✏️",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_find_bytes",
            tool_func=file_tools_find_bytes,
            description="在二进制文件中查找字节序列。",
            icon="🔎",
            tool_type="file",
            target_param="path",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_replace_bytes",
            tool_func=file_tools_replace_bytes,
            description="在二进制文件中查找并替换字节序列。",
            icon="🔄",
            tool_type="file",
            target_param="path",
            enabled=True,
        )


plugin = FileToolsPlugin()

# ── 启动钩子：清理过期备份 ──
        api.register_startup_hook(
            "cleanup_old_backups",
            self._startup_cleanup,
            priority=90,
        )


    def _startup_cleanup(self) -> None:
        """启动时清理超过 30 天的旧备份文件。"""
        try:
            cleanup_old_backups(days=30)
        except Exception as e:
            logger.warning("启动清理备份时出错: %s", e)