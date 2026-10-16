"""公共工具函数。

提供编码检测、路径标准化、CSV 格式化输出、
160 字符截断、max_chars 截断等工具共享的底层能力。

所有文件 I/O 使用 Python 文本模式 (r/w/a)，统一用 \\\\n 换行。
Windows 上文本模式自动处理 \\\\n → \\\\r\\\\n 转换，无需手动处理。
"""

import csv
import hashlib
import io
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────

LINE_CONTENT_TRUNCATE = 160

# ── 路径标准化 ─────────────────────────────────────────────


def get_workspace_dir() -> str:
    """获取用户文件路径的基准目录（智能体工作区）。

    经 QwenPaw 每回合注入的 ContextVar 解析：
    项目目录（聊天界面绑定）→ agent 工作区 → 全局 WORKING_DIR。
    与 QwenPaw 内置 file/shell 工具语义一致。
    """
    from qwenpaw.config.context import get_tool_base_dir

    return str(get_tool_base_dir())


def resolve_path(path: str, workspace_dir: Optional[str] = None) -> str:
    """标准化路径。workspace_dir 为 None 时自动获取。"""
    if workspace_dir is None:
        workspace_dir = get_workspace_dir()
    expanded = os.path.expanduser(path)
    if not os.path.isabs(expanded) and workspace_dir:
        expanded = os.path.join(workspace_dir, expanded)
    return os.path.normpath(os.path.abspath(expanded))


# ── 编码检测 ──────────────────────────────────────────────


def detect_encoding(file_path: str, encoding: str = "auto") -> str:
    """检测或指定文件编码。"""
    if encoding != "auto":
        return encoding

    try:
        import chardet

        with open(file_path, "rb") as f:
            raw = f.read(min(1024 * 64, os.path.getsize(file_path) or 1024))
            result = chardet.detect(raw)
            detected = result.get("encoding", "utf-8")
            if detected and detected.lower() != "ascii":
                return detected
    except Exception as e:
        logger.warning("chardet 检测编码失败 (%s)，降级为 utf-8", e)

    return "utf-8"


# ── 文件行读取（文本模式，统一用 \\\\n） ───────────────────


def read_file_lines(
    file_path: str,
    encoding: str = "auto",
) -> Tuple[List[str], str]:
    """读取文件全部内容，按 \\\\n 拆分成行列表。

    使用 Python 文本模式，Windows 上自动处理 \\\\r\\\\n → \\\\n 转换。

    Returns:
        (lines, resolved_encoding)
    """
    resolved_encoding = detect_encoding(file_path, encoding)

    with open(file_path, "r", encoding=resolved_encoding) as f:
        content = f.read()

    lines = content.split("\n")
    return lines, resolved_encoding


def read_file_content(
    file_path: str,
    encoding: str = "auto",
) -> Tuple[str, str]:
    """读取文件全部内容为字符串。"""
    resolved_encoding = detect_encoding(file_path, encoding)
    with open(file_path, "r", encoding=resolved_encoding) as f:
        content = f.read()
    return content, resolved_encoding


# ── 主行尾探测（v1.7.0 家族行尾保真）─────────────────────


