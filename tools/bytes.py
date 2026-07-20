"""字节级读写与查找替换工具。

提供二进制文件的读取、写入、精确查找和替换功能。
所有字节内容用 hex 字符串表示，返回 hex 全大写。
"""

import logging
import os
import shutil

try:
    from ..backup.manager import backup_file
    from ..utils import (
        format_backup_info,
        format_csv,
        format_error,
        format_hex,
        parse_hex,
        resolve_path,
    )
except ImportError:
    from backup.manager import backup_file
    from utils import (
        format_backup_info,
        format_csv,
        format_error,
        format_hex,
        parse_hex,
        resolve_path,
    )

logger = logging.getLogger(__name__)

_READ_MAX_LENGTH = 4096


# ── 1. file_tools_read_bytes ──────────────────────────────


def file_tools_read_bytes(
    path: str,
    offset: int = 0,
    length: int = 512,
    group_size: int = 16,
) -> str:
    """读取二进制文件的指定字节范围，返回大写 hex 字符串。

    支持从指定偏移量开始读取，可自定义每行显示字节数。
    一次最多读取 4096 字节，大文件请分多次读取。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        offset: 起始偏移量（字节），默认 0 表示从文件开头读取。不能为负数。
        length: 读取长度（字节），默认 512，上限 4096。超过 4096 会报错提示分多次读取。
        group_size: -1=不分组（hex 连在一起），0=报错，>0=每行显示多少字节，默认 16。
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return format_error("读取", f"文件「{resolved}」不存在")

    if offset < 0:
        return format_error("读取", f"偏移量 {offset} 不能为负数")

    if length < 0:
        return format_error("读取", f"读取长度 {length} 不能为负数")

    if length > _READ_MAX_LENGTH:
        return format_error(
            "读取",
            f"一次最多读取 {_READ_MAX_LENGTH} 字节（请求 {length} 字节）",
            f"请减少 length 参数或分多次读取（用 offset 参数调整起始位置）。",
        )

    if group_size == 0:
        return format_error(
            "读取", "group_size 不能为 0", "请使用 -1（不分组）或正数（每行字节数）。"
        )

    try:
        file_size = os.path.getsize(resolved)
    except OSError as e:
        return format_error("读取", f"获取文件大小时出错：{e}")

    if offset >= file_size:
        return format_error(
            "读取", f"偏移量 {offset} 超出文件范围（文件总大小 {file_size} 字节）"
        )

    try:
        with open(resolved, "rb") as f:
            f.seek(offset)
            data = f.read(length)
    except OSError as e:
        return format_error("读取", f"读取文件时出错：{e}")

    actual_length = len(data)
    hex_content = format_hex(data, group_size)

    return (
        f"读取成功：共 {actual_length} 字节（偏移量 {offset}，文件总大小 {file_size} 字节）。\n"
        f"{hex_content}"
    )


# ── 2. file_tools_write_bytes ─────────────────────────────


def file_tools_write_bytes(
    path: str,
    content: str,
    offset: int = -1,
    skip_backup: bool = False,
) -> str:
    """写入二进制文件内容，支持全量覆盖和部分覆盖。

    全量覆盖（offset=-1）：类似 file_tools_write 但用于二进制文件。
        文件已存在时自动备份（除非 skip_backup=True），使用原子写入避免损坏。
    部分覆盖（offset>=0）：从指定偏移量开始覆写，不改变文件大小，不触发备份。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        content: 要写入的字节数据（hex 字符串）。允许空格，大小写不敏感，
            不可以 0x 或 \\x 开头，去掉空格后长度必须是 2 的倍数。
        offset: -1=全量覆盖（默认），>=0=从该偏移量开始写入（部分覆盖）。
        skip_backup: 是否跳过备份（仅全量覆盖时有效），默认 false。
    """
    resolved = resolve_path(path)

    # 解析 hex
    try:
        data = parse_hex(content)
    except ValueError as e:
        return format_error("写入", f"hex 格式错误：{e}")

    expected_bytes = len(data)

    if offset == -1:
        # ── 全量覆盖 ──
        history_number = None
        backup_warning = ""
        if os.path.isfile(resolved) and not skip_backup:
            history_number = backup_file(resolved)
            if history_number is None:
                backup_warning = (
                    "\n⚠️ 警告：备份原文件失败，但已直接覆盖写入。"
                    "请手动确认是否需要备份。"
                )

        # 原子写入：先写 .temp_file，再 shutil.move 替换
        tmp_path = resolved + ".temp_file"
        try:
            with open(tmp_path, "wb") as f:
                actual = f.write(data)
            shutil.move(tmp_path, resolved)
        except Exception as e:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            return format_error("写入", f"写入文件时出错：{e}")

        # 构建返回消息
        result = _build_write_full_result(actual, expected_bytes, history_number, backup_warning, resolved)
        return result

    else:
        # ── 部分覆盖（offset >= 0）──
        if offset < 0:
            return format_error(
                "写入", f"偏移量 {offset} 不合法", "偏移量必须 >= 0，或使用 -1 进行全量覆盖。"
            )

        if not os.path.isfile(resolved):
            return format_error(
                "写入", f"文件「{resolved}」不存在", "部分覆盖仅适用于已有文件，请先创建文件或使用全量覆盖。"
            )

        try:
            with open(resolved, "r+b") as f:
                f.seek(offset)
                actual = f.write(data)
        except OSError as e:
            return format_error("写入", f"写入文件时出错：{e}")

        if actual < expected_bytes:
            return (
                f"写入成功：从偏移量 {offset} 处写入 {actual} 字节"
                f"（预计写入 {expected_bytes} 字节），"
                f"部分字节写入失败，可能是空间不足或触发配额限制。"
            )
        else:
            return f"写入成功：从偏移量 {offset} 处写入 {actual} 字节。"


def _build_write_full_result(
    actual: int,
    expected: int,
    history_number: int | None,
    backup_warning: str,
    resolved: str,
) -> str:
    """构建全量覆盖的返回消息。"""
    if actual < expected:
        msg = (
            f"写入成功：共写入 {actual} 字节"
            f"（预计写入 {expected} 字节），"
            f"部分字节写入失败，可能是空间不足或触发配额限制。"
        )
    else:
        msg = f"写入成功：共写入 {actual} 字节。"

    if history_number is not None:
        msg += f"\n{format_backup_info(resolved, history_number)}"
    elif backup_warning:
        msg += backup_warning

    return msg


# ── 3. file_tools_find_bytes ──────────────────────────────


def file_tools_find_bytes(
    path: str,
    pattern: str,
    offset: int = 0,
    count: int = -1,
) -> str:
    """在二进制文件中精确查找字节序列，返回匹配的偏移量列表（CSV 格式，十进制）。

    查找结果返回 CSV 格式，包含 offset 列，每行一个十进制偏移量。
    精确匹配（不支持通配符），未匹配时返回提示信息。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        pattern: 要查找的字节序列（hex 字符串）。允许空格，大小写不敏感，
            不可以 0x 或 \\x 开头，去掉空格后长度必须是 2 的倍数。
        offset: 搜索起始偏移量，默认 0 表示从文件开头搜索。
        count: 最多返回几个匹配，-1=全部返回（默认），>0=限制匹配数量。
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return format_error("查找", f"文件「{resolved}」不存在")

    if offset < 0:
        return format_error("查找", f"偏移量 {offset} 不能为负数")

    if count == 0:
        return format_error("查找", "count 不能为 0", "请使用 -1（全部匹配）或正数（限制匹配数）。")

    # 解析 pattern
    try:
        pattern_bytes = parse_hex(pattern)
    except ValueError as e:
        return format_error("查找", f"hex 格式错误：{e}")

    if not pattern_bytes:
        return format_error("查找", "pattern 不能为空，请输入要查找的字节序列")

    try:
        file_size = os.path.getsize(resolved)
    except OSError as e:
        return format_error("查找", f"获取文件大小时出错：{e}")

    if offset >= file_size:
        return format_error(
            "查找", f"偏移量 {offset} 超出文件范围（文件总大小 {file_size} 字节）"
        )

    # 读取文件全部内容，用 offset 做搜索起点
    try:
        with open(resolved, "rb") as f:
            data = f.read()
    except OSError as e:
        return format_error("查找", f"读取文件时出错：{e}")

    matches = _find_all(data, pattern_bytes, offset)

    # 应用 count 限制
    if count > 0 and len(matches) > count:
        matches = matches[:count]

    if not matches:
        return "在文件中未找到匹配的字节序列。"

    # 返回 CSV 格式
    rows = [{"offset": pos} for pos in matches]
    return format_csv(rows, fieldnames=["offset"])


