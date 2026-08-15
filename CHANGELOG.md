# 更新日志

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