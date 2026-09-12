"""信息读取类工具。

包含：
- file_tools_listdir: 列出目录内容（过滤器/递归/属性列/Markdown）
- file_tools_info: 查看文件元数据（JSON）
- file_tools_guess: 猜测文件类型（JSON）
- file_tools_diff: 文件差异对比（unified diff）
- file_tools_history: 查看文件历史版本（JSON）
"""

import csv
import difflib
import io
import json
import logging
import os
import re
import stat
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import pathspec

try:
    from ..backup.manager import list_history as _list_history
    from ..utils import (
        format_error,
        guess_file_type,
        detect_file_newline,
        make_error,
        make_success,
        parse_int,
        read_file_content,
        resolve_path,
    )
except ImportError:
    from backup.manager import list_history as _list_history
    from utils import (
        format_error,
        guess_file_type,
        detect_file_newline,
        make_error,
        make_success,
        parse_int,
        read_file_content,
        resolve_path,
    )

logger = logging.getLogger(__name__)


# ── 1. file_tools_listdir ─────────────────────────────────


_LISTDIR_TYPE_TOKENS = {"file", "dir", "symlink"}

_CYCLE_WARN_SUFFIX = " <<<警告，发现循环符号链接，跳过该文件夹展开>>>"
_BROKEN_SYMLINK_SUFFIX = " <<<警告，符号链接目标不可达>>>"

_LISTDIR_MAX_MATCH = 10000
_LISTDIR_MAX_VISIT = 100000


def _listdir_as_str_list(value: Any) -> Optional[List[str]]:
    """过滤参数输入归一为非空字符串列表。

    str 视为单值列表，但 JSON 编码的字符串数组（如 '["a", "b"]'）会先
    json.loads 还原再解析——部分调用通道会把数组参数序列化成字符串送达，
    若不还原会被整体当成一个字面量 token 导致过滤器静默失真。
    None/空列表/仅空串项均返回 None（即「不过滤」）。
    """
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        if s.startswith(("[", "{")):
            try:
                parsed = json.loads(s)
            except ValueError:
                parsed = None
            if isinstance(parsed, (list, tuple)):
                value = list(parsed)
            else:
                # 标量/字典/解析失败 → 保留原字符串为字面量 token，不炸不猜
                value = [value]
        else:
            value = [value]
    if not isinstance(value, (list, tuple)):
        return None
    items = [str(v) for v in value if str(v).strip() != ""]
    return items or None


def _listdir_norm_ext(token: str) -> str:
    """后缀 token 归一为不带点的小写形态："py"/".py"/"*.py" → "py"。"""
    t = token.strip().lower()
    if t.startswith("*."):
        return t[2:]
    if t.startswith("*"):
        return t[1:]
    if t.startswith("."):
        return t[1:]
    return t


