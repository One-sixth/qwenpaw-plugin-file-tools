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
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────

LINE_CONTENT_TRUNCATE = 160
CSV_FIELD_TRUNCATE = 2048
DEFAULT_MAX_CHARS = 2048

# ── 路径标准化 ─────────────────────────────────────────────


def get_workspace_dir() -> Optional[str]:
    """获取QwenPaw默认工作区目录。

    优先用 tool_config 中配置的路径，兜底从 agent 配置读取。
    """
    try:
        from qwenpaw.plugins.api import get_tool_config

        config = get_tool_config("file_tools_listdir")
        if config and isinstance(config, dict):
            ws = config.get("workspace_dir")
            if ws:
                return str(ws)
    except Exception:
        pass

    try:
        from qwenpaw.config.utils import load_config

        cfg = load_config()
        profiles = cfg.agents.profiles  # dict[str, AgentProfileRef]
        if "default" in profiles:
            ws = profiles["default"].workspace_dir
            return str(Path(ws).expanduser().resolve())
        if profiles:
            first = next(iter(profiles.values()))
            ws = first.workspace_dir
            return str(Path(ws).expanduser().resolve())
    except Exception:
        pass
    return None


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

    for row in rows:
        safe_row = {}
        for k, v in row.items():
            if isinstance(v, str) and len(v) > CSV_FIELD_TRUNCATE:
                safe_row[k] = v[:CSV_FIELD_TRUNCATE] + "<<truncated>>"
            else:
                safe_row[k] = v
        writer.writerow(safe_row)

    return output.getvalue()


# ── 纯文本结果 ────────────────────────────────────────────


def make_result(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """构建结果文本，超出 max_chars 时截断。"""
    if len(text) > max_chars:
        return text[:max_chars] + "\n<<truncated>>"
    return text

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


def make_error(text: str) -> "ToolChunk":
    """构建错误结果。

    Args:
        text: 错误提示文本
    """
    _import_toolchunk()
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
    """获取当前会话的 _file_tools 备份目录根路径。

    Returns:
        str: 备份目录根路径

    Raises:
        RuntimeError: 无法获取工作区路径时抛出，附带联系维护者的提示
    """
    ws = get_workspace_dir()
    if not ws:
        raise RuntimeError(
            "无法获取 QwenPaw 工作区目录路径，无法确定备份文件存放位置。"
        )
    session_path = os.path.join(ws, "sessions", "console", "default_default.json")
    backup_root = session_path + "_file_tools"
    return backup_root


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
