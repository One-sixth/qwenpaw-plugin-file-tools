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

### 关键澄清：`_extract_input_schema` 只返回 parameters

```python
# _extract_input_schema 的返回值：
{'type': 'object', 'properties': {...}, 'required': [...]}
# ↑ 只有 parameters，没有 description
```

**不包含总体描述（description）。** 总体描述是在调用方拼接的：

| 场景 | 总体描述来源 | 拼接方式 |
|------|-------------|---------|
| `show_tool_schema.py` 离线预览 | `fn.__doc__` 第一段 | `doc.strip().split('\n\n')[0]` |
| QwenPaw 运行时 | `api.register_tool(description=...)` | 内部自动合并，覆盖 docstring |
| 函数 docstring 官方惯例 | 第一段 = short description | 后续段落 = long description，`Args:` = 参数说明 |

### 另一个澄清：函数 docstring 的 short description 在运行时被覆盖

| 信息源 | 位置 | 用途 |
|--------|------|------|
| 函数 docstring (Args:) | 参数 `properties[].description` | ✅ 每个参数的说明，`_extract_input_schema` 提取 |
| 函数 docstring (short+long) | 工具的 `description` 字段 | ❌ 被 `api.register_tool(description=...)` 覆盖 |
| `api.register_tool(description=...)` | 工具的 `description` 字段 | ✅ 最终发给 LLM 的总体描述 |

**结论：**
- 修改参数说明 → 改 `tools/*.py` 的 `Args:` docstring
- 修改工具总体描述 → 改 `plugin.py` 的 `api.register_tool(description=...)`
- 函数 docstring 的总体描述段在运行时**不起作用**

### 经验

- 给 `tools/*.py` 中的工具函数补上 `Args:` docstring，就能让每个参数的 schema 自带 description
- 不需要用 `Annotated` 或手动维护 `parameters` JSON Schema
- 这条路径不通的检查点：`docstring_parser` 是否安装、函数是否有 `__doc__`

## 2026-07-21 改动汇总

### 1. 修复 `file_tools_read_lines` 截断提示行号 bug
- **问题**：`next_line = start_line + len(rows)` 算成了被截断行的下一行
- **修复**：`next_line = int(rows[-1]["line_number"])`，取被截断行本身的行号
- **测试**：新增 `test_max_chars_truncated_from_start`、`test_max_chars_truncated_from_middle`、`test_max_chars_no_truncation`

### 2. `file_tools_read_block` 改动
- **截断提示**：新增"从第 N 行继续读取"提示，与 `read_lines` 一致
- **空文件提示**：返回 `读取矩形块失败，因为文件为空（长度为 0）。`
- **参数重命名**：`start_line/end_line` → `start_row/end_row`，`start_char/end_char` → `start_col/end_col`
- **语义统一**：全部改为 1-based 包含，与 `start_line` 一致

### 3. `format_csv` 移除 `max_chars` 参数
- **原因**：工具函数已自行截断，`format_csv` 只需格式化，不应再截断
- **影响**：`read.py` 中 3 处调用去掉 `max_chars` 参数

### 4. 参数语义说明完善
- **path 参数**：全部工具统一标注 `相对路径相对于 workspace 目录，支持 ~ 展开。`
- **encoding 参数**：`read.py` 3 处补充 `auto=自动检测`
- **子 agent 扫描**：派生子 agent 扫描全部工具，确认无遗漏的语义模糊问题

### 5. 修改工具输出格式统一
- **系统信息前置**：成功信息 + 备份信息合并到第一行
- **预览内容后置**：diff 格式 / `─── 替换前/后 ───` 格式放在下面
- **涉及工具**：`append`、`replace_lines`、`insert_lines`、`delete_lines`、`replace`、`regex_replace`
- **新增 diff 预览**：`replace` 和 `regex_replace` 新增 `-/+` 格式的逐行 diff

### 6. `file_tools_insert_lines` 预览
- 显示 `─── 插入前/后 ───` 格式，前后各一行上下文
- 插入行过多时（> 6）只显示前 2 + 后 2 行，中间 `<<省略>>`

### 7. `file_tools_indent_lines` 新工具
- **功能**：调整行首缩进，支持 expand（增加）和 shrink（减少）两种模式
- **参数**：`start_line/end_line`、`mode`、`count`、`char`（填充字符）、`line_separator`、`encoding`
- **line_separator 实现**：内部统一用 `\n` 连接，通过 `open(newline=...)` 控制输出，Python 自动处理转换
- **备份**：使用现有 `backup_file` 机制
- **输出**：diff 格式预览，系统信息前置
- **测试**：14 个测试覆盖全部功能

