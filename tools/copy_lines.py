"""跨文件行复制工具。

包含：
- file_tools_copy_lines: 将源文件选中的行复制到目标文件指定位置（支持自复制）

源侧读取与目标侧写回各自独立配置编码与行结束符。
其余文件 I/O 约定与 edit.py 一致。
"""

import logging
import os
from typing import List, Literal, Optional, Union

try:
    from ..backup.manager import backup_file
    from ..utils import (
        detect_encoding,
        format_backup_info,
        make_error,
        make_success,
        normalize_newlines,
        parse_int,
        read_file_lines,
        resolve_path,
        truncate_line,
    )
    from .edit import _write_file
except ImportError:
    from backup.manager import backup_file
    from utils import (
        detect_encoding,
        format_backup_info,
        make_error,
        make_success,
        normalize_newlines,
        parse_int,
        read_file_lines,
        resolve_path,
        truncate_line,
    )
    from tools.edit import _write_file

logger = logging.getLogger(__name__)

# Literal 键为两字符序列（反斜杠+n），与 edit 家族同套路（已知陷阱 #1）
_SRC_SEP_MAP = {"\\n": "\n", "\\r\\n": "\r\n"}
_DST_NEWLINE_MAP = {"auto": None, "\\n": "\n", "\\r\\n": "\r\n"}

# diff 预览中 + 组超过该行数列首尾各一半，中间省略
_PREVIEW_MAX_LINES = 20


def _dominant_newline(content: str) -> Optional[str]:
    """探测文本的主要行尾（作者裁决：自复制 auto = 跟随源文件真实行尾）。

    取 \\r\\n / \\n / \\r 中数量最多者，平局 CRLF 优先（Windows 文件部分
    转换的常见形态）；完全没有换行时返回 None（落回 OS 口径）。
    """
    crlf = content.count("\r\n")
    lf = content.count("\n") - crlf
    cr = content.count("\r") - crlf
    best = max(crlf, lf, cr)
    if best == 0:
        return None
    if crlf >= lf and crlf >= cr:
        return "\r\n"
    return "\n" if lf >= cr else "\r"


def _split_source_lines(
    path: str,
    encoding: str,
    line_separator: str,
):
    """读取源文件并拆行。

    auto: 原始读取、探测主行尾后归一为 \\n 拆行。
    显式 \\n 或 \\r\\n: 仅按该行尾序列拆行，其余换行符保留在行内容中。
    非法值宽容退回 auto。

    Returns:
        (lines, resolved_encoding, dominant_sep)
        dominant_sep: 显式模式=该序列；auto 模式=文件真实主行尾（无换行为 None）
    """
    resolved_encoding = detect_encoding(path, encoding)
    with open(path, "r", encoding=resolved_encoding, newline="") as f:
        content = f.read()

    sep = _SRC_SEP_MAP.get(line_separator)
    if sep is not None:
        return content.split(sep), resolved_encoding, sep
    return (
        normalize_newlines(content).split("\n"),
        resolved_encoding,
        _dominant_newline(content),
    )


def _detect_file_newline(path: str, encoding: str) -> Optional[str]:
    """探测已存在文件（非自复制基线）的真实主行尾；探测失败按无行尾处理。"""
    try:
        with open(path, "r", encoding=encoding, newline="") as f:
            return _dominant_newline(f.read())
    except Exception:
        return None


def _same_file(path_a: str, path_b: str) -> bool:
    """路径恒等判断（Windows 大小写不敏感）。

    刻意不做 samefile/inode 判断：写回走 os.replace 路径级替换，
    若把符号链接判成自复制，成功文案与实际效果（链接被掀掉）会分裂。
    """
    return os.path.normcase(path_a) == os.path.normcase(path_b)


def _build_preview(
    result_lines: List[str],
    insert_pos: int,
    block_count: int,
) -> str:
    """构建 +/- diff 预览（前一行上下文 + 复制行组 + 后一行上下文）。"""
    parts = []
    if insert_pos > 0:
        parts.append(
            f"  {insert_pos} > {truncate_line(result_lines[insert_pos - 1])}"
        )

    new_end = insert_pos + block_count
    if block_count <= _PREVIEW_MAX_LINES:
        for i in range(insert_pos, new_end):
            parts.append(f"+ {i + 1} > {truncate_line(result_lines[i])}")
    else:
        half = _PREVIEW_MAX_LINES // 2
        for i in range(insert_pos, insert_pos + half):
            parts.append(f"+ {i + 1} > {truncate_line(result_lines[i])}")
        parts.append(
            f"+ ... 中间省略 {block_count - _PREVIEW_MAX_LINES} 行 ..."
        )
        for i in range(new_end - half, new_end):
            parts.append(f"+ {i + 1} > {truncate_line(result_lines[i])}")

    if new_end < len(result_lines):
        parts.append(
            f"  {new_end + 1} > {truncate_line(result_lines[new_end])}"
        )
    return "\n".join(parts)


