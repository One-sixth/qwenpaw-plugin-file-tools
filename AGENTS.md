# qwenpaw-plugin-file-tools

QwenPaw 文件操作补充插件。注册 26 个 Agent 工具，补充 QwenPaw 缺失的文件操作能力。

## 快速导航

| 文件 | 用途 |
|------|------|
| `plugin.py` | 插件入口，注册 26 个工具 |
| `utils.py` | 公共工具函数（编码检测、路径标准化） |
| `backup/manager.py` | 历史备份管理 |
| `tools/info.py` | 信息读取类工具（5 个） |
| `tools/read.py` | 文本读取类工具（3 个） |
| `tools/edit.py` | 文件修改类工具（7 个，自动备份） |
| `tools/safe.py` | 安全文件操作类工具（5 个，不触发备份） |
| `tools/history.py` | 历史回滚工具（1 个） |
| `tools/write.py` | 全量写入工具（1 个） |
| `tools/bytes.py` | 字节级工具（4 个） |
| `show_tool_schema.py` | 工具 schema 展示脚本 |
| `tests/` | 300+ 个 pytest 测试 |

## 26 个工具清单

### 信息读取类（5 个）
1. `file_tools_listdir` — 列出目录内容（types/extensions/contains/regex/exclude 五类过滤 + follow_symlink 环检测；路径正斜杠、目录带尾斜杠）
2. `file_tools_info` — 查看文件元数据（JSON）
3. `file_tools_guess` — 猜测文件类型和编码（JSON）
4. `file_tools_diff` — 文件差异对比（unified diff）
5. `file_tools_history` — 查看文件历史版本（JSON）

### 文本读取类（3 个）
6. `file_tools_read_lines` — 按行读取（纯文本格式，支持行号显示）
7. `file_tools_read_block` — 读取矩形块（行+列范围）
8. `file_tools_regex` — 正则搜索，支持跨行匹配，返回 JSON

### 文件修改类（7 个，自动备份）
9. `file_tools_append` — 追加内容到文件末尾
10. `file_tools_replace_lines` — 替换行区间（行数可增减）
11. `file_tools_insert_lines` — 行前插入
12. `file_tools_delete_lines` — 删除行区间
13. `file_tools_replace` — 精确子串替换，支持跨行（dry_run）
14. `file_tools_regex_replace` — 正则替换，支持跨行匹配（dry_run）
15. `file_tools_indent_lines` — 调整行首缩进（expand/shrink）

### 安全文件操作类（5 个，不触发备份）
16. `file_tools_copy` — 复制（目录不存在时自动创建）
17. `file_tools_move` — 移动/重命名
18. `file_tools_trash` — 安全删除到回收站（pytrash）
19. `file_tools_trash_undo` — 从回收站恢复
20. `file_tools_mkdir` — 创建目录

### 历史回滚（1 个）
21. `file_tools_undo` — 恢复到历史版本

### 全量写入（1 个）
22. `file_tools_write` — 写入文件（原子写入，已存在时自动备份）

### 字节级工具（4 个）
23. `file_tools_read_bytes` — 读取二进制文件指定字节范围，返回 hex
24. `file_tools_write_bytes` — 写入二进制，支持全量/部分覆盖
25. `file_tools_find_bytes` — 在二进制文件中查找字节序列
26. `file_tools_replace_bytes` — 在二进制文件中查找并替换字节序列
