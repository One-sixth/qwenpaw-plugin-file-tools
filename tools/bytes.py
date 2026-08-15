"""字节级读写与查找替换工具。

提供二进制文件的读取、写入、精确查找和替换功能。
所有字节内容用 hex 字符串表示，返回 hex 全大写。
"""

import logging
import os
import shutil
from typing import Optional, Union

try:
    from ..backup.manager import backup_file
    from ..utils import (
        format_backup_info,
        format_csv,
        format_error,
        make_error,
        make_success,
        format_hex,
        parse_hex,
        parse_int,
        resolve_path,
    )
except ImportError:
    from backup.manager import backup_file
    from utils import (
        format_backup_info,
        format_csv,
        format_error,
        make_error,
        make_success,
        format_hex,
        parse_hex,
        parse_int,
        resolve_path,
    )

logger = logging.getLogger(__name__)

_READ_MAX_LENGTH = 4096


# ── 1. file_tools_read_bytes ──────────────────────────────


def file_tools_read_bytes(
    path: str,
    offset: Union[int, str] = 0,
    length: Union[int, str] = 512,
    group_size: Union[int, str] = 16,
) -> str:
    """读取二进制文件的指定字节范围，返回全大写 hex 字符串。支持指定起始偏移量和读取长度，可自定义每行显示的字节数。一次最多读取 4096 字节——超过时请分多次读取，用 offset 逐步推进。返回时附带实际读取字节数和文件总大小等信息。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。文件不存在时报错。
        offset: 起始偏移量（字节），默认 0=从文件开头。不能为负数，超出文件大小报错。支持整数或十进制数字字符串。
        length: 读取长度（字节），默认 512。上限 4096，超过时报错提示分多次读取。不能为负数。支持整数或十进制数字字符串。
        group_size: 每行显示的字节数。-1=不分组（hex 连成一行），0=报错，>0=每行显示指定字节数（默认 16）。支持整数或十进制数字字符串。
    """
    resolved = resolve_path(path)

    offset, err = parse_int(offset, "offset")
    if err:
        return make_error("读取", err)
    length, err = parse_int(length, "length")
    if err:
        return make_error("读取", err)
    group_size, err = parse_int(group_size, "group_size")
    if err:
        return make_error("读取", err)

    if not os.path.isfile(resolved):
        return make_error("读取", f"文件「{resolved}」不存在")

    if offset < 0:
        return make_error("读取", f"偏移量 {offset} 不能为负数")

    if length < 0:
        return make_error("读取", f"读取长度 {length} 不能为负数")

    if length > _READ_MAX_LENGTH:
        return make_error(
            "读取",
            f"一次最多读取 {_READ_MAX_LENGTH} 字节（请求 {length} 字节）",
            f"请减少 length 参数或分多次读取（用 offset 参数调整起始位置）。",
        )

    if group_size == 0:
        return make_error(
            "读取", "group_size 不能为 0", "请使用 -1（不分组）或正数（每行字节数）。"
        )

    try:
        file_size = os.path.getsize(resolved)
    except OSError as e:
        return make_error("读取", f"获取文件大小时出错：{e}")

    if offset >= file_size:
        return make_error(
            "读取", f"偏移量 {offset} 超出文件范围（文件总大小 {file_size} 字节）"
        )

    try:
        with open(resolved, "rb") as f:
            f.seek(offset)
            data = f.read(length)
    except OSError as e:
        return make_error("读取", f"读取文件时出错：{e}")

    actual_length = len(data)
    hex_content = format_hex(data, group_size)

    return make_success(
        f"读取成功：共 {actual_length} 字节（偏移量 {offset}，文件总大小 {file_size} 字节）。\n"
        f"{hex_content}"
    )


# ── 2. file_tools_write_bytes ─────────────────────────────


