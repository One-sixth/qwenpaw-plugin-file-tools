# 项目记忆

> 开发过程中的关键决策、踩坑记录、经验沉淀。

## 文件 I/O 模式选择（2026-07-19）

### 问题
Windows 上 Python 文本模式会自动转换 `\n` ↔ `\r\n`：
- `open(path, "w")` 写 `\n` → 文件里变成 `\r\n`
- `open(path, "r")` 读 `\r\n` → 内存里变成 `\n`

这导致二进制检测行分隔符（看到 `\r\n`）和文本模式读内容（只有 `\n`）之间不一致，
`split('\r\n')` 会失败。

### 决策
**最终方案**：统一用文本模式，不加 `line_separator` 参数。
- 读：`open(path, "r")` → 内容统一 `\n` → `split("\n")`
- 写：`open(path, "w")` → Python 自动转 `\n` → 系统行尾
- 写入前用 `normalize_newlines()` 统一 `\r\n`/`\r` → `\n`，避免二次转换

### 废弃方案
之前用二进制模式（`rb`/`wb`/`ab`）+ 手动 `detect_line_separator` + 按检测到的分隔符 `split`。
太复杂了，Python 文本模式已经处理好了。

### 删掉的代码
- `detect_line_separator()` — 从 `utils.py` 移除
- `write_file_content()` — 从 `utils.py` 移除
- `_normalize_content_ls()` — 从 `edit.py` 移除，替换为 `normalize_newlines()`
- 所有工具函数的 `line_separator` 参数 — 6 个修改工具各减 1 个参数

### 保留的 `normalize_newlines`
虽然文本模式能处理 `\r\n` → `\n`（读时）和 `\n` → `\r\n`（写时），
但如果输入内容本身包含 `\r\n`（例如 agent 从别处读来的文本），
用文本模式 `f.write(content)` 时 `\r\n` 中的 `\n` 会被再转一次 → `\r\r\n`。
所以写入前必须统一为 `\n`。

## 相对 vs 绝对导入（2026-07-19）

### 问题
`plugin.py` 最初混用了 `from tools.info import`（绝对）和 `from .tools.read import`（相对）。

### 决策
全部用相对导入。因为插件不会 `pip install`，而是被 QwenPaw 动态 import 加载，
绝对导入可能找不到包路径。

## Description 策略（2026-07-19）

### 问题
初始的 tool description 太简略（每个工具 10~20 字），
agent 无法准确理解参数含义和边界行为。

### 决策
每个工具的 `description` 写得详细，包含：
- 参数说明（每个参数的作用和合法值）
- 边界行为（超出范围、无效值会怎样）
- 返回值格式（成功/失败分别返回什么）
- 用法提示（先 `file_tools_history` 再 `file_tools_undo` 等）

不单独写 skill 文档，description 就是 agent 的完整指南。

## pyproject.toml 不需要（2026-07-19）

测试配置原本用 `conftest.py` 手动改 `sys.path` 来支持 `from tools.xxx import`。
尝试过加 `pyproject.toml` + `[tool.pytest.ini_options] pythonpath = ["."]` 来替代，
但这个项目不会被 `pip install`，也不需要构建系统，`pyproject.toml` 多余。

最终方案：保留 `conftest.py` 中手动 `sys.path.insert(0, _project_root)` 的写法。

## 测试覆盖要点

- **176 个 pytest 测试**，全部通过
- 覆盖空文件、超长行（160 字符截断）、GBK/CRLF 编码
- 覆盖不存在的文件、无效参数（recursive=0, line_count=0 等）
- 覆盖 offset 反转（start_offset > end_offset）
- 覆盖 dry_run 模式（不修改文件）
- 覆盖多版本备份恢复
- 覆盖 Windows CRLF 行尾一致性

## 项目整理（2026-07-19）

