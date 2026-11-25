"""用 agentscope 的 FunctionTool 导出完整 schema（与 QwenPaw 运行时同源）。

description 与 parameters 都从 FunctionTool 实例取——这正是 QwenPaw 注册工具时
走的路径（FunctionTool.__init__ 内部调 _extract_func_description + _extract_input_schema）：

    self.description = description or _extract_func_description(func.__doc__ or "")
    self.input_schema = input_schema or _extract_input_schema(func)

⚠️ 旧版脚本自己实现 _extract_description 用 docstring.split("\\n\\n")[0]，
   那是 agentscope 旧行为（short 段截断）。agentscope 2.0.10 起 description 改为
   short_description + long_description 全文拼接，旧脚本已过时。改走 FunctionTool
   可避免复制宿主逻辑、不再随 agentscope 版本漂移。

注意：QwenPaw 运行时实际用 api.register_tool(description=...) 覆盖工具总体
description（只进 GUI），此处导出的是 docstring 提取值，仅供离线预览/比对参数 schema。
"""
import json
import os
import sys

# 可移植：以脚本所在目录为基准（不再硬编码 D:\Data\github_repo\...）
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from agentscope.tool import FunctionTool

# 全部 27 个工具
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
from tools.copy_lines import file_tools_copy_lines
from tools.safe import (
    file_tools_copy, file_tools_move, file_tools_trash, file_tools_trash_undo, file_tools_mkdir,
)
from tools.history import file_tools_undo
from tools.write import file_tools_write
from tools.bytes import (
    file_tools_read_bytes, file_tools_write_bytes, file_tools_find_bytes, file_tools_replace_bytes,
)

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
    ("跨文件行复制", [file_tools_copy_lines]),
]

all_schemas = {}

for category, fns in tools:
    print(f'\n{"=" * 60}')
    print(f'  {category}（{len(fns)} 个工具）')
    print(f'{"=" * 60}')
    for fn in fns:
        tool = FunctionTool(fn)
        full = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }
        all_schemas[tool.name] = full
        print(f'\n── {tool.name} ──')
        print(json.dumps(full, indent=2, ensure_ascii=False))

# 保存到文件
out_path = os.path.join(PROJECT_ROOT, "tools_schema.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(all_schemas, f, indent=2, ensure_ascii=False)
print(f'\n\n已保存到 {out_path}（{len(all_schemas)} 个工具）')
