# 项目记忆

> 开发过程中的关键决策、踩坑记录、经验沉淀。按主题分类，不按日期记录。
> **版本过程记录（盲测分数、对抗审查战果、裁决演变、未闭环清单）在 `CHANGELOG.md`**——本文件只留活约束、语义契约、坑。

---

## 架构决策

### 插件安装方式（2026-11-11 确立，替代旧「双工作树同步」）
- **新流程**：开发目录 `git ls-files -z` 导出干净 zip（38 跟踪文件，自动排除 `.git`/`__pycache__`/`.coverage`/`.pytest_cache`）→ `qwenpaw plugin install <zip> --force` 热装（QwenPaw 运行时经 API 立即生效，无需重启）
- **zip 结构**：顶层目录 `qwenpaw-plugin-file-tools/`，`plugin.json` 在顶层（服务端 `_find_plugin_dir` 找根或顶层子目录的 plugin.json）
- **坑**：中文文件名（早期测试指南.md/早期设计稿.md）必须 `git ls-files -z`（null 分隔）——普通 `git ls-files` 对非 ASCII 文件名 quote 成 `"\346..."` 致打包失败；zip 内 arcname 需 UTF-8 flag（Python zipfile 默认正确，已验证）
- **装机目录状态**：`C:\Users\TWD\.qwenpaw\plugins\qwenpaw-plugin-file-tools` 经 `--force` 重装后**不再是 git 工作树**（`.git` 消失，变干净拷贝）——不要再对装机目录做 git 操作；装机目录是独立快照，与 git 仓库不再联动
- **⚠️ 热加载不刷新已运行会话**：`qwenpaw plugin install` 替换宿主进程已加载模块（`inspect.getsource` 可验证是新版），但**当前对话会话的工具绑定是启动时快照**——改完工具行为后当前会话调工具仍返回旧结果，需**新开会话**（或重启 QwenPaw）才用上新版

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
- **极简直觉化原则（2026-09-05 作者拍板，v1.3.3）**：指南≠注意事项清单。docstring 只写匹配 agent 世界知识的直觉级说明（每参数一句级），边界情况由运行时输出自解释（行内警告/统计行/中文报错）。listdir 文档 601 字符（schema 参数描述口径）为预算参照；「裹脚布」禁回流清单钉在 `TestEntryWording.test_docstring_minimal_contract`
- **description 精简原则（2026-11-11 确立）**：description 只写「JSON 结构表达不了、且 agent 猜错会出错」的信息——砍 Schema 复述（default/anyOf 已表达）/实现细节/运行时自解释，留语义陷阱 + 新行为。已落地 `file_tools_regex` + `file_tools_regex_replace`，其余 25 工具暂缓
- ⚠️ GUI 文案**只在条目不存在时写入**（`_write_tool_config` 对已存在条目 skip），插件升级不刷新 → 会留 v1.0 化石长文案；刷新办法：卸载插件（条目被删）再安装，或直接改 agent.json（QwenPaw 指纹缓存支持免重启，参考 `fix_agent_desc.py`）

### manifest meta 声明与 agent 可见性（2026-10-15 发现）
- **现象**：27 个工具在非 default agent（ChqnR9）的 UI 工具管理页**完全隐身**（agent.json 快照 0 条）；default 可见仅因历史遗留旧条目（enabled=true、v1.0 化石描述）
- **根因**：plugin.json **无 `meta.tools` 声明** → QwenPaw `_merge_plugin_manifest_tools()`（manifest meta 是插件工具进 agent 配置快照的唯一通道）补不进条目；对照 wait_agent_task 插件有声明故全 agent 可见
- **⚠️ UI 隐身 ≠ 运行时不可用**：实验复现 `_resolve_config_gates` + `ToolRegistry.filter` 证明快照无条目的插件工具照样放行（LLM 可调），只是 UI 看不见、无法开关——「功能正常、设置页隐身」的迷惑型 bug
- **坑**：manifest 声明 `enabled: true` 会被忽略（QwenPaw 2.2.1 `_add_plugin_tool_default` 硬编码 enabled=False），补声明后新条目初始为禁用态，需逐 agent UI 开启
- **落地（v1.8.1/v1.8.2）**：27 条 meta.tools 已补（name/description/icon 与 register_tool 一致，省略 enabled）+ 逐条 `"category": "files"`（QwenPaw 2.2.2 起插件工具 UI 分组走后端 `ToolInfo.category`，前端只认 6 个预定义组，自创组名无效；`register_tool(tool_type=...)` 与 UI 分组无关）；中文**显示名**仍无通道（前端 i18n catalog 仅 33 个内置工具，插件工具渲染走 `s.name` 原名分支）
- **⚠️ 存量 agent 补条目**：QwenPaw `load_agent_config` 指纹缓存——agent.json 文件不变则配置对象永不重载，重启/卸载重装均无法补条目，存量 agent 需直改 agent.json（已对 ChqnR9/test3 执行）

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

