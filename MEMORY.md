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

### 运行时行尾策略（2026-09-05 第三裁决确立，v1.6.0 起生效）
- **Python 文本模式读 `newline=None` 是通用换行翻译（原文件行尾读到即失真）；写 `newline=None` 只认 `os.linesep` 无视文件历史**——"读-改-写"型工具在 Windows 上会把 LF 文件整体转 CRLF，与被编辑内容无关
- **裁决方向**：`*_line_separator=auto` 语义从"跟 OS"改为"**保持目标文件主行尾**"（`_dominant_newline` 探测：\r\n/\n/\r 多数者、平局 CRLF 优先、无行尾/空/新建落回 OS；复制内容随 join 的 `\n` 换装目标行尾）——copy_lines 已实现（第三裁决）
- **推广已拍板、排期在后**：先彻底验证 copy_lines（当前阶段），通过后单开 **v1.7.0** 铺其余 24 工具（动 edit.py 等读面=改原始读+探测，影响面大）
- 写回翻译前须 `content.replace("\r\n","\n")` 折叠（防 strict 拆行带入的 `\r\n` 二次翻译叠成 `\r\r\n`）；目标显式 `\n` 不翻译故豁免
- 配方与实验事实包：小窝知识库《编程技巧速查》§20

### 测试配置
- 保留 `conftest.py` 手动 `sys.path.insert(0, _project_root)`，不加 `pyproject.toml`
- ⚠️ **pytest 和 `show_tool_schema.py` 都必须用 `qwenpaw` conda 环境**（`D:\Software\miniconda3\envs\qwenpaw\python.exe`）——依赖 agentscope，`normal` 环境没有会全量报错；全量测试现 401 个

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

---

## v1.3.0 listdir 过滤改造（2026-09-05，已 commit）

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

**未闭环**：①~~字符串化数组联机复验~~ ✅（1.3.0）；②泰斗先生的第二个新工具想法未公布；③工作区 scratch 留有 `cycle_proto/`、`review_scratch/`、`live_symlink_test/`（环树可复验用，三轮盲测靶场）；④~~v1.4.0 收口句待 commit+重装定稿~~ ✅（`412eebb`+`2625fbc`，装机 1.4.0，四轮盲测已实证收口句）。后续见 v1.5.0 节。

---

## v1.4.0 文档极简重写 + absolute 移除 + gitignore 引擎（2026-09-05，三轮盲测驱动）

**一日四连版本链**：v1.3.1（条目化文案）→ v1.3.2（输出预告，后被极简掉）→ v1.3.3（幽灵版，并入 1.4.0）→ v1.4.0（定稿候选）。

**文档哲学转向（泰斗先生拍板，最重要决策）**：极简直觉化——agent 自带 ls/glob/gitignore 世界知识，docstring 每参数一句级、示例形态代替文字规则、边界由运行时输出（行内警告/统计行/中文报错）自解释。listdir 文档 2340→622 字符（-73%）。**三轮零上下文盲测实证成功**：8/10→8/10→8.5/10，最终 6/6 一次通过零试错，gitignore 直觉题（排树留同名文件）新人凭题目外的世界经验自创正解。方法论全文见小窝知识库《Agent工具文档设计与盲测验证》。

**防退化三钉**：
1. `test_docstring_minimal_contract`：8 必留词 + 7 禁回流词（所见即所搜/先校验/祖先链等注意事项类禁止再堆回 docstring）
2. `TestEntryWording`：条目化运行时文案精确断言
3. **换引擎 checklist**：同函数兄弟过滤器有的 try 守卫必须对称平移（F1 教训：exclude 换 pathspec 漏守卫，半截 `!` 英文 traceback 炸穿中文报错面，审查逮 MAJOR）

**盲测换来的最终两句 docstring 事实**（v1.4.0 收口）：exclude「按显示路径匹配、不解析符号链接」+ 首段「输出路径相对遍历根」——凡新人自曝"在赌"的语义空白都值得一句钉死。C3（警告串塞 name 列机器使用要剥尾）维持 v1.3.0 行内警告裁决不改，仅记录。

**依赖**：`pathspec>=1.1`（工厂名 `'gitignore'` 版本翻转坑，速查 §17）；qwenpaw/normal 环境均已自带。

