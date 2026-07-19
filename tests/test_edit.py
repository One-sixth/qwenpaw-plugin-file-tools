"""测试文件修改类工具。"""

import os

from backup.manager import list_history
from tools.edit import (
    file_tools_append,
    file_tools_delete_lines,
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
        assert "成功追加" in result
        content = _read_file(tmp_file)
        assert "line6" in content
        assert "line7" in content

    def test_nonexistent_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "nonexist.txt")
        result = file_tools_append(path, "content")
        assert "失败" in result

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
        assert "成功追加" in result

    def test_chinese_content(self, chinese_file):
        result = file_tools_append(chinese_file, "\n新增中文行")
        assert "成功追加" in result
        content = _read_file(chinese_file)
        assert "新增中文行" in content


class TestReplaceLines:
    def test_replace_range(self, multi_line_file):
        result = file_tools_replace_lines(
            multi_line_file, start_line=2, end_line=4,
            content="new2\nnew3\nnew4",
        )
        assert "成功替换" in result
        lines = _read_lines(multi_line_file)
        assert lines[1] == "new2"
        assert lines[3] == "new4"
        assert len(lines) == 20

    def test_replace_with_fewer_lines(self, multi_line_file):
        result = file_tools_replace_lines(
            multi_line_file, start_line=2, end_line=5,
            content="replacement",
        )
        assert "成功替换" in result
        lines = _read_lines(multi_line_file)
        assert len(lines) == 17
        assert lines[1] == "replacement"

    def test_replace_with_more_lines(self, multi_line_file):
        result = file_tools_replace_lines(
            multi_line_file, start_line=2, end_line=2,
            content="a\nb\nc\nd",
        )
        assert "成功替换" in result
        lines = _read_lines(multi_line_file)
        assert len(lines) == 23

    def test_nonexistent_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "nonexist.txt")
        result = file_tools_replace_lines(path, 1, 3, "content")
        assert "失败" in result

    def test_invalid_range(self, multi_line_file):
        result = file_tools_replace_lines(multi_line_file, 5, 3, "content")
        assert "失败" in result

    def test_preview_in_result(self, multi_line_file):
        result = file_tools_replace_lines(
            multi_line_file, start_line=5, end_line=7,
            content="new5\nnew6\nnew7",
        )
        assert "替换前" in result or "line5" in result or "line7" in result
        assert "已替换为" in result or "new5" in result or "new7" in result

    def test_backup_created(self, multi_line_file):
        file_tools_replace_lines(multi_line_file, 1, 1, "modified")
        history = list_history(multi_line_file)
        assert len(history) == 1

    def test_boundary_start(self, multi_line_file):
        result = file_tools_replace_lines(multi_line_file, 1, 1, "first")
        assert "成功替换" in result
        lines = _read_lines(multi_line_file)
        assert lines[0] == "first"

    def test_boundary_end(self, multi_line_file):
        result = file_tools_replace_lines(multi_line_file, 20, 20, "last")
        assert "成功替换" in result
        lines = _read_lines(multi_line_file)
        assert lines[-1] == "last"

    def test_chinese(self, chinese_file):
        result = file_tools_replace_lines(chinese_file, 1, 1, "替换第一行")
        assert "成功替换" in result
        lines = _read_lines(chinese_file)
        assert "替换第一行" in lines[0]


class TestInsertLines:
    def test_insert_at_beginning(self, multi_line_file):
        result = file_tools_insert_lines(multi_line_file, line=1, content="new_first")
        assert "成功插入" in result
        lines = _read_lines(multi_line_file)
        assert lines[0] == "new_first"

    def test_insert_in_middle(self, multi_line_file):
        result = file_tools_insert_lines(multi_line_file, line=10, content="new_mid")
        assert "成功插入" in result
        lines = _read_lines(multi_line_file)
        assert lines[9] == "new_mid"

    def test_insert_at_end_plus_one(self, multi_line_file):
        total = len(_read_lines(multi_line_file))
        result = file_tools_insert_lines(multi_line_file, line=total + 1, content="new_end")
        assert "成功插入" in result
        lines = _read_lines(multi_line_file)
        assert lines[-1] == "new_end"

    def test_insert_multiple_lines(self, multi_line_file):
        result = file_tools_insert_lines(
            multi_line_file, line=5,
            content="insert1\ninsert2\ninsert3",
        )
        assert "成功插入" in result
        assert "插入了 3 行" in result
        lines = _read_lines(multi_line_file)
        assert len(lines) == 23

    def test_nonexistent_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "nonexist.txt")
        result = file_tools_insert_lines(path, 1, "content")
        assert "失败" in result

    def test_invalid_line(self, multi_line_file):
        result = file_tools_insert_lines(multi_line_file, 0, "content")
        assert "失败" in result

    def test_backup_created(self, multi_line_file):
        file_tools_insert_lines(multi_line_file, 1, "new_line")
        history = list_history(multi_line_file)
        assert len(history) == 1


