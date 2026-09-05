# 更新日志

## v1.6.1 (2026-09-05)

### copy_lines 行模型转向：list 模型，幻影行退役（作者第四裁决）
- **模型定义**：拆行结果的每个元素都是真实行——文件末尾换行对应的空行也是一行，行数即列表长度，无任何减法/排除特判；`insert_line` 允许 `总行数+1` 作为正式落点（= 插到全部行之后），超界仍按追加
- **新建不补换行**：v1.6.0 的"末尾补换行成规范文本文件"特判删除——文件末尾有无换行完全由所选数据决定：选区含源文件末尾空行 → 新文件以换行结尾；止于中途行 → 裸尾。空行的终止符随行自带（0 字节文件即一行空行，重读口径恒等），M2"复制空行不被吞"在模型公理下天然成立
- **收益**：第七轮盲测批评🥉（同一文件在"从X行变为Y行"与"共N行"两处报数差 1）根除——所有对外表面同一套真实行号；"记账空行不对称"（源侧排除/目标侧包含）的旧裁决整体作废
- ⚠️ **家族口径差异（作者裁决：其他工具先不管，记录在案）**：edit.py 四工具（insert_lines/delete_lines/replace_lines/replace）的摘要"从X行变为Y行"与落点域仍是旧列表口径（带换行结尾文件比 copy_lines 多报 1 行）；跨工具对表时留意
- 工具 docstring 一字未动即在新模型下自洽（极简契约钉测原样通过）；测试 564 → 565（源域宽一行的正反钉、新建裸尾与含末尾空行两向钉、空源=一行公理钉，11 处旧钉按新模型重钉）

### 特例扫荡（同日增补，模型转向红利兑现）
- 逐 if 普查"这是定义还是旧模型的残留"，拔掉 4 处特例（前两处零行为 diff，第三处一处受控收口）：
  1. **编码继承三处分支并一规则**：`auto 且目标没有自己的字节（自复制/不存在/0 字节）→ 沿用源编码`（原 M3 补丁痕迹折叠进正向规则）
  2. **行尾探测删 `not empty_dst`**：0 字节文件探测自然得 None → 与新建同路落回 OS，特判是冗余
  3. **删 `if fresh: insert_pos = 0` 落点特判**：空基线下一切合法落点自然收敛到 0；行为 diff 仅一处——**新建 + insert_line=0/负数从静默忽略改为与已存在目标同规报错**（校验先于创建，零污染），docstring「目标新建时忽略」相应改「新建时任意合法值自然收敛为整体新建」（必留短语同步换钉）
  4. fresh 补换行特判（上文模型转向已删）
- 保留并说明理由的"非特例"：追加落末尾空行之前（= 末尾风格保持的定义）、`follow = src_sep if self_copy else 探测`（strict 自复制字节级还原的必然）、`\r\n→\n` 写回折叠（M1 物理护栏，已条件最小化）、start 报错/end 钳位（家族编辑语法）
- 全量复测 565 全绿，分支覆盖 99%（余 = 双模式导入死弧）

## v1.6.0 (2026-09-05)

### 新工具：file_tools_copy_lines（第 27 个）
- 从源文件选 `start_line..end_line` 行，复制到目标文件 `insert_line` 之前——**行内容全程直接落盘编辑、不经过对话上下文**（此前需 read_lines + insert_lines 两步接力，费 token 且可能转录出错）
- `dst_file` 留空 = 复制到源文件自身（自复制，两端行号均以改前为准）；显式路径大小写不同也识别为同一目标，只备份一次
- 目标不存在自动新建（连同父目录，末尾补换行成规范文本文件）；已存在修改前自动备份；空文件目标无需特判（幻影空行基线自然收敛）
- `insert_line`：1 = 开头、-1/不填 = 末尾追加；**超过总行数与 -1 同意自动追加**（作者中途修订，从严报错+指引句方案作废）；目标不存在自动新建时忽略该参数
- `src_encoding`/`dst_encoding`、`src_line_separator`/`dst_line_separator` 双端独立配置；源 strict 拆行（仅按指定行尾拆，其余换行符保留进行内容）与写回转换间做 `\r\n` 折叠防 `\r\r\n` 字节腐蚀
- **目标行尾保真（作者第三裁决）**：`dst_line_separator=auto` 且目标已有内容时，写回**保持目标文件自身主行尾**（`_dominant_newline` 探测 \r\n/\n/\r 多数者、平局 CRLF 优先；复制内容随之换装目标行尾；探测失败/无换行/空文件/新建落回 OS 口径）——LF 文件跨文件复制、自复制都不再被整体转 CRLF；`dst_encoding=auto` 自复制沿用源编码（初版即如此）。⚠️ 家族其余 24 工具（append/insert 等）的 auto 仍是 OS 口径，是否推广待裁
- 专卷盲测（第六轮，新工具首卷）6/6 全过零意外、自评 8/10：收口句六处逐字引用（含"超过总行数与 -1 同意"当日修订即被实证）；幻影行口径获作者终裁「末尾有换行，那也是换行」维持现状
- 零上下文对抗审查抓漏 4 处（字节腐蚀/单空行 0 字节/空目标编码分裂/链接误判自复制），修复并钉回归测试 `TestAdversarialFixes`
- 测试 491 → 561（新增 70 个，含 IO 异常路径、docstring 极简契约 12 必留短语与自复制行尾保真 7 连钉）；新模块行覆盖 99%（余分支不可达为双模式导入兜底）

