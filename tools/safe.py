"""安全文件操作类工具（不触发历史备份）。

包含：
- file_tools_copy: 复制文件/目录
- file_tools_move: 移动/重命名
- file_tools_trash: 安全删除到回收站
- file_tools_trash_undo: 从回收站恢复
- file_tools_mkdir: 创建目录
"""

import logging
import os
import shutil
from typing import Optional

try:
    from ..utils import format_error, resolve_path
except ImportError:
    from utils import format_error, resolve_path

logger = logging.getLogger(__name__)


# ── 15. file_tools_copy ───────────────────────────────────


def file_tools_copy(
    src: str,
    dst: str,
    overwrite: bool = False,
) -> str:
    """复制文件或目录（含子目录递归）。复制目录时使用 copytree 递归复制，复制文件时使用 copy2 保留元数据。目标目录不存在时自动创建。源目录→目标目录（已存在）时执行融合：将源目录下所有内容复制到目标目录内。源文件→目标目录（已存在）时，将文件复制到目录内部。

    Args:
        src: 源路径。相对路径相对于 workspace 目录，支持 ~ 展开。可以是文件或目录，源不存在时报错。
        dst: 目标路径。相对路径相对于 workspace 目录，支持 ~ 展开。目标已存在且 overwrite=False 时报错。
        overwrite: 覆盖模式。False=目标已存在时报错不覆盖（默认），True=覆盖已存在的目标——目录融合时同名文件/目录会被覆盖。
    """
    resolved_src = resolve_path(src)
    resolved_dst = resolve_path(dst)

    if not os.path.exists(resolved_src):
        return (
            f"复制失败，因为找不到源文件「{resolved_src}」。"
            f"请使用 file_tools_listdir(path=\"{os.path.dirname(src) or '.'}\") "
            f"确认源文件是否存在于该目录中，或检查路径拼写是否正确。"
        )
    if resolved_src == resolved_dst:
        return f"源路径和目标路径相同（{resolved_src}），无需操作。"

    # ── 目录→已存在目录：融合 ──
    if os.path.isdir(resolved_src) and os.path.isdir(resolved_dst):
        if not overwrite:
            conflicts = []
            for item in os.listdir(resolved_src):
                if os.path.exists(os.path.join(resolved_dst, item)):
                    conflicts.append(item)
            if conflicts:
                c_list = "、".join(conflicts)
                return (
                    f"复制失败，因为目标目录「{resolved_dst}」中已存在同名项目（{c_list}）。"
                    f"如果要覆盖，请设置 overwrite=True。"
                )
        for item in os.listdir(resolved_src):
            src_item = os.path.join(resolved_src, item)
            dst_item = os.path.join(resolved_dst, item)
            if os.path.exists(dst_item):
                if os.path.isdir(dst_item):
                    shutil.rmtree(dst_item)
                else:
                    os.remove(dst_item)
            if os.path.isdir(src_item):
                shutil.copytree(src_item, dst_item)
            else:
                shutil.copy2(src_item, dst_item)
        return f"已复制「{resolved_src}」→「{resolved_dst}」（融合）。"

    # ── 文件→已存在目录：放入目录内 ──
    if os.path.isfile(resolved_src) and os.path.isdir(resolved_dst):
        dst_file = os.path.join(resolved_dst, os.path.basename(resolved_src))
        if os.path.exists(dst_file) and not overwrite:
            return (
                f"复制失败，因为目标目录中已存在同名文件「{dst_file}」。"
                f"如果要覆盖，请设置 overwrite=True。"
            )
        if os.path.exists(dst_file):
            os.remove(dst_file)
        shutil.copy2(resolved_src, dst_file)
        return f"已复制「{resolved_src}」→「{dst_file}」。"

    # ── 常规复制 ──
    if os.path.exists(resolved_dst) and not overwrite:
        return (
            f"复制失败，因为目标文件「{resolved_dst}」已存在。"
            f"如果要覆盖目标文件，请设置 overwrite=True。"
        )

    try:
        if os.path.isdir(resolved_src):
            if os.path.exists(resolved_dst):
                shutil.rmtree(resolved_dst)
            shutil.copytree(resolved_src, resolved_dst)
        else:
            # 自动创建目标目录（如目标目录不存在）
            dst_dir = os.path.dirname(resolved_dst)
            if dst_dir:
                os.makedirs(dst_dir, exist_ok=True)
            shutil.copy2(resolved_src, resolved_dst)
    except Exception as e:
        return format_error("复制", f"操作时出错：{e}")

    return f"已复制「{resolved_src}」→「{resolved_dst}」。"