class TestDeleteLines:
    def test_delete_range(self, multi_line_file):
        result = file_tools_delete_lines(multi_line_file, start_line=5, end_line=7)
        assert "成功删除" in result
        lines = _read_lines(multi_line_file)
        assert len(lines) == 17

    def test_delete_first_line(self, multi_line_file):
        result = file_tools_delete_lines(multi_line_file, 1, 1)
        assert "成功删除" in result
        lines = _read_lines(multi_line_file)
        assert lines[0] == "line2"

    def test_delete_last_line(self, multi_line_file):
        result = file_tools_delete_lines(multi_line_file, 20, 20)
        assert "成功删除" in result
        lines = _read_lines(multi_line_file)
        assert len(lines) == 19
        assert lines[-1] == "line19"

    def test_delete_all(self, multi_line_file):
        result = file_tools_delete_lines(multi_line_file, 1, 20)
        assert "成功删除" in result
        lines = _read_lines(multi_line_file)
        assert len(lines) == 0 or (len(lines) == 1 and lines[0] == "")

    def test_preview_format(self, multi_line_file):
        result = file_tools_delete_lines(multi_line_file, 5, 8)
        assert "（被删除）" in result
        assert "已删除" in result

    def test_nonexistent_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "nonexist.txt")
        result = file_tools_delete_lines(path, 1, 3)
        assert "失败" in result

    def test_invalid_range(self, multi_line_file):
        result = file_tools_delete_lines(multi_line_file, 10, 5)
        assert "失败" in result

    def test_backup_created(self, multi_line_file):
        file_tools_delete_lines(multi_line_file, 5, 5)
        history = list_history(multi_line_file)
        assert len(history) == 1


class TestReplace:
    def test_basic_replace(self, multi_line_file):
        result = file_tools_replace(multi_line_file, "line5", "REPLACED")
        assert "成功替换" in result
        content = _read_file(multi_line_file)
        assert "REPLACED" in content
        assert "line5" not in content

    def test_replace_specific_line_range(self, multi_line_file):
        result = file_tools_replace(
            multi_line_file, "line", "ROW",
            start_line=15, end_line=18,
        )
        assert "成功替换" in result
        lines = _read_lines(multi_line_file)
        assert "ROW15" in lines[14]
        assert "line1" in lines[0]

    def test_start_count(self, multi_line_file):
        result = file_tools_replace(
            multi_line_file, "line", "ROW",
            start=3, count=2,
        )
        assert "成功替换" in result
        lines = _read_lines(multi_line_file)
        assert "line1" in lines[0]
        assert "line2" in lines[1]
        assert "ROW3" in lines[2]
        assert "ROW4" in lines[3]
        assert "line5" in lines[4]

    def test_no_match(self, multi_line_file):
        result = file_tools_replace(multi_line_file, "ZZZ_NOT_FOUND", "X")
        assert "失败" in result
        assert "未找到" in result

    def test_dry_run(self, multi_line_file):
        original = _read_file(multi_line_file)
        result = file_tools_replace(multi_line_file, "line", "ROW", dry_run=True)
        assert "dry_run" in result
        assert "模拟替换" in result
        assert _read_file(multi_line_file) == original

    def test_nonexistent_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "nonexist.txt")
        result = file_tools_replace(path, "old", "new")
        assert "失败" in result

    def test_backup_created(self, multi_line_file):
        file_tools_replace(multi_line_file, "line", "ROW")
        history = list_history(multi_line_file)
        assert len(history) == 1

    def test_case_sensitive(self, multi_line_file):
        result = file_tools_replace(multi_line_file, "LINE", "X")
        assert "失败" in result

    def test_substring_matching(self, multi_line_file):
        file_tools_replace(multi_line_file, "ine", "XXX")
        lines = _read_lines(multi_line_file)
        assert "lXXX" in lines[0]

    def test_count_minus1(self, multi_line_file):
        file_tools_replace(multi_line_file, "line", "ROW", count=-1)
        content = _read_file(multi_line_file)
        assert "line" not in content

    def test_empty_old_text(self, multi_line_file):
        result = file_tools_replace(multi_line_file, "", "X")
        assert "成功替换" in result or "失败" in result

    def test_start_lt_1(self, multi_line_file):
        """start<1 应报错"""
        result = file_tools_replace(multi_line_file, "line", "ROW", start=0)
        assert "失败" in result
        assert "start" in result
        result2 = file_tools_replace(multi_line_file, "line", "ROW", start=-1)
        assert "失败" in result2
        assert "start" in result2


