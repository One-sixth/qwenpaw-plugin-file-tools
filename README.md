# File Tools — QwenPaw 文件操作补充插件

**补充 QwenPaw 缺失的文件操作能力：安全文件操作、行级编辑、文件信息、文本搜索、批量处理、历史回滚、回收站操作、字节级操作。**

## 功能概览（26 个工具）

### 信息读取类
| 工具 | 功能 | 返回格式 |
|------|------|:--------:|
| `file_tools_listdir` | 列出目录内容（支持递归、属性列、排序、分页） | 纯文本/Markdown |
| `file_tools_info` | 查看文件/目录元数据 | JSON |
| `file_tools_guess` | 猜测文件类型和编码 | JSON |
| `file_tools_diff` | 文件差异对比（unified diff） | Diff |
| `file_tools_history` | 查看文件历史版本列表 | JSON |

### 文本读取类
| 工具 | 功能 | 返回格式 |
|------|------|:--------:|
| `file_tools_read_lines` | 按行读取文本文件（支持行号开关） | 纯文本 |
| `file_tools_read_block` | 读取矩形块（行+列范围，观察窗口） | 纯文本 |
| `file_tools_regex` | 正则匹配（支持跨行，捕获组提取） | JSON |

### 文件修改类（自动备份）
| 工具 | 功能 |
|------|------|
| `file_tools_append` | 追加内容到文件末尾 |
| `file_tools_replace_lines` | 替换指定行区间 |
| `file_tools_insert_lines` | 在指定行前插入内容 |
| `file_tools_delete_lines` | 删除指定行区间 |
| `file_tools_replace` | 查找替换（子串匹配，支持 dry_run） |
| `file_tools_regex_replace` | 正则替换（支持跨行，支持 dry_run） |
| `file_tools_indent_lines` | 调整行首缩进（expand/shrink），可以轻松调整代码段的缩进 |
| `file_tools_write` | 全量写入文件（原子写入，自动备份） |

### 安全文件操作类
| 工具 | 功能 |
|------|------|
| `file_tools_copy` | 复制文件/目录 |
| `file_tools_move` | 移动/重命名 |
| `file_tools_trash` | 安全删除到回收站 |
| `file_tools_trash_undo` | 从回收站恢复 |
| `file_tools_mkdir` | 创建目录 |

### 字节级操作
| 工具 | 功能 | 返回格式 |
|------|------|:--------:|
| `file_tools_read_bytes` | 读取二进制文件指定范围（hex 输出，上限 4096 字节） | Hex |
| `file_tools_write_bytes` | 二进制写入（全量/部分覆盖，原子写入，skip_backup） | 文本 |
| `file_tools_find_bytes` | 精确查找字节序列（返回十进制偏移量列表） | CSV |
| `file_tools_replace_bytes` | 查找替换字节序列（边长替换，原子写入，skip_backup） | 文本 |

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

> `puremagic` 版本要求 `>=1.20`：2.x 系列要求 Python ≥3.12，云端 QwenPaw（Python 3.11）环境需装 1.x 系列。本插件仅使用 `magic_file()`，1.x/2.x 该 API 一致，检测失败时自动降级。

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

修改类工具（append、replace_lines、insert_lines、delete_lines、replace、regex_replace、indent_lines、write、write_bytes、replace_bytes）在执行前自动备份原文件到 QwenPaw workspace 下的 `file_tools_data/history/` 目录（按文件路径分子目录存放）。使用 `file_tools_history` 查看版本列表，`file_tools_undo` 恢复指定版本。备份超过 30 天会在 QwenPaw 启动时自动清理。

## 字节级工具说明

字节级工具使用 hex 字符串表示二进制数据，全大写输出。

### hex 输入规则
- 允许空格，自动忽略
- 大小写不敏感
- 不可以 `0x` 或 `\x` 开头
- 去掉空格后长度必须是 2 的倍数

### 常用示例
```python
# 读取文件头
file_tools_read_bytes(path="image.jpg", offset=0, length=16)

# 写入 JPEG 文件头
file_tools_write_bytes(path="out.jpg", content="FF D8 FF E0 00 10 4A 46")

# 查找模式
file_tools_find_bytes(path="data.bin", pattern="01 02 03")

# 替换字节序列
file_tools_replace_bytes(path="data.bin", old_bytes="FF D8", new_bytes="00 00")
```

## License

MIT