# ── 16. file_tools_move ───────────────────────────────────


def file_tools_move(
    src: str,
    dst: str,
    overwrite: bool = False,
) -> str:
    """移动或重命名文件或目录。目标已存在时需设置 overwrite=True 才能覆盖。源目录→目标目录（已存在）时执行融合：将源目录下所有内容移动到目标目录内，再删除源目录。常用于文件/文件夹重命名（src 和 dst 在同一目录下）。

    Args:
        src: 源路径。相对路径相对于 workspace 目录，支持 ~ 展开。源不存在时报错。
        dst: 目标路径。相对路径相对于 workspace 目录，支持 ~ 展开。目标已存在且 overwrite=False 时报错。
        overwrite: 覆盖模式。False=目标已存在时报错不覆盖（默认），True=覆盖已存在的目标——目录融合时同名文件/目录会被覆盖。
    """
    resolved_src = resolve_path(src)
    resolved_dst = resolve_path(dst)

    if not os.path.exists(resolved_src):
        return (
            f"移动失败，因为找不到源文件「{resolved_src}」。"
            f"请使用 file_tools_listdir 确认源文件是否存在。"
        )
    if resolved_src == resolved_dst:
        return f"源路径和目标路径相同（{resolved_src}），无需操作。"

    # ── 目录融合模式 ──
    if os.path.isdir(resolved_src) and os.path.isdir(resolved_dst):
        # 检查是否有冲突
        if not overwrite:
            conflicts = []
            for item in os.listdir(resolved_src):
                dst_item = os.path.join(resolved_dst, item)
                if os.path.exists(dst_item):
                    conflicts.append(item)
            if conflicts:
                c_list = "、".join(conflicts)
                return (
                    f"移动失败，因为目标目录「{resolved_dst}」中已存在同名项目（{c_list}）。"
                    f"如果要覆盖，请设置 overwrite=True。"
                )
        # 逐个移动子条目
        for item in os.listdir(resolved_src):
            src_item = os.path.join(resolved_src, item)
            dst_item = os.path.join(resolved_dst, item)
            if os.path.exists(dst_item):
                if os.path.isdir(dst_item):
                    shutil.rmtree(dst_item)
                else:
                    os.remove(dst_item)
            shutil.move(src_item, dst_item)
        os.rmdir(resolved_src)
        return f"已移动「{resolved_src}」→「{resolved_dst}」（融合）。"

    # ── 文件→已存在目录：放入目录内 ──
    if os.path.isfile(resolved_src) and os.path.isdir(resolved_dst):
        dst_file = os.path.join(resolved_dst, os.path.basename(resolved_src))
        if os.path.exists(dst_file) and not overwrite:
            return (
                f"移动失败，因为目标目录中已存在同名文件「{dst_file}」。"
                f"如果要覆盖，请设置 overwrite=True。"
            )
        if os.path.exists(dst_file):
            os.remove(dst_file)
        shutil.move(resolved_src, dst_file)
        return f"已移动「{resolved_src}」→「{dst_file}」。"

    # ── 常规移动模式 ──
    if os.path.exists(resolved_dst) and not overwrite:
        return (
            f"移动失败，因为目标文件「{resolved_dst}」已存在。"
            f"如果要覆盖目标文件，请设置 overwrite=True。"
        )

    try:
        if os.path.exists(resolved_dst):
            if os.path.isdir(resolved_dst):
                shutil.rmtree(resolved_dst)
            else:
                os.remove(resolved_dst)
        # 自动创建目标目录（如目标目录不存在）
        dst_dir = os.path.dirname(resolved_dst)
        if dst_dir:
            try:
                os.makedirs(dst_dir, exist_ok=True)
            except OSError as e:
                return format_error("移动", f"创建目标目录「{dst_dir}」时出错：{e}")
        shutil.move(resolved_src, resolved_dst)
    except Exception as e:
        return format_error("移动", f"操作时出错：{e}")

    return f"已移动「{resolved_src}」→「{resolved_dst}」。"