## v1.5.1 (2026-09-05)

### 报错文案修复（五轮盲测批评🥉）
- `format_error` 句尾去重：全仓 39 处自带「。」结尾的 reason 曾拼出「。。」（历史上仅有 diff start=0 一处局部补丁），现于源头统一归一；新增双句号钉死用例
- **装机版 1.5.0 无此修复**，需重装生效（纯文案级，行为不变）

## v1.5.0 (2026-09-05)

> 四轮盲测（8.5/10，6/6 零试错）批评核实后的 type 系统重做

### type 系统：材质+目标两段复合（`symlink|X`）
- **type 列值域重做**：`dir` / `file` / `symlink|dir` / `symlink|file` / `symlink|invalid`——type 回答"条目是什么做的"，链接的目标类型与可达性以第二段表达；普通目录列值由 `directory` 统一为简写 `dir`
- **types 过滤改分段匹配**：token 命中类型串任一分段即保留。`["dir"]` 含活目录链接、`["symlink"]` 活链死链一网打尽（四轮盲测批评②：旧版链接目录伪装成 directory，想"找链接"必静默漏）
- **尾斜杠规则**：目标可达且为目录 → 恒带杠（含 `follow_symlink=False` 与环条目——type 答"材质"，遍历答"进不进"，两维正交）；断链无杠
- 断链判定改为跟随 stat 失败（`symlink|invalid`），size/permissions 等元数据随目标不变
- **types 文档行重写**：`按类型过滤，命中类型任一分段即可：file、dir、symlink。`——**别名制度废除**（`directory`/`link` 不再接受）、**`all` 退役**（不填/空列表=保留全部）；非法 token 中文报错列出词表并说明"任一分段"
- `path` 描述补「支持绝对路径」（四轮盲测：新人硬着头皮试，值得一句钉死；本版先改 listdir 试水）

### 警告文案统一
- 环警告 `<<<警告，发现symlink环嵌套，…>>>` → `<<<警告，发现循环符号链接，…>>>`（中英混排清退，与「符号链接目标不可达」同词族；盲测批评④）

### 测试与契约
- 钉死契约 `test_docstring_minimal_contract` 换钉：8 必留（+`命中类型任一分段`、`绝对路径`；-`只影响显示，不影响遍历`、`别名`），禁回流 +4（`别名`/`all=不过滤`/`只影响显示`/`invalid`）
- 存量迁移：别名/`all` 断言反转、type 列值 5 处、follow=False 叶子用例改"恒带杠不展开"；新增分段匹配 3 用例 → **490 全绿**


## v1.4.0 (2026-09-05)

> 本版合并原 v1.3.3 草稿段（未单独发布过）：文档极简重写 + 两项破坏性变更

### 文档哲学转向：极简直觉化
- `file_tools_listdir` docstring 全面重写：**2340→601 字符（-74%，schema 参数描述口径）**。原则：agent 对列目录工具自带 ls/glob 世界知识，边界情况由**运行时输出自解释**（行内警告、统计行、中文报错）承接；删除注意事项类（锚定警示/输出预告/类型速查/实现内幕等），保留六个一词级要点
- 全插件文档预算 10738→8999 字符（-16%），listdir 占比 21.8%→6.7%
- docstring 钉死断言改为 `test_docstring_minimal_contract`：6 必留 + 7 禁回流词（防注意事项重新堆回来）