### 8. 测试环境修复
- **问题**：测试环境无 QwenPaw 配置，`get_session_dir()` 抛 `RuntimeError`
- **修复**：`conftest.py` 中 `autouse` fixture 直接覆盖各模块的 `get_session_dir` 引用（值绑定陷阱）
- **涉及模块**：`utils`、`backup.manager`、`tools.edit`、`tools.info`、`tools.history`
## 2026-07-21 改动汇总（第二轮）

### 1. `file_tools_read_lines` 纯文本格式改造
- 新增 `show_line_number: bool = True` 参数
- 输出从 CSV 改为纯文本格式
  - `show_line_number=True`：`行号 > 内容`
  - `show_line_number=False`：直接输出原文
- 行号不需要右对齐（泰斗先生要求简化）
- 新增 4 个 `show_line_number=False` 测试

### 2. `file_tools_read_block` 纯文本格式改造
- 新增 `show_line_number: bool = True` 参数
- 输出从 CSV 改为纯文本格式，与 `read_lines` 统一
- 新增 `test_show_line_number_false` 测试

### 3. `file_tools_regex` 纯文本格式改造（双行模式）
- 输出从 CSV 改为纯文本双行模式：
  ```
  行号 > 行内容
     matched: 匹配文本
  ```
- 移除 `max_chars` 参数（函数体内未使用）
- 新增三种截断关键词：
  - `<<行内容截断>>` — 行内容超过 160 字符
  - `<<匹配文本截断>>` — 匹配文本超过 160 字符
  - `<<结果截断>>` — 匹配数量超过 count 限制
- 不支持跨行匹配（逐行 `re.search()`）
- `pattern` 参数 description 加上「不支持跨行匹配」说明（写入 schema）

### 4. `show_tool_schema.py` 重构
- 发现 `_extract_input_schema` 只返回 parameters，不包含 description
- description 在 QwenPaw 运行时由 `api.register_tool(description=...)` 提供，覆盖函数 docstring
- `show_tool_schema.py` 改用 `_extract_description()` 函数，取 docstring 第一段作为离线预览 description
- 文档记录到 MEMORY.md「工具 Schema 生成机制」章节

### 5. 其他优化
- `file_tools_listdir` 的 `recursive` 参数描述优化：补充「递归深度控制」和「>10000文件时截断」
- `tools_schema.json` 重新生成
- 全部 270 个测试通过

## 2026-07-21 改动汇总（第三轮）

### 1. 补齐 6 个修改工具的 `line_separator` 参数
- `file_tools_append`、`replace_lines`、`insert_lines`、`delete_lines`、`replace`、`regex_replace` 新增 `line_separator` 参数
- `_write_file()` 新增 `newline` 参数（`Optional[str]`，透传 `open(newline=...)`）
- 统一实现模式：
  ```python
  newline_map = {"auto": None, "\\n": "\n", "\\r\\n": "\r\n"}
  nl = newline_map.get(line_separator, None)
  ```
- 每个工具新增 2 个测试（unix/windows），共 12 个新测试
- 全部 282 个测试通过

### 2. `line_separator` 参数字符串字面量统一（重要踩坑）
- **问题**：`Literal["\\n"]` 中的 `"\\n"` 是 **2 个字符**（反斜杠 + n），不是换行符
- `indent_lines` 的 `newline_map` 之前用的 key 是 `"\n"`（1 个换行符），与 `Literal` 不一致
- `newline_map.get("\n")` 不匹配 `Literal["\\n"]` 传来的 `"\\n"`，返回 `None`，`open(newline=None)` 在 Windows 上默认转 `\r\n`，测试假通过
- **修复**：统一 `newline_map` 的 key 为 `"\\n"`（2 字符），测试统一传 `"\\n"`（2 字符）和 `"\\r\\n"`（4 字符）
- **关键教训**：Literal 中的 `"\\n"` 是 2 字符，`newline_map` 的 key 和测试传值必须一致

### 3. `plugin.py` description 同步更新
- 6 个工具的 description 加上 `line_separator` 参数说明

## 2026-07-21 改动汇总（第四轮）

### 1. `file_tools_listdir` 纯文本/Markdown 表格改造
- **输出格式**：无 columns → 纯文本列表（一行一文件），有 columns → Markdown 表格（`|` 分隔，无对齐）
- **新增参数**：`absolute: bool = False`，控制返回绝对路径还是相对路径
    - `absolute=False`（默认）→ 相对路径（recursive 时 `dir_a/sub_file1.txt`）
    - `absolute=True` → 绝对路径（`D:/project/dir_a/sub_file1.txt`）
