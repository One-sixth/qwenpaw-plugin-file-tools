"""测试安全文件操作类工具。"""

import os

import pytest

from tools.safe import (
    file_tools_copy,
    file_tools_mkdir,
    file_tools_move,
    file_tools_trash,
    file_tools_trash_undo,
)


class TestCopy:
    def test_copy_file(self, tmp_file, tmp_dir):
        dst = os.path.join(tmp_dir, "copied.txt")
        result = file_tools_copy(tmp_file, dst)
        assert "已复制" in result
        assert os.path.isfile(dst)

    def test_copy_nonexistent(self, tmp_dir):
        result = file_tools_copy("/nonexistent_xyz", os.path.join(tmp_dir, "dest.txt"))
        assert "失败" in result

    def test_copy_overwrite_false(self, tmp_file, tmp_dir):
        dst = os.path.join(tmp_dir, "dest.txt")
        with open(dst, "w") as f:
            f.write("existing")
        result = file_tools_copy(tmp_file, dst, overwrite=False)
        assert "失败" in result
        assert "已存在" in result

    def test_copy_overwrite_true(self, tmp_file, tmp_dir):
        dst = os.path.join(tmp_dir, "dest.txt")
        with open(dst, "w") as f:
            f.write("existing")
        result = file_tools_copy(tmp_file, dst, overwrite=True)
        assert "已复制" in result

    def test_copy_directory(self, subdir_structure, tmp_dir):
        dst = os.path.join(tmp_dir, "copied_dir")
        result = file_tools_copy(subdir_structure, dst)
        assert "已复制" in result
        assert os.path.isdir(dst)

    def test_copy_file_content(self, tmp_file, tmp_dir):
        dst = os.path.join(tmp_dir, "content_check.txt")
        file_tools_copy(tmp_file, dst)
        with open(tmp_file, "r") as f:
            original = f.read()
        with open(dst, "r") as f:
            copied = f.read()
        assert original == copied

    def test_copy_directory_recursive(self, subdir_structure, tmp_dir):
        dst = os.path.join(tmp_dir, "recursive_copy")
        file_tools_copy(subdir_structure, dst)
        assert os.path.isfile(os.path.join(dst, "file_a.txt"))
        assert os.path.isdir(os.path.join(dst, "dir_a"))

    def test_copy_to_nonexistent_dir(self, tmp_file, tmp_dir):
        """复制到不存在的目录应自动创建"""
        dst = os.path.join(tmp_dir, "new_sub", "nested", "file.txt")
        result = file_tools_copy(tmp_file, dst)
        assert "已复制" in result
        assert os.path.isfile(dst)
        assert os.path.isdir(os.path.join(tmp_dir, "new_sub", "nested"))

    def test_copy_src_eq_dst(self, tmp_file):
        """src==dst 时应返回提示而非崩溃"""
        result = file_tools_copy(tmp_file, tmp_file)
        assert "相同" in result
        assert "无需操作" in result


class TestMove:
    def test_move_file(self, tmp_file, tmp_dir):
        dst = os.path.join(tmp_dir, "moved.txt")
        result = file_tools_move(tmp_file, dst)
        assert "已移动" in result
        assert os.path.isfile(dst)
        assert not os.path.isfile(tmp_file)

    def test_move_nonexistent(self, tmp_dir):
        result = file_tools_move("/nonexistent_xyz", os.path.join(tmp_dir, "dest.txt"))
        assert "失败" in result

    def test_move_overwrite_false(self, tmp_dir):
        src = os.path.join(tmp_dir, "src.txt")
        dst = os.path.join(tmp_dir, "dst.txt")
        with open(src, "w") as f:
            f.write("source")
        with open(dst, "w") as f:
            f.write("dest")
        result = file_tools_move(src, dst, overwrite=False)
        assert "失败" in result

    def test_move_overwrite_true(self, tmp_dir):
        src = os.path.join(tmp_dir, "src.txt")
        dst = os.path.join(tmp_dir, "dst.txt")
        with open(src, "w") as f:
            f.write("source")
        with open(dst, "w") as f:
            f.write("dest")
        result = file_tools_move(src, dst, overwrite=True)
        assert "已移动" in result
        assert os.path.isfile(dst)

    def test_rename(self, tmp_dir):
        src = os.path.join(tmp_dir, "old_name.txt")
        dst = os.path.join(tmp_dir, "new_name.txt")
        with open(src, "w") as f:
            f.write("rename test")
        file_tools_move(src, dst)
        assert os.path.isfile(dst)
        assert not os.path.isfile(src)

    def test_move_src_eq_dst(self, tmp_dir):
        """src==dst 时应返回提示而非崩溃"""
        src = os.path.join(tmp_dir, "same.txt")
        with open(src, "w") as f:
            f.write("test")
        result = file_tools_move(src, src)
        assert "相同" in result
        assert "无需操作" in result

    def test_move_to_nonexistent_dir(self, tmp_file, tmp_dir):
        """移动到不存在的目录应自动创建（与 copy 行为一致）"""
        dst = os.path.join(tmp_dir, "new_sub", "nested", "moved.txt")
        result = file_tools_move(tmp_file, dst)
        assert "已移动" in result
        assert os.path.isfile(dst)
        assert os.path.isdir(os.path.join(tmp_dir, "new_sub", "nested"))


class TestMkdir:
    def test_create(self, tmp_dir):
        new_dir = os.path.join(tmp_dir, "new_dir")
        result = file_tools_mkdir(new_dir)
        assert "已创建目录" in result
        assert os.path.isdir(new_dir)

    def test_exists(self, tmp_dir):
        result = file_tools_mkdir(tmp_dir)
        assert "已存在" in result

    def test_nested(self, tmp_dir):
        nested = os.path.join(tmp_dir, "a", "b", "c")
        result = file_tools_mkdir(nested)
        assert "已创建目录" in result
        assert os.path.isdir(nested)

    def test_invalid_path(self):
        result = file_tools_mkdir("")
        assert "失败" in result
        assert "不能为空" in result


class TestTrash:
    def test_trash_file(self, tmp_file):
        assert os.path.isfile(tmp_file)
        result = file_tools_trash(tmp_file)
        assert "放入回收站" in result or "失败" in result

    def test_trash_nonexistent(self):
        result = file_tools_trash("/nonexistent_xyz")
        assert "失败" in result

    def test_trash_directory(self, tmp_dir):
        result = file_tools_trash(tmp_dir)
        assert "放入回收站" in result or "失败" in result

    def test_trash_undo_no_entry(self):
        result = file_tools_trash_undo("/nonexistent_path_xyz")
        assert "失败" in result
        assert "回收站中未找到" in result