---

## v1.5.0 type 系统重做 symlink|X 复合类型（2026-09-05，四轮盲测驱动）

**四轮盲测**（装机 1.4.0 含收口句，新人 6/6 零试错，8.5/10 平三轮）：C1/C2 收口句双双被逐字引用 credited（T3"照着它下的注"、T4 引首段拼路径）；T5 锚根 `/__pycache__/` 凭世界经验一次过（白嫖第二铁证）。批评 4 条核实全属实，其中 type 伪装比新人描述的更严重（见下）。

**核心设计（作者四拍定稿）**：
- type 值域 = **材质|目标** 两段复合：`dir` / `file` / `symlink|dir` / `symlink|file` / `symlink|invalid`；普通目录列值 directory→dir 简写统一
- types 过滤 = **分段匹配**（token 命中任一分段即保留）→ `["dir"]` 含活目录链、`["symlink"]` 活死链一网打尽；词表严格三词，**别名制度废除**（directory/link 报错）、**`all` 退役**（不填/空=全部）；invalid 只做显示不做过滤 token
- **尾斜杠**：目标可达且为目录→恒带杠（含 follow=False 与环条目）；断链不带。两维正交：type 答材质、斜杠答目标形态、follow 答进不进、警告答遍历事故
- 环警告统一「循环符号链接」去中英混排；E4 path 补「支持绝对路径」（**仅 listdir 试水**，其余 25 工具未动，推广与否看五轮考卷）
- 修掉了四轮批评②的根因：follow 时目录链接 type 曾报 directory，`types=["symlink"]` 静默漏活目录链

**实现红线**：`_entry_type` 返回 (type串, stat)，链接条目必跟随 stat（与 gather 共用）；**遍历递归判断走 `etype=="dir" or (etype=="symlink|dir" and follow_symlink)`，绝不跟 type 串的显示语义走**。

**契约换钉**：必留 8 词（+`命中类型任一分段`、`绝对路径`；−`只影响显示`、`别名`）；禁回流 11 词（+`别名`/`all=不过滤`/`只影响显示`/`invalid`）。490 测试全绿；文档 622→599 字符（退役制度反而省字）。

**遗留观察（五轮实测后终裁，作者拍板维持现状）**：`symlink|dir` 含裸 `|`，Markdown 表格列会被它劈开视觉列（同族 C3 裁决记录在案）。**五轮抽查（7/10，4过1部分）三条设计批评全部裁决"不修"**：①invalid 查询墙（`["invalid"]`/`["symlink|invalid"]` 均拒、警告文字不进过滤，"只要死链"需 symlink 过滤+type 列眼看）=作者裁决"不考虑 invalid 的清单，就这样"，接受为设计成本——报错句"任一分段即保留"被指"邀请函"也一并维持；②`types=["dir"]` 含目录链接与 `find -type d` 直觉**相反**（世界知识核对第 3 项交卷结果），分段匹配既定卖点，补句不加；③follow=True 默认"越界"、活目录链默认零标识、两警告文案不对称——全记录不实施。**教训入库**：五轮证明文档+输出的自愈力（新人靠双数字与 type 列完成 4/5），但也首次暴露"输出词表≠查询词表"是真实摩擦面——未来新工具设计时词表一致性要主动评审，别等盲测逮。

**已修（v1.5.1）**：`format_error` 句尾「。」去重——五轮批评🥉，排查发现全仓 **39 处** reason 自带句号曾拼出"。。"（历史上仅 diff start=0 一处局部补丁没修根），源头归一+钉死；顺修 test_history 存量 `open().read()` 句柄泄漏恢复 -W error 零警告。491 测试全绿；覆盖复查：本轮全部新增代码区域零漏覆。

**未闭环**：①~~v1.5.0 待五轮抽查~~ ✅（五轮 7/10 按设计落地）；②~~v1.5.1 待 commit+重装~~ ✅（`7916764`+作者装机）；③盲测周期收官——8→8→8.5→8.5→7（五轮为压力探针卷，分数不可与常规卷直比），file-tools 盲测线可停；④~~第二个新工具想法未公布~~ ✅（copy_lines，见 v1.6.0 节）；⑤scratch 三目录清理裁决仍挂着；⑥其余 25 工具 path 描述是否推广"绝对路径"句式，留待将来（listdir 已试水）。

