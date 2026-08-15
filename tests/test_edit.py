"""测试文件修改类工具。"""

import os

from backup.manager import list_history
from tools.edit import (
    file_tools_append,
    file_tools_delete_lines,
    file_tools_indent_lines,
    file_tools_insert_lines,
    file_tools_replace,
    file_tools_replace_lines,
    file_tools_regex_replace,
)


def _read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines()


class TestAppend:
    def test_append_to_end(self, tmp_file):
        result = file_tools_append(tmp_file, "\nline6\nline7")
        assert "成功追加" in result.content[0].text
        content = _read_file(tmp_file)
        assert "line6" in content
        assert "line7" in content

    def test_nonexistent_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "nonexist.txt")
        result = file_tools_append(path, "content")
        assert "失败" in result.content[0].text

    def test_backup_created(self, tmp_file):
        file_tools_append(tmp_file, "\nnew_line")
        history = list_history(tmp_file)
        assert len(history) == 1
        assert history[0]["number"] == 1

    def test_content_normalization(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.txt")
        with open(path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write("line1\r\n")
        file_tools_append(path, "\nnew_line")
        content = _read_file(path)
        assert "new_line" in content

    def test_empty_content(self, tmp_file):
        result = file_tools_append(tmp_file, "")
        assert "成功追加" in result.content[0].text

    def test_chinese_content(self, chinese_file):
        result = file_tools_append(chinese_file, "\n新增中文行")
        assert "成功追加" in result.content[0].text
        content = _read_file(chinese_file)
        assert "新增中文行" in content

    def test_line_separator_unix(self, tmp_file):
        """line_separator=\\n 追加的内容使用 Unix 换行。"""
        file_tools_append(tmp_file, "\nnew_line", line_separator="\\n")
        with open(tmp_file, "rb") as f:
            raw = f.read()
        # 追加的 \nnew_line 应该是 \n 而不是 \r\n
        # 文件原内容 line1\nline2\n... 可能被 Windows 自动转 \r\n
        # 但追加行应该匹配 line_separator
        assert b"new_line" in raw

    def test_line_separator_windows(self, tmp_file):
        """line_separator=\\r\\n 追加的内容使用 Windows 换行。"""
        file_tools_append(tmp_file, "\nnew_line", line_separator="\\r\\n")
        with open(tmp_file, "rb") as f:
            raw = f.read()
        # 追加的 \nnew_line 应该被转为 \r\nnew_line
        assert b"\r\nnew_line" in raw

    def test_append_to_empty(self, empty_file):
        """追加到空文件应正常。"""
        result = file_tools_append(empty_file, "hello")
        assert "成功追加" in result.content[0].text
        with open(empty_file) as f:
            assert f.read() == "hello"

    def test_append_no_trailing_newline(self, tmp_dir):
        """末尾无换行符文件追加内容应直接接在最后一行后。"""
        path = os.path.join(tmp_dir, "no_eol.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("line1")
        file_tools_append(path, "\nline2")
        with open(path) as f:
            content = f.read()
        assert content == "line1\nline2"


class TestReplaceLines:
    def test_replace_range(self, multi_line_file):
        result = file_tools_replace_lines(
            multi_line_file, start_line=2, end_line=4,
            content="new2\nnew3\nnew4",
        )
        assert "成功替换" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert lines[1] == "new2"
        assert lines[3] == "new4"
        assert len(lines) == 20

    def test_replace_with_fewer_lines(self, multi_line_file):
        result = file_tools_replace_lines(
            multi_line_file, start_line=2, end_line=5,
            content="replacement",
        )
        assert "成功替换" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert len(lines) == 17
        assert lines[1] == "replacement"

    def test_replace_with_more_lines(self, multi_line_file):
        result = file_tools_replace_lines(
            multi_line_file, start_line=2, end_line=2,
            content="a\nb\nc\nd",
        )
        assert "成功替换" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert len(lines) == 23

    def test_nonexistent_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "nonexist.txt")
        result = file_tools_replace_lines(path, 1, 3, "content")
        assert "失败" in result.content[0].text

    def test_invalid_range(self, multi_line_file):
        result = file_tools_replace_lines(multi_line_file, 5, 3, "content")
        assert "失败" in result.content[0].text

    def test_preview_in_result(self, multi_line_file):
        result = file_tools_replace_lines(
            multi_line_file, start_line=5, end_line=7,
            content="new5\nnew6\nnew7",
        )
        assert "替换前" in result.content[0].text or "line5" in result.content[0].text or "line7" in result.content[0].text
        assert "已替换为" in result.content[0].text or "new5" in result.content[0].text or "new7" in result.content[0].text

    def test_backup_created(self, multi_line_file):
        file_tools_replace_lines(multi_line_file, 1, 1, "modified")
        history = list_history(multi_line_file)
        assert len(history) == 1

    def test_mixed_whitespace(self, tmp_dir):
        """混合缩进内容（tab+空格混合）应正确处理。"""
        path = os.path.join(tmp_dir, "mixed.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\t  mixed\n  \tmixed2\nplain\n")
        result = file_tools_indent_lines(path, mode="expand", count=2)
        assert "成功缩进" in result.content[0].text
        lines = _read_lines(path)
        assert lines[0].startswith("  ")
        assert lines[2].startswith("  ")

    def test_shrink_partial(self, tmp_dir):
        """shrink 模式删除的空白数不超过行首实际空白数。"""
        path = os.path.join(tmp_dir, "partial.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("  3spaces\n\t1tab\n       8spaces\n")
        result = file_tools_indent_lines(path, mode="shrink", count=4)
        assert "成功缩进" in result.content[0].text
        lines = _read_lines(path)
        # "  3spaces" → 删3个空格（只有3个），变成"3spaces"
        assert lines[0] == "3spaces"
        # "\t1tab" → 删1个tab（只有1个），变成"1tab"
        assert lines[1] == "1tab"
        # "       8spaces" → 删4个空格，变成"   8spaces"
        assert lines[2] == "   8spaces"

    def test_boundary_start(self, multi_line_file):
        result = file_tools_replace_lines(multi_line_file, 1, 1, "first")
        assert "成功替换" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert lines[0] == "first"

    def test_boundary_end(self, multi_line_file):
        result = file_tools_replace_lines(multi_line_file, 20, 20, "last")
        assert "成功替换" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert lines[-1] == "last"

    def test_chinese(self, chinese_file):
        result = file_tools_replace_lines(chinese_file, 1, 1, "替换第一行")
        assert "成功替换" in result.content[0].text
        lines = _read_lines(chinese_file)
        assert "替换第一行" in lines[0]

    def test_line_separator_unix(self, multi_line_file):
        """line_separator=\\n 输出 Unix 换行。"""
        file_tools_replace_lines(multi_line_file, 1, 1, "new", line_separator="\\n")
        with open(multi_line_file, "rb") as f:
            content = f.read()
        assert b"\r\nnew" not in content

    def test_line_separator_windows(self, multi_line_file):
        """line_separator=\\r\\n 输出 Windows 换行。"""
        file_tools_replace_lines(multi_line_file, 1, 1, "new", line_separator="\\r\\n")
        with open(multi_line_file, "rb") as f:
            content = f.read()
        assert b"\r\n" in content

    def test_replace_all_lines(self, multi_line_file):
        """替换全部行应正常。"""
        lines = _read_lines(multi_line_file)
        total = len(lines)
        new_content = "\n".join(["new"] * total)
        result = file_tools_replace_lines(multi_line_file, 1, total, new_content)
        assert "成功替换" in result.content[0].text
        new_lines = _read_lines(multi_line_file)
        assert all(l == "new" for l in new_lines)


class TestInsertLines:
    def test_insert_at_beginning(self, multi_line_file):
        result = file_tools_insert_lines(multi_line_file, line=1, content="new_first")
        assert "成功插入" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert lines[0] == "new_first"

    def test_insert_in_middle(self, multi_line_file):
        result = file_tools_insert_lines(multi_line_file, line=10, content="new_mid")
        assert "成功插入" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert lines[9] == "new_mid"

    def test_insert_at_end_plus_one(self, multi_line_file):
        total = len(_read_lines(multi_line_file))
        result = file_tools_insert_lines(multi_line_file, line=total + 1, content="new_end")
        assert "成功插入" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert lines[-1] == "new_end"

    def test_insert_multiple_lines(self, multi_line_file):
        result = file_tools_insert_lines(
            multi_line_file, line=5,
            content="insert1\ninsert2\ninsert3",
        )
        assert "成功插入" in result.content[0].text
        assert "插入了 3 行" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert len(lines) == 23

    def test_nonexistent_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "nonexist.txt")
        result = file_tools_insert_lines(path, 1, "content")
        assert "失败" in result.content[0].text

    def test_invalid_line(self, multi_line_file):
        result = file_tools_insert_lines(multi_line_file, 0, "content")
        assert "失败" in result.content[0].text

    def test_backup_created(self, multi_line_file):
        file_tools_insert_lines(multi_line_file, 1, "new_line")
        history = list_history(multi_line_file)
        assert len(history) == 1

    def test_mixed_whitespace(self, tmp_dir):
        """混合缩进内容（tab+空格混合）应正确处理。"""
        path = os.path.join(tmp_dir, "mixed.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\t  mixed\n  \tmixed2\nplain\n")
        result = file_tools_indent_lines(path, mode="expand", count=2)
        assert "成功缩进" in result.content[0].text
        lines = _read_lines(path)
        assert lines[0].startswith("  ")
        assert lines[2].startswith("  ")

    def test_shrink_partial(self, tmp_dir):
        """shrink 模式删除的空白数不超过行首实际空白数。"""
        path = os.path.join(tmp_dir, "partial.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("  3spaces\n\t1tab\n       8spaces\n")
        result = file_tools_indent_lines(path, mode="shrink", count=4)
        assert "成功缩进" in result.content[0].text
        lines = _read_lines(path)
        # "  3spaces" → 删3个空格（只有3个），变成"3spaces"
        assert lines[0] == "3spaces"
        # "\t1tab" → 删1个tab（只有1个），变成"1tab"
        assert lines[1] == "1tab"
        # "       8spaces" → 删4个空格，变成"   8spaces"
        assert lines[2] == "   8spaces"

    def test_line_separator_unix(self, multi_line_file):
        """line_separator=\\n 输出 Unix 换行。"""
        file_tools_insert_lines(multi_line_file, 1, "new", line_separator="\\n")
        with open(multi_line_file, "rb") as f:
            content = f.read()
        assert b"\r\nnew" not in content

    def test_line_separator_windows(self, multi_line_file):
        """line_separator=\\r\\n 输出 Windows 换行。"""
        file_tools_insert_lines(multi_line_file, 1, "new", line_separator="\\r\\n")
        with open(multi_line_file, "rb") as f:
            content = f.read()
        assert b"\r\n" in content


class TestDeleteLines:
    def test_delete_range(self, multi_line_file):
        result = file_tools_delete_lines(multi_line_file, start_line=5, end_line=7)
        assert "成功删除" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert len(lines) == 17

    def test_delete_first_line(self, multi_line_file):
        result = file_tools_delete_lines(multi_line_file, 1, 1)
        assert "成功删除" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert lines[0] == "line2"

    def test_delete_last_line(self, multi_line_file):
        result = file_tools_delete_lines(multi_line_file, 20, 20)
        assert "成功删除" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert len(lines) == 19
        assert lines[-1] == "line19"

    def test_delete_all(self, multi_line_file):
        result = file_tools_delete_lines(multi_line_file, 1, 20)
        assert "成功删除" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert len(lines) == 0 or (len(lines) == 1 and lines[0] == "")

    def test_preview_format(self, multi_line_file):
        result = file_tools_delete_lines(multi_line_file, 5, 8)
        assert "  4 > line4" in result.content[0].text      # 前一行上下文
        assert "- 5 > line5" in result.content[0].text       # 被删除的行
        assert "- 6 > line6" in result.content[0].text
        assert "  5 > line9" in result.content[0].text       # 后一行上下文
        assert "已删除" in result.content[0].text
        assert "+" not in result.content[0].text             # 不应该有 + 组

    def test_nonexistent_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "nonexist.txt")
        result = file_tools_delete_lines(path, 1, 3)
        assert "失败" in result.content[0].text

    def test_invalid_range(self, multi_line_file):
        result = file_tools_delete_lines(multi_line_file, 10, 5)
        assert "失败" in result.content[0].text

    def test_backup_created(self, multi_line_file):
        file_tools_delete_lines(multi_line_file, 5, 5)
        history = list_history(multi_line_file)
        assert len(history) == 1

    def test_mixed_whitespace(self, tmp_dir):
        """混合缩进内容（tab+空格混合）应正确处理。"""
        path = os.path.join(tmp_dir, "mixed.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\t  mixed\n  \tmixed2\nplain\n")
        result = file_tools_indent_lines(path, mode="expand", count=2)
        assert "成功缩进" in result.content[0].text
        lines = _read_lines(path)
        assert lines[0].startswith("  ")
        assert lines[2].startswith("  ")

    def test_shrink_partial(self, tmp_dir):
        """shrink 模式删除的空白数不超过行首实际空白数。"""
        path = os.path.join(tmp_dir, "partial.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("  3spaces\n\t1tab\n       8spaces\n")
        result = file_tools_indent_lines(path, mode="shrink", count=4)
        assert "成功缩进" in result.content[0].text
        lines = _read_lines(path)
        # "  3spaces" → 删3个空格（只有3个），变成"3spaces"
        assert lines[0] == "3spaces"
        # "\t1tab" → 删1个tab（只有1个），变成"1tab"
        assert lines[1] == "1tab"
        # "       8spaces" → 删4个空格，变成"   8spaces"
        assert lines[2] == "   8spaces"

    def test_line_separator_unix(self, multi_line_file):
        """line_separator=\\n 输出 Unix 换行（删除后剩余行之间用 \\n 连接）。"""
        file_tools_delete_lines(multi_line_file, 1, 1, line_separator="\\n")
        with open(multi_line_file, "rb") as f:
            content = f.read()
        # 删除第1行后，剩余行用 \n 连接，整个文件不应有 \r\n
        assert b"\r\n" not in content

    def test_line_separator_windows(self, multi_line_file):
        """line_separator=\\r\\n 输出 Windows 换行。"""
        file_tools_delete_lines(multi_line_file, 1, 1, line_separator="\\r\\n")
        with open(multi_line_file, "rb") as f:
            content = f.read()
        assert b"\r\n" in content

    def test_chinese_content(self, chinese_file):
        """中文内容删除应正常。"""
        result = file_tools_delete_lines(chinese_file, 2, 2)
        assert "成功删除" in result.content[0].text
        lines = _read_lines(chinese_file)
        assert len(lines) == 2
        assert "这是第一行" in lines[0]


class TestReplace:
    def test_basic_replace(self, multi_line_file):
        result = file_tools_replace(multi_line_file, "line5", "REPLACED")
        assert "成功替换" in result.content[0].text
        content = _read_file(multi_line_file)
        assert "REPLACED" in content
        assert "line5" not in content

    def test_replace_specific_line_range(self, multi_line_file):
        result = file_tools_replace(
            multi_line_file, "line", "ROW",
            start_line=15, end_line=18,
        )
        assert "成功替换" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert "ROW15" in lines[14]
        assert "line1" in lines[0]

    def test_start_count(self, multi_line_file):
        result = file_tools_replace(
            multi_line_file, "line", "ROW",
            start_line=3, count=2,
        )
        assert "成功替换" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert "line1" in lines[0]
        assert "line2" in lines[1]
        assert "ROW3" in lines[2]
        assert "ROW4" in lines[3]
        assert "line5" in lines[4]

    def test_no_match(self, multi_line_file):
        result = file_tools_replace(multi_line_file, "ZZZ_NOT_FOUND", "X")
        assert "失败" in result.content[0].text
        assert "未找到" in result.content[0].text

    def test_dry_run(self, multi_line_file):
        original = _read_file(multi_line_file)
        result = file_tools_replace(multi_line_file, "line", "ROW", dry_run=True)
        assert "dry_run" in result.content[0].text
        assert "模拟替换" in result.content[0].text
        assert _read_file(multi_line_file) == original

    def test_nonexistent_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "nonexist.txt")
        result = file_tools_replace(path, "old", "new")
        assert "失败" in result.content[0].text

    def test_backup_created(self, multi_line_file):
        file_tools_replace(multi_line_file, "line", "ROW")
        history = list_history(multi_line_file)
        assert len(history) == 1

    def test_mixed_whitespace(self, tmp_dir):
        """混合缩进内容（tab+空格混合）应正确处理。"""
        path = os.path.join(tmp_dir, "mixed.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\t  mixed\n  \tmixed2\nplain\n")
        result = file_tools_indent_lines(path, mode="expand", count=2)
        assert "成功缩进" in result.content[0].text
        lines = _read_lines(path)
        assert lines[0].startswith("  ")
        assert lines[2].startswith("  ")

    def test_shrink_partial(self, tmp_dir):
        """shrink 模式删除的空白数不超过行首实际空白数。"""
        path = os.path.join(tmp_dir, "partial.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("  3spaces\n\t1tab\n       8spaces\n")
        result = file_tools_indent_lines(path, mode="shrink", count=4)
        assert "成功缩进" in result.content[0].text
        lines = _read_lines(path)
        # "  3spaces" → 删3个空格（只有3个），变成"3spaces"
        assert lines[0] == "3spaces"
        # "\t1tab" → 删1个tab（只有1个），变成"1tab"
        assert lines[1] == "1tab"
        # "       8spaces" → 删4个空格，变成"   8spaces"
        assert lines[2] == "   8spaces"

    def test_case_sensitive(self, multi_line_file):
        result = file_tools_replace(multi_line_file, "LINE", "X")
        assert "失败" in result.content[0].text

    def test_substring_matching(self, multi_line_file):
        file_tools_replace(multi_line_file, "ine", "XXX")
        lines = _read_lines(multi_line_file)
        assert "lXXX" in lines[0]

    def test_count_minus1(self, multi_line_file):
        """count=-1 替换全部匹配"""
        file_tools_replace(multi_line_file, "line", "ROW", count=-1)
        content = _read_file(multi_line_file)
        assert "line" not in content

    def test_empty_old_text(self, multi_line_file):
        result = file_tools_replace(multi_line_file, "", "X")
        assert "失败" in result.content[0].text

    def test_invalid_count(self, multi_line_file):
        """count=0 应报错，count=-1 应通过"""
        result = file_tools_replace(multi_line_file, "line", "ROW", count=0)
        assert "失败" in result.content[0].text
        assert "count" in result.content[0].text
        result2 = file_tools_replace(multi_line_file, "line", "ROW", count=-1)
        assert "成功替换" in result2.content[0].text


    def test_cross_line_matching(self, multi_line_file):
        """跨行匹配：old_text 含 \n 时匹配多行内容"""
        result = file_tools_replace(
            multi_line_file, "line5\nline6", "X\nY\nZ",
        )
        assert "成功替换" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert lines[4] == "X"
        assert lines[5] == "Y"
        assert lines[6] == "Z"
        assert lines[7] == "line7"

    def test_line_separator_unix(self, multi_line_file):
        """line_separator=\\n 输出 Unix 换行。"""
        file_tools_replace(multi_line_file, "line", "ROW", line_separator="\\n")
        with open(multi_line_file, "rb") as f:
            content = f.read()
        assert b"\r\n" not in content

    def test_line_separator_windows(self, multi_line_file):
        """line_separator=\\r\\n 输出 Windows 换行。"""
        file_tools_replace(multi_line_file, "line", "ROW", line_separator="\\r\\n")
        with open(multi_line_file, "rb") as f:
            content = f.read()
        assert b"\r\n" in content

    def test_special_chars(self, tmp_dir):
        """替换含正则特殊字符的文本应正确（纯文本替换，非正则）。"""
        path = os.path.join(tmp_dir, "special.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("price: $10.00\n")
        result = file_tools_replace(path, "$10.00", "$20.00")
        assert "成功替换" in result.content[0].text
        with open(path) as f:
            assert "$20.00" in f.read()


class TestRegexReplace:
    def test_basic(self, multi_line_file):
        """count 默认=1，只替换第一次匹配。"""
        result = file_tools_regex_replace(multi_line_file, r"line(\d+)", r"NUM\1")
        assert "成功替换" in result.content[0].text
        assert "替换了 1 处" in result.content[0].text  # 默认 count=1
        lines = _read_lines(multi_line_file)
        assert "NUM1" in lines[0]
        assert "line2" in lines[1]  # 只替换了第1个匹配

    def test_replace_all(self, multi_line_file):
        """count=-1 替换全部。"""
        result = file_tools_regex_replace(multi_line_file, r"line(\d+)", r"X\1", count=-1)
        assert "成功替换" in result.content[0].text
        assert "替换了 20 处" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert all("X" in l for l in lines)

    def test_backreference(self, multi_line_file):
        result = file_tools_regex_replace(multi_line_file, r"line(\d+)", r"item_\1_value")
        assert "成功替换" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert "item_1_value" in lines[0]

    def test_no_match(self, multi_line_file):
        result = file_tools_regex_replace(multi_line_file, r"ZZZ", "X")
        assert "失败" in result.content[0].text
        assert "未找到" in result.content[0].text

    def test_dry_run(self, multi_line_file):
        original = _read_file(multi_line_file)
        result = file_tools_regex_replace(multi_line_file, r"line\d+", "ITEM", dry_run=True)
        assert "dry_run" in result.content[0].text
        assert "模拟替换" in result.content[0].text
        assert _read_file(multi_line_file) == original

    def test_nonexistent_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "nonexist.txt")
        result = file_tools_regex_replace(path, r".", "X")
        assert "失败" in result.content[0].text

    def test_invalid_regex(self, multi_line_file):
        result = file_tools_regex_replace(multi_line_file, r"[invalid", "X")
        assert "失败" in result.content[0].text

    def test_start_count(self, multi_line_file):
        """start=3, count=2 → 只替换第3、4个匹配。"""
        result = file_tools_regex_replace(
            multi_line_file, r"line(\d+)", r"X\1",
            start=3, count=2,
        )
        assert "成功替换" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert "line1" in lines[0]   # 第1个未替换
        assert "line2" in lines[1]   # 第2个未替换
        assert "X3" in lines[2]      # 第3个替换了
        assert "X4" in lines[3]      # 第4个替换了
        assert "line5" in lines[4]   # 第5个未替换

    def test_line_range(self, multi_line_file):
        """start_line/end_line 控制搜索行范围。"""
        result = file_tools_regex_replace(
            multi_line_file, r"line", "ROW",
            start_line=10, end_line=12,
            count=-1,
        )
        assert "成功替换" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert "line1" in lines[0]    # 范围外未改
        assert "ROW10" in lines[9]    # 范围内改了
        assert "ROW12" in lines[11]
        assert "line13" in lines[12]  # 范围外未改

    def test_backup_created(self, multi_line_file):
        file_tools_regex_replace(multi_line_file, r"line", "ROW")
        history = list_history(multi_line_file)
        assert len(history) == 1

    def test_mixed_whitespace(self, tmp_dir):
        """混合缩进内容（tab+空格混合）应正确处理。"""
        path = os.path.join(tmp_dir, "mixed.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\t  mixed\n  \tmixed2\nplain\n")
        result = file_tools_indent_lines(path, mode="expand", count=2)
        assert "成功缩进" in result.content[0].text
        lines = _read_lines(path)
        assert lines[0].startswith("  ")
        assert lines[2].startswith("  ")

    def test_shrink_partial(self, tmp_dir):
        """shrink 模式删除的空白数不超过行首实际空白数。"""
        path = os.path.join(tmp_dir, "partial.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("  3spaces\n\t1tab\n       8spaces\n")
        result = file_tools_indent_lines(path, mode="shrink", count=4)
        assert "成功缩进" in result.content[0].text
        lines = _read_lines(path)
        # "  3spaces" → 删3个空格（只有3个），变成"3spaces"
        assert lines[0] == "3spaces"
        # "\t1tab" → 删1个tab（只有1个），变成"1tab"
        assert lines[1] == "1tab"
        # "       8spaces" → 删4个空格，变成"   8spaces"
        assert lines[2] == "   8spaces"

    def test_start_lt_1(self, multi_line_file):
        """start<1 应报错"""
        result = file_tools_regex_replace(multi_line_file, r"line", "ROW", start=0)
        assert "失败" in result.content[0].text
        assert "start" in result.content[0].text

    def test_line_separator_unix(self, multi_line_file):
        """line_separator=\\n 输出 Unix 换行。"""
        file_tools_regex_replace(multi_line_file, r"line", "ROW", line_separator="\\n")
        with open(multi_line_file, "rb") as f:
            content = f.read()
        assert b"\r\n" not in content

    def test_line_separator_windows(self, multi_line_file):
        """line_separator=\\r\\n 输出 Windows 换行。"""
        file_tools_regex_replace(multi_line_file, r"line", "ROW", line_separator="\\r\\n")
        with open(multi_line_file, "rb") as f:
            content = f.read()
        assert b"\r\n" in content

    # ── 边缘情况 ──────────────────────────────────────────

    def test_empty_pattern(self, multi_line_file):
        """空 pattern 应报错"""
        result = file_tools_regex_replace(multi_line_file, "", "X")
        assert "失败" in result.content[0].text
        assert "pattern" in result.content[0].text.lower()

    def test_count_zero(self, multi_line_file):
        """count=0 应报错"""
        result = file_tools_regex_replace(multi_line_file, r"line", "ROW", count=0)
        assert "失败" in result.content[0].text
        assert "count" in result.content[0].text.lower()

    def test_count_negative_invalid(self, multi_line_file):
        """count<-1 应报错"""
        result = file_tools_regex_replace(multi_line_file, r"line", "ROW", count=-5)
        assert "失败" in result.content[0].text
        assert "count" in result.content[0].text.lower()

    def test_start_line_lt_1(self, multi_line_file):
        """start_line<1 应报错"""
        result = file_tools_regex_replace(multi_line_file, r"line", "ROW", start_line=0)
        assert "失败" in result.content[0].text

    def test_start_line_gt_total(self, multi_line_file):
        """start_line>总行数 应报错"""
        result = file_tools_regex_replace(multi_line_file, r"line", "ROW", start_line=100)
        assert "失败" in result.content[0].text
        assert "超出" in result.content[0].text

    def test_end_line_lt_start_line(self, multi_line_file):
        """end_line<start_line 应报错"""
        result = file_tools_regex_replace(multi_line_file, r"line", "ROW", start_line=10, end_line=5)
        assert "失败" in result.content[0].text
        assert "矛盾" in result.content[0].text

    def test_cross_line_replacement(self, cross_line_regex_file):
        """跨行模式替换函数定义。"""
        result = file_tools_regex_replace(
            cross_line_regex_file,
            r"def (\w+)\(.*?\):\s+return (.+)",
            r"def \1():\n    return \2 + 1",
            count=-1,
        )
        assert "成功替换" in result.content[0].text
        lines = _read_lines(cross_line_regex_file)
        assert "def foo():" in lines[0]
        assert "    return x + 1 + 1" in lines[1]
        assert "def bar():" in lines[3]
        assert "    return 42 + 1" in lines[4]

    def test_cross_line_single_replace(self, cross_line_regex_file):
        """跨行模式只替换第1次匹配（默认 count=1）。"""
        result = file_tools_regex_replace(
            cross_line_regex_file,
            r"def (\w+)\(.*?\):\s+return (.+)",
            r"def \1():\n    return 0",
        )
        assert "成功替换" in result.content[0].text
        assert "替换了 1 处" in result.content[0].text
        lines = _read_lines(cross_line_regex_file)
        assert "def foo():" in lines[0]  # foo 被替换了
        assert "def bar()" in lines[3]   # bar 还在（第2个匹配）
        assert "return 42" in lines[4]

    def test_complex_backref(self, tmp_dir):
        """复杂反向引用（命名组、条件替换）应正确。"""
        path = os.path.join(tmp_dir, "backref.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("foo_123\nbar_456\n")
        result = file_tools_regex_replace(path, r"(\w+)_(\d+)", r"\2_\1", count=-1)
        assert "成功替换" in result.content[0].text
        lines = _read_lines(path)
        assert lines[0] == "123_foo"
        assert lines[1] == "456_bar"

    def test_replace_empty(self, multi_line_file):
        """替换为空字符串应删除匹配内容。"""
        result = file_tools_regex_replace(multi_line_file, r"line", "", count=-1)
        assert "成功替换" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert all("line" not in l for l in lines)  # "line" 被移除，只剩数字
        assert lines[0] == "1"


class TestIndentLines:
    def test_expand_basic(self, multi_line_file):
        """expand 模式：每行添加 4 空格。"""
        result = file_tools_indent_lines(multi_line_file, mode="expand")
        assert "成功缩进" in result.content[0].text
        assert "增加了" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert lines[0].startswith("    ")
        assert lines[0].strip() == "line1"

    def test_shrink_basic(self, multi_line_file):
        """shrink 模式：先 expand 再 shrink 回到原样。"""
        file_tools_indent_lines(multi_line_file, mode="expand", count=4)
        result = file_tools_indent_lines(multi_line_file, mode="shrink", count=4)
        assert "成功缩进" in result.content[0].text
        assert "减少了" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert lines[0] == "line1"

    def test_line_range(self, multi_line_file):
        """只缩进指定行范围。"""
        result = file_tools_indent_lines(multi_line_file, start_line=5, end_line=8, mode="expand")
        assert "成功缩进" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert not lines[0].startswith(" ")  # 第1行不变
        assert lines[4].startswith("    ")    # 第5行缩进
        assert lines[7].startswith("    ")    # 第8行缩进
        assert not lines[8].startswith(" ")   # 第9行不变

    def test_end_line_lt_1(self, multi_line_file):
        """end_line < 1 应报错。"""
        result = file_tools_indent_lines(multi_line_file, end_line=0)
        assert "失败" in result.content[0].text
        assert "不合法" in result.content[0].text

    def test_end_line_lt_start_line(self, multi_line_file):
        """end_line < start_line 应报错。"""
        result = file_tools_indent_lines(multi_line_file, start_line=5, end_line=3)
        assert "失败" in result.content[0].text
        assert "小于" in result.content[0].text

    def test_custom_char(self, multi_line_file):
        """使用 tab 作为缩进字符。"""
        result = file_tools_indent_lines(multi_line_file, mode="expand", count=2, char="\t")
        assert "成功缩进" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert lines[0].startswith("\t\t")

    def test_custom_count(self, multi_line_file):
        """自定义缩进数量。"""
        result = file_tools_indent_lines(multi_line_file, mode="expand", count=8)
        assert "成功缩进" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert lines[0].startswith("        ")

    def test_line_separator_unix(self, multi_line_file):
        """line_separator=\\n 输出 Unix 换行。"""
        file_tools_indent_lines(multi_line_file, mode="expand", count=2, line_separator="\\n")
        with open(multi_line_file, "rb") as f:
            content = f.read()
        assert b"\r\n" not in content  # 没有 Windows 换行

    def test_line_separator_windows(self, multi_line_file):
        """line_separator=\\r\\n 输出 Windows 换行。"""
        file_tools_indent_lines(multi_line_file, mode="expand", count=2, line_separator="\\r\\n")
        with open(multi_line_file, "rb") as f:
            content = f.read()
        assert b"\r\n" in content

    def test_no_changes(self, multi_line_file):
        """shrink 模式行首无空白时，没有行被修改。"""
        result = file_tools_indent_lines(multi_line_file, mode="shrink", count=4)
        assert "没有行被修改" in result.content[0].text

    def test_empty_file(self, empty_file):
        """空文件视为 1 行空行，可以被缩进。"""
        result = file_tools_indent_lines(empty_file, mode="expand")
        assert "成功缩进" in result.content[0].text
        with open(empty_file, encoding="utf-8") as f:
            content = f.read()
        assert content == "    "  # 空行被加了 4 空格

    def test_nonexistent_file(self, tmp_dir):
        """文件不存在报错。"""
        path = os.path.join(tmp_dir, "nonexist.txt")
        result = file_tools_indent_lines(path, mode="expand")
        assert "失败" in result.content[0].text

    def test_invalid_start_line(self, multi_line_file):
        """start_line < 1 报错。"""
        result = file_tools_indent_lines(multi_line_file, start_line=0, mode="expand")
        assert "失败" in result.content[0].text

    def test_invalid_mode(self, multi_line_file):
        """不合法模式报错。"""
        result = file_tools_indent_lines(multi_line_file, mode="invalid")
        assert "失败" in result.content[0].text

    def test_invalid_count(self, multi_line_file):
        """count < 0 报错。"""
        result = file_tools_indent_lines(multi_line_file, count=-1, mode="expand")
        assert "失败" in result.content[0].text

    def test_backup_created(self, multi_line_file):
        """备份被创建。"""
        file_tools_indent_lines(multi_line_file, mode="expand", count=2)
        history = list_history(multi_line_file)
        assert len(history) == 1

    def test_mixed_whitespace(self, tmp_dir):
        """混合缩进内容（tab+空格混合）应正确处理。"""
        path = os.path.join(tmp_dir, "mixed.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\t  mixed\n  \tmixed2\nplain\n")
        result = file_tools_indent_lines(path, mode="expand", count=2)
        assert "成功缩进" in result.content[0].text
        lines = _read_lines(path)
        assert lines[0].startswith("  ")
        assert lines[2].startswith("  ")

    def test_shrink_partial(self, tmp_dir):
        """shrink 模式删除的空白数不超过行首实际空白数。"""
        path = os.path.join(tmp_dir, "partial.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("  3spaces\n\t1tab\n       8spaces\n")
        result = file_tools_indent_lines(path, mode="shrink", count=4)
        assert "成功缩进" in result.content[0].text
        lines = _read_lines(path)
        # "  3spaces" → 删3个空格（只有3个），变成"3spaces"
        assert lines[0] == "3spaces"
        # "\t1tab" → 删1个tab（只有1个），变成"1tab"
        assert lines[1] == "1tab"
        # "       8spaces" → 删4个空格，变成"   8spaces"
        assert lines[2] == "   8spaces"

class TestStrLineParams:
    """行号/数字参数兼容字符串输入（LLM 常传 "123"）。"""

    def test_replace_lines_string_ok(self, multi_line_file):
        result = file_tools_replace_lines(multi_line_file, "2", "3", "REPLACED")
        assert "成功替换" in result.content[0].text
        assert "REPLACED" in _read_file(multi_line_file)

    def test_replace_lines_illegal_string(self, multi_line_file):
        result = file_tools_replace_lines(multi_line_file, "abc", "3", "X")
        assert "失败" in result.content[0].text
        assert "start_line 参数应当输入整数" in result.content[0].text

    def test_insert_lines_string_ok(self, multi_line_file):
        result = file_tools_insert_lines(multi_line_file, "2", "INSERTED")
        assert "成功插入" in result.content[0].text
        assert "INSERTED" in _read_file(multi_line_file)

    def test_insert_lines_illegal_string(self, multi_line_file):
        result = file_tools_insert_lines(multi_line_file, "2.5", "X")
        assert "失败" in result.content[0].text
        assert "line 参数应当输入整数" in result.content[0].text

    def test_delete_lines_string_ok(self, multi_line_file):
        result = file_tools_delete_lines(multi_line_file, "1", "2")
        assert "成功删除" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert "line1" not in lines
        assert "line2" not in lines
        assert lines[0] == "line3"

    def test_replace_string_params_ok(self, multi_line_file):
        result = file_tools_replace(multi_line_file, "line", "ROW", start_line="1", end_line="20", count="-1")
        assert "成功替换" in result.content[0].text
        assert "ROW" in _read_file(multi_line_file)

    def test_replace_illegal_count(self, multi_line_file):
        result = file_tools_replace(multi_line_file, "line", "ROW", count="abc")
        assert "失败" in result.content[0].text
        assert "count 参数应当输入整数" in result.content[0].text

    def test_regex_replace_string_params_ok(self, multi_line_file):
        result = file_tools_regex_replace(
            multi_line_file, r"line(\d+)", r"item_\1", start_line="1", count="-1"
        )
        assert "成功替换" in result.content[0].text
        assert "item_1" in _read_file(multi_line_file)

    def test_indent_lines_string_ok(self, multi_line_file):
        result = file_tools_indent_lines(multi_line_file, start_line="1", end_line="3", count="2")
        assert "成功" in result.content[0].text
        lines = _read_lines(multi_line_file)
        assert lines[0].startswith("  ")

    def test_indent_lines_illegal_count(self, multi_line_file):
        result = file_tools_indent_lines(multi_line_file, count="x")
        assert "失败" in result.content[0].text
        assert "count 参数应当输入整数" in result.content[0].text