### 清理内容
- 删除 11 个临时调试脚本（`_check_args.py`、`_check_future.py`、`_check_schema.py`、`_export_schema.py`、`_fix.py`、`_fix_tools.py`、`_inspect_sig.py`、`_rm_wrapper.py`、`_rm_ws_param.py`、`_test_anno.py`、`_test_doc.py`）
- 删除 `QwenPaw工具Schema生成机制.md`（已复制到 `memory/知识库/`）
- 删除 `tools_schema.json`（Schema 导出产物）
- 清理全部 `__pycache__/` 目录

### 改名
- `_show_schema.py` → `show_tool_schema.py`（保留为可用的工具脚本）

### 保留
- `设计稿.md`、`测试指南.md` 保留

### 名字泄露检查
- 检查全部项目文件，仅 `设计稿.md` 第 4 行有「泰斗先生、小音」泄露
- 已修复为「项目维护者」
- 其余文件均无名字泄露，符合公开策略

## 手动测试验证（2026-07-19）

三次完整的 Agent 手动测试通过：

| 版本 | 场景 | PASS | 修复验证 |
|:----:|:----:|:----:|:--------:|
| v1 | 57 | 57/57 | 4 项改进建议 |
| v2 | 58 | 58/58 | 4/4 修复通过 |
| v3 交叉测试 | 4 种文件组合 × 多工具 | 全部通过 | 备份路径 bug 修复 ✅ |

### v2 修复的 4 项
1. **🔴 `replace_lines` 预览格式** — `─── 替换前/替换后 ───` 对称结构，被替换行标 `（被替换）`
2. **🟡 `delete_lines` 标题分隔** — `─── 删除前/删除后 ───` 明确分隔
3. **🟢 `replace` 用词** — "行之间" → "行范围内"
4. **🟢 截断说明** — 提示补充「该行内容不完整，会重新返回完整内容」

### v3 修复（2026-07-19 追加）
5. **🔴 `replace_lines` 正文截断** — 正文区超过 6 行时只显示前 2 + 后 2 行，中间 `<<省略>>`
6. **🔴 `<<省略>>` 重复输出 bug** — `_build_replace_preview` 中 `if show_end < total` 判断被写了两次，删掉重复行

### v3 交叉测试验证

在备份路径 bug 修复后，用 4 种不同文件组合（6行×5字符、6行×100字符、100行×5字符、100行×100字符）进行了全面交叉测试：

**文件读取类**（4 种组合全部通过）：`read_lines`、`read_block`、`regex`、`info`、`history`
**文件修改类**（备份路径修复后全部通过）：`append`（4组）、`replace_lines`（20行替换10行预览）、`insert_lines`、`delete_lines`、`replace`、`regex_replace`
**安全操作类**（全部通过）：`copy`、`move`、`trash`、`trash_undo`、`mkdir`

### 行为验证确认

通过测试验证并确认了以下行为符合预期：

1. **`append` 不自动补换行符** — 追加内容到文件末尾已有的内容之后，不自动插入 `\n`。如果文件末尾没有换行符，新增内容会直接接到最后一行后面。这是按设计的行为，不改。
2. **`append` 内容末尾的 `\n` 会保留** — 如果 content 末尾有 `\n`，文件末尾会多一个空行。这是 `split("\n")` 的自然结果。
3. **`read_lines` 保留空行** — 底层使用 `split("\n")`，空行（`""`）和末尾空行都被如实保留，不额外过滤也不额外添加。

## 备份路径解析踩坑（2026-07-19）

### 问题
修改类工具执行备份时报错 `[WinError 5] 拒绝访问。: 'C:\\Windows\\System32\\_file_tools_backup'`，
备份路径被错误地解析到了系统目录。

### 根因
`_get_workspace_dir()` 使用 `for agent_ref in config.agents` 迭代 `AgentsConfig` 对象。
但 `config.agents` 是 `AgentsConfig` 对象，不是列表，迭代返回的是 `tuple` 而非 `AgentProfileRef`，
导致 `agent_ref.workspace_dir` 获取失败，最终回退到 `os.getcwd()`。

当 Agent 运行在 `C:\Windows\System32` 目录下时，`os.getcwd()` 返回系统目录，
备份路径就变成了 `C:\Windows\System32\_file_tools_backup`，权限不足报错。