### 破坏性变更
- **移除 `file_tools_listdir` 的 `absolute` 参数**（及全部相关逻辑）：输出路径统一为**相对遍历根**的正斜杠串；需要绝对路径时，用工具入参 `path` 与结果拼接即可。contains/regex 从此只面对一种路径形态
- **`exclude` 换 gitignore 语义引擎**（pathspec，`requirements.txt` 新增 `pathspec>=1.1`）：`build/` 目录型（旧语义死模式，现真剪枝）、`/x` 锚根、`!` 豁免（被剪目录的子项无法复活，与 git 一致）、`#` 行注释、裸名任意深度
- **行为漂移清单**（对抗审查 F2 修正版，替换初稿失实句）：
  - 含斜杠模式**锚定翻转**：旧 fnmatch 整串 `*/tests/*`、`src/*.py` 可在任意深度生效；新引擎按 gitignore 锚定遍历根，深层同款请用 `**/tests/**` 或裸目录名
  - `*`/`?` 不再跨路径分隔符（gitignore 规则；`*` 旧引擎经 basename 串等效任意深度，故无斜杠裸 glob 如 `*.tmp` 行为不变）
  - `#` 开头从字面 glob 变注释行；`\#foo` 型转义受预处理 `\`→`/` 影响，仅根层可表达（Windows 分隔符便利与转义表达的折中，保留）
  - 非法模式（半截 `!`、逆序字符集 `[z-a]`）经新守卫返回中文报错（`exclude 含不合法的 gitignore 模式：…`），不再向上抛异常
- 测试：absolute 专属 4 例删除；exclude 1 例反转（尾斜杠）+ 7 例新增（`!` 豁免/`/` 锚根/剪枝防复活/`#` 注释/大小写双低/嵌套裸名/非法模式中文报错）→ **489 全绿零警告**
- **三轮盲测（8.5/10，6/6 一次通过零试错）反馈收口**：C1 docstring 补「exclude 按显示路径匹配、不解析符号链接」（新人 T3 自曝在赌匹配基准）；C2 首段补「输出路径相对遍历根」（新人 T5 找绝对路径白绕一圈）；C4 `recursive` 改「往下列几层。1=本层，2=含子目录一层，-1=全部层」（免换算）；C3 警告串塞 name 列**维持 v1.3.0 行内警告裁决不改**（破坏性候选，仅记录）。两新句入 `test_docstring_minimal_contract` 钉死，listdir 文档 601→622 字符
- ⚠️ 依赖锁 `>=1.1`：工厂名 `'gitignore'` 在 0.12 是弃用别名（1.1 才翻正），`'gitwildmatch'` 自 1.1 弃用

## v1.3.2 (2026-09-05)

> 二轮盲测反馈：输出格式预告 + 类型速查等文档盲区补全

### 变更
- **docstring 首段补输出形态预告**：写明 listdir 的四类伴随信息——分页尾注、过滤统计行、上限截断提示、行尾「<<<警告，…>>>」内联标记（警告文字不参与匹配与排序）——终结二轮盲测最大批评「见到才知道」
- **follow_symlink 类型判定速查**：链接目录（跟随时 directory / 不跟随时 symlink）、链接文件（恒 symlink）、断链（恒 symlink+行内警告）三条规则收拢成一句，不再散落三处拼图
- **sort_by 平局提醒**：补「Windows 上目录 size 恒 0，混合清单按 size 排序可能大面积平局」的组合后果警告
- **条目口径收尾**：首段「一行一文件」→「一行一条目」；运行时「（空目录，无文件）」→「（空目录，无条目）」——至此四类运行时提示全部统一
- 版本号 1.3.1 → 1.3.2

### 测试
- `TestEntryWording` docstring 钉死断言 7→11 句（新增输出预告/类型速查/平局提醒/一行一条目）；空目录 2 处精确断言同步；486 全绿

## v1.3.1 (2026-09-05)

> 零上下文盲测反馈：文案「条目化」与文档盲区补全（纯文案，逻辑零改动）

### 变更
- **运行时文案「文件」→「条目」**：分页尾语「当前列出的条目 X~Y，后面还有 N 个条目。」、越界「（没有更多条目，共 N 个条目，当前从第 M 个开始）」、start 参数错误「start 表示『从第几个条目开始显示』」——listdir 计数/排序对象含目录与符号链接，旧措辞误导（盲测新人按字面理解 count，结果前 3 条全是目录）。零匹配消息本就是「（无匹配条目）」，统一口径
- **docstring 五处**（`file_tools_listdir`，schema 已重导出）：
  - `count`/`start`：文件数/第几个文件 → **条目数（目录、symlink 均计入）/第几个条目**
  - `columns` size：补「Windows 下目录恒为 0，断链取不到元数据时为空/0」
  - `sort_by`：补「稳定排序，同值条目保持遍历收集次序，不承诺跨调用可复现」
  - `types`：「含 all 即不过滤（但其余非法值仍会报错，先校验后生效）」重写为「任何非法值都会报错（与列表顺序无关），全部合法且含 all 时本过滤器不生效」
- 版本号 1.3.0 → 1.3.1

### 测试
- 存量 15 处文案断言迁移「条目」；新增 `TestEntryWording` 4 例（分页尾语整句精确、start 报错文案、Windows 下 size 列目录=0 表检[非 Windows skip]、**docstring 七关键句钉死**含 contains 防误锚与 regex `(^|/)` 示例），合计 486 全绿

### 背景
- 反馈来自零上下文子 agent 盲测：仅凭工具描述一次通过 5 场景任务、评 8/10，批评 4 条（count 条目数/目录 size 语义/平局次序/尾语口径）全部在本版修复或写入文档

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