def _find_all(data: bytes, pattern: bytes, base_offset: int) -> list[int]:
    """在 data 中从 base_offset 开始查找所有 pattern 出现的位置，返回绝对偏移量列表。"""
    matches = []
    start = base_offset
    while True:
        pos = data.find(pattern, start)
        if pos == -1:
            break
        matches.append(pos)
        start = pos + 1
    return matches


# ── 4. file_tools_replace_bytes ───────────────────────────


def file_tools_replace_bytes(
    path: str,
    old_bytes: str,
    new_bytes: str,
    count: int = -1,
    offset: int = 0,
    skip_backup: bool = False,
) -> str:
    """在二进制文件中查找并替换字节序列，支持变长替换。

    old_bytes 和 new_bytes 长度可以不同（替换后文件大小会变）。
    从后往前替换，避免偏移量变化导致替换错误。
    修改前自动备份（除非 skip_backup=True），使用原子写入避免文件损坏。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        old_bytes: 要查找的字节序列（hex 字符串）。
        new_bytes: 替换成的字节序列（hex 字符串）。
        count: 替换次数，-1=全部替换（默认），>0=限制替换次数。
        offset: 搜索起始偏移量，默认 0 表示从文件开头搜索。
        skip_backup: 是否跳过备份，默认 false。大文件可设为 true 提高速度。
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return format_error("替换", f"文件「{resolved}」不存在")

    if offset < 0:
        return format_error("替换", f"偏移量 {offset} 不能为负数")

    if count == 0:
        return format_error("替换", "count 不能为 0", "请使用 -1（全部替换）或正数（限制替换次数）。")

    if not old_bytes.strip():
        return format_error("替换", "old_bytes 不能为空")

    # 解析 hex
    try:
        old_data = parse_hex(old_bytes)
        new_data = parse_hex(new_bytes)
    except ValueError as e:
        return format_error("替换", f"hex 格式错误：{e}")

    if not old_data:
        return format_error("替换", "old_bytes 不能为空，请输入要查找的字节序列")

    # 备份
    if not skip_backup:
        history_number = backup_file(resolved)
        if history_number is None:
            # 备份失败仍继续，加警告
            pass
    else:
        history_number = None

    # 读取文件内容
    try:
        with open(resolved, "rb") as f:
            data = f.read()
    except OSError as e:
        return format_error("替换", f"读取文件时出错：{e}")

    # 查找所有匹配
    matches = _find_all(data, old_data, offset)
    if not matches:
        return "在文件中未找到匹配的字节序列。"

    # 应用 count 限制
    if count > 0:
        matches = matches[:count]

    # 执行替换（从后往前替换，避免偏移量变化）
    result = bytearray(data)
    replace_count = 0
    replaced_positions = []
    for pos in reversed(matches):
        result[pos : pos + len(old_data)] = new_data
        replace_count += 1
        replaced_positions.append(pos)

    # 原子写入：先写 .temp_file，再 shutil.move 替换
    tmp_path = resolved + ".temp_file"
    try:
        with open(tmp_path, "wb") as f:
            f.write(result)
        shutil.move(tmp_path, resolved)
    except Exception as e:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return format_error("替换", f"写入文件时出错：{e}")

    # 构建返回消息
    positions_str = "、".join(str(p) for p in reversed(replaced_positions))
    msg = f"替换成功：替换了 {replace_count} 处。\n替换位置（十进制）：\n{positions_str}"

    if history_number is not None:
        msg += f"\n{format_backup_info(resolved, history_number)}"

    return msg