# 项目记忆

> 开发过程中的关键决策、踩坑记录、经验沉淀。按主题分类，不按日期记录。

---

## 架构决策

### 文件 I/O 模式
- **统一用文本模式**（`r`/`w`/`a`），不手动处理行分隔符
- Python 文本模式自动处理 `\n` ↔ `\r\n`，无需手动干预
- 写入前用 `normalize_newlines()` 统一 `\r\n`/`\r` → `\n`，避免 `\r\n` 中的 `\n` 被二次转换 → `\r\r\n`
- 删掉的废弃代码：`detect_line_separator()`、`write_file_content()`、`_normalize_content_ls()`

### 导入方式
- **全部用相对导入**（`from .tools.xxx import`），插件被 QwenPaw 动态 import 加载，绝对导入可能找不到包路径
- 子模块使用 `try/except ImportError` 双模式导入，兼容 QwenPaw 动态加载和 pytest 测试

### 工具 Description 策略
- **双通道（2026-09-04 实测修正）**：Agent（LLM）看到的工具总体描述 = **函数 docstring 第一段**（`\n\n` 截断），参数说明 = docstring 的 `Args:` 段落；`plugin.py` 的 `register_tool(description=...)` **只进 GUI**（写入 agent.json 的 `tools.builtin_tools.<name>.description`，工具选项栏展示），Agent 看不到
- `register_tool` description 保持简短中文（1 句话），**不写依赖库名等实现细节**（v1.2.4 起：「依赖 pytrash」类语句全部移除；运行时错误提示除外）
- 不单独写 skill 文档，docstring 就是 agent 的完整指南
- **极简直觉化原则（2026-09-05 泰斗先生拍板，v1.3.3）**：指南≠注意事项清单。docstring 只写匹配 agent 世界知识的直觉级说明（每参数一句级），边界情况由运行时输出自解释（行内警告/统计行/中文报错）。listdir 文档 601 字符（schema 参数描述口径）为预算参照；「裹脚布」禁回流清单钉在 `TestEntryWording.test_docstring_minimal_contract`
- ⚠️ GUI 文案**只在条目不存在时写入**（`_write_tool_config` 对已存在条目 skip），插件升级不刷新 → 会留 v1.0 化石长文案；刷新办法：卸载插件（条目被删）再安装，或直接改 agent.json（QwenPaw 指纹缓存支持免重启，参考 `fix_agent_desc.py`）

### 工具 Schema 生成机制
QwenPaw 插件工具 schema 由 `agentscope.tool._utils._extract_input_schema()` 自动生成：
```
函数签名 + docstring Args: → pydantic.create_model() → JSON Schema
```
- 参数 description 来自 `Args:` docstring 段落
- 总体描述（LLM 侧）来自 **docstring 第一段**（`\n\n` 截断）；`register_tool(description=...)` 不覆盖它，只写 GUI 配置
- 修改参数说明 → 改 `tools/*.py` 的 `Args:` docstring
- 修改 Agent 总体描述 → 改 `tools/*.py` 的 docstring 第一段
- 修改 GUI 展示 → 改 `plugin.py` 的 `register_tool(description=...)` + 走上面的刷新办法

### 行尾策略（2026-09-04 确立）
- `.gitattributes` 用 **`*.py -text`**：Windows 个人仓库，仓库字节 = 工作区字节（CRLF），git 永不转换
- 教训：旧规则 `*.py text` 会在**每次 git add 时无条件**把 blob 归一成 LF（与 core.autocrlf 无关），造成 commit 假象"整文件重写"；`text=auto`（json/md 等）反而有历史 blob 保护不会翻
- 归一化只发生在 **add 时刻**：v1.2.2 先 add 后建 .gitattributes，才让 20 个 .py 的 CRLF blob 逃过一劫（另 6 个没逃过，已于 v1.2.4 前后归队）
- 验收：`git ls-files --eol` 全部 `.py` 应为 `i/crlf`

### 测试配置
- 保留 `conftest.py` 手动 `sys.path.insert(0, _project_root)`，不加 `pyproject.toml`
- ⚠️ **pytest 和 `show_tool_schema.py` 都必须用 `qwenpaw` conda 环境**（`D:\Software\miniconda3\envs\qwenpaw\python.exe`）——依赖 agentscope，`normal` 环境没有会全量报错；全量测试现 401 个

---

## 返回格式（ToolChunk）

### 标准模式
全部 26 个工具返回 `ToolChunk` 对象，与 QwenPaw 内置工具一致：

```python
# 成功
return make_success("已复制「a.txt」→「b.txt」。")
# → ToolChunk(is_last=True, state=SUCCESS, content=[TextBlock(text="...")])

# 失败
return make_error("读取", "文件不存在")
# → ToolChunk(is_last=True, state=ERROR, content=[TextBlock(text="...")])
```

