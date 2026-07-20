# -*- coding: utf-8 -*-
"""File Tools 插件入口。

注册 25 个文件操作工具到 QwenPaw Agent 工具箱。
"""

import logging

from qwenpaw.plugins.api import PluginApi

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
            description=(
                "列出目录内容，返回 CSV。隐藏文件默认包含。\n\n"
                "参数：\n"
                " path(str) 目标目录路径\n"
                " recursive(int) 1=当前目录，2=当前+一层子目录，-1=无限递归(>10000文件截断)\n"
                " columns(list) 额外列：size/permissions/type/modified_at/created_at/extension\n\n"
                "输出按文件名升序，目录排在文件前。路径不存在时返回错误提示。"
            ),
            icon="📂",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_info",
            tool_func=file_tools_info,
            description=(
                "查看文件/目录的详细元数据，返回 JSON。\n\n"
                "参数：\n"
                " path(str) 目标路径\n\n"
                "返回字段：path/size/is_dir/is_file/is_link/permissions/created_at/modified_at。"
                "文件不存在时 exists=false，不返回其他字段。"
            ),
            icon="ℹ️",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_guess",
            tool_func=file_tools_guess,
            description=(
                "猜测文件类型和编码，返回 JSON。\n\n"
                "参数：\n"
                " path(str) 文件路径\n\n"
                "返回字段：type(text/image/audio/video/application/unknown)/subtype/encoding/confidence。"
                "目录返回 type=directory，不存在的文件返回 error。"
            ),
            icon="🔍",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_diff",
            tool_func=file_tools_diff,
            description=(
                "对比两个文件的差异，返回 unified diff。\n\n"
                "参数：\n"
                " path_a(str) 旧文件路径\n"
                " path_b(str) 新文件路径\n"
                " start(int) 从第几个hunk开始，1-based，默认1\n"
                " count(int) 最多显示多少个hunk，默认10\n"
                " max_chars(int) 返回内容字符上限，默认2048\n\n"
                "文件相同时返回「文件相同，没有差异。」。start<1报错。"
            ),
            icon="📋",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_history",
            tool_func=file_tools_history,
            description=(
                "查看文件的历史版本列表（修改类工具执行前自动备份），返回 JSON。\n\n"
                "参数：\n"
                " path(str) 文件路径\n\n"
                '返回 {"history": [{"number":1,"created_at":"..."},...]}。'
                "number=1是最旧，越大越新。无历史时数组为空。可用undo恢复到指定版本。"
            ),
            icon="🕐",
            enabled=True,
        )

        # ── 文本读取类 ──
        api.register_tool(
            tool_name="file_tools_read_lines",
            tool_func=file_tools_read_lines,
            description=(
                "按行读取文本文件，返回 CSV（列名：line_number,content）。\n\n"
                "参数：\n"
                " path(str) 文件路径\n"
                " start_line(int) 起始行号，1-based，默认1\n"
                " line_count(int) 读取行数，-1=到末尾，默认20\n"
                " max_chars(int) 返回内容字符上限，默认2048\n"
                " encoding(str) auto=自动检测，或指定 utf-8/gbk\n\n"
                "示例：read_lines(\"app.log\", start_line=8, line_count=-1) → 查看日志尾部\n\n"
                "注意：整行读取。要截取矩形区域用 read_block。"
            ),
            icon="📖",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_read_block",
            tool_func=file_tools_read_block,
            description=(
                "读取文本文件的矩形区域（可上下左右移动），返回 CSV。\n\n"
                "参数：\n"
                " path(str) 文件路径\n"
                " start_line/end_line(int) 行范围，1-based\n"
                " start_offset/end_offset(int) 行内字符偏移\n"
                " max_chars(int) 返回内容字符上限，默认2048\n"
                " encoding(str) auto=自动检测\n\n"
                "start_offset超行长度时该行返回空。start_offset>end_offset报错。\n\n"
                "注意：整行读取用 read_lines，精确匹配用 regex。"
            ),
            icon="🔲",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_regex",
            tool_func=file_tools_regex,
            description=(
                "正则搜索文件内容，返回 CSV（列名：match_number/line_number/line_content/matched_text）。\n\n"
                "参数：\n"
                " path(str) 文件路径\n"
                " pattern(str) 正则表达式，Python re语法\n"
                " start_line/end_line(int) 搜索行范围，1-based，end_line默认文件末尾\n"
                " start(int) 从第几个匹配开始看，1-based，默认1\n"
                " count(int) 最多返回几个匹配，默认10\n"
                " max_chars(int) 返回内容字符上限，默认2048\n"
                " encoding(str) auto=自动检测\n\n"
                "示例：regex(\"app.log\", pattern=\"ERROR|WARN\") → 搜索错误和警告\n\n"
                "注意：逐行用re.search()，每行只返回第一个匹配。未匹配时返回空表头。"
            ),
            icon="🔎",
            enabled=True,
        )

        # ── 文件修改类（自动备份） ──
        api.register_tool(
            tool_name="file_tools_append",
            tool_func=file_tools_append,
            description=(
                "追加内容到文件末尾。修改前自动备份。\n\n"
                "参数：\n"
                " path(str) 文件路径\n"
                " content(str) 追加内容，\\r\\n/\\r自动统一为\\n\n"
                " encoding(str) auto=自动检测\n\n"
                "示例：append(\"app.log\", content=\"\\n2026-07-19 INFO Shutting down\")\n\n"
                "注意：文件不存在时返回错误（不自动创建）。"
            ),
            icon="➕",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_replace_lines",
            tool_func=file_tools_replace_lines,
            description=(
                "整段替换文件中的指定行区间。行数可增减。修改前自动备份。\n\n"
                "参数：\n"
                "  path (str)           文件路径\n"
                "  start_line (int)     起始行号，1-based。范围 [1, 文件末尾]\n"
                "  end_line (int)       结束行号，1-based。范围 [start_line, 文件末尾]\n"
                "  content (str)        替换内容，含 \\n 时拆成多行\n"
                "  encoding (str)       编码，默认 auto（自动检测）\n\n"
                "示例：\n"
                "  replace_lines(\"config.ini\", start_line=3, end_line=3,\n"
                "                 content=\"port = 9090\")\n"
                "  → 把第3行整行替换为 \"port = 9090\"\n\n"
                "注意：整行替换。要替换行内子串用 replace，要删行用 delete_lines。"
            ),
            icon="🔀",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_insert_lines",
            tool_func=file_tools_insert_lines,
            description=(
                "在指定行号前插入新内容。修改前自动备份。\n\n"
                "参数：\n"
                " path(str) 文件路径\n"
                " line(int) 插入位置，在 line 行之前插入，1-based\n"
                " content(str) 插入内容，含\\n拆成多行\n"
                " encoding(str) auto=自动检测\n\n"
                "示例：insert_lines(\"main.py\", line=10, content=\"# 新函数开头\")\n\n"
                "注意：line=文件总行数+1时追加到末尾。line<1或文件不存在报错。"
            ),
            icon="📄",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_delete_lines",
            tool_func=file_tools_delete_lines,
            description=(
                "删除文件中的指定行区间。修改前自动备份。\n\n"
                "参数：\n"
                " path(str) 文件路径\n"
                " start_line(int) 起始行号，1-based，范围 [1, EOF]\n"
                " end_line(int) 结束行号，1-based，范围 [start, EOF]\n"
                " encoding(str) auto=自动检测\n\n"
                "示例：delete_lines(\"main.py\", start_line=5, end_line=8) → 删除第5~8行\n\n"
                "注意：删行用这个。要删内容（留空行）用 replace_lines。要删文件用 trash。"
            ),
            icon="✂️",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_replace",
            tool_func=file_tools_replace,
            description=(
                "精确子串查找替换（str.replace，区分大小写）。修改前自动备份。\n\n"
                "参数：\n"
                " path(str) 文件路径\n"
                " old_text(str) 要查找的文本，精确匹配\n"
                " new_text(str) 替换成的文本\n"
                " start_line/end_line(int) 搜索行范围，1-based，end_line默认文件末尾\n"
                " start(int) 从第几个匹配开始替换，1-based，默认1\n"
                " count(int) 替换次数，-1=全部替换，默认\n"
                " dry_run(bool) true=只统计不修改\n"
                " encoding(str) auto=自动检测\n\n"
                "示例：replace(\"config.ini\", \"debug = false\", \"debug = true\")\n\n"
                "注意：精确子串匹配（不是正则）。正则替换用 regex_replace。"
            ),
            icon="🔄",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_regex_replace",
            tool_func=file_tools_regex_replace,
            description=(
                "正则替换文件内容（re.sub）。修改前自动备份。\n\n"
                "参数：\n"
                " path(str) 文件路径\n"
                " pattern(str) 正则表达式，Python re语法\n"
                " replacement(str) 替换字符串，支持\\1/\\g<name>等反向引用\n"
                " start_line/end_line(int) 行范围，1-based\n"
                " start(int) 从第几个匹配开始替换，1-based，默认1\n"
                " count(int) 替换次数，-1=全部替换，默认\n"
                " dry_run(bool) true=只统计不修改\n"
                " encoding(str) auto=自动检测\n\n"
                "示例：regex_replace(\"data.txt\", r\"(\\d+\\.\\d+)\", r\"\\1°C\")\n\n"
                "注意：正则替换。子串精确匹配用 replace。"
            ),
            icon="✨",
            enabled=True,
        )

        # ── 安全文件操作类（不触发备份） ──
        api.register_tool(
            tool_name="file_tools_copy",
            tool_func=file_tools_copy,
            description=(
                "复制文件或目录（不触发历史备份）。目标目录不存在时自动创建。\n\n"
                "参数：\n"
                " src(str) 源路径\n"
                " dst(str) 目标路径\n"
                " overwrite(bool) 是否覆盖已有目标，默认false\n\n"
                "示例：copy(\"main.py\", \"backup/main.py\") → 复制到backup/下，自动建目录\n\n"
                "注意：目录递归复制全部内容。覆盖时先删已有目标再复制。"
            ),
            icon="📋",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_move",
            tool_func=file_tools_move,
            description=(
                "移动或重命名文件/目录（不触发历史备份）。\n\n"
                "参数：\n"
                " src(str) 原路径\n"
                " dst(str) 新路径\n"
                " overwrite(bool) 是否覆盖已有目标，默认false\n\n"
                "示例：move(\"old.txt\", \"new.txt\") → 重命名\n\n"
                "注意：同一目录下移动=重命名。覆盖时先删已有目标再移动。"
            ),
            icon="📦",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_trash",
            tool_func=file_tools_trash,
            description=(
                "安全删除文件/目录到回收站（不触发历史备份）。\n\n"
                "参数：\n"
                " path(str) 要删除的文件或目录路径\n\n"
                "示例：trash(\"temp.txt\") → 文件进回收站\n\n"
                "注意：删文件用这个（可恢复）。删文件内行用 delete_lines。依赖 pytrash。"
            ),
            icon="🗑️",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_trash_undo",
            tool_func=file_tools_trash_undo,
            description=(
                "从回收站恢复最近删除的文件。\n\n"
                "参数：\n"
                " path(str) 要恢复的原文件路径\n\n"
                "示例：trash_undo(\"temp.txt\") → 从回收站恢复\n\n"
                "注意：按原路径精确匹配。同一文件删多次时恢复最近版本。回收站找不到时返回错误。依赖 pytrash。"
            ),
            icon="♻️",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_mkdir",
            tool_func=file_tools_mkdir,
            description=(
                "创建目录（不触发历史备份）。自动创建所有父目录。\n\n"
                "参数：\n"
                " path(str) 要创建的目录路径\n\n"
                "示例：mkdir(\"project/src/utils\") → 自动创建 project/ src/ utils/ 三级\n\n"
                "注意：目录已存在时直接跳过不报错。以文件路径为父路径时报错。"
            ),
            icon="📁",
            enabled=True,
        )

        # ── 历史回滚 ──
        api.register_tool(
            tool_name="file_tools_undo",
            tool_func=file_tools_undo,
            description=(
                "恢复文件到历史版本（不触发新的备份）。\n\n"
                "参数：\n"
                " path(str) 文件路径\n"
                " history_number(int) 历史版本号，1=最旧，越大越新\n\n"
                "示例：undo(\"main.py\", history_number=1) → 恢复到最旧版本\n\n"
                "注意：先用 history 查看可用版本。只有修改类工具（append/replace等）会创建备份。"
            ),
            icon="⏪",
            enabled=True,
        )

        # ── 全量写入（替代 write_file） ──
        api.register_tool(
            tool_name="file_tools_write",
            tool_func=file_tools_write,
            description=(
                "写入文件内容。如果文件已存在，自动备份后覆盖写入；如果文件不存在，直接创建新文件。"
                "使用原子写入（先写临时文件再 os.replace 替换），避免写入中断导致文件损坏。\n\n"
                "参数：\n"
                " path(str) 文件路径\n"
                " content(str) 写入内容，\\r\\n/\\r 自动统一为 \\n\n"
                " encoding(str) 编码，默认 utf-8\n"
                " line_separator(str) 行结束符，auto=按平台自动处理，\\n=Unix风格，\\r\\n=Windows风格\n\n"
                "示例：write(\"config.py\", content=\"print('hello')\")\n"
                "  → 创建新文件（不存在时）或覆盖已有文件（已存在时自动备份）\n\n"
                "注意：新文件不触发备份。覆盖已有文件时自动备份，可用 file_tools_undo 恢复。"
            ),
            icon="✏️",
            enabled=True,
        )

        logger.info("✓ File Tools 插件注册完成（25 个工具）")

        # ── 字节级工具 ──
        api.register_tool(
            tool_name="file_tools_read_bytes",
            tool_func=file_tools_read_bytes,
            description=(
                "读取二进制文件的指定字节范围，返回 hex 字符串（全大写）。\n\n"
                "参数：\n"
                " path(str) 文件路径\n"
                " offset(int) 起始偏移量（字节），默认 0\n"
                " length(int) 读取长度（字节），默认 512，上限 4096\n"
                " group_size(int) -1=不分组，0=报错，>0=每行显示多少字节，默认 16\n\n"
                "示例：read_bytes(\"image.bin\", offset=0, length=16)\n"
                "  → 读取文件头 16 字节\n\n"
                "注意：一次最多读取 4096 字节，大文件请分多次读取。"
            ),
            icon="🔢",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_write_bytes",
            tool_func=file_tools_write_bytes,
            description=(
                "写入二进制文件内容。支持全量覆盖和部分覆盖。\n"
                "全量覆盖时自动备份，部分覆盖时不改变文件大小。\n\n"
                "参数：\n"
                " path(str) 文件路径\n"
                " content(str) 写入内容（hex 字符串），允许空格，不可以 0x/\\x 开头\n"
                " offset(int) -1=全量覆盖，>=0=从该偏移量开始写入，默认 -1\n"
                " skip_backup(bool) 是否跳过备份（仅全量覆盖时有效），默认 false\n\n"
                "示例：\n"
                "  write_bytes(\"out.bin\", content=\"FF D8 FF E0\")\n"
                "    → 全量覆盖写入 4 字节\n"
                "  write_bytes(\"out.bin\", offset=256, content=\"00 00\")\n"
                "    → 从偏移量 256 处写入 2 字节\n\n"
                "注意：hex 字符串去掉空格后长度必须是 2 的倍数。"
            ),
            icon="✏️",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_find_bytes",
            tool_func=file_tools_find_bytes,
            description=(
                "在二进制文件中精确查找字节序列，返回匹配的偏移量列表（CSV，十进制）。\n\n"
                "参数：\n"
                " path(str) 文件路径\n"
                " pattern(str) 要查找的字节序列（hex 字符串）\n"
                " offset(int) 搜索起始偏移量，默认 0\n"
                " count(int) 最多返回几个匹配，-1=全部，默认 -1\n\n"
                "示例：find_bytes(\"data.bin\", pattern=\"FF D8\")\n"
                "  → 查找所有 FF D8 出现的位置\n\n"
                "注意：精确匹配，不支持通配符。"
            ),
            icon="🔎",
            enabled=True,
        )
        api.register_tool(
            tool_name="file_tools_replace_bytes",
            tool_func=file_tools_replace_bytes,
            description=(
                "在二进制文件中查找并替换字节序列。\n"
                "old_bytes 和 new_bytes 长度可以不同（替换后文件大小会变）。\n\n"
                "参数：\n"
                " path(str) 文件路径\n"
                " old_bytes(str) 要查找的字节序列（hex 字符串）\n"
                " new_bytes(str) 替换成的字节序列（hex 字符串）\n"
                " count(int) 替换次数，-1=全部替换，默认 -1\n"
                " offset(int) 搜索起始偏移量，默认 0\n"
                " skip_backup(bool) 是否跳过备份，默认 false\n\n"
                "示例：replace_bytes(\"data.bin\", old_bytes=\"FF D8\", new_bytes=\"00 00\")\n"
                "  → 把所有 FF D8 替换为 00 00\n\n"
                "注意：修改前自动备份（除非 skip_backup=true）。"
            ),
            icon="🔄",
            enabled=True,
        )


plugin = FileToolsPlugin()