# ── 17. file_tools_trash ──────────────────────────────────


def file_tools_trash(
    path: str,
) -> str:
    """将文件或目录安全删除到回收站（而非永久删除）。依赖 pytrash 库。删除后可通 file_tools_trash_undo 恢复。回收站内的文件保留原始路径信息，恢复时可以按原路径精确找回。

    Args:
        path: 要删除的文件或目录路径。相对路径相对于 workspace 目录，支持 ~ 展开。路径不存在时报错。pytrash 未安装时提示安装。
    """
    resolved = resolve_path(path)

    if not os.path.exists(resolved):
        return (
            f"删除失败，因为找不到「{resolved}」。"
            f"请确认路径是否正确。"
        )

    try:
        import pytrash

        pytrash.recycle([resolved])
    except ImportError:
        return "删除失败，因为 pytrash 库未安装。请执行 pip install pytrash。"
    except Exception as e:
        return format_error("删除", f"放入回收站时出错：{e}")

    return (
        f"已把「{resolved}」放入回收站。"
        f"如需恢复，可使用 file_tools_trash_undo(path=\"{path}\")。"
    )


# ── 18. file_tools_trash_undo ─────────────────────────────


def file_tools_trash_undo(
    path: str,
) -> str:
    """从回收站恢复文件到原始位置。依赖 pytrash 库。按原路径精确匹配回收站条目，如果发现多条记录（如多次删除同路径文件），取最近删除的那个恢复。恢复后文件回到原始路径。

    Args:
        path: 原文件路径（删除前的路径）。相对路径相对于 workspace 目录，支持 ~ 展开。回收站中找不到匹配时返回提示。pytrash 未安装时提示安装。
    """
    resolved = resolve_path(path)

    try:
        import pytrash

        entries = pytrash.entries()
    except ImportError:
        return "恢复失败，因为 pytrash 库未安装。请执行 pip install pytrash。"
    except Exception as e:
        return format_error("恢复", f"读取回收站时出错：{e}")

    # 按原路径匹配
    matched = [e for e in entries if hasattr(e, "original_path") and e.original_path == resolved]

    if not matched:
        return (
            f"恢复失败，因为在回收站中未找到「{resolved}」。"
            f"该文件可能已被永久删除，请确认路径是否正确。"
        )

    # 按 deleted_at 降序排列，取最近删除的
    matched.sort(key=lambda e: getattr(e, "deleted_at", ""), reverse=True)
    best = matched[0]

    try:
        pytrash.restore([best])
    except Exception as e:
        return format_error("恢复", f"从回收站恢复时出错：{e}")

    return f"已从回收站恢复「{resolved}」。"


# ── 19. file_tools_mkdir ──────────────────────────────────


def file_tools_mkdir(
    path: str,
) -> str:
    """创建目录，支持多级目录自动创建（类似 mkdir -p）。目录已存在时返回提示而非报错，可以安全重复调用。

    Args:
        path: 要创建的目录路径。相对路径相对于 workspace 目录，支持 ~ 展开。支持多级目录（如 a/b/c 会递归创建）。目录已存在时返回提示。
    """
    resolved = resolve_path(path)

    if not path:
        return format_error("创建目录", "路径不能为空，请指定一个有效的目录路径")
    if os.path.isdir(resolved):
        return f"目录「{resolved}」已存在，无需创建。"

    try:
        os.makedirs(resolved, exist_ok=True)
    except Exception as e:
        return format_error("创建目录", f"操作时出错：{e}")

    return f"已创建目录「{resolved}」。"