def file_tools_write_bytes(
    path: str,
    content: str,
    offset: Union[int, str] = -1,
    skip_backup: bool = False,
) -> str:
    """写入二进制文件内容，支持全量覆盖和部分覆盖两种模式。全量覆盖（offset=-1）时自动备份并原子写入，部分覆盖（offset>=0）时从指定偏移量开始覆写、不改变文件大小、不触发备份。所有输入为 hex 字符串（全大写输出）。备份后的文件可通过 file_tools_undo 恢复。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。部分覆盖时文件必须先存在。
        content: 要写入的字节数据（hex 字符串）。允许空格，大小写不敏感，不可以 0x 或 \\x 开头。去掉空格后长度必须是 2 的倍数（每个字节 2 个 hex 字符）。
        offset: 写入模式。-1=全量覆盖（默认，先备份再原子写入），>=0=部分覆盖（从该偏移量开始覆写，不备份不改变文件大小）。支持整数或十进制数字字符串。
        skip_backup: 是否跳过备份。仅全量覆盖（offset=-1）时有效。大文件可设为 true 提高速度。默认 false。
    """
    resolved = resolve_path(path)

    offset, err = parse_int(offset, "offset")
    if err:
        return make_error("写入", err)

    # 解析 hex
    try:
        data = parse_hex(content)
    except ValueError as e:
        return make_error("写入", f"hex 格式错误：{e}")

    expected_bytes = len(data)

    if offset == -1:
        # ── 全量覆盖 ──
        history_number = None
        if os.path.isfile(resolved) and not skip_backup:
            history_number = backup_file(resolved)
            if history_number is None:
                return make_error(
                    "写入",
                    "备份原文件失败",
                    "请暂停执行，向用户询问是否可以不备份。"
                    "只有用户明确打字「同意跳过备份」后，"
                    "才能设置 skip_backup=True 继续执行。",
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
            return make_error("写入", f"写入文件时出错：{e}")

        # 构建返回消息
        result = _build_write_full_result(actual, expected_bytes, history_number, resolved)
        return result

    else:
        # ── 部分覆盖（offset >= 0）──
        if offset < 0:
            return make_error(
                "写入", f"偏移量 {offset} 不合法", "偏移量必须 >= 0，或使用 -1 进行全量覆盖。"
            )

        if not os.path.isfile(resolved):
            return make_error(
                "写入", f"文件「{resolved}」不存在", "部分覆盖仅适用于已有文件，请先创建文件或使用全量覆盖。"
            )

        try:
            with open(resolved, "r+b") as f:
                f.seek(offset)
                actual = f.write(data)
        except OSError as e:
            return make_error("写入", f"写入文件时出错：{e}")

        if actual < expected_bytes:
            return make_success((
                f"写入成功：从偏移量 {offset} 处写入 {actual} 字节"
                f"（预计写入 {expected_bytes} 字节），"
                f"部分字节写入失败，可能是空间不足或触发配额限制。"
            ))
        else:
            return make_success(f"写入成功：从偏移量 {offset} 处写入 {actual} 字节。")


def _build_write_full_result(
    actual: int,
    expected: int,
    history_number: int | None,
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

    return make_success(msg)


# ── 3. file_tools_find_bytes ──────────────────────────────


def file_tools_find_bytes(
    path: str,
    pattern: str,
    offset: Union[int, str] = 0,
    count: Union[int, str] = -1,
) -> str:
    """在二进制文件中精确查找字节序列，返回 CSV 格式的匹配偏移量列表（十进制）。精确匹配，不支持通配符或模糊匹配。未匹配到时返回提示信息。返回结果包含 offset 列，每行一个十进制偏移量。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。文件不存在时报错。
        pattern: 要查找的字节序列（hex 字符串）。允许空格，大小写不敏感，不可以 0x 或 \\x 开头。去掉空格后长度必须是 2 的倍数。不能为空。
        offset: 搜索起始偏移量（字节），默认 0=从文件开头。不能为负数，超出文件大小报错。支持整数或十进制数字字符串。
        count: 最多返回几个匹配。-1=全部返回（默认），>0=限制返回数量。传 0 报错。支持整数或十进制数字字符串。
    """
    resolved = resolve_path(path)

    offset, err = parse_int(offset, "offset")
    if err:
        return make_error("查找", err)
    count, err = parse_int(count, "count")
    if err:
        return make_error("查找", err)

    if not os.path.isfile(resolved):
        return make_error("查找", f"文件「{resolved}」不存在")

    if offset < 0:
        return make_error("查找", f"偏移量 {offset} 不能为负数")

    if count == 0:
        return make_error("查找", "count 不能为 0", "请使用 -1（全部匹配）或正数（限制匹配数）。")

    # 解析 pattern
    try:
        pattern_bytes = parse_hex(pattern)
    except ValueError as e:
        return make_error("查找", f"hex 格式错误：{e}")

    if not pattern_bytes:
        return make_error("查找", "pattern 不能为空，请输入要查找的字节序列")

    try:
        file_size = os.path.getsize(resolved)
    except OSError as e:
        return make_error("查找", f"获取文件大小时出错：{e}")

    if offset >= file_size:
        return make_error(
            "查找", f"偏移量 {offset} 超出文件范围（文件总大小 {file_size} 字节）"
        )

    # 读取文件全部内容，用 offset 做搜索起点
    try:
        with open(resolved, "rb") as f:
            data = f.read()
    except OSError as e:
        return make_error("查找", f"读取文件时出错：{e}")

    matches = _find_all(data, pattern_bytes, offset)

    # 应用 count 限制
    if count > 0 and len(matches) > count:
        matches = matches[:count]

    if not matches:
        return make_success("在文件中未找到匹配的字节序列。")

    # 返回 CSV 格式
    rows = [{"offset": pos} for pos in matches]
    return make_success(format_csv(rows, fieldnames=["offset"]))


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
    count: Union[int, str] = 1,
    offset: Union[int, str] = 0,
    skip_backup: bool = False,
) -> str:
    """在二进制文件中查找并替换字节序列，支持变长替换（old_bytes 和 new_bytes 长度可以不同）。从后往前逐个替换，避免偏移量变化导致替换位置错误。修改前自动备份（除非 skip_backup=True），使用原子写入避免文件损坏。备份后的文件可通过 file_tools_undo 恢复。返回替换位置（十进制偏移量），CSV 格式。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。文件不存在时报错。
        old_bytes: 要查找的字节序列（hex 字符串）。允许空格，大小写不敏感，不可以 0x 或 \\x 开头。不能为空。
        new_bytes: 替换成的字节序列（hex 字符串）。空字符串表示删除匹配内容。可以与 old_bytes 长度不同——替换后文件大小会变。
        count: 替换次数。1=只替换第一个匹配（默认），-1=全部替换，>0=限制替换次数。传 0 报错。支持整数或十进制数字字符串。
        offset: 搜索起始偏移量（字节），默认 0=从文件开头。不能为负数。支持整数或十进制数字字符串。
        skip_backup: 是否跳过备份。大文件可设为 true 提高写入速度。默认 false。
    """
    resolved = resolve_path(path)

    count, err = parse_int(count, "count")
    if err:
        return make_error("替换", err)
    offset, err = parse_int(offset, "offset")
    if err:
        return make_error("替换", err)

    if not os.path.isfile(resolved):
        return make_error("替换", f"文件「{resolved}」不存在")

    if offset < 0:
        return make_error("替换", f"偏移量 {offset} 不能为负数")

    if count == 0:
        return make_error("替换", "count 不能为 0", "请使用 -1（全部替换）或正数（限制替换次数）。")

    if not old_bytes.strip():
        return make_error("替换", "old_bytes 不能为空")

    # 解析 hex
    try:
        old_data = parse_hex(old_bytes)
        new_data = parse_hex(new_bytes)
    except ValueError as e:
        return make_error("替换", f"hex 格式错误：{e}")

    if not old_data:
        return make_error("替换", "old_bytes 不能为空，请输入要查找的字节序列")

    # 备份
    history_number = None
    if not skip_backup:
        history_number = backup_file(resolved)
        if history_number is None:
            return make_error(
                "替换",
                "备份原文件失败",
                "请暂停执行，向用户询问是否可以不备份。"
                "只有用户明确打字「同意跳过备份」后，"
                "才能设置 skip_backup=True 继续执行。",
            )
    else:
        history_number = None

    # 读取文件内容
    try:
        with open(resolved, "rb") as f:
            data = f.read()
    except OSError as e:
        return make_error("替换", f"读取文件时出错：{e}")

    # 查找所有匹配
    matches = _find_all(data, old_data, offset)
    if not matches:
        return make_success("在文件中未找到匹配的字节序列。")

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
        return make_error("替换", f"写入文件时出错：{e}")

    # 构建返回消息
    positions = [{"offset": pos} for pos in reversed(replaced_positions)]
    positions_str = format_csv(positions, fieldnames=["offset"])
    msg = f"替换成功：替换了 {replace_count} 处。\n替换位置（十进制）：\n{positions_str}"

    if history_number is not None:
        msg += f"\n{format_backup_info(resolved, history_number)}"

    return make_success(msg)