### 行尾策略
- `.gitattributes` 用 **`*.py -text`**：Windows 个人仓库，仓库字节 = 工作区字节（CRLF），git 永不转换
- 教训：旧规则 `*.py text` 会在**每次 git add 时无条件**把 blob 归一成 LF（与 core.autocrlf 无关），造成 commit 假象"整文件重写"；`text=auto`（json/md 等）反而有历史 blob 保护不会翻
- 归一化只发生在 **add 时刻**：v1.2.2 先 add 后建 .gitattributes，才让 20 个 .py 的 CRLF blob 逃过一劫（另 6 个没逃过，已于 v1.2.4 前后归队）
- 验收：`git ls-files --eol` 全部 `.py` 应为 `i/crlf`

### 运行时行尾策略（2026-09-05 第三裁决确立，v1.6.0 起 copy_lines、v1.7.0 起全家生效）
- **Python 文本模式读 `newline=None` 是通用换行翻译（原文件行尾读到即失真）；写 `newline=None` 只认 `os.linesep` 无视文件历史**——"读-改-写"型工具在 Windows 上会把 LF 文件整体转 CRLF，与被编辑内容无关
- **裁决方向**：`*_line_separator=auto` 语义 = "**保持目标文件主行尾**"（`_dominant_newline` 探测：\r\n/\n/\r 多数者、平局 CRLF 优先、无行尾/空/新建落回 OS；复制内容随 join 的 `\n` 换装目标行尾）
- **推广（v1.7.0）**：铺满 edit.py 六读改写工具 + `file_tools_write`（整覆盖也保持旧文件主行尾）；`file_tools_append` 为**有意豁免**（auto=平台行尾，只做增量追加不重排已有字节，钉在 `TestAppendIntentionalDivergence` 防后人"顺手统一"）；探测函数 `dominant_newline`/`detect_file_newline` 下沉 utils.py 共享
- 写回翻译前须 `content.replace("\r\n","\n")` 折叠（防 strict 拆行/用户 content 带入的 `\r\n` 二次翻译叠成 `\r\r\n`）；目标显式 `\n` 不翻译故豁免——v1.7.0 起此守卫**上移到 `_write_file` 中央**（`newline != "\n"` 才折叠，幂等），copy_lines 本地同条件折叠保留成双保险；副产物：replace/regex_replace 的 new_text/replacement 直通道（不过 normalize_newlines）自此不再能叠出 `\r\r\n`，"写回自动统一"的 docstring 承诺首次成立；POSIX 反向失真（CRLF 文件被误转 LF）同修
- 配方与实验事实包：小窝知识库《编程技巧速查》§20

### 工作区解析（v1.8.3 重构，2026-10-17）
- **用户文件路径**：`get_workspace_dir()` → QwenPaw 官方 `qwenpaw.config.context.get_tool_base_dir()`（解析优先级：项目目录 → agent 工作区 → WORKING_DIR；ContextVar 每回合由 `ContextVarsSetupHook` 注入，同步工具经 `asyncio.to_thread` 自动携带 context 副本）。旧实现硬编码 `profiles["default"]` 是多 agent 相对路径全落 default 工作区的根因，已删
- **备份小窝**：`get_session_dir()` → `get_current_workspace_dir()`（agent 自己的工作区）；file_tools_data 永不跟随聊天界面绑定的项目目录（防 agent 状态写进用户项目）
- **无兜底链（作者拍板）**：运行时不做 load_config/tool_config 兜底，出错即抛；测试路径注入走 conftest `_mock_workspace_dirs`（mock 模块级 `get_workspace_dir`→tmp_dir + `get_session_dir` 值绑定仅 backup/manager.py 一处）
- **⚠️ startup hook 清理在回合外必失败**（ContextVar 未注入 → RuntimeError 被吞）→ 已移除启动钩子，改备份成功后惰性清理（见「备份系统」）；plugin.json min 版本 2.2.2（`get_tool_base_dir` 2.2.0 引入，实测边界 2.2.2，旧声明致低版本宿主全工具 ImportError 静默瘫痪）；test_workspace_context.py 5 钉（模块导入期保存原函数引用绕过 autouse mock，ContextVar token reset 防污染）

### 测试配置
- 保留 `conftest.py` 手动 `sys.path.insert(0, _project_root)`，不加 `pyproject.toml`
- ⚠️ **pytest 和 `show_tool_schema.py` 都必须用 `qwenpaw` conda 环境**（`D:\Software\miniconda3\envs\qwenpaw\python.exe`）——依赖 agentscope，`normal` 环境没有会全量报错；测试数量随版本变，以 `pytest tests -q` 实际输出为准

