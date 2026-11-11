"""测试文本读取类工具。"""

import csv
import io
import os
import re

from tools.read import (
    file_tools_read_block,
    file_tools_read_lines,
    file_tools_regex,
)


class TestReadLines:
    def test_basic(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line=1, line_count=5)
        assert "line1" in result.content[0].text
        assert "line5" in result.content[0].text
        # 纯文本格式，行号 > 内容
        assert "1 > line1" in result.content[0].text
        assert "5 > line5" in result.content[0].text

    def test_from_middle(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line=10, line_count=3)
        assert "line10" in result.content[0].text
        assert "line12" in result.content[0].text
        assert "line9" not in result.content[0].text

    def test_to_end(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line=18, line_count=-1)
        assert "line18" in result.content[0].text
        assert "line20" in result.content[0].text

    def test_line_count_zero(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line=1, line_count=0)
        assert "失败" in result.content[0].text

    def test_beyond_file(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line=100, line_count=5)
        assert "失败" in result.content[0].text or "超出" in result.content[0].text

    def test_nonexistent_file(self):
        result = file_tools_read_lines("/nonexistent_xyz.txt")
        assert "失败" in result.content[0].text

    def test_padded_line_numbers(self, multi_line_file):
        """顶部图例行，其后每行 `行号 > 内容`。"""
        result = file_tools_read_lines(multi_line_file, start_line=9, line_count=3)
        lines = result.content[0].text.strip().split("\n")
        assert len(lines) >= 1
        # 第一行是图例，第二行是空行，第三行起才是内容
        assert lines[0] == "行号 > 行内容"
        assert lines[1] == ""
        assert "9 > line9" in lines[2]

    def test_empty_file(self, empty_file):
        """空文件返回空字符串。"""
        result = file_tools_read_lines(empty_file, line_count=5)
        result = result.content[0].text.strip()
        assert result == ""

    def test_max_chars(self, long_line_file):
        result = file_tools_read_lines(long_line_file, line_count=-1, max_chars=50)
        assert "<<<TRUNCATED>>>" in result.content[0].text

    def test_chinese(self, chinese_file):
        result = file_tools_read_lines(chinese_file, line_count=3)
        assert "第一行" in result.content[0].text

    def test_max_chars_truncated_from_start(self, many_medium_lines_file):
        """从头读，截断发生在中间行，提示行号应等于被截断行号。"""
        result = file_tools_read_lines(many_medium_lines_file, start_line=1, line_count=-1, max_chars=200)
        assert "如需继续阅读" in result.content[0].text
        match = re.search(r"从第 (\d+) 行开始读取", result.content[0].text)
        assert match is not None, f"未找到提示行号，结果：{result}"
        next_line = int(match.group(1))
        # 被截断行号应 >= 起始行号，且 <= 文件总行数
        assert 1 <= next_line <= 30, f"提示行号 {next_line} 越界"
        assert next_line >= 5, f"提示行号 {next_line} 应 >= 5（至少读到第5行才可能截断）"

    def test_max_chars_truncated_from_middle(self, many_medium_lines_file):
        """从中间读，截断发生在中间行，提示行号应等于被截断行号。"""
        result = file_tools_read_lines(many_medium_lines_file, start_line=10, line_count=-1, max_chars=150)
        assert "如需继续阅读" in result.content[0].text
        match = re.search(r"从第 (\d+) 行开始读取", result.content[0].text)
        assert match is not None, f"未找到提示行号，结果：{result}"
        next_line = int(match.group(1))
        # 提示行号应 >= start_line 且 <= 文件总行数
        assert 10 <= next_line <= 30, f"提示行号 {next_line} 越界"
        assert next_line >= 12, f"提示行号 {next_line} 应 >= 12（至少读到第12行才可能截断）"

    def test_max_chars_no_truncation(self, multi_line_file):
        """max_chars 足够大，不截断，不应有提示。"""
        result = file_tools_read_lines(multi_line_file, start_line=1, line_count=-1, max_chars=9999)
        assert "如需继续阅读" not in result.content[0].text
        assert "line20" in result.content[0].text

    # ── show_line_number=False ──────────────────────────────

    def test_show_line_number_false(self, multi_line_file):
        """show_line_number=False 时不显示行号，直接输出原文。"""
        result = file_tools_read_lines(multi_line_file, start_line=1, line_count=3, show_line_number=False)
        assert "line1" in result.content[0].text
        assert "line2" in result.content[0].text
        assert "line3" in result.content[0].text
        # 不应出现行号格式
        assert " 1 >" not in result.content[0].text
        lines = result.content[0].text.strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "line1"
        assert lines[1] == "line2"

    def test_show_line_number_false_empty_file(self, empty_file):
        """show_line_number=False 时空文件返回空字符串。"""
        result = file_tools_read_lines(empty_file, line_count=5, show_line_number=False)
        assert result.content[0].text.strip() == ""

    def test_show_line_number_false_to_end(self, multi_line_file):
        """show_line_number=False 时读取到末尾。"""
        result = file_tools_read_lines(multi_line_file, start_line=18, line_count=-1, show_line_number=False)
        lines = result.content[0].text.strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "line18"
        assert lines[-1] == "line20"

    def test_show_line_number_false_truncated(self, long_line_file):
        """show_line_number=False 时截断提示仍保留。"""
        result = file_tools_read_lines(long_line_file, line_count=-1, max_chars=50, show_line_number=False)
        assert "<<<TRUNCATED>>>" in result.content[0].text
        assert "如需继续阅读" in result.content[0].text
        # False 模式不带图例
        assert "行号 > 行内容" not in result.content[0].text

    def test_only_newlines_file(self, tmp_dir):
        """仅换行符文件应正确读取。"""
        path = os.path.join(tmp_dir, "newlines.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n\n\n")
        result = file_tools_read_lines(path, line_count=-1, show_line_number=False)
        assert result.content[0].text.count("\n") == 3  # 3 个换行符 = 4 行（含末尾空行）

    def test_no_trailing_newline(self, tmp_dir):
        """末尾无换行符文件应正确读取。"""
        path = os.path.join(tmp_dir, "no_eol.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("line1\nline2")
        result = file_tools_read_lines(path, line_count=-1, show_line_number=True)
        assert "1 > line1" in result.content[0].text
        assert "2 > line2" in result.content[0].text

    def test_legend_header(self, multi_line_file):
        """show_line_number=True 时输出顶部带格式图例。"""
        result = file_tools_read_lines(multi_line_file, start_line=1, line_count=3)
        assert result.content[0].text.startswith("行号 > 行内容\n\n")
        assert "1 > line1" in result.content[0].text

    def test_truncated_footer_format(self, long_line_file):
        """截断尾部格式：行尾标记 + 空行 + 标记开头说明，图例仍在顶部。"""
        result = file_tools_read_lines(long_line_file, line_count=-1, max_chars=50)
        text = result.content[0].text
        assert text.startswith("行号 > 行内容\n\n")
        assert "<<<TRUNCATED>>>" in text
        assert "\n\n<<<TRUNCATED>>>内容已超出 max_chars=50 限制。" in text

    def test_default_max_chars_5000_under(self, tmp_dir):
        """默认 max_chars=5000：4500 字符内容一次性读完不截断。"""
        path = os.path.join(tmp_dir, "under.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(f"row{i:04d} " + "x" * 40 for i in range(1, 91)))
        result = file_tools_read_lines(path, line_count=-1)
        text = result.content[0].text
        assert "如需继续阅读" not in text
        assert "row0090" in text

    def test_default_max_chars_5000_over(self, tmp_dir):
        """默认 max_chars=5000：5500 字符内容触发截断并带新尾部说明。"""
        path = os.path.join(tmp_dir, "over.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(f"row{i:04d} " + "x" * 40 for i in range(1, 111)))
        result = file_tools_read_lines(path, line_count=-1)
        text = result.content[0].text
        assert "\n\n<<<TRUNCATED>>>内容已超出 max_chars=5000 限制。" in text
        assert "如需继续阅读" in text


class TestReadBlock:
    def test_basic(self, multi_line_file):
        result = file_tools_read_block(
            multi_line_file, start_row=2, end_row=4,
            start_col=1, end_col=10,
        )
        assert "2 > line2" in result.content[0].text
        assert "4 > line4" in result.content[0].text

    def test_offset_beyond_line(self, multi_line_file):
        """start_col 超行长度返回空。"""
        result = file_tools_read_block(
            multi_line_file, start_row=1, end_row=2,
            start_col=100, end_col=200,
        )
        lines = result.content[0].text.strip().split("\n")
        # 图例 + 空行 + 两行内容
        assert len(lines) == 4
        assert lines[0] == "行号 > 行内容"
        # 行内容为空，格式为 `行号 >`
        assert "1 >" in lines[2]
        assert "2 >" in lines[3]

    def test_offset_reverse(self, multi_line_file):
        result = file_tools_read_block(
            multi_line_file, start_row=1, end_row=2,
            start_col=5, end_col=2,
        )
        assert "失败" in result.content[0].text

    def test_max_chars(self, multi_line_file):
        result = file_tools_read_block(
            multi_line_file, start_row=1, end_row=20,
            start_col=1, end_col=5000, max_chars=50,
        )
        assert "<<<TRUNCATED>>>" in result.content[0].text
        assert "\n\n<<<TRUNCATED>>>内容已超出" in result.content[0].text

    def test_max_chars_truncated_hint_from_start(self, many_medium_lines_file):
        """从头读，截断后提示行号应等于被截断行号。"""
        result = file_tools_read_block(
            many_medium_lines_file, start_row=1, end_row=30,
            start_col=1, end_col=200, max_chars=60,
        )
        assert "如需继续阅读" in result.content[0].text
        match = re.search(r"从第 (\d+) 行开始读取", result.content[0].text)
        assert match is not None, f"未找到提示行号，结果：{result}"
        next_line = int(match.group(1))
        # 被截断行号应 >= 起始行号，且在文件范围内
        assert 1 <= next_line <= 30, f"提示行号 {next_line} 越界"

    def test_max_chars_truncated_hint_from_middle(self, many_medium_lines_file):
        """从中间读，截断后提示行号应等于被截断行号。"""
        result = file_tools_read_block(
            many_medium_lines_file, start_row=10, end_row=30,
            start_col=1, end_col=200, max_chars=60,
        )
        assert "如需继续阅读" in result.content[0].text
        match = re.search(r"从第 (\d+) 行开始读取", result.content[0].text)
        assert match is not None, f"未找到提示行号，结果：{result}"
        next_line = int(match.group(1))
        # 提示行号应 >= start_row
        assert 10 <= next_line <= 30, f"提示行号 {next_line} 越界"

    def test_legend_header(self, multi_line_file):
        """show_line_number=True 顶部带图例，False 无图例。"""
        r_true = file_tools_read_block(multi_line_file, start_row=2, end_row=3)
        assert r_true.content[0].text.startswith("行号 > 行内容\n\n")
        assert "2 > line2" in r_true.content[0].text
        r_false = file_tools_read_block(multi_line_file, start_row=2, end_row=3, show_line_number=False)
        assert "行号 > 行内容" not in r_false.content[0].text

    def test_default_max_chars_5000_under(self, tmp_dir):
        """默认 max_chars=5000：约 4300 字符窗口一次读完不截断（旧默认 2048 必截断）。"""
        path = os.path.join(tmp_dir, "blk_under.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(f"row{i:04d} " + "x" * 40 for i in range(1, 91)))
        result = file_tools_read_block(path, start_row=1, end_row=90, start_col=1, end_col=200)
        text = result.content[0].text
        assert "如需继续阅读" not in text
        assert "row0090" in text

    def test_default_max_chars_5000_over(self, tmp_dir):
        """默认 max_chars=5000：约 5300 字符窗口触发截断并带新尾部说明。"""
        path = os.path.join(tmp_dir, "blk_over.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(f"row{i:04d} " + "x" * 40 for i in range(1, 111)))
        result = file_tools_read_block(path, start_row=1, end_row=110, start_col=1, end_col=200)
        text = result.content[0].text
        assert "\n\n<<<TRUNCATED>>>内容已超出 max_chars=5000 限制。" in text
        assert "如需继续阅读" in text

    def test_nonexistent(self):
        result = file_tools_read_block("/nonexistent.txt", start_row=1, end_row=5)
        assert "失败" in result.content[0].text

    def test_beyond_file(self, multi_line_file):
        result = file_tools_read_block(multi_line_file, start_row=1, end_row=999)
        assert "20 > line20" in result.content[0].text

    # ── 参数校验 ──────────────────────────────────────────

    def test_start_row_lt_1(self, multi_line_file):
        result = file_tools_read_block(multi_line_file, start_row=0, end_row=5)
        assert "失败" in result.content[0].text

    def test_end_row_lt_1(self, multi_line_file):
        result = file_tools_read_block(multi_line_file, start_row=1, end_row=0)
        assert "失败" in result.content[0].text

    def test_start_row_gt_end_row(self, multi_line_file):
        result = file_tools_read_block(multi_line_file, start_row=10, end_row=5)
        assert "失败" in result.content[0].text

    def test_start_col_lt_1(self, multi_line_file):
        result = file_tools_read_block(
            multi_line_file, start_row=1, end_row=3,
            start_col=0, end_col=10,
        )
        assert "失败" in result.content[0].text

    def test_end_col_lt_1(self, multi_line_file):
        result = file_tools_read_block(
            multi_line_file, start_row=1, end_row=3,
            start_col=1, end_col=0,
        )
        assert "失败" in result.content[0].text

    # ── 边界场景 ──────────────────────────────────────────

    def test_single_char(self, multi_line_file):
        """start_col == end_col 取单个字符（1-based 包含）。"""
        result = file_tools_read_block(
            multi_line_file, start_row=1, end_row=1,
            start_col=4, end_col=4,
        )
        # "line1" 第 4 个字符 = "e"
        assert "1 > e" in result.content[0].text

    def test_empty_file(self, empty_file):
        """空文件应提示文件长度为 0。"""
        result = file_tools_read_block(empty_file, start_row=1, end_row=5)
        assert "失败" in result.content[0].text
        assert "空" in result.content[0].text or "0" in result.content[0].text

    def test_no_truncation_full_output(self, multi_line_file):
        """max_chars 足够大，不截断，无提示。"""
        result = file_tools_read_block(
            multi_line_file, start_row=1, end_row=20,
            start_col=1, end_col=100, max_chars=9999,
        )
        assert "如需继续阅读" not in result.content[0].text
        assert "20 > line20" in result.content[0].text

    # ── show_line_number=False ──────────────────────────────

    def test_show_line_number_false(self, multi_line_file):
        """show_line_number=False 时不显示行号，直接输出原文切片。"""
        result = file_tools_read_block(
            multi_line_file, start_row=2, end_row=4,
            start_col=1, end_col=10, show_line_number=False,
        )
        assert "2 >" not in result.content[0].text
        lines = result.content[0].text.strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "line2"
        assert lines[2] == "line4"

    def test_chinese_file(self, chinese_file):
        """中文文件应正确读取矩形块。"""
        result = file_tools_read_block(chinese_file, start_row=1, end_row=2, show_line_number=True)
        assert "1 > 这是第一行" in result.content[0].text
        assert "2 > 这是第二行" in result.content[0].text


class TestRegex:
    def _text(self, result):
        return result.content[0].text

    def _data_rows(self, result):
        """解析表格：返回 (数据行列表, 页脚行列表)。
        数据行格式 `序号 | 行号,列号 | 组 | 内容`，页脚在空行之后。"""
        text = self._text(result)
        # 跳过表头行
        body = text.split("\n", 1)[1] if "\n" in text else ""
        lines = body.split("\n")
        # 页脚 = 空行之后的所有行
        data, footer = [], []
        seen_blank = False
        for ln in lines:
            if not seen_blank:
                if ln.strip() == "":
                    seen_blank = True
                    continue
                data.append(ln)
            else:
                footer.append(ln)
        return data, footer

    def test_basic(self, multi_line_file):
        """无捕获组：20 个匹配，默认 count=10，不显示组列。"""
        result = file_tools_regex(multi_line_file, pattern=r"line")
        data, footer = self._data_rows(result)
        assert len(data) == 10  # 默认 count=10
        assert data[0] == "1 | 1,1 | line"
        assert data[9] == "10 | 10,1 | line"
        assert "当前展示了 1 → 10 行（共 20 行）" in "\n".join(footer)
        assert "start=11" in "\n".join(footer)

    def test_single_capture(self, multi_line_file):
        """单捕获组：内容为组 1，不显示组列。"""
        result = file_tools_regex(multi_line_file, pattern=r"line(\d+)")
        data, footer = self._data_rows(result)
        assert data[0] == "1 | 1,5 | 1"   # line1 中 '1' 在第 5 列
        assert data[1] == "2 | 2,5 | 2"

    def test_multi_capture(self, multi_line_file):
        """多捕获组：展平为每组一行，显示组列。"""
        result = file_tools_regex(multi_line_file, pattern=r"(line)(\d+)")
        data, footer = self._data_rows(result)
        # 2+ 组显示组列表头
        assert "序号 | 行号,列号 | 组 | 匹配内容" in self._text(result)
        # line1 → 组1 'line' + 组2 '1'
        assert data[0] == "1 | 1,1 | 1 | line"
        assert data[1] == "2 | 1,5 | 2 | 1"
        # line2 → 组1 'line' + 组2 '2'
        assert data[2] == "3 | 2,1 | 1 | line"
        assert data[3] == "4 | 2,5 | 2 | 2"

    def test_no_match(self, multi_line_file):
        result = file_tools_regex(multi_line_file, pattern=r"ZZZZ_NOT_FOUND")
        assert self._text(result) == "共 0 个匹配。"

    def test_nonexistent_file(self):
        result = file_tools_regex("/nonexistent.txt", pattern=r"test")
        assert "失败" in self._text(result)

    def test_invalid_regex(self, multi_line_file):
        result = file_tools_regex(multi_line_file, pattern=r"[invalid")
        assert "失败" in self._text(result)
        assert "语法错误" in self._text(result)

    def test_pagination(self, multi_line_file):
        """start 和 count 控制返回行数。"""
        result = file_tools_regex(multi_line_file, pattern=r"line", start=2, count=3)
        data, footer = self._data_rows(result)
        assert len(data) == 3
        assert data[0] == "2 | 2,1 | line"
        assert data[2] == "4 | 4,1 | line"
        assert "当前展示了 2 → 4 行（共 20 行）" in "\n".join(footer)
        assert "start=5" in "\n".join(footer)

    def test_count_all(self, multi_line_file):
        """count=-1 返回全部行。"""
        result = file_tools_regex(multi_line_file, pattern=r"line", count=-1)
        data, footer = self._data_rows(result)
        assert len(data) == 20
        assert "已全部展示" in "\n".join(footer)

    def test_start_end_line(self, multi_line_file):
        """行范围过滤：只搜 15~18 行。"""
        result = file_tools_regex(
            multi_line_file, pattern=r"line",
            start_line=15, end_line=18,
        )
        data, footer = self._data_rows(result)
        assert len(data) == 4
        assert data[0] == "1 | 15,1 | line"
        assert data[3] == "4 | 18,1 | line"
        assert "已全部展示" in "\n".join(footer)

    def test_chinese_regex(self, chinese_file):
        result = file_tools_regex(chinese_file, pattern=r"第")
        data, footer = self._data_rows(result)
        assert len(data) >= 1
        assert "第" in data[0]

    def test_empty_file(self, empty_file):
        result = file_tools_regex(empty_file, pattern=r"test")
        assert self._text(result) == "共 0 个匹配。"

    def test_start_lt_1(self, multi_line_file):
        """start<1 应报错"""
        result = file_tools_regex(multi_line_file, pattern=r"line", start=0)
        assert "失败" in self._text(result)
        assert "start" in self._text(result)

    def test_start_gt_total_rows(self, multi_line_file):
        """start 超出总行数应报错。"""
        result = file_tools_regex(multi_line_file, pattern=r"line", start=99)
        assert "失败" in self._text(result)
        assert "超出总行数" in self._text(result)

    def test_cross_line_multi_capture(self, cross_line_regex_file):
        """跨行匹配+多捕获组：各组独立行号。"""
        result = file_tools_regex(cross_line_regex_file, pattern=r"def (\w+)\(.*?\):\s+return (.+)")
        data, footer = self._data_rows(result)
        # 匹配1: def foo(x):\n    return x + 1  → 组1 'foo'(1,5) 组2 'x + 1'(2,12)
        assert data[0] == "1 | 1,5 | 1 | foo"
        assert data[1] == "2 | 2,12 | 2 | x + 1"
        # 匹配2: def bar():\n    return 42  → 组1 'bar'(4,5) 组2 '42'(5,12)
        assert data[2] == "3 | 4,5 | 1 | bar"
        assert data[3] == "4 | 5,12 | 2 | 42"

    def test_cross_line_no_capture(self, cross_line_regex_file):
        """跨行匹配+无捕获组：内容含 \\n 转义。"""
        # \s+return 使匹配跨越 def 行与 return 行
        result = file_tools_regex(cross_line_regex_file, pattern=r"def \w+\(.*?\):\s+return")
        data, footer = self._data_rows(result)
        assert len(data) == 2
        # 组0 整匹配跨两行，写成一行含 \n 转义（0 组不显示组列）
        assert data[0].startswith("1 | 1,1 | ")
        assert "\\n" in data[0]
        assert "def foo" in data[0]

    # ── 转义 ──────────────────────────────────────────────

    def test_escape_pipe(self, tmp_dir):
        """内容含 | 应转义为 \\|，不破坏表格。"""
        path = os.path.join(tmp_dir, "pipe.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("a|b\nc|d\n")
        result = file_tools_regex(path, pattern=r"\w\|\w")
        data, footer = self._data_rows(result)
        assert data[0] == "1 | 1,1 | a\\|b"
        assert data[1] == "2 | 2,1 | c\\|d"

    def test_escape_backslash(self, tmp_dir):
        """内容含反斜杠应转义为 \\\\（文件存 1 个反斜杠 → 显示 2 个）。"""
        path = os.path.join(tmp_dir, "bs.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("C:\\dir\\file\n")  # 文件内容含单个反斜杠
        result = file_tools_regex(path, pattern=r"C:\\dir")  # 匹配 C:\dir
        data, footer = self._data_rows(result)
        assert len(data) == 1
        assert data[0] == "1 | 1,1 | C:\\\\dir"

    def test_escape_tab(self, tmp_dir):
        """内容含制表符应转义为 \\t。"""
        path = os.path.join(tmp_dir, "tab.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("a\tb\n")
        result = file_tools_regex(path, pattern=r"a\tb")
        data, footer = self._data_rows(result)
        assert data[0] == "1 | 1,1 | a\\tb"

    # ── 截断 ──────────────────────────────────────────────

    def test_row_truncated(self, long_matched_file):
        """单行内容超 260 字符应截断并带标记。"""
        result = file_tools_regex(long_matched_file, pattern=r"x{300}")
        data, footer = self._data_rows(result)
        assert data[0].endswith("<<<TRUNCATED>>>")
        # 截断后内容部分 = 260 个 x（0 组无组列，内容在第 3 列）
        cell = data[0].split(" | ", 2)[2]
        assert cell == "x" * 260 + "<<<TRUNCATED>>>"
        assert "部分行因超过每行 260 字符上限被截断" in "\n".join(footer)

    def test_row_no_truncation(self, multi_line_file):
        """内容不超 260 字符不应有截断标记。"""
        result = file_tools_regex(multi_line_file, pattern=r"line")
        data, footer = self._data_rows(result)
        assert "<<<TRUNCATED>>>" not in "\n".join(data)
        assert "每行 260" not in "\n".join(footer)

    def test_max_chars_truncated(self, multi_line_file):
        """总字符超 max_chars 应整行停止并提示用 start 继续。"""
        # 20 个匹配，每行约 20 字符，max_chars=60 应只展示前几行后停止
        result = file_tools_regex(multi_line_file, pattern=r"line", count=-1, max_chars=60)
        data, footer = self._data_rows(result)
        # 整行停：不输出半行，footer 提示超限
        assert len(data) < 20
        assert "总字符超限 60" in "\n".join(footer)
        assert "start=" in "\n".join(footer)

    def test_max_chars_all_fit(self, multi_line_file):
        """max_chars 足够大时全部展示无截断。"""
        result = file_tools_regex(multi_line_file, pattern=r"line", count=-1, max_chars=10000)
        data, footer = self._data_rows(result)
        assert len(data) == 20
        assert "已全部展示" in "\n".join(footer)
        assert "<<<TRUNCATED>>>" not in "\n".join(data)

    # ── 边缘情况 ──────────────────────────────────────────

    def test_count_zero(self, multi_line_file):
        """count=0 应报错"""
        result = file_tools_regex(multi_line_file, pattern=r"line", count=0)
        assert "失败" in self._text(result)
        assert "count" in self._text(result).lower()

    def test_count_negative_invalid(self, multi_line_file):
        """count<-1 应报错"""
        result = file_tools_regex(multi_line_file, pattern=r"line", count=-5)
        assert "失败" in self._text(result)
        assert "count" in self._text(result).lower()

    def test_start_line_lt_1(self, multi_line_file):
        """start_line<1 应报错"""
        result = file_tools_regex(multi_line_file, pattern=r"line", start_line=0)
        assert "失败" in self._text(result)

    def test_start_line_gt_total(self, multi_line_file):
        """start_line>总行数 应报错"""
        result = file_tools_regex(multi_line_file, pattern=r"line", start_line=100)
        assert "失败" in self._text(result)
        assert "超出" in self._text(result)
        assert "20" in self._text(result)  # 提示总行数

    def test_end_line_lt_1(self, multi_line_file):
        """end_line<1 应报错"""
        result = file_tools_regex(multi_line_file, pattern=r"line", end_line=0)
        assert "失败" in self._text(result)

    def test_end_line_lt_start_line(self, multi_line_file):
        """end_line<start_line 应报错"""
        result = file_tools_regex(multi_line_file, pattern=r"line", start_line=10, end_line=5)
        assert "失败" in self._text(result)
        assert "矛盾" in self._text(result)

    def test_empty_pattern(self, multi_line_file):
        """空pattern 应报错"""
        result = file_tools_regex(multi_line_file, pattern="")
        assert "失败" in self._text(result)
        assert "pattern" in self._text(result).lower()

    def test_gbk_file(self, gbk_file):
        """GBK编码文件的正则搜索。"""
        result = file_tools_regex(gbk_file, pattern="你好")
        data, footer = self._data_rows(result)
        assert len(data) >= 1
        assert "你好" in data[0]

    def test_crlf_file(self, crlf_file):
        """CRLF行尾文件的正则搜索。"""
        result = file_tools_regex(crlf_file, pattern="line")
        data, footer = self._data_rows(result)
        assert len(data) == 3

    def test_special_chars(self, tmp_dir):
        """正则特殊字符（如 . * + ? 等）应正确匹配。"""
        path = os.path.join(tmp_dir, "special.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("hello.world\nfoo*bar\nbaz+qux\n")
        result = file_tools_regex(path, pattern=r"hello\.world")
        data, footer = self._data_rows(result)
        assert len(data) == 1
        result2 = file_tools_regex(path, pattern=r"foo\*bar")
        data2, footer2 = self._data_rows(result2)
        assert len(data2) == 1

    def test_zero_width_match(self, tmp_dir):
        """零宽匹配（空串）应显式显示为 \"\"（双引号）。"""
        path = os.path.join(tmp_dir, "zw.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("abc")
        # a* 匹配: 位置0='a', 位置1/2/3=''（空串）→ 4 个匹配
        result = file_tools_regex(path, pattern=r"a*", count=-1)
        data, footer = self._data_rows(result)
        assert len(data) == 4
        assert data[0].endswith("| a")
        # 空串匹配内容显式显示为 ""
        assert data[1].endswith('| ""')
        assert data[3].endswith('| ""')

    def test_group_not_matched(self, tmp_dir):
        """未参与匹配的组（如 (a)|(b) 中未命中侧）应显示 None。"""
        path = os.path.join(tmp_dir, "gm.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("b\n")  # 含 b 不含 a
        # (a)|(b) 只有 b 命中，组1 未命中 → None
        result = file_tools_regex(path, pattern=r"(a)|(b)", count=-1)
        data, footer = self._data_rows(result)
        # 匹配1: 组1(a)未命中=None, 组2(b)命中='b'
        assert data[0] == "1 | - | 1 | None"
        assert data[1] == "2 | 1,1 | 2 | b"

class TestStrLineParams:
    """行号/数字参数兼容字符串输入。"""

    def test_read_lines_string_ok(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line="2", line_count="3")
        assert "2 > line2" in result.content[0].text
        assert "4 > line4" in result.content[0].text

    def test_read_lines_illegal_string(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line="abc")
        assert "失败" in result.content[0].text
        assert "start_line 参数应当输入整数" in result.content[0].text

    def test_read_block_string_ok(self, multi_line_file):
        result = file_tools_read_block(multi_line_file, "1", "3", start_col="1", end_col="10")
        assert "line1" in result.content[0].text
        assert "line3" in result.content[0].text

    def test_read_block_illegal_string(self, multi_line_file):
        result = file_tools_read_block(multi_line_file, "1.5", "3")
        assert "失败" in result.content[0].text
        assert "start_row 参数应当输入整数" in result.content[0].text

    def test_regex_string_params_ok(self, multi_line_file):
        result = file_tools_regex(multi_line_file, r"line(\d+)", start_line="1", count="5")
        text = result.content[0].text
        # 字符串参数正常解析，返回表格格式（1 组不显示组列）
        assert "序号 | 行号,列号 | 匹配内容" in text
        assert "1 | 1,5 | 1" in text

    def test_regex_illegal_count(self, multi_line_file):
        result = file_tools_regex(multi_line_file, r"line", count="abc")
        assert "失败" in result.content[0].text
        assert "count 参数应当输入整数" in result.content[0].text

    # ── MULTILINE：^/$ 按行匹配，跨行 \n 不受影响 ──────────────────

    def test_regex_multiline_anchor_middle_line(self, multi_line_file):
        """^/$ 按行匹配：匹配中间行（multi_line_file 第 2 行 line2）。"""
        result = file_tools_regex(multi_line_file, r"^line2$")
        text = result.content[0].text
        assert "1 | 2,1 | line2" in text          # 第 2 行整行匹配
        assert "共 1 行" in text                   # 只 1 处（不是 0 也不是全匹配）

    def test_regex_multiline_dollar_all_lines(self, multi_line_file):
        """$ 匹配每行行尾：line\\d+$ 匹配所有 lineN 行（20 行）。"""
        result = file_tools_regex(multi_line_file, r"line\d+$", count=-1)
        text = result.content[0].text
        assert "共 20 行" in text                  # 20 行各匹配一次

    def test_regex_multiline_cross_line_unaffected(self, cross_line_regex_file):
        """跨行匹配（pattern 内 \\n）不受 MULTILINE 影响。"""
        # fixture: "def foo(x):\n    return x + 1\n\ndef bar():\n    return 42\n"
        result = file_tools_regex(cross_line_regex_file, r"return 42$")
        text = result.content[0].text
        assert "return 42" in text                 # $ 按行匹配行尾，跨行能力不受影响
