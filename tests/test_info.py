"""测试信息读取类工具。"""

import json
import os

import pytest

from tools.info import (
    file_tools_diff,
    file_tools_guess,
    file_tools_history,
    file_tools_info,
    file_tools_listdir,
)


def _make_files(dir_path, names):
    for n in names:
        path = os.path.join(dir_path, n)
        if n.endswith("/"):
            os.makedirs(path, exist_ok=True)
        else:
            open(path, "w").close()


class TestListdir:
    def test_basic(self, tmp_dir):
        open(os.path.join(tmp_dir, "a.txt"), "w").close()
        open(os.path.join(tmp_dir, "b.txt"), "w").close()
        result = file_tools_listdir(tmp_dir, recursive=1)
        assert "a.txt" in result
        assert "b.txt" in result

    def test_with_columns(self, tmp_dir):
        open(os.path.join(tmp_dir, "test.txt"), "w").close()
        result = file_tools_listdir(tmp_dir, recursive=1, columns=["size", "type"])
        assert "| name" in result
        assert "| size" in result
        assert "| type" in result
        assert "|---" in result

    def test_recursive_2(self, subdir_structure):
        result = file_tools_listdir(subdir_structure, recursive=2)
        assert "dir_a" + os.sep + "sub_file1.txt" in result
        assert "dir_a" + os.sep + "sub_dir1" in result
        assert "dir_b" + os.sep + "sub_file2.txt" in result
        assert "file_a.txt" in result
        assert ".hidden" in result

    def test_recursive_minus1(self, subdir_structure):
        result = file_tools_listdir(subdir_structure, recursive=-1)
        assert "dir_a" + os.sep + "sub_file1.txt" in result
        assert "dir_a" + os.sep + "sub_dir1" in result
        assert "dir_b" + os.sep + "sub_file2.txt" in result

    def test_invalid_recursive(self, tmp_dir):
        result = file_tools_listdir(tmp_dir, recursive=0)
        assert "失败" in result
        assert "不合法" in result

        result = file_tools_listdir(tmp_dir, recursive=-2)
        assert "失败" in result

    def test_nonexistent_dir(self):
        result = file_tools_listdir("/nonexistent_path_xyz")
        assert "失败" in result
        assert "不存在" in result

    def test_hidden_files(self, tmp_dir):
        open(os.path.join(tmp_dir, ".hidden"), "w").close()
        result = file_tools_listdir(tmp_dir, recursive=1)
        assert ".hidden" in result

    def test_sort_order(self, tmp_dir):
        """默认按 name 升序排列，目录和文件混在一起按名称排。"""
        open(os.path.join(tmp_dir, "z_last.txt"), "w").close()
        os.makedirs(os.path.join(tmp_dir, "a_dir"))
        open(os.path.join(tmp_dir, "b_file.txt"), "w").close()
        result = file_tools_listdir(tmp_dir, recursive=1)
        lines = result.strip().split("\n")
        a_idx = next(i for i, l in enumerate(lines) if l == "a_dir")
        b_idx = next(i for i, l in enumerate(lines) if l == "b_file.txt")
        z_idx = next(i for i, l in enumerate(lines) if l == "z_last.txt")
        assert a_idx < b_idx < z_idx

    def test_markdown_table_format(self, tmp_dir):
        open(os.path.join(tmp_dir, "normal.csv"), "w").close()
        result = file_tools_listdir(tmp_dir, recursive=1, columns=["size"])
        lines = result.strip().split("\n")
        assert lines[0].startswith("| name")
        assert lines[1].startswith("|---")
        assert "normal.csv" in lines[2]

    def test_empty_dir(self, tmp_dir):
        result = file_tools_listdir(tmp_dir, recursive=1)
        assert result == "（空目录，无文件）"

    def test_permission_column(self, tmp_dir):
        open(os.path.join(tmp_dir, "perm.txt"), "w").close()
        result = file_tools_listdir(tmp_dir, recursive=1, columns=["permissions"])
        assert "| permissions" in result
        # 纯文本列表没有表头
        result_no_col = file_tools_listdir(tmp_dir, recursive=1)
        assert "permissions" not in result_no_col

    def test_absolute_path(self, tmp_dir):
        open(os.path.join(tmp_dir, "abs_test.txt"), "w").close()
        # absolute=True 时返回绝对路径
        result_abs = file_tools_listdir(tmp_dir, recursive=1, absolute=True)
        abs_path = os.path.join(tmp_dir, "abs_test.txt")
        assert abs_path in result_abs
        # absolute=False（默认）时只返回文件名
        result_rel = file_tools_listdir(tmp_dir, recursive=1, absolute=False)
        assert "abs_test.txt" in result_rel
        assert abs_path not in result_rel

    def test_invalid_sort_by(self, tmp_dir):
        result = file_tools_listdir(tmp_dir, sort_by="invalid")
        assert "失败" in result
        assert "不合法" in result

    def test_invalid_start(self, tmp_dir):
        result = file_tools_listdir(tmp_dir, start=0)
        assert "失败" in result

    def test_invalid_count(self, tmp_dir):
        result = file_tools_listdir(tmp_dir, count=0)
        assert "失败" in result
        result = file_tools_listdir(tmp_dir, count=501)
        assert "失败" in result

    def test_pagination(self, tmp_dir):
        _make_files(tmp_dir, [f"f{i:03d}.txt" for i in range(20)])
        # count=5, start=1 → 第1~5个
        result = file_tools_listdir(tmp_dir, count=5)
        lines = result.strip().split("\n")
        assert len(lines) == 7  # 5文件名 + 1空行 + 1页脚
        assert "f000.txt" in result
        assert "f004.txt" in result
        assert "f005.txt" not in result
        assert "后面还有 15 个文件" in result
        # start=3 → 第3~7个（f002 ~ f006）
        result2 = file_tools_listdir(tmp_dir, start=3, count=5)
        assert "f002.txt" in result2
        assert "f006.txt" in result2
        assert "f001.txt" not in result2
        assert "后面还有 13 个文件" in result2

    def test_pagination_out_of_range(self, tmp_dir):
        _make_files(tmp_dir, [f"f{i}.txt" for i in range(3)])
        result = file_tools_listdir(tmp_dir, start=10)
        assert "没有更多文件" in result
        assert "共 3 个" in result

    def test_sort_ascending_descending(self, tmp_dir):
        _make_files(tmp_dir, ["c.txt", "a.txt", "b.txt"])
        asc = file_tools_listdir(tmp_dir, ascending=True)
        desc = file_tools_listdir(tmp_dir, ascending=False)
        assert asc.strip().split("\n") == ["a.txt", "b.txt", "c.txt"]
        assert desc.strip().split("\n") == ["c.txt", "b.txt", "a.txt"]

    def test_sort_by_type(self, tmp_dir):
        os.makedirs(os.path.join(tmp_dir, "zzz_dir"))
        open(os.path.join(tmp_dir, "aaa_file.txt"), "w").close()
        result = file_tools_listdir(tmp_dir, sort_by="type", ascending=True)
        lines = result.strip().split("\n")
        # "文件" < "文件夹"（字典序前缀关系）
        assert lines[0] == "aaa_file.txt"
        assert lines[1] == "zzz_dir"
        # descending
        result2 = file_tools_listdir(tmp_dir, sort_by="type", ascending=False)
        lines2 = result2.strip().split("\n")
        assert lines2[0] == "zzz_dir"
        assert lines2[1] == "aaa_file.txt"

    def test_sort_by_size(self, tmp_dir):
        open(os.path.join(tmp_dir, "small.txt"), "w").close()
        with open(os.path.join(tmp_dir, "large.txt"), "w") as f:
            f.write("x" * 1000)
        asc = file_tools_listdir(tmp_dir, sort_by="size", ascending=True)
        desc = file_tools_listdir(tmp_dir, sort_by="size", ascending=False)
        lines_asc = asc.strip().split("\n")
        lines_desc = desc.strip().split("\n")
        assert lines_asc[0] == "small.txt"
        assert lines_asc[1] == "large.txt"
        assert lines_desc[0] == "large.txt"
        assert lines_desc[1] == "small.txt"

    def test_sort_by_extension(self, tmp_dir):
        open(os.path.join(tmp_dir, "a.py"), "w").close()
        open(os.path.join(tmp_dir, "b.txt"), "w").close()
        open(os.path.join(tmp_dir, "c.md"), "w").close()
        result = file_tools_listdir(tmp_dir, sort_by="extension", ascending=True)
        lines = result.strip().split("\n")
        assert lines[0] == "c.md"
        assert lines[1] == "a.py"
        assert lines[2] == "b.txt"

    def test_sort_by_modified_at(self, tmp_dir):
        open(os.path.join(tmp_dir, "old.txt"), "w").close()
        # 确保 old.txt 的修改时间早于 new.txt
        old_ts = os.path.getmtime(os.path.join(tmp_dir, "old.txt"))
        open(os.path.join(tmp_dir, "new.txt"), "w").close()
        # 强制设置 new.txt 的时间比 old.txt 晚 1 秒
        os.utime(os.path.join(tmp_dir, "new.txt"), (old_ts + 2, old_ts + 2))
        asc = file_tools_listdir(tmp_dir, sort_by="modified_at", ascending=True)
        desc = file_tools_listdir(tmp_dir, sort_by="modified_at", ascending=False)
        lines_asc = asc.strip().split("\n")
        lines_desc = desc.strip().split("\n")
        assert lines_asc[0] == "old.txt"
        assert lines_asc[1] == "new.txt"
        assert lines_desc[0] == "new.txt"
        assert lines_desc[1] == "old.txt"

    def test_pagination_last_page(self, tmp_dir):
        _make_files(tmp_dir, [f"f{i:03d}.txt" for i in range(7)])
        result = file_tools_listdir(tmp_dir, start=6, count=5)
        assert "f005.txt" in result
        assert "f006.txt" in result
        assert "f004.txt" not in result
        # 最后一页无剩余，不显示尾部提示
        assert "后面还有" not in result

    def test_pagination_with_columns(self, tmp_dir):
        _make_files(tmp_dir, [f"f{i:03d}.txt" for i in range(20)])
        result = file_tools_listdir(tmp_dir, columns=["size"], count=5)
        lines = result.strip().split("\n")
        assert lines[0].startswith("| name")
        assert lines[1].startswith("|---")
        assert "f000.txt" in lines[2]
        assert "f004.txt" in result
        assert "f005.txt" not in result
        assert "后面还有 15 个文件" in result

    def test_pagination_single_file(self, tmp_dir):
        open(os.path.join(tmp_dir, "only.txt"), "w").close()
        result = file_tools_listdir(tmp_dir, start=1, count=1)
        assert result.strip() == "only.txt"


