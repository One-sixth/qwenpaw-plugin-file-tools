# File Tools — QwenPaw 文件操作补充插件

**补充 QwenPaw 缺失的文件操作能力：安全文件操作、行级编辑、文件信息、文本搜索、批量处理、历史回滚。**

## 功能概览（20 个工具）

### 信息读取类
| 工具 | 功能 | 返回格式 |
|------|------|:--------:|
| `file_tools_listdir` | 列出目录内容（支持递归、属性列） | CSV |
| `file_tools_info` | 查看文件/目录元数据 | JSON |
| `file_tools_guess` | 猜测文件类型和编码 | JSON |
| `file_tools_diff` | 文件差异对比（unified diff） | Diff |
| `file_tools_history` | 查看文件历史版本列表 | JSON |

### 文本读取类
| 工具 | 功能 | 返回格式 |
|------|------|:--------:|
| `file_tools_read_lines` | 按行读取文本文件 | CSV |
| `file_tools_read_block` | 读取矩形块（观察窗口） | CSV |
| `file_tools_regex` | 正则匹配文件内容 | CSV |

### 文件修改类（自动备份）
| 工具 | 功能 |
|------|------|
| `file_tools_append` | 追加内容到文件末尾 |
| `file_tools_replace_lines` | 替换指定行区间 |
| `file_tools_insert_lines` | 在指定行前插入内容 |
| `file_tools_delete_lines` | 删除指定行区间 |
| `file_tools_replace` | 查找替换（子串匹配，支持 dry_run） |
| `file_tools_regex_replace` | 正则替换（支持反向引用，支持 dry_run） |

### 安全文件操作类
| 工具 | 功能 |
|------|------|
| `file_tools_copy` | 复制文件/目录 |
| `file_tools_move` | 移动/重命名 |
| `file_tools_trash` | 安全删除到回收站 |
| `file_tools_trash_undo` | 从回收站恢复 |
| `file_tools_mkdir` | 创建目录 |

### 历史回滚
| 工具 | 功能 |
|------|------|
| `file_tools_undo` | 恢复文件到历史版本 |

## 安装

```bash
# 安装插件（QwenPaw 离线时执行）
qwenpaw plugin install /path/to/qwenpaw-plugin-file-tools

# 启动 QwenPaw
qwenpaw app
```

> 依赖（`pytrash`、`puremagic`、`chardet`）由 QwenPaw 在插件安装时自动处理。

安装后工具默认启用，无需额外配置。

## 依赖

| 库 | 用途 |
|---|------|
| `pytrash` | 回收站操作 |
| `puremagic` | 文件类型魔数检测 |
| `chardet` | 文本编码自动检测 |

## 路径规范

- 相对路径默认相对于 workspace 目录
- 自动展开 `~`
- 用 `os.path.abspath()` + `os.path.normpath()` 标准化

## 错误处理

失败时统一返回三段式错误信息：

```
XX操作失败，因为XX原因。如果要XX，请XX。
```

## 历史备份机制

修改类工具（append、replace_lines、insert_lines、delete_lines、replace、regex_replace）在执行前自动备份原文件到 `_file_tools/history/` 目录。使用 `file_tools_history` 查看版本列表，`file_tools_undo` 恢复指定版本。

## License

MIT