class TestRegexReplace:
    def test_basic(self, multi_line_file):
        result = file_tools_regex_replace(multi_line_file, r"line(\d+)", r"NUM\1")
        assert "成功替换" in result
        lines = _read_lines(multi_line_file)
        assert "NUM1" in lines[0]
        assert "line1" not in lines[0]

    def test_backreference(self, multi_line_file):
        result = file_tools_regex_replace(
            multi_line_file, r"line(\d+)", r"item_\1_value",
        )
        assert "成功替换" in result
        lines = _read_lines(multi_line_file)
        assert "item_1_value" in lines[0]

    def test_no_match(self, multi_line_file):
        result = file_tools_regex_replace(multi_line_file, r"ZZZ", "X")
        assert "失败" in result
        assert "未找到" in result

    def test_dry_run(self, multi_line_file):
        original = _read_file(multi_line_file)
        result = file_tools_regex_replace(multi_line_file, r"line\d+", "ITEM", dry_run=True)
        assert "dry_run" in result
        assert "模拟替换" in result
        assert _read_file(multi_line_file) == original

    def test_nonexistent_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "nonexist.txt")
        result = file_tools_regex_replace(path, r".", "X")
        assert "失败" in result

    def test_invalid_regex(self, multi_line_file):
        result = file_tools_regex_replace(multi_line_file, r"[invalid", "X")
        assert "失败" in result

    def test_start_count(self, multi_line_file):
        result = file_tools_regex_replace(
            multi_line_file, r"line(\d+)", r"X\1",
            start=3, count=2,
        )
        assert "成功替换" in result
        lines = _read_lines(multi_line_file)
        assert "line1" in lines[0]
        assert "X3" in lines[2]
        assert "X4" in lines[3]
        assert "line5" in lines[4]

    def test_line_range(self, multi_line_file):
        result = file_tools_regex_replace(
            multi_line_file, r"line", "ROW",
            start_line=10, end_line=12,
        )
        assert "成功替换" in result
        lines = _read_lines(multi_line_file)
        assert "line1" in lines[0]
        assert "ROW10" in lines[9]
        assert "ROW12" in lines[11]
        assert "line13" in lines[12]

    def test_backup_created(self, multi_line_file):
        file_tools_regex_replace(multi_line_file, r"line", "ROW")
        history = list_history(multi_line_file)
        assert len(history) == 1

    def test_complex_pattern(self, multi_line_file):
        result = file_tools_regex_replace(multi_line_file, r"^line(\d+)$", r"[\1]")
        assert "成功替换" in result
        lines = _read_lines(multi_line_file)
        assert "[1]" in lines[0]

    def test_start_lt_1(self, multi_line_file):
        """start<1 应报错"""
        result = file_tools_regex_replace(multi_line_file, r"line", "ROW", start=0)
        assert "失败" in result
        assert "start" in result
        result2 = file_tools_regex_replace(multi_line_file, r"line", "ROW", start=-1)
        assert "失败" in result2
        assert "start" in result2
