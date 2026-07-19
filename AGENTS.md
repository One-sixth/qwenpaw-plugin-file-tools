# qwenpaw-plugin-file-tools

QwenPaw 文件操作补充插件。注册 20 个 Agent 工具，补充 QwenPaw 缺失的文件操作能力。

## 快速导航

| 文件 | 用途 |
|------|------|
| `plugin.py` | 插件入口，注册 20 个工具 |
| `utils.py` | 公共工具函数（编码检测、路径标准化、CSV 格式化等） |
| `backup/manager.py` | 历史备份管理 |
| `tools/info.py` | 信息读取类工具（5 个） |
| `tools/read.py` | 文本读取类工具（3 个） |
| `tools/edit.py` | 文件修改类工具（6 个，自动备份） |
| `tools/safe.py` | 安全文件操作类工具（5 个，不触发备份） |
| `tools/history.py` | 历史回滚工具（1 个） |
| `show_tool_schema.py` | 工具 schema 展示脚本（模拟 QwenPaw 的 schema 生成） |
| `tests/` | 176 个 pytest 测试 |

## 20 个工具清单

### 信息读取类（返回 CSV/JSON/Diff）
1. `file_tools_listdir` — 列出目录内容（recursive=1/2/-1, columns）
2. `file_tools_info` — 查看文件元数据（JSON）
3. `file_tools_guess` — 猜测文件类型（puremagic+chardet, JSON）
4. `file_tools_diff` — 文件差异对比（unified diff, hunk 分页）
5. `file_tools_history` — 查看文件历史版本（JSON）

### 文本读取类（返回 CSV）
6. `file_tools_read_lines` — 按行读取（start_line, line_count, max_chars）
7. `file_tools_read_block` — 读取矩形块（行+字符偏移）
8. `file_tools_regex` — 正则匹配（逐行 search, CSV）

### 文件修改类（自动备份）
9. `file_tools_append` — 追加内容到文件末尾
10. `file_tools_replace_lines` — 替换行区间（含预览对比）
11. `file_tools_insert_lines` — 行前插入
12. `file_tools_delete_lines` — 删除行区间（含预览对比）
13. `file_tools_replace` — 子串替换（dry_run 支持）
14. `file_tools_regex_replace` — 正则替换（反向引用, dry_run 支持）

### 安全文件操作类（不触发备份）
15. `file_tools_copy` — 复制（overwrite 控制）
16. `file_tools_move` — 移动/重命名（overwrite 控制）
17. `file_tools_trash` — 安全删除到回收站（pytrash）
18. `file_tools_trash_undo` — 从回收站恢复
19. `file_tools_mkdir` — 创建目录

### 历史回滚
20. `file_tools_undo` — 恢复到历史版本

## 关键设计决策

### 文件 I/O 使用文本模式
所有文件读写使用 Python 文本模式（`r`/`w`/`a`），不手动处理行分隔符。
Windows 上 `\n` → `\r\n` 由 Python 自动处理。
写入前调用 `normalize_newlines()` 统一 `\r\n`/`\r` → `\n`，避免二次转换。

### 相对导入
`plugin.py` 和所有子模块使用相对导入（`from .xxx import yyy`），
因为插件通过 QwenPaw 动态加载，不会 `pip install`。

### 历史备份
- 备份目录：`{会话路径}_file_tools/history/{编码目录}/{版本号}`
- 路径编码：`len(path) + blake2b(path.encode())[:32]`
- 修改类工具（9~14）自动备份，安全类工具（15~19）不触发备份
- `backup/manager.py` 独立模块，可被 tools 各模块直接 import
- 备份根路径来自 `utils.get_session_dir()`，基于 QwenPaw 配置中的 workspace_dir
- **注意**：`config.agents` 是 `AgentsConfig` 对象，不是列表。正确获取 workspace_dir
  的方式是 `config.agents.profiles["default"].workspace_dir`
- 兜底路径不要用 `os.getcwd()`（会受工作目录影响），应用固定路径
- 无法获取备份路径时抛出 RuntimeError，工具函数返回「备份原文件失败。因为获取会话文件路径失败。」

### 错误处理
所有工具失败时返回三段式错误信息：
```
XX操作失败，因为XX原因。如果要XX，请XX。
```

### 返回格式
| 格式 | 适用工具 |
|:----:|---------|
| JSON | info, guess, history |
| CSV | listdir, read_lines, read_block, regex |
| Diff | diff |
| 纯文本 | 其他所有工具 |

### description 策略
`plugin.py` 中每个工具的 `description` 写得详细，包含：
参数说明 + 边界行为 + 返回值格式 + 错误处理。不使用额外 skill 文档。

### 预览格式
`replace_lines` 和 `delete_lines` 使用对称结构：
- `─── 替换前/替换后 ───` 或 `─── 删除前/删除后 ───`
- 被替换/被删除行标 `（被替换）`/`（被删除）`
- 上下文只显示前 2 行 + 后 2 行，中间 `<<省略>>`
- 正文区超过 6 行时也只显示前 2 + 后 2 行
- `<<省略>>` 只在真的有行被省略时才出现

## 测试

```bash
cd qwenpaw-plugin-file-tools
pytest tests/ -v
```

176 个 pytest 测试覆盖，包含边界情况（空文件、超长行、GBK/CRLF 编码、
不存在的文件、无效参数、offset 反转、dry_run 模式、多版本恢复等）。
另有 58 个手动测试场景全部通过，含 4 种文件组合交叉测试验证。

## 外部依赖

| 库 | 用途 | 安装 |
|---|------|------|
| `pytrash` | 回收站操作 | ✅ 已安装 |
| `puremagic` | 文件类型检测 | 需 pip install |
| `chardet` | 编码检测 | 需 pip install |

`puremagic` 和 `chardet` 在 `file_tools_guess` 中使用，缺失时降级返回 unknown。
