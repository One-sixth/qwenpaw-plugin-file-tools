"""测试信息读取类工具。"""

import csv
import io
import json
import os

from tools.info import (
    file_tools_diff,
    file_tools_guess,
    file_tools_history,
    file_tools_info,
    file_tools_listdir,
)


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
        assert "name" in result
        assert "size" in result
        assert "type" in result

    def test_recursive_2(self, subdir_structure):
        result = file_tools_listdir(subdir_structure, recursive=2)
        assert "sub_file1.txt" in result
        assert "sub_file2.txt" in result
        assert "file_a.txt" in result
        assert ".hidden" in result

    def test_recursive_minus1(self, subdir_structure):
        result = file_tools_listdir(subdir_structure, recursive=-1)
        assert "sub_file1.txt" in result
        assert "sub_file2.txt" in result
        assert "sub_dir1" in result

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
        open(os.path.join(tmp_dir, "z_last.txt"), "w").close()
        os.makedirs(os.path.join(tmp_dir, "a_dir"))
        open(os.path.join(tmp_dir, "b_file.txt"), "w").close()
        result = file_tools_listdir(tmp_dir, recursive=1)
        assert "name" in result

    def test_csv_format(self, tmp_dir):
        open(os.path.join(tmp_dir, "normal.csv"), "w").close()
        result = file_tools_listdir(tmp_dir, recursive=1)
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) >= 1
        assert "name" in rows[0]

    def test_empty_dir(self, tmp_dir):
        result = file_tools_listdir(tmp_dir, recursive=1)
        assert len(result.strip().split("\n")) >= 1

    def test_permission_column(self, tmp_dir):
        open(os.path.join(tmp_dir, "perm.txt"), "w").close()
        result = file_tools_listdir(tmp_dir, recursive=1, columns=["permissions"])
        assert "permissions" in result


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
        data = json.loads(result)
        assert data["exists"] is False

    def test_fields(self, tmp_file):
        result = file_tools_info(tmp_file)
        data = json.loads(result)
        assert "permissions" in data
        assert "created_at" in data
        assert "modified_at" in data

    def test_json_format(self, tmp_file):
        result = file_tools_info(tmp_file)
        json.loads(result)


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


class TestHistory:
    def test_no_history(self, tmp_file):
        result = file_tools_history(tmp_file)
        data = json.loads(result)
        assert data["history"] == []

    def test_nonexistent(self):
        result = file_tools_history("/nonexistent_xyz")
        data = json.loads(result)
        assert "error" in data