# ── file_tools_copy_lines ─────────────────────────────────


def file_tools_copy_lines(
    src_file: str,
    start_line: Union[int, str],
    end_line: Union[int, str],
    dst_file: Optional[str] = None,
    insert_line: Union[int, str] = -1,
    src_encoding: str = "auto",
    dst_encoding: str = "auto",
    src_line_separator: Literal["auto", "\\n", "\\r\\n"] = "auto",
    dst_line_separator: Literal["auto", "\\n", "\\r\\n"] = "auto",
) -> str:
    """将 src_file 中选中的行复制到 dst_file 指定位置，行内容全程直接落盘编辑、不经过对话上下文。dst_file 不存在时自动新建（连同父目录），已存在时修改前自动备份；dst_file 留空表示复制到源文件自身（自复制，两端行号均以修改前为准）。返回结果摘要与插入点 +/- diff 预览，行号一律 1-based。

    Args:
        src_file: 源文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。文件不存在时报错。
        start_line: 源选中起始行号，1-based，包含。超出源文件总行数时报错。支持整数或十进制数字字符串。
        end_line: 源选中结束行号，1-based，包含。必须 >= start_line。超出源文件总行数时取到文件末尾。支持整数或十进制数字字符串。
        dst_file: 目标文件路径。留空（None）= 复制到 src_file 自身。不存在时自动新建（连同父目录），已存在时修改前自动备份。
        insert_line: 插入到 dst_file 第 insert_line 行之前，1-based；1 = 插入到开头；-1 或不填 = 末尾追加；超过总行数与 -1 同意；目标新建时忽略。支持整数或十进制数字字符串。
        src_encoding: 源文件编码。auto=自动检测（默认），也可指定编码名称。
        dst_encoding: 目标文件编码。auto=已存在时检测自身编码、新建时沿用源文件编码；也可指定编码名称。
        src_line_separator: 源文件拆行方式。auto=先把 \\r\\n/\\r 统一为 \\n 再拆行（默认）；指定 \\n 或 \\r\\n=仅按该行尾拆行，其余换行符保留在行内容中。
        dst_line_separator: 写回行结束符。auto=（默认）保持目标文件主行尾（自复制即源文件；新建/空/无换行文件按操作系统），\\n=Unix 风格 LF，\\r\\n=Windows 风格 CRLF。
    """
    # ── 参数解析 ──
    start_line, err = parse_int(start_line, "start_line")
    if err:
        return make_error("复制行", err)
    end_line, err = parse_int(end_line, "end_line")
    if err:
        return make_error("复制行", err)
    if insert_line is None:
        insert_line = -1
    insert_line, err = parse_int(insert_line, "insert_line")
    if err:
        return make_error("复制行", err)

    if start_line < 1 or end_line < 1:
        return make_error("复制行", "行号必须 >= 1")
    if start_line > end_line:
        return make_error("复制行", f"起始行号 {start_line} 大于结束行号 {end_line}")

    src_resolved = resolve_path(src_file)
    if not os.path.isfile(src_resolved):
        return make_error("复制行", f"源文件「{src_resolved}」不存在")

    # ── 读源文件、截取选中块 ──
    try:
        src_lines, src_enc, src_sep = _split_source_lines(
            src_resolved, src_encoding, src_line_separator
        )
    except Exception as e:
        return make_error("复制行", f"读取源文件时出错：{e}")

    src_total = len(src_lines)
    # 末尾空元素是文件换行的记账位，不算可选内容行
    src_content_total = src_total - 1 if src_lines[-1] == "" else src_total
    if start_line > src_content_total:
        return make_error(
            "复制行", f"起始行号 {start_line} 超出源文件范围（共 {src_content_total} 行）"
        )
    actual_end = min(end_line, src_content_total)
    block = src_lines[start_line - 1 : actual_end]

    # ── 确定目标文件（留空/同路径 = 自复制） ──
    if dst_file is None:
        self_copy = True
        dst_resolved = src_resolved
    else:
        dst_resolved = resolve_path(dst_file)
        self_copy = _same_file(dst_resolved, src_resolved)

    if os.path.exists(dst_resolved) and not os.path.isfile(dst_resolved):
        return make_error("复制行", f"目标路径「{dst_resolved}」已存在但不是文件")

    dst_exists = os.path.isfile(dst_resolved)
    empty_dst = dst_exists and os.path.getsize(dst_resolved) == 0

    # ── 读目标文件基线 ──
    if self_copy:
        base_lines = list(src_lines)
        dst_enc = src_enc if dst_encoding == "auto" else dst_encoding
        fresh = False
    elif dst_exists:
        try:
            base_lines, dst_enc = read_file_lines(dst_resolved, dst_encoding)
        except Exception as e:
            return make_error("复制行", f"读取目标文件时出错：{e}")
        if empty_dst and dst_encoding == "auto":
            # 空文件没有自身编码可言，与新建一样沿用源编码
            dst_enc = src_enc
        fresh = False
    else:
        base_lines = []
        fresh = True
        dst_enc = src_enc if dst_encoding == "auto" else dst_encoding
        parent = os.path.dirname(dst_resolved)
        try:
            os.makedirs(parent, exist_ok=True)
        except Exception as e:
            return make_error("复制行", f"创建目标目录「{parent}」失败：{e}")

    # ── 计算插入位置 ──
    dst_total = len(base_lines)
    append_mode = insert_line == -1
    if fresh:
        insert_pos = 0
    elif append_mode or insert_line > dst_total:
        # 超过末尾与 -1 同意：自动追加到末尾（作者裁决）。
        # 文件以换行结尾（有末尾空行）时插到空行之前
        insert_pos = dst_total - 1 if base_lines[-1] == "" else dst_total
        append_mode = True
    else:
        if insert_line < 1:
            return make_error(
                "复制行",
                f"插入行号 {insert_line} 不合法，行号从 1 开始；末尾追加用 -1",
            )
        insert_pos = insert_line - 1

    # ── 备份（仅目标文件已存在时） ──
    history_number = None
    if dst_exists:
        history_number = backup_file(dst_resolved)
        if history_number is None:
            return make_error("复制行", "备份原文件失败。因为获取会话文件路径失败。")

    # ── 插入并写回 ──
    result_lines = list(base_lines)
    result_lines[insert_pos:insert_pos] = block
    new_total = len(result_lines)

    content = "\n".join(result_lines)
    if fresh:
        content += "\n"  # 新建文件补末尾换行，成为规范文本文件（单空行也算）

    nl = _DST_NEWLINE_MAP.get(dst_line_separator, None)
    if dst_line_separator == "auto" and dst_exists and not empty_dst:
        # 作者裁决：auto = 保持目标文件主行尾（自复制时目标即源文件）；
        # 新建/空文件/无换行文件落回 OS 口径
        follow = src_sep if self_copy else _detect_file_newline(dst_resolved, dst_enc)
        if follow:
            nl = follow
    if nl != "\n":
        # strict 拆行可带入 \r\n 行内容；写回转换（\n→行尾）前先折叠，
        # 杜绝 \r\r\n 字节腐蚀。dst 显式 \n 不转换，字节原样保留。
        content = content.replace("\r\n", "\n")
    try:
        _write_file(dst_resolved, content, dst_enc, newline=nl)
    except Exception as e:
        return make_error("复制行", f"写入目标文件时出错：{e}")

    # ── 摘要 + 预览 ──
    src_desc = f"「{src_resolved}」第 {start_line}-{actual_end} 行（{len(block)} 行）"
    if fresh:
        summary = f"已复制：{src_desc} → 新建「{dst_resolved}」（共 {new_total} 行）。"
    else:
        pos_desc = "末尾追加" if append_mode else f"第 {insert_line} 行之前"
        summary = (
            f"已复制：{src_desc} → 「{dst_resolved}」{pos_desc}。"
            f"文件从 {dst_total} 行变为 {new_total} 行。"
        )
    if history_number is not None:
        summary += f"\n{format_backup_info(dst_resolved, history_number)}"

    preview = _build_preview(result_lines, insert_pos, len(block))
    return make_success(f"{summary}\n\n{preview}")