### listdir 语义契约（v1.3.0~v1.5.0 沉淀，改 listdir 必须遵守）
- 过滤器间 AND、列表内 OR；空列表/全空白/不可识别输入 = 不过滤；列表参数接受单值 str 与 JSON 字符串化数组（`[`/`{` 开头字符串先 `json.loads` 还原、失败退回字面量——联机验收事故钉死）
- types = **材质|目标** 两段复合（`dir`/`file`/`symlink|dir`/`symlink|file`/`symlink|invalid`），**分段匹配**（token 命中任一分段即保留）；词表严格三词，`invalid` 只做显示不做过滤 token
- exclude = **gitignore 语义**（pathspec `from_lines("gitignore", ...)`，下限 >=1.1 因工厂名翻转坑）；**匹配对象 = 显示路径、绝不 realpath 解析链接**；目录命中 = 整树剪枝（剪后子项 `!` 无法复活，与 git 一致）
- contains/regex 匹配**完整显示串**（所见即所搜）；子串可命中父目录名（`tools/` 被 `file-tools/` 吞），限定目录用 `(^|/)utils/` regex 锚定
- 遍历剪枝唯二来源 = exclude 命中目录、环检测（防环用**祖先链** set 非全局 visited，两链合法复用同一目录不得误杀）；双上限常量 `_LISTDIR_MAX_MATCH/_LISTDIR_MAX_VISIT`（测试 monkeypatch 压低复现）
- 警告后缀（环/断链）只在**输出阶段**拼接、不参与匹配与排序；断链 = symlink 条目 stat 失败
- 文案契约：分页/越界/start 报错/空目录一律称「条目」不称「文件」；docstring 必留/禁回流词清单钉在 `TestEntryWording` + `test_docstring_minimal_contract`（禁回流词别拿旧版本文档当 REFERENCE）

### copy_lines 行模型（v1.6.0/v1.6.1 list 模型，作者第四裁决）
- **模型公理**：`split("\n")` 每个元素都是**真实行**，末尾换行对应的空行就是真实行，**行数 = 列表长度**（减法/排除/不对称特判全部删除）；**新建不补换行**（文件末尾状态由选区数据镜像）；0 字节文件 = 一行空行
- `dst_file=None` = **自复制**（normcase 路径恒等；弃 samefile——链接场景文案与效果分裂）；两端行号以改前为准，落点可在选中区内部
- 落点：1..总行数 = 该行之前；总行数+1、超界、-1/不填 ≡ 末尾追加；新建时任意合法值自然收敛为整体新建（fresh 特判枝已删，非法落点与已存在目标同规报错）
- 编码继承：auto 且目标没有自己的字节（自复制/不存在/0 字节）→ 沿用源编码
- 校验序：一切参数/落点校验在备份之前，报错零污染（比家族更严）
- 家族口径差异（作者裁决"其他工具先不管"）：edit.py 四工具摘要"从X行变为Y行"与 insert_lines 落点域仍是旧列表口径（换行结尾文件比 copy_lines 真实行数多报 1）

### read_lines / read_block / diff 输出协议（v1.8.0 三件套 + 折叠重设计）
- `show_line_number=True` 输出顶部加 `行号 > 行内容` 图例头 + 空行（动机：多个 LLM 把 `N > 内容` 前缀误读为文件自带行号；False 模式/空文件不加）
- 截断标记 **`<<<TRUNCATED>>>`**（行尾粘标记 + 4096 行内上限标记同步升格）；尾部说明 `\n\n<<<TRUNCATED>>>内容已超出 max_chars=N 限制。…`（空行分隔内容区/元信息区、说明行以标记开头）；元信息不占 max_chars 预算
- max_chars 默认 **5000**（read_lines / read_block / diff / regex / regex_replace 统一；`end_col=2048` 是行内列宽、`LINE_CONTENT_TRUNCATE=160` 是列截断，均非总预算性质，不动）
- diff 五机制：跳跃装填（超预算 hunk 折叠名片后继续尝试后续）/ 名片两态（a 给 start 指引、b 给可照抄建议值 max_chars=cost+500）/ 末位部分展开（线性装填到预算耗尽）/ max_line_length=600（min 100）行内截断 + 尾部汇总 / 双下限钳制（max_chars min 1000）
- **hunk 头行尾序号 `@@ ... @@ #N`**（@@ 后注解位 = git 函数名惯例，合法 unified diff；序号↔start 翻页闭环）
- CRLF/LF 行尾差异被 universal newline 吞掉误报"文件相同"→ 相同分支 `detect_file_newline` 比对行尾并提示（对抗复审 MAJOR 修入）
- 会计 = 简单 len 累加 + 名片成本定值估算，允许小幅超支（作者拍板不纠结精确）；hunk 分组后须 `rstrip("\r\n")`（keepends 行尾符不清会致双换行 + 成本虚高）