`make_error` 兼容两种调用方式：
- `make_error("错误文本")` — 直接包装
- `make_error("操作名", "原因", "建议")` — 自动调用 `format_error` 拼接三段式

### 各工具内部格式

| 格式 | 工具 |
|:----|:----|
| 纯文本描述 | `listdir`, `diff`, `append`, `replace_lines`, `insert_lines`, `delete_lines`, `indent_lines`, `copy`, `move`, `trash`, `trash_undo`, `mkdir`, `undo`, `write` |
| JSON | `info`, `guess`, `history`, `regex`, `read_bytes`, `find_bytes` |
| 纯文本行号 | `read_lines`, `read_block` |
| CSV | `find_bytes`, `replace_bytes` |

---

## 已知陷阱

### 1. `line_separator` Literal 字面量陷阱
`Literal["\\n"]` 中的 `"\\n"` 是 **2 个字符**（反斜杠 + n），不是换行符。
`newline_map` 的 key 必须与 Literal 一致，否则 `open(newline=None)` 在 Windows 上默认转 `\r\n`，测试假通过。

### 2. `config.agents` 不是列表
`config.agents` 是 `AgentsConfig` 对象，不是列表，不要用 `for` 迭代。
正确方式：`config.agents.profiles["default"].workspace_dir`

### 3. 字节写入的 `_build_write_full_result` 双重包装
`_build_write_full_result()` 已返回 ToolChunk，调用处不应再用 `make_success()` 包装。

### 4. `from module import` 值绑定陷阱
`from .database import LOCAL_TZ` 在模块导入时创建值绑定（copy），后续修改不生效。
函数内部 `from .database import LOCAL_TZ as db_local_tz` 动态获取最新值。

### 5. 备份路径硬编码
`get_session_dir()` 返回 `{ws}/file_tools_data`，所有会话共享备份目录。
如需 session 隔离，需通过 QwenPaw 内核注入 session ID。

---

## 备份系统

### 路径结构
```
{ws}/file_tools_data/history/{blake2b_hash}/{版本号}
```
- `get_session_dir()` 返回备份根目录
- `_get_history_dir(path)` 返回 `{root}/history/{encoded_path}`
- 编码方式：`f"{len(path)}{blake2b(path)[:32]}"`

### 原子写入
`_write_json_atomic(path, data)` 使用 `.temp` + `os.replace` 原子写入。
`files.json` 的写入（`_update_files_json` 和 `cleanup_old_backups`）均使用此函数。

### 启动自动清理
`cleanup_old_backups(days=30)` 通过 `register_startup_hook` 注册，每次启动时：
1. 扫描 `history/` 下的所有备份目录
2. 超过 30 天 → `pytrash.recycle()`（回退 `os.remove()`）
3. 空目录 → `os.rmdir()`
4. `files.json` 无效条目 → 清理

---

## 治理系统集成

### 工具注册参数
所有 26 个 `register_tool()` 调用指定：
```python
tool_type="file",      # 声明为文件类工具
target_param="path",   # 指定 target 参数名
```

与 QwenPaw 内置工具一致（`Read` 用 `tool_type="file"`, `target_param="file_path"`）。

### 安全策略
- `approval_level=OFF` 时治理层直接放行
- 如需启用安全检测，在 `policy.yaml` 添加：`FileTools*(WORKSPACE_DIR/**) → ALLOW`
- 内置敏感路径规则（`*(**/.env*)`、`*(**/.ssh/**)` 等）自动保护所有 `file_tools_*` 工具

---

## 已知限制

- 不处理并发写入
- `file_tools_listdir(recursive=-1)` 在 >10000 文件时截断
- 其他工具建议在 <100MB 文件上使用
- `file_tools_guess` 依赖 `puremagic` 和 `chardet`，未安装时降级
- `file_tools_trash` / `file_tools_trash_undo` 依赖 `pytrash`
- `file_tools_append` 不会自动插入换行符——如果文件末尾没有换行符，追加内容会直接接到最后一行后面
- `file_tools_read_lines` 使用 `split("\n")` 分割行，空行和末尾空行均保留

---

## v1.3.0 listdir 过滤改造（2026-09-05，未 commit）

**特性总览**：新增 6 参数 `types`/`extensions`/`contains`/`regex`/`exclude`/`follow_symlink`；输出全正斜杠+目录尾斜杠；realpath 祖先链防环 + 断链警告；双上限（匹配 10000 / 检查 100000）；过滤统计 footer；482 测试，listdir 区域行覆盖 100% + 分支仅余结构不可达死弧。