def file_tools_listdir(
    path: str,
    recursive: Union[int, str] = 1,
    columns: Optional[List[str]] = None,
    start: Union[int, str] = 1,
    count: Union[int, str] = 500,
    sort_by: str = "name",
    ascending: bool = True,
    types: Optional[Union[str, List[str]]] = None,
    extensions: Optional[Union[str, List[str]]] = None,
    contains: Optional[Union[str, List[str]]] = None,
    regex: Optional[str] = None,
    exclude: Optional[Union[str, List[str]]] = None,
    follow_symlink: bool = True,
) -> str:
    """列出目录内容，可递归、过滤、排序、分页；输出路径相对遍历根、统一正斜杠、目录带尾斜杠。过滤器之间 AND、列表内 OR。

    Args:
        path: 目录路径。支持相对路径（相对于 workspace 目录）和绝对路径，支持 ~ 展开。
        recursive: 往下列几层。1=本层（默认），2=含子目录一层，-1=全部层。
        columns: 额外属性列：size、permissions、type、modified_at、created_at、extension。不传则不显示属性列。
        start: 起始条目序号，1-based，默认 1。
        count: 最多返回的条目数，默认 500，范围 1~500。
        sort_by: 排序字段：name（默认）、size、permissions、type、modified_at、created_at、extension。
        ascending: True 升序（默认）、False 降序。
        types: 按类型过滤，命中类型任一分段即可：file、dir、symlink。
        extensions: 后缀过滤，如 ["py", "md"]。只作用于文件，目录不受影响（想隐藏目录配 types=["file"]）。
        contains: 显示路径包含某子串即保留（大小写不敏感）。
        regex: 显示路径命中该正则（re.search 语义）即保留。
        exclude: 排除模式，gitignore 语法，按显示路径匹配、不解析符号链接，如 [".git", "build/", "!keep.log"]。命中目录整树跳过。
        follow_symlink: 是否进入符号链接目录，默认 True；环与断链会在输出行内以 <<<警告>>> 标注。
    """
    # ── 参数校验 ──
    recursive, err = parse_int(recursive, "recursive")
    if err:
        return make_error("列出目录", err)
    start, err = parse_int(start, "start")
    if err:
        return make_error("列出目录", err)
    count, err = parse_int(count, "count")
    if err:
        return make_error("列出目录", err)

    if recursive not in (1, 2, -1):
        return make_error(
            f"列出目录失败，因为 recursive 参数值 {recursive} 不合法。"
            f"合法值为：1（当前目录）、2（包含一层子目录）、-1（递归）。"
        )

    resolved = resolve_path(path)
    if not os.path.isdir(resolved):
        return make_error(
            f"列出目录失败，因为路径「{resolved}」不存在或不是一个目录。"
        )

    if start < 1:
        return make_error(
            f"列出目录失败，因为 start 参数值 {start} 不合法。"
            f"start 表示「从第几个条目开始显示」，最小值为 1。"
        )

    if count < 1 or count > 500:
        return make_error(
            f"列出目录失败，因为 count 参数值 {count} 不合法。"
            f"count 范围为 1~500。"
        )

    valid_sort = {"name", "size", "permissions", "type", "modified_at", "created_at", "extension"}
    if sort_by not in valid_sort:
        return make_error(
            f"列出目录失败，因为 sort_by 参数值「{sort_by}」不合法。"
            f"合法值为：{', '.join(sorted(valid_sort))}。"
        )

    # ── 过滤器参数规范化 ──
    type_set: Optional[set] = None
    types_list = _listdir_as_str_list(types)
    if types_list:
        norm_types = []
        for t in types_list:
            key = t.strip().lower()
            if key not in _LISTDIR_TYPE_TOKENS:
                return make_error(
                    "列出目录",
                    f"types 参数值「{t}」不合法。合法值为：file、dir、symlink"
                    "（命中类型任一分段即保留），不填为全部。",
                )
            norm_types.append(key)
        type_set = set(norm_types)

    regex_pat = None
    if isinstance(regex, str) and regex.strip():
        try:
            regex_pat = re.compile(regex)
        except re.error as exc:
            return make_error(
                "列出目录", f"regex 参数不是合法的正则表达式：{exc}"
            )

    ext_list = _listdir_as_str_list(extensions)
    ext_set = None
    if ext_list:
        # 归一后丢弃空 token（"."/"*." 这类无效项），避免误命中"无后缀文件"
        ext_set = {e for e in (_listdir_norm_ext(t) for t in ext_list) if e} or None
    contains_list = _listdir_as_str_list(contains)
    contains_terms = [t.lower() for t in contains_list] if contains_list else None
    exclude_list = _listdir_as_str_list(exclude)
    exclude_spec = None
    if exclude_list:
        try:
            exclude_spec = pathspec.PathSpec.from_lines(
                "gitignore",
                [t.strip().lower().replace("\\", "/") for t in exclude_list],
            )
        except (ValueError, re.error) as exc:
            # 覆盖 GitIgnorePatternError（如半截 "!"，继承 ValueError）与坏字符集 re.error
            return make_error(
                "列出目录", f"exclude 含不合法的 gitignore 模式：{exc}"
            )

    filter_active = any(
        x is not None
        for x in (type_set, ext_set, contains_terms, regex_pat, exclude_spec)
    )

    # ── 确定需要收集的列 ──
    columns = _listdir_as_str_list(columns) or []
    valid_columns = {"size", "permissions", "type", "modified_at", "created_at", "extension"}
    extra_columns = [c for c in columns if c in valid_columns]

    # 排序所需的列（sort_by 不是 name 时，需要在 scan 时额外收集）
    gather_set = set(extra_columns)
    if sort_by != "name" and sort_by in valid_columns:
        gather_set.add(sort_by)

    # ── 扫描 ──
    rows: List[Dict[str, Any]] = []
    visited = 0
    matched = 0
    max_match = _LISTDIR_MAX_MATCH
    max_visit = _LISTDIR_MAX_VISIT
    stop_flags = {"match_cap": False, "visit_cap": False}
    max_depth = {1: 1, 2: 2, -1: 10 ** 9}[recursive]

    def _entry_type(entry: os.DirEntry) -> "tuple[str, Any]":
        """条目本质类型（显示/过滤用）：dir、file、symlink|dir、symlink|file、symlink|invalid。

        返回 (type串, 跟随链后的 stat 或 None)。链接条目必 stat 判定目标类型与可达性，
        与 follow_symlink（是否展开）无关——type 答"材质"，遍历答"进不进"，两维正交。
        """
        try:
            is_link = entry.is_symlink()
        except OSError:
            is_link = False
        if is_link:
            try:
                st = entry.stat(follow_symlinks=True)
            except OSError:
                st = None
            if st is None:
                return "symlink|invalid", None
            kind = "dir" if stat.S_ISDIR(st.st_mode) else "file"
            return f"symlink|{kind}", st
        try:
            return ("dir" if entry.is_dir(follow_symlinks=True) else "file"), None
        except OSError:
            return "file", None

    def _scan(dir_path: str, depth: int, ancestors: set) -> None:
        nonlocal visited, matched
        try:
            entries = list(os.scandir(dir_path))
        except OSError:
            return
        for entry in entries:
            visited += 1
            if visited > max_visit:
                stop_flags["visit_cap"] = True
                return

            etype, link_st = _entry_type(entry)
            is_dirish = etype in ("dir", "symlink|dir")

            # 环检测：仅对「准备进入」的目录计算 realpath（普通目录链无环风险，开销可忽略）
            descend = (etype == "dir" or (etype == "symlink|dir" and follow_symlink)) and depth < max_depth
            rp = None
            is_cycle = False
            if descend:
                try:
                    rp = os.path.realpath(entry.path)
                except OSError:
                    rp = None
                if rp is not None and rp in ancestors:
                    is_cycle = True
                    descend = False

            # 显示串：相对遍历根、统一正斜杠；disp 不带尾斜杠（exclude 匹配用），disp_full 带（列表/匹配用）
            disp = os.path.relpath(entry.path, resolved).replace("\\", "/")
            base = entry.name
            disp_full = disp + "/" if is_dirish else disp

            # exclude：gitignore 语义。目录带尾斜杠喂入（`build/` 型模式），命中目录=整树剪枝，命中文件=跳过；`!` 取反后到先中
            if exclude_spec is not None and exclude_spec.match_file(
                (disp + "/" if is_dirish else disp).lower()
            ):
                continue

            # 五类正向过滤器：参数间 AND、列表内 OR；extensions 对目录直通
            ok = True
            if type_set is not None and type_set.isdisjoint(etype.split("|")):
                ok = False
            if ok and ext_set is not None and not is_dirish:
                _, ext = os.path.splitext(base)
                if ext.lower().lstrip(".") not in ext_set:
                    ok = False
            if ok and contains_terms is not None:
                low = disp_full.lower()
                if not any(t in low for t in contains_terms):
                    ok = False
            if ok and regex_pat is not None and regex_pat.search(disp_full) is None:
                ok = False

            if ok:
                row: Dict[str, Any] = {"name": disp_full}
                if is_cycle:
                    row["warn"] = True
                # 断链检测：链的 stat 已在 _entry_type 完成（link_st=None 即不可达）；
                # 普通 file/dir 维持惰性（仅 gather 需要时 stat）
                st = link_st
                if etype == "symlink|invalid":
                    row["broken"] = True
                if st is None and gather_set:
                    try:
                        st = entry.stat()
                    except OSError:
                        st = None
                if gather_set:
                    for col in gather_set:
                        if col == "size":
                            row["size"] = st.st_size if st else 0
                        elif col == "permissions":
                            row["permissions"] = stat.filemode(st.st_mode) if st else ""
                        elif col == "type":
                            row["type"] = etype
                        elif col == "modified_at":
                            row["modified_at"] = (
                                datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                                if st else ""
                            )
                        elif col == "created_at":
                            row["created_at"] = (
                                datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                                if st else ""
                            )
                        elif col == "extension":
                            _, ext = os.path.splitext(base)
                            row["extension"] = ext.lower() if ext else ""
                rows.append(row)
                matched += 1
                if matched >= max_match:
                    stop_flags["match_cap"] = True
                    return

            # 遍历与显示过滤无关：未列出的目录照样下降（exclude 剪枝与环除外）
            if descend:
                _scan(entry.path, depth + 1, ancestors | {rp})
                if stop_flags["match_cap"] or stop_flags["visit_cap"]:
                    return

    # 根祖先链初始化：realpath 极端失败不应炸掉整个调用（退回 resolved 本身，
    # 代价仅是该次调用失去环检测，功能不中断）
    try:
        root_rp = os.path.realpath(resolved)
    except OSError:
        root_rp = resolved
    _scan(resolved, 1, {root_rp})
    # 截断场景下对外口径统一为"检查到上限为止"，避免 visited 计数比文案多 1
    visited_display = min(visited, max_visit)

    def _match_cap_note() -> str:
        return (
            f"\n目标文件夹搜索文件超过{max_match}条，当前可以通过翻页 获取前{max_match}条文件信息。"
            "如需获取更多的文件条目，请尝试其他方法。\n"
        )

    def _visit_cap_note(matched_now: int) -> str:
        return (
            f"\n已检查 {max_visit} 个条目，提前停止扫描（当前匹配 {matched_now} 条）。"
            "建议用 exclude 剪除噪音目录、收紧过滤条件或减小 recursive。\n"
        )

    if not rows:
        if filter_active:
            msg = f"（无匹配条目，共扫描 {visited_display} 条）"
            if stop_flags["visit_cap"]:
                msg += _visit_cap_note(0)
            return make_success(msg)
        return make_success("（空目录，无条目）")

    # ── 排序（按警告后缀拼接前的纯路径串） ──
    if sort_by == "name":
        rows.sort(key=lambda r: r["name"].lower(), reverse=not ascending)
    else:
        rows.sort(key=lambda r: r.get(sort_by, ""), reverse=not ascending)

    # ── 分页 ──
    total = len(rows)
    start_idx = start - 1
    if start_idx >= total:
        msg = f"（没有更多条目，共 {total} 个条目，当前从第 {start} 个开始）"
        if filter_active:
            msg += f"\n过滤统计：共扫描 {visited_display} 条，匹配 {total} 条。"
            if stop_flags["match_cap"]:
                msg += _match_cap_note()
            elif stop_flags["visit_cap"]:
                msg += _visit_cap_note(total)
        return make_success(msg)

    end_idx = min(start_idx + count, total)
    page = rows[start_idx:end_idx]

    # ── 输出格式 ──
    def _display_name(r: Dict[str, Any]) -> str:
        if r.get("warn"):
            return r["name"] + _CYCLE_WARN_SUFFIX
        if r.get("broken"):
            return r["name"] + _BROKEN_SYMLINK_SUFFIX
        return r["name"]

    if not extra_columns:
        # 纯文本列表
        output = "\n".join(_display_name(r) for r in page)
    else:
        # Markdown 表格
        fieldnames = ["name"] + extra_columns
        header = "| " + " | ".join(fieldnames) + " |"
        separator = "|" + "|".join("---" for _ in fieldnames) + "|"
        data_lines = []
        for r in page:
            cells = [_display_name(r)] + [str(r.get(col, "")) for col in extra_columns]
            data_lines.append("| " + " | ".join(cells) + " |")
        output = header + "\n" + separator + "\n" + "\n".join(data_lines)

    # ── 尾部信息 ──
    end_display = start + len(page) - 1
    remaining = total - end_display
    if remaining > 0:
        output += f"\n\n当前列出的条目 {start}~{end_display}，后面还有 {remaining} 个条目。"
    if filter_active:
        output += f"\n过滤统计：共扫描 {visited_display} 条，匹配 {total} 条。"

    if stop_flags["match_cap"]:
        output += _match_cap_note()
    elif stop_flags["visit_cap"]:
        output += _visit_cap_note(total)

    return make_success(output)