---

## v1.6.0 file_tools_copy_lines 跨文件行复制（2026-09-05，第二个新工具落地）

**动机**：行内容搬运不经过模型上下文（旧路 read_lines+insert_lines 接力费 token 且转录易飘）。首段 docstring 钩住该直觉。

**作者裁决**（方案评审定稿+当日修订，全落实现+钉测）：start/end_line 编辑家族语法；src_encoding/dst_encoding 双参数；dst 父目录自动创建；不做多段选择；src/dst_line_separator 双参数；insert_line 名+1-based+"1=开头"提示；src_file/dst_file 参数名；**dst_file=None=自复制**；**insert_line 超总行数与 -1 同意自动追加**（十裁决原案"越界从严报错+指引句"被作者当日推翻——越界=追加后空文件特判也随之消失，修订后指引句删除）。

**核心语义**：
- 自复制：dst=None 或 normcase 路径恒等；两端行号以改前为准，落点可在选中区内部（编辑器粘贴语义，快照无别名）；只备份一次
- ~~**记账空行不对称（作者裁决）**：源侧选中域排除末尾换行的记账空行（空文件"共 0 行"报错）；目标侧 insert 域含之~~ ⚠️ **v1.6.1 list 模型整体作废**：两侧同一套真实行号，行数=len（含末尾空行），详 v1.6.1 节
- 校验序：一切参数/落点校验在备份之前，报错零污染（比家族更严，家族 start_line 超界在备份后才查）
- 编码继承链：新建/空文件 dst auto→沿用 src 探测编码；已存在 dst auto→检测自身；显式 dst_encoding 即转码
- strict 拆行（src_line_separator 显式）= 仅按指定序列拆行、其余换行符保留进行内容；写回前 `content.replace("\r\n","\n")`（dst 显式 \n 除外）防 newline 转换叠 `\r\r\n`
- **目标行尾保真（作者第三裁决，覆盖第二裁决）**：专卷现场逮到"LF 靶档被 auto 写回整体转 CRLF"后实验钉死机制——**Python 文本模式读 newline=None 是通用换行翻译（原文件行尾读到即失真）、写 newline=None 只认 os.linesep 完全无视文件历史**，家族 read+重写必然 Windows LF→CRLF。裁决：`dst_line_separator=auto`+目标有内容 → 先 raw 读探测**目标文件主行尾**（`_detect_file_newline`/`_dominant_newline`，多数者、平局 CRLF 优先、探测失败按无行尾）并跟随写回，复制内容同步换装；自复制目标即源（跟随 src_sep，含显式参数值）；新建/空/无换行落回 OS。**家族推广已拍板**：作者裁决"保持目标主行尾"**推广到其余 24 工具**，但排期在当前工具完全验证通过之后（潜在 v1.7.0，动 edit.py 等读面=原始读+探测，影响面大单开版本；知识库《编程技巧速查》§20 已备配方）
- ~~fresh（目标不存在）忽略 insert_line（0/999/None 皆可）~~ ⚠️ **v1.6.1 特例扫荡删落点特判**：空基线一切合法落点自然收敛为整体新建，非法落点与已存在目标同规报错；~~末尾补换行只对真新建执行~~ ⚠️ **v1.6.1 起补换行特判删除**，文件末尾状态由所选数据镜像（详 v1.6.1 节）；空文件目标无需特判——读入基线恰为 `[""]`，任意落点插入后 join 自然产出规范换行（当日 insert 修订的红利）

**对抗审查战果（零上下文子 agent，544 绿基线上打穿 4 漏）**：
- 🔴 M1 strict×auto 写回 `\r\r\n` 字节腐蚀（钉测只钉了对侧 dst="\n"）→ 折叠防御+回归钉
- 🟠 M2 单空行新建 content 假值跳换行→0 字节+谎报"共 1 行" → 去 `and content`
- 🟠 M3 空 dst"视为新建"但编码走 chardet 落空 utf-8 与真新建分裂 → 继承 src
- 🟠 M4 samefile 把"指向 src 的链接"判成自复制但 os.replace 实际掀链接（文案与效果分裂）→ **裁决弃 samefile 纯 normcase 恒等**（规格原文只裁决"实际同路径含大小写"，链接场景交家族路径级行为）；删对侧旧测试
- 🟡 已处理：m3 fresh 忽略语义入 docstring+钉、m5 文档计数 26→27 全家（README/AGENTS/plugin/MEMORY/show_tool_schema+重新生成 tools_schema.json 27 个）、m6 撤 conftest 死补丁（copy_lines 不 import get_session_dir 无需挂）
- 🟡 维持现状（家族一致性优先，记录在案）：m1 写回失败留 .temp_file 残件（_write_file 家族通病）、m2 fresh"共 K 行"内容口径 vs 既有"从 M 行"记账口径之差（家族 legacy 口径）、m4 strict 嵌入换行破预览版式（纯观感）

