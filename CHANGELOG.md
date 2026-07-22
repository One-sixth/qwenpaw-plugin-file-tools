# 更新日志

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