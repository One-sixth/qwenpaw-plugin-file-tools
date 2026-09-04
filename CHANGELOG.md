# 更新日志

## v1.3.0 (2026-09-05)

> listdir 大版本：五类过滤器 + 符号链接控制 + 路径格式统一

### 新增
- `file_tools_listdir` 新增 6 个参数：
  - `types`：条目类型过滤（`file`/`dir`/`symlink`/`all`，别名 `directory`/`link`，多选 OR、大小写不敏感），只控显示不影响遍历；含 `all` 即不过滤（先全量校验非法值、后判 all，不受列表顺序影响）
  - `extensions`：后缀名过滤（容忍 `py`/`.py`/`*.py` 写法，OR、大小写不敏感）；**目录条目一律直通**；归一后为空的无效 token（`.`/`*.`）被忽略，全部无效 = 不过滤
  - `contains`：对完整显示路径做大小写不敏感子串匹配（所见即所搜，匹配基准为正斜杠输出串，反斜杠不归一），多值 OR
  - `regex`：**re.search** 过滤，匹配完整显示路径，大小写敏感（`(?i)` 前缀可忽略；`\.md$` 只命中文件、`/$` 只命中目录）
  - `exclude`：glob 排除（对 {条目名, 显示路径去尾斜杠} 双串匹配），**命中目录整树剪枝**（不进入、不列出）、命中文件跳过
  - `follow_symlink`：是否跟随符号链接目录（默认 True；False 时链接目录按 symlink 叶子处理、不进入）
- **symlink 环防护**：`follow_symlink=True` 时 realpath 祖先链检测，环不展开、该目录显示行尾追加 `<<<警告，发现symlink环嵌套，跳过该文件夹展开>>>`（警告后缀不参与过滤匹配，警告行作为普通目录条目受过滤器管辖）
- **双上限**：匹配满 10000 提前停（原语义）；新增检查条目满 100000 提前停防遍历失控，尾部提示缩小范围；过滤器激活时尾部附「过滤统计：共扫描 N 条，匹配 M 条。」

### 变更
- **路径格式统一**：listdir 输出路径一律正斜杠 `/`（含 absolute 模式），目录条目带尾斜杠（排序与 regex/contains 匹配同串）
- **排序次序随尾斜杠微调**：同前缀的文件/目录相对顺序会变（`'.'(0x2E) < '/'(0x2F)`，如 `a_dir.txt` 排在 `a_dir/` 前）
- **断链符号链接以警告形式列出**：旧版对 `os.stat` 失败的条目静默丢弃，新版按 `symlink` 类型显示并行尾追加「<<<警告，符号链接目标不可达>>>」（输出阶段拼接、不参与匹配与排序，与环警告同规则），元数据列取不到时为空/0；断链判定需要 stat，故 symlink 条目必 stat（普通 file/dir 仍维持惰性 stat）
- **根目录 realpath 失败降级**：祖先链初始化的 `os.path.realpath(resolved)` 增加 try 守卫，极端文件系统错误下退回原路径（代价仅为当次调用失去环检测），不再让整个 listdir 崩溃（行覆盖审计发现）
- **过滤器与 columns 兼容 JSON 编码字符串数组**：联机验收发现部分调用通道会把数组参数序列化成字符串（如 `'["py", "md"]'`）送达，原宽容逻辑将其整体视为单字面量 token，导致 extensions/exclude/types 等静默失真（且无任何报错）。现 `_listdir_as_str_list` 对以 `[`/`{` 开头的字符串先 `json.loads` 还原再解析，解析失败退回字面量不炸不猜；`columns` 参数同享此归一（旧版收到字符串化数组会逐字符空转、属性列静默消失）
- **单个目录 scandir 失败的捕获从 `PermissionError` 放宽到 `OSError`**：不可读目录跳过扫描而非抛异常
- **早退路径不吞提示**：零匹配、`start` 越界时同样输出过滤统计与上限截断提示；无过滤器时这些消息与 v1.2.4 逐字一致
- 内部改用 `os.scandir`，仅命中过滤器的条目才 `stat()` 采集列
- `file_tools_listdir` 注册描述同步过滤器能力
- **contains/regex docstring 防误锚警示**（联机回归后补）：旧推荐形态 `["utils/"]` 会被父目录名误吞（如仓库名 `file-tools/` 天然含 `tools/`，absolute 模式全盘命中）；现警示「子串可命中路径任意片段、含父目录名」，限定目录推荐 `"/utils/"` 斜杠边界（顶层目录够不到）或 `regex="(^|/)utils/"`。regex 示例 `^src/` 同步改 `(^|/)src/`（absolute 模式 `^` 锚在盘符头永不命中）。仅文案、逻辑零改动；schema 重导出，482 测试全绿