**审查教训**：新工具测试全绿 ≠ 组合空间安全——M1-M4 全活在"钉测组合的对侧"（换 dst 行尾/换 ASCII 内容/换文件系统语义）。**测试矩阵要跨参数维度做笛卡尔抽查**，下次出卷直接带"钉测对侧"清单题。

**发版链**：491→554 测试（新模块 63 个，行覆盖 99% 余双模式导入死弧）→ plugin.json 1.6.0 + CHANGELOG + schema 重导 → 重装 1.6.0 → **copy_lines 专卷盲测（第六轮，新工具首卷）**：6/6 全过、零意外失败、自评 8/10（首卷即达 listdir 常规卷分段 8~8.5）。考点全中：收口句六处逐字引用（"**超过总行数与 -1 同意**"直接支撑超界题、当日修订即被新人引用实证；"dst_file 留空=自复制，两端行号均以修改前为准"支撑省略参数下注）；新人自创「借 +/- 预览当只读通道」侦查法（工具无读面时的运行时自解释红利）；M2/M3 修复被实战点名通过（复制空行不被吞、探测新建文件 GBK 编码自动沿用）。**批评处置**：☠幻影空行计入"从X行变为Y行"口径（真实，家族 legacy，src"共0行"与 dst"共N+1"双标被点破）→**作者终裁维持**（"末尾有换行，那也是换行"——dst 落点域含幻影行是有意设计，与 src 选中域排除之构成不对称裁决一体两面）；☠"请调用 file_tools_undo"对无 undo 环境画饼→考卷侧裁剪产物（真机 undo 同插件恒可用），不修；⚠"留空"三义（省略/null/""）——""会报"不是文件"可自解释，不修；⚠三参数越界行为不对称=作者已裁决设计，新人靠逐字句用对，不修；⚠预览空行无视觉重量=家族版式，记录。**审查盲区发现→第二裁决落地**：复盘字节时逮到"LF 文件被 auto 写回整体转 CRLF"（新人无读工具看不见）；作者裁决**自复制**双 auto 复用源真实设定（编码本已如此，行尾新增 `_dominant_newline` 主行尾跟随，显式参数则跟参数、无换行落回 OS）；**跨文件仍家族 OS 口径**，残余悬案②（入已知限制 or 推广家族"auto=保持目标主行尾"）待终裁。→ **第三裁决落地（目标行尾保真，见上）**，悬案②在 copy_lines 范围内定案、家族推广=已拍板排后；复测 564 全绿（行尾保真 10 连钉含探测失败兜底）覆盖 99%。→ commit 由作者（建议 msg：`v1.6.0: add file_tools_copy_lines`；工作区当前含 8a18443 之后的第二+第三裁决修正增量）。

**第七轮复核卷（2026-09-05，对 f008285 装机版，收官通过）**：A 联机冒烟 11 场景字节级全绿（LF 自复制/跨文件保 LF、新建 OS 口径、超界追加、**CR 老麦与 mixed 主行尾两个"已钉未联机"项补证、strict×auto 双目标零 `\r\r\n`、M2/M3 联机）；B 564 全绿；C 零上下文盲测 1 新人六题（对照 2/探针 3/应变 1）全部完成零报错、自评 **8/10 与六轮持平**——三裁决收口句被逐字引用（「保持目标文件主行尾」直接支撑 T3 老麦文件"全参数故意不填"下注），新人自创「全量切片复制探针当只读通道」（比六轮 diff 预览法更进一步）；D 盲测后字节巡检全部 exact match（T3 赌注兑现）。**批评处置**：🥉 幻影行报数跨调用矛盾（-1.5 主扣分）→ 触发本版模型转向裁决；⚠「超过总行数与 -1 同意」黑话 → N+1 转正后句义无损维持；undo 画饼/"留空"三义 = 旧裁决复采不修。考卷瑕疵记录：T2 恒等变换出题失误（新人识破拒绝重复复制=正确应变）、T5 报错探针被 T1 累计状态吞掉（主对话机补测通过）。