- **空目录**：返回 `（空目录，无文件）`
- **超限截断**：末尾追加 `结果过多，仅返回前 10000 条。`
- 旧 CSV 格式中的 `format_csv` 调用移除，改用纯文本拼接
- 测试：`test_markdown_table_format`、`test_absolute_path`、`test_sort_order` 更新
- 全部 283 个测试通过

### 2. `plan.md` 清空
- 所有待办已完成，plan.md 清空为仅含「已完成」标题

## 2026-07-22 改动汇总

### `file_tools_listdir` 新增分页+排序功能
- **新增参数**：`start(int, 默认1)` + `count(int, 默认500, 最大500)` + `sort_by(str, 默认"name")` + `ascending(bool, 默认True)`
- **排序**：扫描后统一按 sort_by+ascending 排序，支持 name/size/permissions/type/modified_at/created_at/extension
- **分页**：超出范围时返回「没有更多文件」提示；尾部信息格式「当前列出的文件 N~M，后面还有 X 个文件」
- **性能保护**：保留 10000 文件上限，超出时提示可通过分页浏览前 10000 条
- **空行分隔**：尾部提示前加空行，视觉更清晰
- **测试**：新增 6 个测试（sort_by_size/extension/modified_at、pagination_last_page/with_columns/single_file），全量 318 测试通过

### 1. `file_tools_regex` 跨行匹配 + JSON 输出 + 捕获组提取

#### 核心变化
- **匹配方式**：逐行 `search` → 拼接后整体 `finditer`（跨行匹配）
- **返回格式**：纯文本双行模式 → JSON（`indent=2`）
- **捕获组提取**：
  - 无捕获组 → `matched` 为完整匹配串（str）
  - 单捕获组 → `matched` 为提取内容（str）
  - 多捕获组 → `matched` 为列表（list[str]）
- **行号**：跨行匹配显示 `"1~2"`，单行显示 `"3"`
- **移除顶层 `path` 字段**（函数参数已有）

#### 参数校验（新增 7 项）
- `count=0` → 报错
- `count<-1` → 报错（仅 -1 合法）
- `pattern=""` → 报错
- `start_line<1` → 报错
- `start_line>total_lines` → 报错提示行数范围
- `end_line<start_line` → 报错参数矛盾
- `end_line<1` → 报错

#### matched 截断 + note 提示
- 超过 250 字符截断，附加 `<<truncated>>`
- 出现截断时 JSON 顶层加 `note` 字段，提示用 read_lines/read_block 获取完整内容

#### 行号计算
- 构建 `line_offsets` 索引，用 `bisect.bisect_right` 将 `match.start()` 映射到原始行号
- `_pos_to_line()` 内部函数

### 2. `file_tools_regex_replace` 跨行匹配 + count 默认值 1

#### 核心变化
- **匹配方式**：逐行 `sub` → 拼接后整体 `finditer` + 从后往前替换
- **count 默认值**：`-1`（全部替换）→ `1`（只替换第 1 个匹配）
- **diff 预览**：手动逐行 diff → `difflib.unified_diff(n=1)`

#### 参数校验（新增 7 项）
与 `regex` 一致：`pattern=""`、`count=0`、`count<-1`、`start_line<1`、`start_line>total`、`end_line<start_line`、`end_line<1`

#### 从后往前替换
```python
for m in reversed(effective_matches):
    range_content = range_content[:m.start()] + m.expand(replacement) + range_content[m.end():]
```
避免偏移漂移。

#### start 超出总数
改前返回「剩余匹配数不足」，改后报错「超出匹配总数（共 N 个匹配）」。

### 3. `plugin.py` description 精简
全部 26 个工具的 `description` 改为简短中文描述（1 句话），去掉详细参数列表和示例。
因为这些 description 在 UI 上展示给用户，Agent 看到的工具参数说明来自函数 docstring 的 `Args:` 段落。

### 4. 全量测试
- `test_read.py`：55 个测试（新增 8 个边缘测试）
- `test_edit.py`：89 个测试（TestRegexReplace 重写为 21 个测试）
- 全量 305 测试全部通过

## 2026-07-22 改动汇总（第二轮）

### `file_tools_indent_lines` 返回格式优化

#### 1. diff 预览改为先 - 后 + 分组
- **改前**：`- 1, + 1, - 2, + 2` 交错排列
- **改后**：所有 `-` 行排前面，所有 `+` 行排后面，视觉更清晰
- 代码：两个 `for` 循环代替原来的一个循环（`changes` 遍历两次，分别取 old 和 new）
- 同步修改的 `_` 解包：`for row_num, old, _ in changes` 和 `for row_num, _, new in changes`

#### 2. 系统提示数字前加空格
- **改前**：`已对第 10~16 行减少了4 个缩进`
- **改后**：`已对第 10~16 行减少了 4 个缩进`
- 拼接从 `{mode_text}{count}` 改为 `{mode_text} {count}`## 2026-07-22 备份失败处理策略 — 安全优先