# ── 2. file_tools_info ────────────────────────────────────


def file_tools_info(
    path: str,
) -> str:
    """查看文件或目录的元数据，返回 JSON 格式。包含路径、大小、权限、创建时间和修改时间等信息。路径不存在时返回错误提示。

    Args:
        path: 文件或目录路径。相对路径相对于 workspace 目录，支持 ~ 展开。路径不存在时返回提示，请检查路径拼写。
    """
    resolved = resolve_path(path)
    if not os.path.exists(resolved):
        return make_error(format_error(
            "查看文件信息",
            f"路径「{resolved}」不存在",
            "请使用 file_tools_listdir 确认文件是否存在，或检查路径拼写是否正确。",
        ))

    try:
        st = os.stat(resolved)
    except OSError as e:
        return make_success(json.dumps({
            "path": resolved,
            "error": f"无法读取文件元数据: {e}",
        }, ensure_ascii=False))

    info: Dict[str, Any] = {
        "path": resolved,
        "exists": True,
        "size": st.st_size,
        "is_dir": os.path.isdir(resolved),
        "is_file": os.path.isfile(resolved),
        "is_link": os.path.islink(resolved),
        "permissions": stat.filemode(st.st_mode),
        "created_at": datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
        "modified_at": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }

    return make_success(json.dumps(info, ensure_ascii=False, indent=2))