### 测试
- 新增 `TestListdirFilters` 38 例（显示格式/五过滤器语义/AND 组合/单串宽容输入/环检测与合法复用不误杀等）+ `TestListdirCapsAndFixes` 14 例（双上限早退提示/`all`+非法值顺序/无效 token/断链警告与匹配独立性/absolute 路径形态 exclude/尾斜杠排序等，双上限经模块级常量 monkeypatch 测试）；符号链接用例无权限时自动 skip（需管理员或开发者模式）
- 全部新用例经独立审查探针复核；新增 `TestListdirEdgeCorners` 29 例（行覆盖审计补网：created_at 列、防御性 OSError 三分支、上限×递归/×越界分页、contains 字面量语义、dotfile/多后缀语义、正则中置全局标志报错、`(?i:…)` 局部组、前瞻 AND、exclude `*`/`?`/尾斜杠、页脚次序、中文路径、指向根的自环、symlink 后缀按链接名/size 随目标、非序列过滤值兜底、六列全开 Markdown、JSON 字符串化数组还原/columns JSON/方括号字面量兜底）；coverage.py 分支模式审计：listdir 区域**行覆盖 100%**、分支弧仅余 1 条结构不可达的防御性 elif 穷尽死弧（gather_set 按构造仅含 6 已知列）
- 5 个旧用例断言适配新路径格式；全量 482 例通过

## v1.2.4 (2026-09-04)

> 工具描述精简：面向 Agent 的描述去依赖库实现细节

### 变更
- **工具描述精简（去依赖库实现细节）**：
  - `file_tools_trash` / `file_tools_trash_undo`：注册描述与 docstring 移除「依赖 pytrash」句，Args 移除「pytrash 未安装时提示安装」
  - `file_tools_guess`：描述由「依赖 puremagic 库…辅以 chardet…」改为「根据文件魔数（magic number）检测类型，文本自动检测编码」，库名不再出现
  - `file_tools_read_lines`：`encoding` 参数说明移除「使用 chardet」
  - 运行时「pytrash 未安装」错误提示保持不变；`tools_schema.json` 同步重新导出，全 schema 已无依赖库名

## v1.2.3 (2026-09-04)

> 兼容性发布：QwenPaw 版本上限放宽 + 云端 Python 3.11 依赖兼容

### 变更
- **QwenPaw 兼容上限放宽**：`plugin.json` 的 `qwenpaw_version.max` 从 `2.1.0` 提升到 `2.3.0`
- **puremagic 依赖下限放宽**：`requirements.txt` 从 `puremagic>=2.2.0` 调整为 `puremagic>=1.20`。puremagic 2.x 要求 `Python >=3.12`，而云端 QwenPaw 运行环境为 Python 3.11 装不上 2.2.0；放宽下限后 3.11 环境可安装 1.x（本地 3.12+ 环境仍可正常使用 2.2.0）

### 文档
- README 备份目录路径修正：`_file_tools/history/` → `file_tools_data/history/`（v1.2.0 已改路径，README 当时未同步）；新增 puremagic 1.x/2.x 兼容性说明
- `file_tools_undo` docstring 中旧备份路径同步修正，重新导出 `tools_schema.json`
- 补漏：`tools_schema.json` 中 `file_tools_undo.history_number` 的 schema 在 v1.2.2 时漏更新，本次重新导出补为 `anyOf: [integer, string]`
- `.gitignore` 清理旧备份目录条目；`show_tool_schema.py` 工具数注释修正（25 → 26）


