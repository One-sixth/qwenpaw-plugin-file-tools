"""模拟 QwenPaw 的 schema 生成，展示 agent 看到的工具 schema。"""
import inspect, os, sys
sys.path.insert(0, r'D:\Data\github_repo\qwenpaw-plugin-file-tools')
os.chdir(r'D:\Data\github_repo\qwenpaw-plugin-file-tools')

from tools.info import file_tools_listdir, file_tools_info, file_tools_diff
from tools.read import file_tools_read_lines, file_tools_regex
from tools.edit import file_tools_replace, file_tools_replace_lines, file_tools_regex_replace
from tools.safe import file_tools_copy, file_tools_trash

# 选 4 个有代表性的工具
tools = [
    file_tools_listdir,
    file_tools_replace_lines,
    file_tools_replace,
    file_tools_copy,
]

for fn in tools:
    sig = inspect.signature(fn)
    print(f'{"="*60}')
    print(f'工具：{fn.__name__}')
    print(f'{"="*60}')
    
    # 参数列表
    required = []
    props = {}
    for name, p in sig.parameters.items():
        # 类型
        ann = p.annotation
        if ann is inspect.Parameter.empty:
            py_type = 'any'
        elif ann is str:
            py_type = 'string'
        elif ann is int:
            py_type = 'integer'
        elif ann is bool:
            py_type = 'boolean'
        elif hasattr(ann, '__origin__') and ann.__origin__ is list:
            py_type = 'array'
        else:
            py_type = str(ann)
        
        # 默认值
        has_default = p.default is not inspect.Parameter.empty
        
        prop = {'type': py_type}
        if has_default:
            prop['default'] = p.default
            prop['description'] = f'默认: {p.default}'
        else:
            required.append(name)
        
        props[name] = prop
    
    schema = {
        'type': 'object',
        'properties': props,
        'required': required,
    }
    
    import json
    print(json.dumps(schema, indent=2, ensure_ascii=False))
    print()
