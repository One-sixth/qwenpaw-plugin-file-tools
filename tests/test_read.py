"""测试文本读取类工具。"""

import csv
import io
import json
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
        assert "line1" in result
        assert "line5" in result
        # 纯文本格式，行号 > 内容
        assert "1 > line1" in result
        assert "5 > line5" in result

    def test_from_middle(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line=10, line_count=3)
        assert "line10" in result
        assert "line12" in result
        assert "line9" not in result

    def test_to_end(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line=18, line_count=-1)
        assert "line18" in result
        assert "line20" in result

    def test_line_count_zero(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line=1, line_count=0)
        assert "失败" in result

    def test_beyond_file(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line=100, line_count=5)
        assert "失败" in result or "超出" in result

    def test_nonexistent_file(self):
        result = file_tools_read_lines("/nonexistent_xyz.txt")
        assert "失败" in result

    def test_padded_line_numbers(self, multi_line_file):
        """行号右对齐固定宽度。"""
        result = file_tools_read_lines(multi_line_file, start_line=9, line_count=3)
        lines = result.strip().split("\n")
        assert len(lines) >= 1
        # 第一行格式：` 9 > line9`（行号右对齐，2位宽度）
        assert "9 > line9" in lines[0]

    def test_empty_file(self, empty_file):
        """空文件返回空字符串。"""
        result = file_tools_read_lines(empty_file, line_count=5)
        result = result.strip()
        assert result == ""

    def test_max_chars(self, long_line_file):
        result = file_tools_read_lines(long_line_file, line_count=-1, max_chars=50)
        assert "<<truncated>>" in result

    def test_chinese(self, chinese_file):
        result = file_tools_read_lines(chinese_file, line_count=3)
        assert "第一行" in result

    def test_max_chars_truncated_from_start(self, many_medium_lines_file):
        """从头读，截断发生在中间行，提示行号应等于被截断行号。"""
        result = file_tools_read_lines(many_medium_lines_file, start_line=1, line_count=-1, max_chars=200)
        assert "如需继续阅读" in result
        match = re.search(r"从第 (\d+) 行开始读取", result)
        assert match is not None, f"未找到提示行号，结果：{result}"
        next_line = int(match.group(1))
        # 被截断行号应 >= 起始行号，且 <= 文件总行数
        assert 1 <= next_line <= 30, f"提示行号 {next_line} 越界"
        assert next_line >= 5, f"提示行号 {next_line} 应 >= 5（至少读到第5行才可能截断）"

    def test_max_chars_truncated_from_middle(self, many_medium_lines_file):
        """从中间读，截断发生在中间行，提示行号应等于被截断行号。"""
        result = file_tools_read_lines(many_medium_lines_file, start_line=10, line_count=-1, max_chars=150)
        assert "如需继续阅读" in result
        match = re.search(r"从第 (\d+) 行开始读取", result)
        assert match is not None, f"未找到提示行号，结果：{result}"
        next_line = int(match.group(1))
        # 提示行号应 >= start_line 且 <= 文件总行数
        assert 10 <= next_line <= 30, f"提示行号 {next_line} 越界"
        assert next_line >= 12, f"提示行号 {next_line} 应 >= 12（至少读到第12行才可能截断）"

    def test_max_chars_no_truncation(self, multi_line_file):
        """max_chars 足够大，不截断，不应有提示。"""
        result = file_tools_read_lines(multi_line_file, start_line=1, line_count=-1, max_chars=9999)
        assert "如需继续阅读" not in result
        assert "line20" in result

    # ── show_line_number=False ──────────────────────────────

    def test_show_line_number_false(self, multi_line_file):
        """show_line_number=False 时不显示行号，直接输出原文。"""
        result = file_tools_read_lines(multi_line_file, start_line=1, line_count=3, show_line_number=False)
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result
        # 不应出现行号格式
        assert " 1 >" not in result
        lines = result.strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "line1"
        assert lines[1] == "line2"

    def test_show_line_number_false_empty_file(self, empty_file):
        """show_line_number=False 时空文件返回空字符串。"""
        result = file_tools_read_lines(empty_file, line_count=5, show_line_number=False)
        assert result.strip() == ""

    def test_show_line_number_false_to_end(self, multi_line_file):
        """show_line_number=False 时读取到末尾。"""
        result = file_tools_read_lines(multi_line_file, start_line=18, line_count=-1, show_line_number=False)
        lines = result.strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "line18"
        assert lines[-1] == "line20"

    def test_show_line_number_false_truncated(self, long_line_file):
        """show_line_number=False 时截断提示仍保留。"""
        result = file_tools_read_lines(long_line_file, line_count=-1, max_chars=50, show_line_number=False)
        assert "<<truncated>>" in result
        assert "如需继续阅读" in result

    def test_only_newlines_file(self, tmp_dir):
        """仅换行符文件应正确读取。"""
        path = os.path.join(tmp_dir, "newlines.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n\n\n")
        result = file_tools_read_lines(path, line_count=-1, show_line_number=False)
        assert result.count("\n") == 3  # 3 个换行符 = 4 行（含末尾空行）

    def test_no_trailing_newline(self, tmp_dir):
        """末尾无换行符文件应正确读取。"""
        path = os.path.join(tmp_dir, "no_eol.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("line1\nline2")
        result = file_tools_read_lines(path, line_count=-1, show_line_number=True)
        assert "1 > line1" in result
        assert "2 > line2" in result


class TestReadBlock:
    def test_basic(self, multi_line_file):
        result = file_tools_read_block(
            multi_line_file, start_row=2, end_row=4,
            start_col=1, end_col=10,
        )
        assert "2 > line2" in result
        assert "4 > line4" in result

    def test_offset_beyond_line(self, multi_line_file):
        """start_col 超行长度返回空。"""
        result = file_tools_read_block(
            multi_line_file, start_row=1, end_row=2,
            start_col=100, end_col=200,
        )
        lines = result.strip().split("\n")
        assert len(lines) == 2
        # 行内容为空，格式为 `行号 >`
        assert "1 >" in lines[0]
        assert "2 >" in lines[1]

    def test_offset_reverse(self, multi_line_file):
        result = file_tools_read_block(
            multi_line_file, start_row=1, end_row=2,
            start_col=5, end_col=2,
        )
        assert "失败" in result

    def test_max_chars(self, multi_line_file):
        result = file_tools_read_block(
            multi_line_file, start_row=1, end_row=20,
            start_col=1, end_col=5000, max_chars=50,
        )
        assert "<<truncated>>" in result or len(result) < 200

    def test_max_chars_truncated_hint_from_start(self, many_medium_lines_file):
        """从头读，截断后提示行号应等于被截断行号。"""
        result = file_tools_read_block(
            many_medium_lines_file, start_row=1, end_row=30,
            start_col=1, end_col=200, max_chars=60,
        )
        assert "如需继续阅读" in result
        match = re.search(r"从第 (\d+) 行开始读取", result)
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
        assert "如需继续阅读" in result
        match = re.search(r"从第 (\d+) 行开始读取", result)
        assert match is not None, f"未找到提示行号，结果：{result}"
        next_line = int(match.group(1))
        # 提示行号应 >= start_row
        assert 10 <= next_line <= 30, f"提示行号 {next_line} 越界"

    def test_nonexistent(self):
        result = file_tools_read_block("/nonexistent.txt", start_row=1, end_row=5)
        assert "失败" in result

    def test_beyond_file(self, multi_line_file):
        result = file_tools_read_block(multi_line_file, start_row=1, end_row=999)
        assert "20 > line20" in result

    # ── 参数校验 ──────────────────────────────────────────

    def test_start_row_lt_1(self, multi_line_file):
        result = file_tools_read_block(multi_line_file, start_row=0, end_row=5)
        assert "失败" in result

    def test_end_row_lt_1(self, multi_line_file):
        result = file_tools_read_block(multi_line_file, start_row=1, end_row=0)
        assert "失败" in result

    def test_start_row_gt_end_row(self, multi_line_file):
        result = file_tools_read_block(multi_line_file, start_row=10, end_row=5)
        assert "失败" in result

    def test_start_col_lt_1(self, multi_line_file):
        result = file_tools_read_block(
            multi_line_file, start_row=1, end_row=3,
            start_col=0, end_col=10,
        )
        assert "失败" in result

    def test_end_col_lt_1(self, multi_line_file):
        result = file_tools_read_block(
            multi_line_file, start_row=1, end_row=3,
            start_col=1, end_col=0,
        )
        assert "失败" in result

    # ── 边界场景 ──────────────────────────────────────────

    def test_single_char(self, multi_line_file):
        """start_col == end_col 取单个字符（1-based 包含）。"""
        result = file_tools_read_block(
            multi_line_file, start_row=1, end_row=1,
            start_col=4, end_col=4,
        )
        # "line1" 第 4 个字符 = "e"
        assert "1 > e" in result

    def test_empty_file(self, empty_file):
        """空文件应提示文件长度为 0。"""
        result = file_tools_read_block(empty_file, start_row=1, end_row=5)
        assert "失败" in result
        assert "空" in result or "0" in result

    def test_no_truncation_full_output(self, multi_line_file):
        """max_chars 足够大，不截断，无提示。"""
        result = file_tools_read_block(
            multi_line_file, start_row=1, end_row=20,
            start_col=1, end_col=100, max_chars=9999,
        )
        assert "如需继续阅读" not in result
        assert "20 > line20" in result

    # ── show_line_number=False ──────────────────────────────

    def test_show_line_number_false(self, multi_line_file):
        """show_line_number=False 时不显示行号，直接输出原文切片。"""
        result = file_tools_read_block(
            multi_line_file, start_row=2, end_row=4,
            start_col=1, end_col=10, show_line_number=False,
        )
        assert "2 >" not in result
        lines = result.strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "line2"
        assert lines[2] == "line4"

    def test_chinese_file(self, chinese_file):
        """中文文件应正确读取矩形块。"""
        result = file_tools_read_block(chinese_file, start_row=1, end_row=2, show_line_number=True)
        assert "1 > 这是第一行" in result
        assert "2 > 这是第二行" in result


class TestRegex:
    def _parse(self, result):
        """解析 JSON 返回结果。错误消息直接返回。"""
        if result.startswith("{"):
            return json.loads(result)
        return result

    def test_basic(self, multi_line_file):
        result = self._parse(file_tools_regex(multi_line_file, pattern=r"line"))
        assert isinstance(result, dict)
        assert result["total_matches"] == 20
        assert len(result["matches"]) == 10  # 默认 count=10
        assert result["matches"][0]["lines"] == "1"
        assert result["matches"][0]["matched"] == "line"

    def test_single_capture(self, multi_line_file):
        result = self._parse(file_tools_regex(multi_line_file, pattern=r"line(\d+)"))
        assert isinstance(result, dict)
        assert result["total_matches"] == 20
        # 单捕获组 → str
        assert result["matches"][0]["matched"] == "1"
        assert result["matches"][1]["matched"] == "2"

    def test_multi_capture(self, multi_line_file):
        result = self._parse(file_tools_regex(multi_line_file, pattern=r"(line)(\d+)"))
        assert isinstance(result, dict)
        # 多捕获组 → list
        assert result["matches"][0]["matched"] == ["line", "1"]

    def test_no_match(self, multi_line_file):
        result = file_tools_regex(multi_line_file, pattern=r"ZZZZ_NOT_FOUND")
        data = self._parse(result)
        assert isinstance(data, dict)
        assert data["total_matches"] == 0
        assert data["matches"] == []

    def test_nonexistent_file(self):
        result = file_tools_regex("/nonexistent.txt", pattern=r"test")
        assert "失败" in result

    def test_invalid_regex(self, multi_line_file):
        result = file_tools_regex(multi_line_file, pattern=r"[invalid")
        assert "失败" in result

    def test_pagination(self, multi_line_file):
        """start 和 count 控制返回范围。"""
        result = self._parse(file_tools_regex(multi_line_file, pattern=r"line", start=2, count=3))
        assert isinstance(result, dict)
        assert result["total_matches"] == 20
        assert len(result["matches"]) == 3
        assert result["matches"][0]["match"] == 2
        assert result["matches"][2]["match"] == 4

    def test_count_all(self, multi_line_file):
        """count=-1 返回全部匹配。"""
        result = self._parse(file_tools_regex(multi_line_file, pattern=r"line", count=-1))
        assert isinstance(result, dict)
        assert len(result["matches"]) == 20  # 全部

    def test_start_end_line(self, multi_line_file):
        result = self._parse(file_tools_regex(
            multi_line_file, pattern=r"line",
            start_line=15, end_line=18,
        ))
        assert isinstance(result, dict)
        assert result["total_matches"] == 4  # line15~line18
        assert result["matches"][0]["lines"] == "15"

    def test_chinese_regex(self, chinese_file):
        result = self._parse(file_tools_regex(chinese_file, pattern=r"第"))
        assert isinstance(result, dict)
        assert result["total_matches"] >= 1

    def test_empty_file(self, empty_file):
        result = self._parse(file_tools_regex(empty_file, pattern=r"test"))
        assert isinstance(result, dict)
        assert result["total_matches"] == 0

    def test_start_lt_1(self, multi_line_file):
        """start<1 应报错"""
        result = file_tools_regex(multi_line_file, pattern=r"line", start=0)
        assert "失败" in result
        assert "start" in result

    def test_cross_line_multi_capture(self, cross_line_regex_file):
        """跨行匹配+多捕获组"""
        result = self._parse(file_tools_regex(cross_line_regex_file, pattern=r"def (\w+)\(.*?\):\s+return (.+)"))
        assert isinstance(result, dict)
        assert result["total_matches"] == 2
        m1 = result["matches"][0]
        assert m1["lines"] == "1~2"
        assert m1["matched"] == ["foo", "x + 1"]
        m2 = result["matches"][1]
        assert m2["lines"] == "4~5"
        assert m2["matched"] == ["bar", "42"]

    def test_cross_line_no_capture(self, cross_line_regex_file):
        """跨行匹配+无捕获组"""
        result = self._parse(file_tools_regex(cross_line_regex_file, pattern=r"def \w+\(.*?\):"))
        assert isinstance(result, dict)
        assert result["total_matches"] == 2
        assert result["matches"][0]["lines"] == "1"  # 单行匹配
        assert "def foo" in result["matches"][0]["matched"]

    # ── 边缘情况 ──────────────────────────────────────────

    def test_count_zero(self, multi_line_file):
        """count=0 应报错"""
        result = file_tools_regex(multi_line_file, pattern=r"line", count=0)
        assert "失败" in result
        assert "count" in result.lower()

    def test_count_negative_invalid(self, multi_line_file):
        """count<-1 应报错"""
        result = file_tools_regex(multi_line_file, pattern=r"line", count=-5)
        assert "失败" in result
        assert "count" in result.lower()

    def test_start_line_lt_1(self, multi_line_file):
        """start_line<1 应报错"""
        result = file_tools_regex(multi_line_file, pattern=r"line", start_line=0)
        assert "失败" in result

    def test_start_line_gt_total(self, multi_line_file):
        """start_line>总行数 应报错"""
        result = file_tools_regex(multi_line_file, pattern=r"line", start_line=100)
        assert "失败" in result
        assert "超出" in result
        assert "20" in result  # 提示总行数

    def test_end_line_lt_1(self, multi_line_file):
        """end_line<1 应报错"""
        result = file_tools_regex(multi_line_file, pattern=r"line", end_line=0)
        assert "失败" in result

    def test_end_line_lt_start_line(self, multi_line_file):
        """end_line<start_line 应报错"""
        result = file_tools_regex(multi_line_file, pattern=r"line", start_line=10, end_line=5)
        assert "失败" in result
        assert "矛盾" in result

    def test_empty_pattern(self, multi_line_file):
        """空pattern 应报错"""
        result = file_tools_regex(multi_line_file, pattern="")
        assert "失败" in result
        assert "pattern" in result.lower()

    def test_gbk_file(self, gbk_file):
        """GBK编码文件的正则搜索。"""
        result = self._parse(file_tools_regex(gbk_file, pattern="你好"))
        assert isinstance(result, dict)
        assert result["total_matches"] >= 1

    def test_crlf_file(self, crlf_file):
        """CRLF行尾文件的正则搜索。"""
        result = self._parse(file_tools_regex(crlf_file, pattern="line"))
        assert isinstance(result, dict)
        assert result["total_matches"] == 3

    def test_matched_truncated(self, long_matched_file):
        """matched 超 250 字符应截断并带 note。"""
        result = self._parse(file_tools_regex(long_matched_file, pattern=r"x{300}"))
        assert isinstance(result, dict)
        assert "note" in result
        assert "<<truncated>>" in str(result["matches"][0]["matched"])

    def test_matched_no_truncation(self, multi_line_file):
        """matched 不超过 250 字符不应有 note。"""
        result = self._parse(file_tools_regex(multi_line_file, pattern=r"line"))
        assert isinstance(result, dict)
        assert "note" not in result

    def test_special_chars(self, tmp_dir):
        """正则特殊字符（如 . * + ? 等）应正确匹配。"""
        path = os.path.join(tmp_dir, "special.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("hello.world\nfoo*bar\nbaz+qux\n")
        result = self._parse(file_tools_regex(path, pattern=r"hello\.world"))
        assert result["total_matches"] == 1
        result2 = self._parse(file_tools_regex(path, pattern=r"foo\*bar"))
        assert result2["total_matches"] == 1