**核心语义契约**（改 listdir 必须遵守）：
- 过滤器间 AND、列表内 OR；空列表/全空白/不可识别输入 = 不过滤；列表参数接受单值 str 与 JSON 字符串化数组
- types 只控显示**不影响遍历**；遍历剪枝唯二来源 = exclude 命中目录、环检测
- extensions：目录一律直通；后缀 = basename 最后点号后段（dotfile 无后缀、多后缀取最后段）
- contains/regex 匹配**完整显示串**（所见即所搜；regex 底层 re.search、大小写敏感、`(?i)` 前缀、`(?i:…)` 局部组）；**子串可命中父目录名**（`tools/` 被 `file-tools/` 吞），限定目录用 `/utils/` 边界（顶层够不到）或 `(^|/)utils/` regex 锚定，docstring 已警示（联机回归教训）
- exclude：v1.4.0 起 **gitignore 语义**（pathspec `from_lines("gitignore", ...)`，模式与路径均 lower、反斜杠转正斜杠）：裸名任意深度命中文件+目录、`dir/` 只命中目录、`/x` 锚根、`!` 豁免后到先中、目录命中=整树剪枝（剪后子项 ! 无法复活，与 git 一致）；注释行/空行自动忽略；**匹配对象=显示路径、绝不 realpath 解析链接**（三轮盲测钉死，穿透链接的同名内容不受被排目录波及）；非法模式（`!` 半截、`[z-a]`）有 try 守卫 → 中文报错（ValueError+re.error 双捕获）。已知折中：`\`→`/` 预转换使 `\#foo` 转义仅根层可表达；含斜杠旧模式（`*/tests/*`）锚定翻转，任意深度改写 `**/x/**` 或裸名。⚠️ 别用 "gitwildmatch" 工厂名（1.1 起弃用；0.12 里 'gitignore' 反而是弃用名，故下限锁 >=1.1）
- 文案契约：listdir 分页/越界/start 报错/空目录一律称条目不称「文件」（TestEntryWording+迁移断言钉死）；sort 为稳定排序、平局保持收集次序不承诺可复现；目录 size Windows 恒 0——**均属运行时事实，v1.4.0 极简重写后不再写进 docstring**（禁回流词已锁，别拿旧版本文档当REFERENCE）
- 警告后缀（环/断链）只在**输出阶段**拼接、不参与匹配与排序；警告行作为普通条目受全部过滤器管辖、无尾部保底汇报
- 断链 = symlink 条目 stat 失败；symlink 条目必 stat（普通 file/dir 维持惰性）；根 realpath 有 try 守卫（失败退 resolved，仅失去环检测不崩）
- 双上限常量放模块级 `_LISTDIR_MAX_MATCH/_LISTDIR_MAX_VISIT`，测试用 monkeypatch 压低复现

**踩坑（承前编号）**：
6. **通道字符串化数组参数**（联机验收事故）：数组以 `'["py"]'` 字符串送达时，原「str=单值」宽容把整串当一个字面量 token → 过滤器静默失真零报错。修复：`_listdir_as_str_list` 对 `[`/`{` 开头字符串先 `json.loads` 还原、失败退回字面量；`columns` 同享归一（旧版还有逐字符空转存量问题）。
7. **monkeypatch 打桩 OS 函数还原晚于 tmp fixture 的 rmtree**：fake scandir 泄漏进 teardown 炸 TypeError；OS 桩用例一律 `try/finally: monkeypatch.undo()`。
8. **手工行审计的盲区**：只收目标函数嵌套 code 会漏**模块级辅助函数**；行覆盖看不出 if 只走单边——需 coverage.py `--branch` 交叉。

**Windows symlink/realpath 实测事实包**（3.13/管理员）：建目录链接需管理员或开发者模式；realpath 归一大小写、无 `\\?\` 前缀，裸 `==` 可靠（链接目标全大写写法仍归一回真路径）；`shutil.rmtree` 不跟随链接可安全清理环树；`DirEntry.is_dir/is_symlink` 对断链返回 False 不抛（stat 才抛）；防环必须用**祖先链** set（非全局 visited），两链合法复用同一目录不得误杀；无防环时 6 文件小树可虚增至 2400+。

**覆盖率复测口令**（coverage 7.16.0 已装 qwenpaw 环境，未进 requirements.txt）：
```powershell
D:\Software\miniconda3\envs\qwenpaw\python.exe -m coverage run --branch -m pytest tests -q
D:\Software\miniconda3\envs\qwenpaw\python.exe -m coverage report -m --include="tools/info.py"
```

**流程结论**：零上下文子 agent 对抗审查（抓到 5 bug：早退吞截断提示/all 顺序/断链丢弃等）+ 覆盖率审计（抓到审查没见的：根 realpath 裸调用、created_at 列零测试、非序列兜底）——**双管齐下**是发版前黄金组合。

**未闭环**：①✅2026-09-05联机复验通过（字符串化extensions/columns生效，环/断链/合法复用全对，v1.3.0已提交）；②泰斗先生的第二个新工具想法未公布；③工作区 scratch 留有 `cycle_proto/`、`review_scratch/`、`live_symlink_test/`（环树可复验用）。