---

## v1.6.1 copy_lines 行模型转向：list 模型（2026-09-05，作者第四裁决）

**缘起**：第七轮复核通过前夜，作者否定了"批评🥉维持现状"方案，先追问无末尾换行文件的行为（实测：模型自适应、第二裁决恰好抹平两种形态——但"巧合收敛"不如"定义成立"），继而拍板换模型：分隔符模型（`"\n".join` + 幻影记账）整体退役。

**模型公理**（全部钉死）：
- `split("\n")` 每个元素都是**真实行**；文件末尾换行对应的那个 `""` 就是一行空行（编辑器末行光标站的真实位置），**行数=列表长度**，减法/排除/不对称等特判全部删除——第六轮「末尾有换行，那也是换行」终裁的记账含义被字面化：那一行从此就是行
- **新建不补换行**：文件末尾有无换行完全由选区数据镜像（含源末尾空行→规范结尾；止于中途行→裸尾）；0 字节文件=一行空行、空行的终止符随其自带 → **M2"复制空行不被吞"升级为模型公理**，无需任何保护逻辑
- 落点域两种文件形态同构：1..总行数 = 该行之前；总行数+1、超界、-1/不填 ≡ 末尾追加（保留换行结尾文件的"填回末尾空行"落法——`dst_total-1 if base[-1]==""` 公式一字未动，语义从"插幻影前"正名为"填入末尾空行槽位"）
- **模型分辨（非 bug）**：对已存在的 0 字节 dst 追加 = "内容\n"（它的末尾空行让位行尾），同数据真新建 = 裸尾"内容"——基线不同源不同果
- 写回三裁决**原样保留**：编码继承链、目标主行尾保真（`_dominant_newline` 探测/自复制跟 src_sep/strict 折叠防 `\r\r\n`）、新建/空/无换行落回 OS
- **家族口径差异（作者裁决"其他工具先不管"，记录在案）**：edit.py 四工具摘要"从X行变为Y行"与 insert_lines 落点域仍是旧列表口径（换行结尾文件比 copy_lines 真实行数多报 1）；copy_lines 预览里末尾空行行号（如 `  9 >`）按作者指示"真实行状态 diff，不需管太多"原样保留
- **docstring 一字未动即在新模型下自洽**（"超出总行数取末尾/共 N 行/与 -1 同意"全部收口句原语义成立）——极简契约钉测原样通过，这是 v1.4.0 极简哲学的最强背书案例

**改造成本**：工具本体仅两处（源域减法删除、fresh 补换行删除），插入落点/写回/预览逻辑零改动；测试 564→565（11 处旧钉按新模型重钉 + 新增：末尾空行可入选区正反钉、新建裸尾/含末尾空行两向钉、空源=一行公理钉、M2/M3 语义钉改写）。

**新会话续接口令（当前阶段）**：读本节。待办顺序：① 作者**重装 1.6.1**（list 模型未装机）→ 联机冒烟重钉新口径：新建中途止=裸尾、选到末尾空行=规范结尾、空源 1-1 合法 0 字节、末尾空行可拷、LF 保真与超界追加不受影响；② 通过后 commit（建议 msg：`v1.6.1: switch copy_lines to list model, retire phantom line`）；③ **v1.7.0 家族推广**范围=行尾保真铺其余 24 工具（auto=保持目标主行尾，动 edit.py 读面，知识库《编程技巧速查》§20 有配方）——记账行数字**暂不随迁**（作者裁决），若将来要统一另案；④ scratch 四目录清理裁决仍挂（cycle_proto/review_scratch/live_symlink_test/copy_lines_exam，其中 r7_smoke/r7_exam/r7_edge 为第七轮靶场）；⑤ 覆盖率 --branch 复测（口令见 v1.6.0 节）。