## v1.2.2 (2026-08-15)

> 字符串数字参数兼容 + 报错消息优化 + 行尾统一

### 变更
- **整数参数兼容字符串输入**：16 个工具、32 个整数参数（行号/位置/数量/偏移量）类型从 `int` 放宽为 `int | str`，LLM 传 `"123"` 字符串也能正常工作
  - 新增 `parse_int()` 统一解析：十进制数字字符串（含负号）合法，`"abc"`/`"1.5"`/`True` 等非法输入报错「xxx 参数应当输入整数」
  - 涉及工具：`replace_lines`、`insert_lines`、`delete_lines`、`replace`、`regex_replace`、`indent_lines`、`read_lines`、`read_block`、`regex`、`listdir`、`diff`、`undo`、`read_bytes`、`write_bytes`、`find_bytes`、`replace_bytes`
- **未找到匹配不再回显源文本**：`file_tools_replace` / `file_tools_regex_replace` 未找到匹配时去掉 old_text/pattern 全文回显（长文本会刷屏），保留文件路径和行范围定位信息
- **行尾统一**：全部 `.py` 文件统一为 Windows CRLF 行尾

### 测试
- 新增 36 个测试（`parse_int` 单元测试 + 各工具字符串参数兼容/非法报错），全量 401 个测试通过
- 同步更新 `tools_schema.json`（整数参数 schema 变为 `anyOf: [integer, string]`）

## v1.2.1 (2026-07-25)

> 工具描述优化

### 变更
- **`file_tools_indent_lines` 描述优化**：docstring 和注册描述新增「可以轻松调整代码段的缩进」，提升 AI 对工具适用场景的理解
- 同步更新 README 工具表格、`tools_schema.json` 导出 schema
## v1.2.0 (2026-07-24)

> 治理兼容 + ToolChunk 结构化返回 + 备份重构 + 自动清理

### 变更
- **治理系统兼容**：全部 26 个 `register_tool()` 调用新增 `tool_type="file"`、`target_param="path"` 参数，解决 QwenPaw 治理系统因默认 `tool_type="network"` 无法识别工具类型导致的拦截问题
- **ToolChunk 结构化返回**：全部 26 个工具返回从纯字符串改为 `ToolChunk(is_last=True, state=SUCCESS/ERROR, content=[TextBlock(...)])`，与 QwenPaw 内置工具一致
- **备份路径简化**：`{ws}/sessions/console/default_default.json_file_tools/` → `{ws}/file_tools_data/`
- **启动自动清理**：注册 `register_startup_hook`，每次 QwenPaw 启动时自动清理超过 30 天的旧备份
- **原子写入**：`files.json` 写入改为 `.temp` + `os.replace` 原子写入，防止写入中断导致文件损坏

### 修复
- 启动钩子注册代码位置错误（在 `register()` 方法外调用，永不执行），已移入方法内
- 插件注册日志误报「25 个工具」，修正为「26 个工具」
- `plugin = FileToolsPlugin()` 实例化位置错误，已移至文件末尾

### 测试
- 新增 4 个 `cleanup_old_backups` 测试（空目录、过期清理、空目录删除、files.json 清理）
- 全量 365 个测试全部通过

## v1.1.0 (2026-07-22)

> 字节级操作 + 缩进工具 + 跨行正则 + 安全增强

### 新增工具（6 个）
- **字节级工具 4 个**：`file_tools_read_bytes`（hex 读取）、`file_tools_write_bytes`（全量/部分覆盖写入）、`file_tools_find_bytes`（精确查找）、`file_tools_replace_bytes`（变长替换）
- **`file_tools_indent_lines`**：调整行首缩进，支持 expand/shrink 两种模式
- **`file_tools_write`**：全量写入文本文件，原子写入，已存在时自动备份