class TestInfo:
    def test_file(self, tmp_file):
        result = file_tools_info(tmp_file)
        data = json.loads(result)
        assert data["exists"] is True
        assert data["is_file"] is True
        assert data["size"] > 0
        assert "path" in data

    def test_directory(self, tmp_dir):
        result = file_tools_info(tmp_dir)
        data = json.loads(result)
        assert data["exists"] is True
        assert data["is_dir"] is True

    def test_nonexistent(self):
        result = file_tools_info("/nonexistent_xyz_789")
        assert "失败" in result
        assert "不存在" in result

    def test_fields(self, tmp_file):
        result = file_tools_info(tmp_file)
        data = json.loads(result)
        assert "permissions" in data
        assert "created_at" in data
        assert "modified_at" in data

    def test_json_format(self, tmp_file):
        result = file_tools_info(tmp_file)
        json.loads(result)

    def test_chinese_filename(self, tmp_dir):
        """中文文件名路径应正确返回信息。"""
        path = os.path.join(tmp_dir, "测试文件.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("test")
        result = file_tools_info(path)
        data = json.loads(result)
        assert data["exists"] is True
        assert "测试文件" in data["path"]

    def test_symlink(self, tmp_dir):
        """符号链接应正确返回信息。"""
        target = os.path.join(tmp_dir, "target.txt")
        with open(target, "w") as f:
            f.write("test")
        link = os.path.join(tmp_dir, "link.txt")
        try:
            os.symlink(target, link)
        except OSError:
            pytest.skip("当前环境不支持创建符号链接")
        result = file_tools_info(link)
        data = json.loads(result)
        assert data["exists"] is True
        assert data["is_link"] is True


class TestGuess:
    def test_text_file(self, tmp_file):
        result = file_tools_guess(tmp_file)
        data = json.loads(result)
        assert data["type"] == "text"

    def test_directory(self, tmp_dir):
        result = file_tools_guess(tmp_dir)
        data = json.loads(result)
        assert data["type"] == "directory"

    def test_nonexistent(self):
        result = file_tools_guess("/nonexistent_xyz_789")
        data = json.loads(result)
        assert "error" in data

    def test_encoding_present(self, tmp_file):
        result = file_tools_guess(tmp_file)
        data = json.loads(result)
        assert data.get("encoding") is not None

    def test_gbk_file(self, gbk_file):
        """GBK 编码文件应正确检测编码。"""
        result = file_tools_guess(gbk_file)
        data = json.loads(result)
        assert data["type"] == "text"
        encoding = data.get("encoding", "").lower()
        assert "gb" in encoding or "utf-8" in encoding


class TestDiff:
    def test_same_file(self, tmp_file):
        result = file_tools_diff(tmp_file, tmp_file)
        assert "文件相同" in result

    def test_different_files(self, tmp_dir):
        a = os.path.join(tmp_dir, "a.txt")
        b = os.path.join(tmp_dir, "b.txt")
        with open(a, "w") as f:
            f.write("hello\nworld\n")
        with open(b, "w") as f:
            f.write("hello\npython\nworld\n")
        result = file_tools_diff(a, b)
        assert "python" in result
        assert "@@" in result

    def test_nonexistent(self):
        result = file_tools_diff("/nonexist_a", "/nonexist_b")
        assert "失败" in result

    def test_hunk_pagination(self, tmp_dir):
        a = os.path.join(tmp_dir, "a.txt")
        b = os.path.join(tmp_dir, "b.txt")
        lines_a = [f"line{i}" for i in range(100)]
        lines_b = lines_a.copy()
        lines_b[10] = "changed_line10"
        lines_b[50] = "changed_line50"
        lines_b[80] = "changed_line80"
        with open(a, "w") as f:
            f.write("\n".join(lines_a))
        with open(b, "w") as f:
            f.write("\n".join(lines_b))

        result = file_tools_diff(a, b, start=2, count=1)
        assert "第 2" in result or "changed" in result

    def test_max_chars(self, tmp_dir):
        a = os.path.join(tmp_dir, "a.txt")
        b = os.path.join(tmp_dir, "b.txt")
        with open(a, "w") as f:
            f.write("a\n" * 1000)
        with open(b, "w") as f:
            f.write("b\n" * 1000)
        result = file_tools_diff(a, b, max_chars=100)
        assert "<<truncated>>" in result or len(result) <= 150

    def test_start_lt_1(self, tmp_dir):
        """diff 的 start<1 应报错"""
        a = os.path.join(tmp_dir, "a.txt")
        b = os.path.join(tmp_dir, "b.txt")
        with open(a, "w", encoding="utf-8") as f:
            f.write("hello\nworld\n")
        with open(b, "w", encoding="utf-8") as f:
            f.write("hello\nuniverse\n")
        result = file_tools_diff(a, b, start=0)
        assert "失败" in result
        assert "start" in result
        assert "。。" not in result  # 无双句号

    def test_count_lt_1(self, tmp_dir):
        """diff 的 count<1 应报错"""
        a = os.path.join(tmp_dir, "a.txt")
        b = os.path.join(tmp_dir, "b.txt")
        with open(a, "w", encoding="utf-8") as f:
            f.write("hello\nworld\n")
        with open(b, "w", encoding="utf-8") as f:
            f.write("hello\nuniverse\n")
        result = file_tools_diff(a, b, count=0)
        assert "失败" in result
        assert "count" in result

    def test_start_gt_total_hunks(self, tmp_dir):
        """diff 的 start>total_hunks 应报错"""
        a = os.path.join(tmp_dir, "a.txt")
        b = os.path.join(tmp_dir, "b.txt")
        with open(a, "w", encoding="utf-8") as f:
            f.write("hello\nworld\n")
        with open(b, "w", encoding="utf-8") as f:
            f.write("hello\nuniverse\n")
        result = file_tools_diff(a, b, start=999)
        assert "失败" in result
        assert "超出" in result


class TestHistory:
    def test_no_history(self, tmp_file):
        result = file_tools_history(tmp_file)
        data = json.loads(result)
        assert data["history"] == []

    def test_nonexistent(self):
        result = file_tools_history("/nonexistent_xyz")
        data = json.loads(result)
        assert "error" in data

    def test_after_modifications(self, tmp_file):
        """多次修改文件后，历史记录应包含对应版本。"""
        from tools.edit import file_tools_append, file_tools_replace_lines

        file_tools_append(tmp_file, "new_line\n")
        file_tools_replace_lines(tmp_file, 1, 1, "modified\n")
        result = file_tools_history(tmp_file)
        data = json.loads(result)
        assert len(data["history"]) >= 2
        for entry in data["history"]:
            assert "number" in entry or "history_number" in entry
            assert "created_at" in entry