def dominant_newline(content: str) -> Optional[str]:
    """探测文本的主行尾（作者裁决：auto = 保持文件真实主行尾）。

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


def detect_file_newline(path: str, encoding: str) -> Optional[str]:
    """探测已存在文件的真实主行尾；探测失败按无行尾处理（落回 OS）。"""
    try:
        with open(path, "r", encoding=encoding, newline="") as f:
            return dominant_newline(f.read())
    except Exception:
        return None


# ── 行内容截断 ────────────────────────────────────────────


def truncate_line(line: str, max_len: int = LINE_CONTENT_TRUNCATE) -> str:
    """截断超长行内容。"""
    if len(line) > max_len:
        return line[:max_len] + "<<truncated>>"
    return line


# ── CSV 格式化输出 ────────────────────────────────────────


def format_csv(
    rows: List[Dict[str, Any]],
    fieldnames: Optional[List[str]] = None,
) -> str:
    """将字典列表格式化为 CSV 字符串。"""
    if not rows:
        fieldnames = fieldnames or []
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        return output.getvalue()

    if fieldnames is None:
        fieldnames = list(rows[0].keys())

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    writer.writerows(rows)

    return output.getvalue()


# ── ToolChunk 结果封装 ────────────────────────────────────


def make_success(text: str) -> "ToolChunk":
    """构建成功结果。

    Args:
        text: 显示文本内容
    """
    _import_toolchunk()
    return _ToolChunk(
        is_last=True,
        state=_ToolResultState.SUCCESS,
        content=[_TextBlock(type="text", text=text)],
    )


def parse_int(value, param_name: str) -> Tuple[Optional[int], Optional[str]]:
    """将 int 或十进制数字字符串转换为 int。

    兼容 LLM 将数字参数传成字符串（如 "123"）的情况。
    - int → 原样返回
    - str → strip 后匹配十进制（可选负号），合法转 int
    - None → 原样返回（用于 Optional 参数未指定）
    - 其他 / 非法字符串 → 返回错误消息

    Args:
        value: 原始值，int / str / None
        param_name: 参数名，用于错误消息

    Returns:
        (int_or_None, None) 成功；
        (None, 错误消息) 非法输入
    """
    if value is None:
        return None, None
    if isinstance(value, bool):
        return None, f"{param_name} 参数应当输入整数，收到「{value}」"
    if isinstance(value, int):
        return value, None
    if isinstance(value, str):
        s = value.strip()
        if re.fullmatch(r"-?\d+", s):
            return int(s), None
    return None, f"{param_name} 参数应当输入整数，收到「{value}」"


def make_error(text: str, reason: str = "", suggestion: str = "") -> "ToolChunk":
    """构建错误结果。支持两种调用方式：
    - make_error("错误文本")
    - make_error("操作名", "原因", "建议")  # 自动调用 format_error 拼接

    Args:
        text: 错误文本，或 format_error 的 action 参数
        reason: 当提供时，与 text 一起传给 format_error
        suggestion: 当提供时，传给 format_error
    """
    _import_toolchunk()
    if reason:
        text = format_error(text, reason, suggestion)
    return _ToolChunk(
        is_last=True,
        state=_ToolResultState.ERROR,
        content=[_TextBlock(type="text", text=text)],
    )


_ToolChunk = None
_ToolResultState = None
_TextBlock = None


def _import_toolchunk():
    """延迟导入 agentscope 类型，避免模块级依赖。"""
    global _ToolChunk, _ToolResultState, _TextBlock
    if _ToolChunk is None:
        from agentscope.message import ToolResultState, TextBlock
        from agentscope.tool import ToolChunk

        _ToolChunk = ToolChunk
        _ToolResultState = ToolResultState
        _TextBlock = TextBlock

# ── 备份提示 ──────────────────────────────────────────────


def format_backup_info(backup_path: str, history_number: int) -> str:
    return (
        f"原文件已备份，历史号 #{history_number}。"
        f"如需恢复，请调用 file_tools_undo(path=\"{backup_path}\", "
        f"history_number={history_number})。"
    )


# ── 错误信息格式 ──────────────────────────────────────────


def format_error(action: str, reason: str, suggestion: str = "") -> str:
    # 全仓 39 处 reason 自带句尾「。」，此处兜底去重，杜绝「。。」（五轮盲测批评🥉）
    reason = reason.rstrip()
    if reason.endswith("。"):
        reason = reason[:-1]
    msg = f"{action}失败，因为{reason}。"
    if suggestion:
        msg += suggestion
    return msg


# ── 统一换行符 ────────────────────────────────────────────


def normalize_newlines(content: str) -> str:
    """统一换行符为 \\\\n。

    文本模式下 \\\\n 会被 Python 自动处理为系统默认行尾，
    但 \\\\r\\\\n 中的 \\\\n 再被转一次会变成 \\\\r\\\\r\\\\n，
    所以写入前必须把 \\\\r\\\\n/\\\\r 统一为 \\\\n。
    """
    return content.replace("\r\n", "\n").replace("\r", "\n")


# ── 文件类型检测 ──────────────────────────────────────────


def guess_file_type(file_path: str) -> Dict[str, Any]:
    """猜测文件类型和编码。"""
    result = {
        "type": "unknown",
        "subtype": "unknown",
        "encoding": None,
        "confidence": 0.0,
    }

    try:
        import puremagic

        mg = puremagic.magic_file(file_path)
        if mg:
            best = max(mg, key=lambda x: x.confidence)
            result["subtype"] = best.extension or "unknown"
            result["confidence"] = best.confidence

            mime = best.mime_type or ""
            if mime.startswith("text/"):
                result["type"] = "text"
            elif mime.startswith("image/"):
                result["type"] = "image"
            elif mime.startswith("audio/"):
                result["type"] = "audio"
            elif mime.startswith("video/"):
                result["type"] = "video"
            elif mime.startswith("application/"):
                result["type"] = "application"

            text_extensions = {"json", "xml", "yaml", "yml", "toml", "ini", "cfg", "conf"}
            if result["subtype"].lower() in text_extensions:
                result["type"] = "text"
    except ImportError:
        pass
    except Exception as e:
        logger.warning("puremagic 检测失败: %s", e)

    if result["type"] == "text":
        try:
            import chardet

            with open(file_path, "rb") as f:
                raw = f.read(min(1024 * 64, max(1024, os.path.getsize(file_path) or 1024)))
                cd = chardet.detect(raw)
                result["encoding"] = cd.get("encoding", "utf-8")
                if result["confidence"] is not None:
                    result["confidence"] = min(
                        result["confidence"],
                        cd.get("confidence", 0.0) if cd.get("confidence") else result["confidence"],
                    )
        except Exception as e:
            logger.warning("chardet 检测编码失败: %s", e)
            result["encoding"] = "utf-8"

    return result


# ── 会话路径（用于历史备份定位） ──────────────────────────


def get_session_dir() -> str:
    """获取 file_tools 数据目录根路径（agent 工作区内的 file_tools_data）。

    历史备份等 agent 状态固定存放在 agent 自己的工作区（小窝），
    不跟随聊天界面绑定的项目目录，避免写进用户项目。

    Returns:
        str: 数据目录根路径

    Raises:
        RuntimeError: QwenPaw 上下文未注入（agent 工作区未知）时抛出
    """
    from qwenpaw.config.context import get_current_workspace_dir

    ws = get_current_workspace_dir()
    if ws is None:
        raise RuntimeError(
            "无法获取 agent 工作区目录（QwenPaw 上下文未注入），"
            "无法确定备份文件存放位置。"
        )
    return os.path.join(str(ws), "file_tools_data")


# ── 路径编码（用于历史备份） ─────────────────────────────


def encode_path(path: str) -> str:
    """路径编码：len + blake2b[:32]"""
    path_bytes = path.encode("utf-8")
    hash_hex = hashlib.blake2b(path_bytes, digest_size=16).hexdigest()[:32]
    return f"{len(path)}{hash_hex}"


# ── Hex 解析（用于字节级工具） ────────────────────────────


def parse_hex(hex_str: str) -> bytes:
    """解析 hex 字符串为 bytes。

    规则：
    - 允许空格，自动忽略
    - 大小写不敏感
    - 不可以 0x 或 \\x 开头
    - 去掉空格后必须是有效 hex 字符
    - 去掉空格后长度必须是 2 的倍数（不自动补 0）

    Args:
        hex_str: hex 字符串

    Returns:
        bytes: 解析后的字节数据

    Raises:
        ValueError: 格式不符合规则时抛出
    """
    import string

    cleaned = hex_str.replace(" ", "").replace("\t", "").replace("\n", "").replace("\r", "")

    if not cleaned:
        return b""

    # 检查前缀
    if cleaned.startswith("0x") or cleaned.startswith("\\x"):
        raise ValueError(f"hex 字符串不可以以 0x 或 \\x 开头，请去掉前缀后重试")

    # 检查长度
    if len(cleaned) % 2 != 0:
        raise ValueError(
            f"hex 字符串长度 {len(cleaned)} 不是 2 的倍数，"
            f"每个字节需要 2 个 hex 字符，请检查输入是否完整"
        )

    # 检查字符有效性
    valid_hex = set(string.hexdigits)
    for c in cleaned:
        if c not in valid_hex:
            raise ValueError(f"hex 字符串包含无效字符「{c}」，仅支持 0-9 A-F a-f")

    return bytes.fromhex(cleaned)


def format_hex(data: bytes, group_size: int = 16) -> str:
    """将字节数据格式化为 hex 字符串（全大写）。

    Args:
        data: 字节数据
        group_size: -1=不分组，0=报错，>0=每行显示多少字节

    Returns:
        hex 字符串

    Raises:
        ValueError: group_size=0 时抛出
    """
    if group_size == 0:
        raise ValueError("group_size 不能为 0，请使用 -1（不分组）或正数（每行字节数）")

    hex_str = data.hex().upper()

    if group_size == -1:
        return hex_str

    # 按 group_size 分组，空格分隔
    lines = []
    for i in range(0, len(hex_str), group_size * 2):
        chunk = hex_str[i : i + group_size * 2]
        # 每两个字符一组加空格
        grouped = " ".join(chunk[j : j + 2] for j in range(0, len(chunk), 2))
        lines.append(grouped)

    return "\n".join(lines)