### 增强功能
- `file_tools_listdir` 新增分页、排序（7 种字段）、`absolute` 路径控制、Markdown 表格输出
- `file_tools_regex` 改为跨行匹配，JSON 输出，支持捕获组提取
- `file_tools_regex_replace` 改为跨行匹配，从后往前替换
- `file_tools_read_lines`/`read_block` 新增 `show_line_number` 参数
- `file_tools_replace` 新增 `count=-1`（全部替换）和 diff 预览
- 6 个修改工具补齐 `line_separator` 参数
- `file_tools_read_block` 参数重命名统一语义（row/col，1-based 包含）

### 安全增强
- **备份失败安全锁**：字节级写入备份失败时拒绝修改，需用户打字「同意跳过备份」
- **原子写入**：全部 6 个编辑工具改用 `.temp_file` + `os.replace` 原子写入
- `file_tools_write` 备份失败统一安全策略

### 预览格式统一
- 全部修改工具（`replace_lines`、`delete_lines`、`insert_lines`、`indent_lines`）统一为 `+/-` diff 格式

### 目录融合
- `copy`/`move` 源目录→已存在目标目录时融合，文件→已存在目录时放入内部

### 修复
- `replace_bytes`：备份失败不再静默忽略
- `delete_lines`：预览 `<<省略>>` 死代码移除
- `indent_lines`/`diff`：补齐参数校验
- `replace`：支持 `count=-1`
- `copy`/`move`：`src==dst` 检测、`move` 自动创建目标目录
- `mkdir`：空字符串报错
- `info`：三段式错误格式
- `replace_bytes`：位置列表统一 CSV 格式

### 测试
- 测试从 176 增至 **361**，覆盖中文路径、GBK 编码、特殊字符、重叠匹配、变长替换等场景

---

## v1.0.0 (2026-07-19)

> 初始发布

### 20 个文件操作工具

**信息读取类（5 个）**
| 工具 | 功能 | 返回格式 |
|------|------|:--------:|
| `file_tools_listdir` | 列出目录内容 | 纯文本/Markdown |
| `file_tools_info` | 查看文件/目录元数据 | JSON |
| `file_tools_guess` | 猜测文件类型和编码 | JSON |
| `file_tools_diff` | 文件差异对比 | Diff |
| `file_tools_history` | 查看文件历史版本列表 | JSON |

**文本读取类（3 个）**
| 工具 | 功能 | 返回格式 |
|------|------|:--------:|
| `file_tools_read_lines` | 按行读取文本文件 | 纯文本 |
| `file_tools_read_block` | 读取矩形块（行+列范围） | 纯文本 |
| `file_tools_regex` | 正则匹配 | JSON |

**文件修改类（6 个，自动备份）**
| 工具 | 功能 |
|------|------|
| `file_tools_append` | 追加内容到文件末尾 |
| `file_tools_replace_lines` | 替换指定行区间 |
| `file_tools_insert_lines` | 在指定行前插入内容 |
| `file_tools_delete_lines` | 删除指定行区间 |
| `file_tools_replace` | 查找替换（子串匹配） |
| `file_tools_regex_replace` | 正则替换 |

**安全操作类（5 个）**
| 工具 | 功能 |
|------|------|
| `file_tools_copy` | 复制文件/目录 |
| `file_tools_move` | 移动/重命名 |
| `file_tools_trash` | 安全删除到回收站 |
| `file_tools_trash_undo` | 从回收站恢复 |
| `file_tools_mkdir` | 创建目录 |

**历史回滚（1 个）**
| 工具 | 功能 |
|------|------|
| `file_tools_undo` | 恢复文件到历史版本 |

### 核心特性
- 所有修改类工具 **自动备份**，支持历史回滚
- 三段式错误提示（`XX失败，因为XX。如果要XX，请XX。`）
- 自动编码检测（chardet）+ 魔数类型检测（puremagic）
- 176 个 pytest 测试，58 个手动测试场景全部通过
- 工具默认启用（`enabled=True`）