### 修复
改用 `config.agents.profiles` 字典直接访问：
```python
profiles = config.agents.profiles  # dict[str, AgentProfileRef]
ws = profiles["default"].workspace_dir
```

### 对比 session-tools
session-tools 的 slash 命令有 `ctx.workspace_dir`（AgentScope 上下文直接提供），
不需要依赖 `load_config` 解析。其 HTTP API 的兜底路径是固定的 `~/.qwenpaw/workspaces/default`，
不受当前工作目录影响。

file-tools 是 tool 插件，没有 `ctx`，只能靠 `load_config`，所以解析必须正确。

### 教训
- `config.agents` 是 `AgentsConfig` 对象，不是列表，不要用 `for` 迭代
- 正确方式：`config.agents.profiles` 字典，key 是 agent_id
- 兜底路径不要用 `os.getcwd()`，应用固定路径如 `~/.qwenpaw/workspaces/default`
- 无法获取备份路径时，直接抛出异常而非静默降级，让工具函数返回明确的错误信息
- 修改后的错误信息统一为：「备份原文件失败。因为获取会话文件路径失败。」

由于项目名含连字符（`qwenpaw-plugin-file-tools`），不是合法 Python 包名，
QwenPaw 动态加载和 pytest 测试之间存在导入方式冲突。

**最终方案**：子模块全部使用 `try/except ImportError` 双模式导入。

```python
try:
    from ..utils import xxx      # QwenPaw 动态加载走这条
except ImportError:
    from utils import xxx        # pytest 测试走这条（conftest.py 已加 sys.path）
```

涉及文件：`backup/manager.py`、`tools/edit.py`、`tools/info.py`、`tools/read.py`、`tools/safe.py`、`tools/history.py`

## 已知限制

- 不处理并发写入
- `file_tools_listdir(recursive=-1)` 在 >10000 文件时截断
- 其他工具建议在 <100MB 文件上使用
- `file_tools_guess` 依赖 `puremagic` 和 `chardet`，未安装时降级
- `file_tools_trash` / `file_tools_trash_undo` 依赖 `pytrash`
- `file_tools_append` 不会自动插入换行符分隔——如果文件末尾没有换行符，追加内容会直接接到最后一行后面。用户需自行确保新内容前有 `\n`，或文件末尾有换行符。
- `file_tools_read_lines` 使用 `split("\n")` 分割行，空行和末尾空行均保留，不会额外过滤。

---

## 工具 Schema 生成机制（2026-07-19）

### 核心发现

QwenPaw 插件的工具 schema 由 `agentscope.tool._utils._extract_input_schema()` 自动生成，流程：

```
工具函数 → inspect.signature() 提取参数 → docstring_parser 解析 docstring
→ pydantic.create_model() 创建动态模型 → model_json_schema() 生成 JSON Schema
```

### 关键：参数 description 来自 docstring

`_extract_input_schema` 会从函数的 **docstring 的 `Args:` 段落** 中提取每个参数的描述，传给 `Field(description=...)`：

```python
def replace_lines(path: str, start_line: int):
    """一句话总结。

    Args:
        path: 文件路径
        start_line: 起始行号，1-based
    """
```

生成 schema：
```json
"path": { "type": "string", "description": "文件路径" }
```

### 与 `api.register_tool()` 的 description 关系

| 信息源 | 位置 | 用途 |
|--------|------|------|
| 函数 docstring (short+long) | 工具的 `description` 字段 | tools 整体说明 |
| 函数 docstring (Args:) | 参数 `properties[].description` | 每个参数的说明 |
| `api.register_tool(description=...)` | 工具的 `description` 字段 | **覆盖** 函数 docstring 作为工具说明 |

### 经验

- 给 `tools/*.py` 中的工具函数补上 `Args:` docstring，就能让每个参数的 schema 自带 description
- 不需要用 `Annotated` 或手动维护 `parameters` JSON Schema
- 这条路径不通的检查点：`docstring_parser` 是否安装、函数是否有 `__doc__`