### regex / regex_replace 输出协议（v1.9.x）
- `file_tools_regex` 输出 = 纯文本表格 `序号 | 行号,列号 | [组 |] 匹配内容`：捕获组展平（2+ 组每组一行、独立行号,列号；未命中组 `None`、零宽 `""`）；0/1 组隐藏「组」列（条件列）；多行匹配转义一行（`\n`/`\t`/`|`/`\`）；每行 260 字符上限；`max_chars`（默认 5000）整行停止不输出半行；`start`/`count` 按**结果行**分页（不是第几匹配）
- **`re.MULTILINE` 默认开**（`^`/`$` = 每行首尾；整段绝对首尾用 `\A`/`\Z`）——跨行匹配不受影响（跨行靠 `"\n".join` 拼段后 pattern 内 `\n`，与 MULTILINE 正交）
- `file_tools_regex_replace` `dry_run` 显示**模拟 diff**（`_diff_truncated`：unified diff n=1、按 hunk 边界截断到 max_chars、至少 1 个 hunk；dry_run 不写文件不备份）
- **截断 footer 列出被省略 hunk 的 `@@` 头**（≤10 全列、>10 折叠为「列前 10」）——hunk 头天生自带旧/新起始行号 + 跨度，零计数器零语义混杂；⚠️ 禁止「完整 diff 请用 file_tools_diff 查看」死路指引（regex_replace 的 diff 是**内存模拟**，磁盘上不存在"修改后"文件；行动后验证的最短路径是直接 read_lines）
- 教训：续读指引必须可操作 + 优先复用 diff 自带结构信息，别另起炉灶提取（入知识库《长输出截断与折叠协议设计》）
- **description 盲测法**：无上下文 agent + 只给 description + 预测 → 实测 → 对比 + 结构化反馈（理解清晰度/预期差/多余缺失/加一句话/总评）；方法论入知识库《Agent工具文档设计与盲测验证》

---

## 返回格式（ToolChunk）

### 标准模式
全部 27 个工具返回 `ToolChunk` 对象，与 QwenPaw 内置工具一致：

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
| 纯文本描述 | `listdir`、`diff`、`append`、`replace`、`replace_lines`、`insert_lines`、`delete_lines`、`indent_lines`、`copy`、`copy_lines`、`move`、`trash`、`trash_undo`、`mkdir`、`undo`、`write`、`write_bytes`、`regex`（表格）、`regex_replace`（dry_run 含模拟 diff） |
| JSON | `info`、`guess`、`history`、`read_bytes` |
| 纯文本行号（图例头 + `<<<TRUNCATED>>>` 截断协议） | `read_lines`、`read_block` |
| CSV | `find_bytes`、`replace_bytes` |

---

## 已知陷阱

### 1. `line_separator` Literal 字面量陷阱
`Literal["\\n"]` 中的 `"\\n"` 是 **2 个字符**（反斜杠 + n），不是换行符。
`newline_map` 的 key 必须与 Literal 一致，否则 `open(newline=None)` 在 Windows 上默认转 `\r\n`，测试假通过。

### 2. 字节写入的 `_build_write_full_result` 双重包装
`_build_write_full_result()` 已返回 ToolChunk，调用处不应再用 `make_success()` 包装。

### 3. `from module import` 值绑定陷阱
`from .database import LOCAL_TZ` 在模块导入时创建值绑定（copy），后续修改不生效。
函数内部 `from .database import LOCAL_TZ as db_local_tz` 动态获取最新值。

### 4. 备份路径硬编码
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

### 惰性清理（v1.8.3 起，替代启动钩子）
`cleanup_old_backups(days=30)` 由 `_maybe_cleanup()` 在**备份成功后**触发（`.last_cleanup` 时间戳 24h 限频）——原 `register_startup_hook` 启动清理在回合外必失败（ContextVar 未注入 → RuntimeError 被吞），已移除。清理内容：
1. 扫描 `history/` 下的所有备份目录
2. 超过 30 天 → `pytrash.recycle()`（回退 `os.remove()`）
3. 空目录 → `os.rmdir()`
4. `files.json` 无效条目 → 清理

---

## 治理系统集成

### 工具注册参数
所有 27 个 `register_tool()` 调用指定：
```python
tool_type="file",      # 声明为文件类工具
target_param="path",   # 指定 target 参数名（例外：copy_lines 用 "dst_file"）
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
- `file_tools_regex` 表格每行 260 字符上限、`max_chars` 默认 5000 整行停止（v1.9.0）
- `file_tools_regex` / `file_tools_regex_replace` 默认 MULTILINE，`^`/`$` 按行首尾；绝对首尾用 `\A`/`\Z`（v1.9.1）
