"""用 agentscope 的 _extract_input_schema 导出完整 schema。

description 取自函数 docstring 中 Args: 之前的段落，
parameters 取自 _extract_input_schema（从 Args: 中提取）。

注意：QwenPaw 运行时实际使用 api.register_tool(description=...) 覆盖 description，
此处仅为离线预览，与运行时不完全一致。
"""
import json
import os
import sys

sys.path.insert(0, r'D:\Data\github_repo\qwenpaw-plugin-file-tools')
os.chdir(r'D:\Data\github_repo\qwenpaw-plugin-file-tools')

from agentscope.tool._utils import _extract_input_schema

# 全部 26 个工具
from tools.info import (
    file_tools_listdir, file_tools_info, file_tools_guess, file_tools_diff, file_tools_history,
)
from tools.read import (
    file_tools_read_lines, file_tools_read_block, file_tools_regex,
)
from tools.edit import (
    file_tools_append, file_tools_replace_lines, file_tools_insert_lines,
    file_tools_delete_lines, file_tools_replace, file_tools_regex_replace,
    file_tools_indent_lines,
)
from tools.safe import (
    file_tools_copy, file_tools_move, file_tools_trash, file_tools_trash_undo, file_tools_mkdir,
)
from tools.history import file_tools_undo
from tools.write import file_tools_write
from tools.bytes import (
    file_tools_read_bytes, file_tools_write_bytes, file_tools_find_bytes, file_tools_replace_bytes,
)


def _extract_description(func) -> str:
    """从函数 docstring 提取第一段作为工具描述。

    与 QwenPaw 运行时不同（运行时使用 api.register_tool(description=...)），
    此处仅为离线预览。
    """
    doc = func.__doc__
    if not doc:
        return ""
    return doc.strip().split("\n\n")[0]


tools = [
    ("信息读取", [file_tools_listdir, file_tools_info, file_tools_guess, file_tools_diff, file_tools_history]),
    ("文本读取", [file_tools_read_lines, file_tools_read_block, file_tools_regex]),
    ("文件修改", [file_tools_append, file_tools_replace_lines, file_tools_insert_lines,
                  file_tools_delete_lines, file_tools_replace, file_tools_regex_replace,
                  file_tools_indent_lines]),
    ("安全操作", [file_tools_copy, file_tools_move, file_tools_trash, file_tools_trash_undo, file_tools_mkdir]),
    ("历史回滚", [file_tools_undo]),
    ("全量写入", [file_tools_write]),
    ("字节级操作", [file_tools_read_bytes, file_tools_write_bytes, file_tools_find_bytes, file_tools_replace_bytes]),
]

all_schemas = {}

for category, fns in tools:
    print(f'\n{"=" * 60}')
    print(f'  {category}（{len(fns)} 个工具）')
    print(f'{"=" * 60}')
    for fn in fns:
        schema = _extract_input_schema(fn)
        desc = _extract_description(fn)
        full = {
            "type": "function",
            "function": {
                "name": fn.__name__,
                "description": desc,
                "parameters": schema,
            },
        }
        all_schemas[fn.__name__] = full
        print(f'\n── {fn.__name__} ──')
        print(json.dumps(full, indent=2, ensure_ascii=False))

# 保存到文件
out_path = "tools_schema.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(all_schemas, f, indent=2, ensure_ascii=False)
print(f'\n\n已保存到 {out_path}（{len(all_schemas)} 个工具）')