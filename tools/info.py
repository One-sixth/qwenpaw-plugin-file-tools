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
import fnmatch
import io
import json
import logging
import os
import re
import stat
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

try:
    from ..backup.manager import list_history as _list_history
    from ..utils import (
        CSV_FIELD_TRUNCATE,
        DEFAULT_MAX_CHARS,
        format_csv,
        format_error,
        guess_file_type,
        make_error,
        make_result,
        make_success,
        parse_int,
        read_file_content,
        resolve_path,
    )
except ImportError:
    from backup.manager import list_history as _list_history
    from utils import (
        CSV_FIELD_TRUNCATE,
        DEFAULT_MAX_CHARS,
        format_csv,
        format_error,
        guess_file_type,
        make_error,
        make_result,
        make_success,
        parse_int,
        read_file_content,
        resolve_path,
    )

logger = logging.getLogger(__name__)


# ── 1. file_tools_listdir ─────────────────────────────────


_LISTDIR_TYPE_ALIAS = {
    "file": "file",
    "dir": "directory",
    "directory": "directory",
    "symlink": "symlink",
    "link": "symlink",
    "all": "all",
}

_CYCLE_WARN_SUFFIX = " <<<警告，发现symlink环嵌套，跳过该文件夹展开>>>"
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
    absolute: bool = False,
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
    """列出目录内容。支持递归遍历、类型/后缀/子串/正则/排除五类过滤器、符号链接跟随控制、自定义属性列、排序和分页。过滤器之间 AND、列表内 OR；路径输出统一正斜杠分隔，目录条目带尾斜杠。匹配超过 10000 条或检查超过 100000 条时截断。无 columns 时返回纯文本列表（一行一文件），有 columns 时返回 Markdown 表格。

    Args:
        path: 目录路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        recursive: 递归深度。1=仅当前目录（默认），2=包含一层子目录，-1=无限递归。匹配超过 10000 条或检查超过 100000 条时提前停止，更多条目需缩小范围或用其他方法获取。支持整数或十进制数字字符串。
        columns: 额外属性列的列表。可选值：size（字节数；Windows 下目录恒为 0，断链 symlink 取不到元数据时为空/0）、permissions（Unix 风格权限字符串）、type（file/directory/symlink）、modified_at（最后修改时间）、created_at（创建时间）、extension（小写扩展名）。为空时不显示属性列。
        absolute: 路径显示模式。False=相对路径（默认，以目标目录为根），True=绝对路径。两种模式路径均统一为正斜杠「/」分隔，目录条目带尾斜杠。
        start: 起始序号，1-based。从第几个条目开始显示，默认 1。超出条目总数时返回「没有更多条目」提示。支持整数或十进制数字字符串。
        count: 最多返回的条目数（目录、symlink 均计入），默认 500。范围 1~500，超出时报错。支持整数或十进制数字字符串。
        sort_by: 排序字段。name=按文件名排序（默认，大小写不敏感），也可按 size、permissions、type、modified_at、created_at、extension 排序。稳定排序，同值条目保持遍历收集次序，不承诺跨调用可复现。
        ascending: 排序方向。True=升序排列（默认），False=降序排列。
        types: 条目类型过滤器。可选值 file、dir（别名 directory）、symlink（别名 link）、all；列表内任一命中即通过（OR），大小写不敏感；任何非法值都会报错（与列表顺序无关），全部合法且含 all 时本过滤器不生效。None 或空列表 = 不过滤。只控制显示清单，不影响是否进入目录遍历。
        extensions: 后缀名过滤器，如 ["py", "md"]。容忍 "py"/".py"/"*.py" 写法，大小写不敏感，列表内 OR，只匹配条目自身名的后缀；"."/"*." 这类归一后为空的无效 token 会被忽略（全部无效时=不过滤）。目录条目一律直通（不受本过滤器影响；想隐藏目录用 types=["file"]）。空列表 = 不过滤。
        contains: 子串过滤器。对完整显示路径（正斜杠、含目录尾斜杠）做大小写不敏感的子串匹配——所见即所搜，路径任意一段命中即可，列表内 OR；匹配基准是输出串，请写正斜杠（传反斜杠不归一、不会命中）。子串可命中路径任意片段、含父目录名（如 "tools/" 会连 file-tools/ 下的条目一起命中）；想限定某目录请用斜杠边界如 "/utils/"（顶层目录够不到）或改用 regex "(^|/)utils/" 锚定。空列表 = 不过滤。
        regex: 正则过滤器。底层实现为 re.search（子串匹配语义：模式可命中路径任意位置，无需写 .* 包裹），匹配对象为完整显示路径（正斜杠、目录带尾斜杠）。大小写敏感，可用前缀 (?i) 忽略大小写。示例：(^|/)src/ 限定 src 目录下（单 ^src/ 只命中顶层，absolute 模式下 ^ 锚在盘符头永不命中）、\\.md$ 只命中文件（目录带尾斜杠被 $ 天然排除）、/$ 只命中目录。非法正则报错。
        exclude: 排除过滤器，glob 模式列表，如 [".git", "__pycache__", "*/tests/*", "*.tmp"]。对 {条目名, 显示路径(去尾斜杠)} 两个串做大小写不敏感的 fnmatch 整串匹配，任一命中即排除；模式中的反斜杠自动视为正斜杠。命中目录时整树剪枝（不进入、不列出），命中文件时跳过。空列表 = 不过滤。
        follow_symlink: 是否跟随符号链接目录。True（默认）=进入符号链接目录，类型按目标判定（链接目录记 directory、链接文件记 symlink）；并启用 realpath 祖先链环检测：链接指向本次遍历路径上的祖先目录时不展开该条目，其显示行尾追加「<<<警告，发现symlink环嵌套，跳过该文件夹展开>>>」标记（警告标记不参与过滤匹配，警告行本身作为普通目录条目受各过滤器管辖）。False=符号链接一律记为 symlink 类型、不进入符号链接目录。断链（目标不存在/不可访问的符号链接）在任何模式下都会以 symlink 类型列出并在行尾追加「<<<警告，符号链接目标不可达>>>」，与环警告同规则——仅在输出阶段拼接、不参与匹配与排序，元数据列取不到时为空/0。
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
            alias = _LISTDIR_TYPE_ALIAS.get(key)
            if alias is None:
                return make_error(
                    "列出目录",
                    f"types 参数值「{t}」不合法。合法值为：file、dir（directory）、symlink（link）、all。",
                )
            norm_types.append(alias)
        # 先全量校验、再判 all：避免 ["all","bogus"] 因顺序跳过校验
        if "all" not in norm_types:
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
    exclude_pats = (
        [t.strip().lower().replace("\\", "/") for t in exclude_list]
        if exclude_list
        else None
    )

    filter_active = any(
        x is not None
        for x in (type_set, ext_set, contains_terms, regex_pat, exclude_pats)
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

    def _entry_type(entry: os.DirEntry) -> str:
        try:
            is_link = entry.is_symlink()
        except OSError:
            is_link = False
        if is_link and not follow_symlink:
            return "symlink"
        try:
            is_dir = entry.is_dir(follow_symlinks=True)
        except OSError:
            is_dir = False
        if is_dir:
            return "directory"
        return "symlink" if is_link else "file"

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

            etype = _entry_type(entry)

            # 环检测：仅对「准备进入」的目录计算 realpath（普通目录链无环风险，开销可忽略）
            descend = etype == "directory" and depth < max_depth
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

            # 显示串：统一正斜杠；disp 不带尾斜杠（exclude 匹配用），disp_full 带（列表/匹配用）
            if absolute:
                disp = entry.path
            else:
                disp = os.path.relpath(entry.path, resolved)
            disp = disp.replace("\\", "/")
            base = entry.name
            disp_full = disp + "/" if etype == "directory" else disp

            # exclude：目录命中 = 整树剪枝，文件命中 = 跳过
            if exclude_pats is not None and (
                any(fnmatch.fnmatchcase(base.lower(), p) for p in exclude_pats)
                or any(fnmatch.fnmatchcase(disp.lower(), p) for p in exclude_pats)
            ):
                continue

            # 五类正向过滤器：参数间 AND、列表内 OR；extensions 对目录直通
            ok = True
            if type_set is not None and etype not in type_set:
                ok = False
            if ok and ext_set is not None and etype != "directory":
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
                # 断链检测：symlink 条目必须 stat（判定目标可达性，
                # 与 columns 需求共用一次调用）；普通 file/dir 维持惰性
                st = None
                if etype == "symlink" or gather_set:
                    try:
                        st = entry.stat()
                    except OSError:
                        st = None
                if etype == "symlink" and st is None:
                    row["broken"] = True
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
        return make_success("（空目录，无文件）")

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


def file_tools_diff(
    path_a: str,
    path_b: str,
    start: Union[int, str] = 1,
    count: Union[int, str] = 10,
    max_chars: Union[int, str] = 2048,
) -> str:
    """对比两个文件的差异，返回 unified diff 格式。支持 hunk 分页，可指定从第几个差异块开始显示。文件相同时返回「文件相同，没有差异。」

    Args:
        path_a: 旧文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        path_b: 新文件路径。相对路径相对于 workspace 目录，支持 ~ 展开。
        start: 起始 hunk 序号，1-based。从第几个差异块开始显示，最小值为 1。支持整数或十进制数字字符串。
        count: 最多显示多少个差异块，默认 10。支持整数或十进制数字字符串。
        max_chars: 返回内容总字符上限，默认 2048。超过时自动截断。支持整数或十进制数字字符串。
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

    if not os.path.isfile(resolved_a):
        return make_error(f"对比失败，因为找不到旧文件「{resolved_a}」。请确认路径是否正确。")
    if not os.path.isfile(resolved_b):
        return make_error(f"对比失败，因为找不到新文件「{resolved_b}」。请确认路径是否正确。")

    try:
        content_a, _ = read_file_content(resolved_a)
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
                hunks.append(current_hunk)
            current_hunk = [line]
        elif current_hunk:
            current_hunk.append(line)

    if current_hunk:
        hunks.append(current_hunk)

    if not hunks:
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

    output_lines = [f"共有 {total_hunks} 个差异块，显示第 {start}~{end_idx} 个：\n"]
    for hunk in selected:
        output_lines.extend(hunk)
        output_lines.append("")

    result = "".join(output_lines)
    return make_success(make_result(result, max_chars))


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