# ── 3. file_tools_guess ───────────────────────────────────


def file_tools_guess(
    path: str,
) -> str:
    """猜测文件类型和编码，返回 JSON 格式。根据文件魔数（magic number）检测类型，文本自动检测编码。目录直接返回 type 为 directory。检测库未安装时降级处理。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。如果是目录直接返回 type=directory，不执行魔数检测。
    """
    resolved = resolve_path(path)

    if not os.path.exists(resolved):
        return make_success(json.dumps({
            "path": resolved,
            "error": "文件不存在",
        }, ensure_ascii=False))

    if os.path.isdir(resolved):
        return make_success(json.dumps({
            "path": resolved,
            "type": "directory",
            "subtype": "directory",
            "encoding": None,
            "confidence": 1.0,
        }, ensure_ascii=False))

    result = guess_file_type(resolved)
    result["path"] = resolved
    return make_success(json.dumps(result, ensure_ascii=False, indent=2))


# ── 4. file_tools_diff ────────────────────────────────────

DIFF_MAX_CHARS_FLOOR = 1000   # max_chars 下限：保证折叠名片/部分展开有健康工作区
DIFF_LINE_LENGTH_FLOOR = 100  # max_line_length 下限：正常代码行不截断


def file_tools_diff(
    path_a: str,
    path_b: str,
    start: Union[int, str] = 1,
    count: Union[int, str] = 10,
    max_chars: Union[int, str] = 5000,
    max_line_length: Union[int, str] = 600,
) -> str:
    """对比两个文件的差异，返回 unified diff 格式。支持 hunk 分页，可指定从第几个差异块开始显示。文件相同时返回「文件相同，没有差异。」装不下的 hunk 会折叠成一行摘要并附翻页指引，单行超过 max_line_length 会被截断标记。

    Args:
        path_a: 旧文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        path_b: 新文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        start: 起始 hunk 序号，1-based。从第几个差异块开始显示，最小值为 1。支持整数或十进制数字字符串。
        count: 最多显示多少个差异块，默认 10。支持整数或十进制数字字符串。
        max_chars: 返回内容总字符上限，默认 5000，最小 1000（低于按 1000 处理）。装不下的 hunk 折叠并给指引。支持整数或十进制数字字符串。
        max_line_length: 单行字符上限，默认 600，最小 100（低于按 100 处理）。超过时截断该行并标记。支持整数或十进制数字字符串。
    """
    resolved_a = resolve_path(path_a)
    resolved_b = resolve_path(path_b)

    start, err = parse_int(start, "start")
    if err:
        return make_error("对比", err)
    count, err = parse_int(count, "count")
    if err:
        return make_error("对比", err)
    max_chars, err = parse_int(max_chars, "max_chars")
    if err:
        return make_error("对比", err)
    max_line_length, err = parse_int(max_line_length, "max_line_length")
    if err:
        return make_error("对比", err)

    if not os.path.isfile(resolved_a):
        return make_error(f"对比失败，因为找不到旧文件「{resolved_a}」。请确认路径是否正确。")
    if not os.path.isfile(resolved_b):
        return make_error(f"对比失败，因为找不到新文件「{resolved_b}」。请确认路径是否正确。")

    try:
        content_a, resolved_encoding = read_file_content(resolved_a)
        content_b, _ = read_file_content(resolved_b)
    except Exception as e:
        return make_error(f"对比失败，因为读取文件时出错：{e}。")

    lines_a = content_a.splitlines(keepends=True)
    lines_b = content_b.splitlines(keepends=True)

    # 生成 unified diff
    diff_lines = list(
        difflib.unified_diff(
            lines_a,
            lines_b,
            fromfile=resolved_a,
            tofile=resolved_b,
            lineterm="",
        )
    )

    # 按 hunk 分组
    hunks: List[List[str]] = []
    current_hunk: List[str] = []

    for line in diff_lines:
        if line.startswith("@@"):
            if current_hunk:
                hunks.append([l.rstrip("\r\n") for l in current_hunk])
            current_hunk = [line]
        elif current_hunk:
            current_hunk.append(line)

    if current_hunk:
        hunks.append([l.rstrip("\r\n") for l in current_hunk])

    if not hunks:
        # universal newline 读取下行尾差异不可见，行尾风格不同时显式提示
        nl_a = detect_file_newline(resolved_a, resolved_encoding)
        nl_b = detect_file_newline(resolved_b, resolved_encoding)
        if nl_a != nl_b:
            names = {"\r\n": "CRLF", "\n": "LF", "\r": "CR", None: "无换行"}
            return make_success(
                f"文件相同，没有差异。（两文件仅行尾风格不同：旧={names.get(nl_a, nl_a)}，新={names.get(nl_b, nl_b)}）"
            )
        return make_success("文件相同，没有差异。")

    # 分页
    total_hunks = len(hunks)
    if start < 1:
        return make_error("对比", f"start 参数值 {start} 不合法。start 表示「从第几个 hunk 开始显示」，最小值为 1")
    if count < 1:
        return make_error("对比", f"count 参数值 {count} 不合法。count 表示「最多显示多少个差异块」，最小值为 1")
    if start > total_hunks:
        return make_error("对比", f"start 参数值 {start} 超出差异块总数（共 {total_hunks} 个）。start 取值范围 1~{total_hunks}")
    end_idx = min(start - 1 + count, total_hunks)
    selected = hunks[start - 1 : end_idx]

    # 参数下限钳制
    max_chars = max(max_chars, DIFF_MAX_CHARS_FLOOR)
    max_line_length = max(max_line_length, DIFF_LINE_LENGTH_FLOOR)

    # 行长截断：超长行截到 max_line_length 并标记（按 hunk 计数，尾部汇总只计实际输出的）
    trunc_per_hunk: List[int] = []
    for hunk in selected:
        count_trunc = 0
        for j, line in enumerate(hunk):
            if len(line) > max_line_length:
                hunk[j] = line[:max_line_length] + "<<<TRUNCATED>>>"
                count_trunc += 1
        trunc_per_hunk.append(count_trunc)

    # 跳跃装填：放不下的 hunk 折叠成名片并继续尝试后续；末位 hunk 部分展开
    parts: List[str] = [f"共有 {total_hunks} 个差异块，显示第 {start}~{end_idx} 个：\n"]
    used = len(parts[0])
    hidden: List[Tuple[int, int]] = []  # 兜底汇总的 (全局序号, 成本)
    truncated_out = 0  # 实际输出 hunk 的截断行数

    def hunk_cost(hunk: List[str], n: int) -> int:
        # 展开成本估算：@@ 行含序号后缀，每行含换行，块尾空行
        return sum(len(line) + 1 for line in hunk) + len(f" #{n}") + 1

    for i, hunk in enumerate(selected):
        n = start + i
        header = hunk[0] + f" #{n}\n"
        cost = hunk_cost(hunk, n)

        if used + cost <= max_chars:
            # 全展开
            parts.append(header)
            parts.extend(line + "\n" for line in hunk[1:])
            parts.append("\n")
            used += cost
            truncated_out += trunc_per_hunk[i]
            continue

        is_last = i == len(selected) - 1
        # 末位 hunk：至少能放下 @@ 头 + 首行内容时部分展开，线性装填到预算耗尽
        if is_last and used + len(header) + len(hunk[1]) + 1 <= max_chars:
            parts.append(header)
            used += len(header)
            shown = 0
            for line in hunk[1:]:
                if used + len(line) + 1 > max_chars:
                    break
                parts.append(line + "\n")
                used += len(line) + 1
                shown += len(line)
            used += 1  # 块尾空行
            parts.append(
                f"[该 hunk 展开约 {cost} 字符，仅显示前 {shown} 字符。"
                f"完整查看：start={n} count=1 max_chars={cost + 500}]\n"
            )
            truncated_out += trunc_per_hunk[i]
            continue

        # 折叠名片（超出剩余预算 / 超出 max_chars 上限，均附完整查看建议）
        over = (
            f"超出 max_chars={max_chars} 上限，已折叠。"
            if cost > max_chars
            else "超出剩余预算，已折叠。"
        )
        note = f"[该 hunk 展开约 {cost} 字符，{over}查看：start={n} count=1 max_chars={cost + 500}]\n"
        if used + len(header) + len(note) + 1 <= max_chars:
            parts.append(header + note + "\n")
            used += len(header) + len(note) + 1
        else:
            hidden.append((n, cost))

    if hidden:
        n0, n1 = hidden[0][0], hidden[-1][0]
        total_cost = sum(c for _, c in hidden)
        span = n1 - n0 + 1
        parts.append(
            f"\n[另有 {len(hidden)} 个差异块未显示（约 {total_cost} 字符）。查看：start={n0} count={span}]\n"
        )

    if truncated_out:
        parts.append(
            f"\n<<<TRUNCATED>>>共 {truncated_out} 行因超过 max_line_length={max_line_length} 被截断。\n"
        )

    return make_success("".join(parts))


# ── 5. file_tools_history ─────────────────────────────────


def file_tools_history(
    path: str,
) -> str:
    """查看文件的历史备份版本列表，返回 JSON 格式。包含每个历史版本的编号（history_number）和创建时间。文件没有历史版本时返回空列表。历史版本由修改类工具（append、replace_lines 等）在修改前自动创建。

    Args:
        path: 文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。文件不存在时返回对应的错误信息。
    """
    resolved = resolve_path(path)

    if not os.path.isfile(resolved):
        return make_success(json.dumps({
            "path": resolved,
            "error": "文件不存在",
        }, ensure_ascii=False))

    history = _list_history(resolved)

    return make_success(json.dumps({
        "path": resolved,
        "history": history,
    }, ensure_ascii=False, indent=2))