### 背景
字节级写入工具（`file_tools_write_bytes`、`file_tools_replace_bytes`）的备份失败处理，原设计是只给警告不阻断（`backup_warning` 变量 + 继续写入）。审计发现这种做法不安全——字节写入可能导致文件损坏且永久无法修复。

### 决策
备份失败时，必须**拒绝修改**，要求用户明确授权才能继续。具体规则：

1. **`backup_file()` 返回 `None` 时**：`return format_error(...)` 立即返回，不执行写入
2. **错误信息必须包含**：
   - 「暂停执行」
   - 「向用户询问」
   - 「同意跳过备份」
   - 「skip_backup=True」
3. **用户必须打字「同意跳过备份」** 才授权，模糊回应（如"好的""继续"）不通过
4. `_build_write_full_result` 函数签名去掉 `backup_warning` 参数

### 涉及工具
- `file_tools_write_bytes`（全量覆盖模式，`offset=-1`）
- `file_tools_replace_bytes`

### 涉及的代码变更
- `tools/bytes.py`：两个工具的备份失败分支，从 `pass` / 设 `backup_warning` 改为 `return format_error(...)`
- `tools/bytes.py`：`_build_write_full_result` 签名简化，去掉 `backup_warning` 参数

### 不涉及的工具
- 其他修改类工具（`append`、`replace_lines` 等，备份失败直接报错阻断）

### 扩展：`file_tools_write` 统一为安全优先（2026-07-22）
审计后决定将 `file_tools_write` 也统一为安全优先策略。文本文件虽小，但备份失败可能意味着磁盘满、权限异常或配置损坏等严重问题，停下来排查是合理的。

**改动**：
- `backup/manager.py`：新增 `_last_backup_error` 模块级变量 + `get_last_backup_error()` 函数，记录每次备份失败的具体原因
- `tools/write.py`：备份失败时 `return format_error(...)` 拒绝修改，错误信息中包含具体失败原因，无 `skip_backup` 参数因此不提示跳过

**涉及工具**：
- `file_tools_write`（全量覆盖写入）## 2026-07-22 改动：`file_tools_replace` 增加 `count=-1` 支持

### 改动
- `file_tools_replace` 的 `count` 参数现在支持 `count=-1`（替换全部匹配），与 `regex_replace` 和 `replace_bytes` 一致
- 校验逻辑：`count < 1` 拦截改为 `count == 0` 报错 + `count < -1` 报错
- `effective_count` 计算：`count=-1` 时取 `match_count`，否则 `min(count, match_count)`
- docstring 同步更新：`count=-1 表示替换全部匹配，count>=1 表示替换指定数量`

### 测试
- `test_count_minus1`：`count=20` → `count=-1`，语义与测试名一致
- `test_invalid_count`：`count=-1` 从报错改为断言成功替换
- 全量 318 测试全部通过## 2026-07-22 改动：预览格式统一为 `+/-` diff

### 背景
泰斗先生要求将 `replace_lines`、`delete_lines`、`insert_lines` 的预览输出改为 `+/-` diff 格式，与 `indent_lines` 统一。

### 改动

**`file_tools_replace_lines`**：
- 旧：`─── 替换前/后 ───` 对称预览 + `_build_replace_preview` 函数
- 新：`+/-` diff 格式，先 `-` 旧行再 `+` 新行，带行号

**`file_tools_delete_lines`**：
- 旧：`─── 删除前/后 ───` 对比，被删行标记（被删除）
- 新：`+/-` diff 格式，前一行上下文 + `-` 被删行 + 后一行上下文，无 `+` 组

**`file_tools_insert_lines`**：
- 旧：`─── 插入前/后 ───` 预览，前后各一行上下文，超 6 行截断
- 新：`+/-` diff 格式，前一行上下文 + `+` 新插入行 + 后一行上下文，无 `-` 组

### 关键设计决策
- **`delete_lines` 无 `+` 组**：删除就是删除，不需要告诉用户删完后那里变成了什么
- **`insert_lines` 无 `-` 组**：插入就是新内容，不需要展示被挤开的旧行
- **上下文行**：前后各一行上下文，用两个空格对齐（`  N > ...`）
- **`replace_lines` 保留 `+/-` 双组**：替换是"旧→新"的映射，双组合理

### 衔接
- `_build_replace_preview` 函数变为死代码，不再被任何工具调用
- `delete_lines` 预览死代码 bug（审计 P0 #2）自然解决
- 审计报告已更新

### 测试
- 更新 `test_preview_format` 断言
- 全量 318 测试全部通过