# 新工具测试指南

## 新工具列表

本插件新增了 5 个工具，请按以下顺序逐一测试，确保全部正常工作。

工具清单：
1. `file_tools_write` — 全量写入（替代 write_file）
2. `file_tools_read_bytes` — 字节读取
3. `file_tools_write_bytes` — 字节写入
4. `file_tools_find_bytes` — 精确查找
5. `file_tools_replace_bytes` — 查找替换

---

## 1. file_tools_write — 全量写入

### 创建新文件
```
file_tools_write(path="_test_write.txt", content="第1行：hello\n第2行：world")
```
✅ 预期：成功，显示字符数和行数

### 覆盖已有文件（自动备份）
```
file_tools_write(path="_test_write.txt", content="覆盖后的新内容")
```
✅ 预期：成功，包含「历史号 #1」

### 写入空内容
```
file_tools_write(path="_test_empty.txt", content="")
```
✅ 预期：成功，「共 0 个字符」「0 行」

### 指定行结束符
```
file_tools_write(path="_test_crlf.txt", content="a\nb", line_separator="\r\n")
```
✅ 预期：成功，文件以 CRLF 换行

### 无效 line_separator
```
file_tools_write(path="_test_bad.txt", content="x", line_separator="invalid")
```
✅ 预期：报错，提示不支持

---

## 2. file_tools_read_bytes — 字节读取

### 基础读取
```
file_tools_read_bytes(path="_test_write.txt", offset=0, length=16)
```
✅ 预期：成功，显示 16 字节 hex（全大写），每 16 字节换行

### 自定义分组
```
file_tools_read_bytes(path="_test_write.txt", offset=0, length=16, group_size=8)
```
✅ 预期：每行 8 字节，共 2 行

### 不分组
```
file_tools_read_bytes(path="_test_write.txt", offset=0, length=8, group_size=-1)
```
✅ 预期：hex 连在一起无空格

### group_size=0 报错
```
file_tools_read_bytes(path="_test_write.txt", offset=0, length=8, group_size=0)
```
✅ 预期：报错，提示 group_size 不能为 0

### 超过 4096 上限
```
file_tools_read_bytes(path="_test_write.txt", offset=0, length=5000)
```
✅ 预期：报错，提示一次最多 4096 字节

### 偏移量超出文件
```
file_tools_read_bytes(path="_test_write.txt", offset=9999, length=8)
```
✅ 预期：报错，提示超出文件范围

---

## 3. file_tools_write_bytes — 字节写入

### 创建新文件
```
file_tools_write_bytes(path="_test_bin.bin", content="FF D8 FF E0 00 10 4A 46")
```
✅ 预期：成功，「共写入 8 字节」

### 覆盖已有文件（自动备份）
```
file_tools_write_bytes(path="_test_bin.bin", content="00 00 00 00")
```
✅ 预期：成功，包含「历史号」

### 跳过备份
```
file_tools_write_bytes(path="_test_bin.bin", content="FF", skip_backup=True)
```
✅ 预期：成功，无「历史号」提示

### 部分覆盖
```
file_tools_write_bytes(path="_test_partial.bin", content="00 01 02 03 04 05 06 07")
file_tools_write_bytes(path="_test_partial.bin", offset=4, content="FF FF")
```
✅ 预期：先创建 8 字节文件，后从偏移量 4 写入 2 字节，前 4 字节不变

### 无效 hex 输入
```
file_tools_write_bytes(path="_test_bad.bin", content="0xFF")
```
✅ 预期：报错，提示 hex 格式错误

### 部分覆盖目标文件不存在
```
file_tools_write_bytes(path="nonexist.bin", offset=0, content="FF")
```
✅ 预期：报错，提示部分覆盖仅适用于已有文件

---

## 4. file_tools_find_bytes — 精确查找

### 准备工作
先创建一个包含重复模式的文件：
```
file_tools_write_bytes(path="_test_find.bin", content="00 01 02 00 01 02 00 01 02")
```

### 基础查找
```
file_tools_find_bytes(path="_test_find.bin", pattern="00 01 02")
```
✅ 预期：CSV 格式，offset 列，3 个匹配（0、3、6）

### 限制匹配数量
```
file_tools_find_bytes(path="_test_find.bin", pattern="00 01 02", count=2)
```
✅ 预期：CSV，2 个匹配（0、3）

### 指定搜索起始偏移量
```
file_tools_find_bytes(path="_test_find.bin", pattern="00 01 02", offset=5)
```
✅ 预期：从偏移量 5 开始搜索，匹配在 6、9...

### 未匹配
```
file_tools_find_bytes(path="_test_find.bin", pattern="FF FF")
```
✅ 预期：提示「在文件中未找到匹配的字节序列。」

### 空 pattern 报错
```
file_tools_find_bytes(path="_test_find.bin", pattern="")
```
✅ 预期：报错，提示 pattern 不能为空

---

## 5. file_tools_replace_bytes — 查找替换

### 基础替换
```
file_tools_write_bytes(path="_test_replace.bin", content="01 02 03 04 05")
file_tools_replace_bytes(path="_test_replace.bin", old_bytes="01 02", new_bytes="FF FF")
```
✅ 预期：成功，「替换了 1 处」，文件内容变为 FF FF 03 04 05

### 替换多处（变短）
```
file_tools_write_bytes(path="_test_multi.bin", content="00 01 02 00 01 02 00 01 02")
file_tools_replace_bytes(path="_test_multi.bin", old_bytes="00 01 02", new_bytes="FF")
```
✅ 预期：成功，「替换了 3 处」，文件从 9 字节变为 3 字节

### 变长替换
```
file_tools_write_bytes(path="_test_var.bin", content="00 01 02 00 01 02")
file_tools_replace_bytes(path="_test_var.bin", old_bytes="00 01 02", new_bytes="AA BB")
```
✅ 预期：成功，文件变为 AA BB AA BB（4 字节）

### 限制替换次数
```
file_tools_write_bytes(path="_test_count.bin", content="00 00 00 00 00 00")
file_tools_replace_bytes(path="_test_count.bin", old_bytes="00", new_bytes="FF", count=3)
```
✅ 预期：成功，「替换了 3 处」，前 3 字节变为 FF，后 3 字节仍为 00

### 跳过备份
```
file_tools_write_bytes(path="_test_skip.bin", content="00 01 02")
file_tools_replace_bytes(path="_test_skip.bin", old_bytes="00", new_bytes="FF", skip_backup=True)
```
✅ 预期：成功，无「历史号」提示

### 无效 hex 输入
```
file_tools_replace_bytes(path="_test_replace.bin", old_bytes="0xFF", new_bytes="00")
```
✅ 预期：报错，提示 hex 格式错误

---

## 清理测试文件

测试完成后清理：
```
file_tools_trash(path="_test_write.txt")
file_tools_trash(path="_test_empty.txt")
file_tools_trash(path="_test_crlf.txt")
file_tools_trash(path="_test_bad.txt")
file_tools_trash(path="_test_bin.bin")
file_tools_trash(path="_test_partial.bin")
file_tools_trash(path="_test_find.bin")
file_tools_trash(path="_test_replace.bin")
file_tools_trash(path="_test_multi.bin")
file_tools_trash(path="_test_var.bin")
file_tools_trash(path="_test_count.bin")
file_tools_trash(path="_test_skip.bin")
```