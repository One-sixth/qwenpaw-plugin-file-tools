"""测试全量写入工具 file_tools_write。"""

import os

from backup.manager import list_history
from tools.write import file_tools_write


def _read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestWriteNewFile:
    """测试创建新文件。"""

    def test_create_new(self, tmp_dir):
        path = os.path.join(tmp_dir, "new.txt")
        result = file_tools_write(path, "hello\nworld")
        assert "成功写入文件" in result
        assert "共 11 个字符" in result
        assert "2 行" in result
        assert _read_file(path) == "hello\nworld"

    def test_create_new_empty(self, tmp_dir):
        path = os.path.join(tmp_dir, "empty.txt")
        result = file_tools_write(path, "")
        assert "成功写入文件" in result
        assert "0 个字符" in result
        assert "0 行" in result
        assert _read_file(path) == ""

    def test_create_new_chinese(self, tmp_dir):
        path = os.path.join(tmp_dir, "chinese.txt")
        result = file_tools_write(path, "你好世界")
        assert "成功写入文件" in result
        assert _read_file(path) == "你好世界"

    def test_new_file_no_backup(self, tmp_dir):
        """新文件不触发备份。"""
        path = os.path.join(tmp_dir, "new.txt")
        file_tools_write(path, "content")
        history = list_history(path)
        assert len(history) == 0

    def test_create_new_crlf(self, tmp_dir):
        path = os.path.join(tmp_dir, "crlf.txt")
        result = file_tools_write(path, "line1\nline2", line_separator="\\r\\n")
        assert "成功写入文件" in result
        with open(path, "rb") as f:
            raw = f.read()
        assert raw == b"line1\r\nline2"


class TestWriteOverwrite:
    """测试覆盖已有文件。"""

    def test_overwrite(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("old content")
        result = file_tools_write(path, "new content")
        assert "成功写入文件" in result
        assert "历史号" in result
        assert _read_file(path) == "new content"

    def test_overwrite_backup_created(self, tmp_dir):
        """覆盖时自动备份。"""
        path = os.path.join(tmp_dir, "test.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("old content")
        file_tools_write(path, "new content")
        history = list_history(path)
        assert len(history) == 1

    def test_overwrite_multiple_backups(self, tmp_dir):
        """多次覆盖，每次都有备份。"""
        path = os.path.join(tmp_dir, "test.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("v1")
        file_tools_write(path, "v2")
        file_tools_write(path, "v3")
        history = list_history(path)
        assert len(history) == 2

    def test_overwrite_larger_content(self, tmp_dir):
        """覆盖时写入更大的内容。"""
        path = os.path.join(tmp_dir, "test.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("short")
        result = file_tools_write(path, "a" * 1000)
        assert "成功写入文件" in result
        assert "1000 个字符" in result
        assert len(_read_file(path)) == 1000

    def test_overwrite_empty_content(self, tmp_dir):
        """覆盖为空内容。"""
        path = os.path.join(tmp_dir, "test.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("old")
        result = file_tools_write(path, "")
        assert "成功写入文件" in result
        assert _read_file(path) == ""


class TestWriteEncoding:
    """测试编码参数。"""

    def test_gbk_encoding(self, tmp_dir):
        path = os.path.join(tmp_dir, "gbk.txt")
        file_tools_write(path, "你好", encoding="gbk")
        with open(path, "rb") as f:
            raw = f.read()
        # GBK 编码下"你好"是 4 字节
        assert len(raw) == 4

    def test_utf8_default(self, tmp_dir):
        path = os.path.join(tmp_dir, "utf8.txt")
        file_tools_write(path, "你好")
        with open(path, "rb") as f:
            raw = f.read()
        # UTF-8 编码下"你好"是 6 字节
        assert len(raw) == 6


class TestWriteLineSeparator:
    """测试 line_separator 参数。"""

    def test_auto_lf(self, tmp_dir):
        path = os.path.join(tmp_dir, "auto.txt")
        file_tools_write(path, "a\nb", line_separator="auto")
        with open(path, "rb") as f:
            raw = f.read()
        # Windows 上 auto 会转为 \r\n
        assert raw == b"a\r\nb" or raw == b"a\nb"

    def test_explicit_lf(self, tmp_dir):
        path = os.path.join(tmp_dir, "lf.txt")
        file_tools_write(path, "a\nb", line_separator="\\n")
        with open(path, "rb") as f:
            raw = f.read()
        assert raw == b"a\nb"

    def test_explicit_crlf(self, tmp_dir):
        path = os.path.join(tmp_dir, "crlf.txt")
        file_tools_write(path, "a\nb", line_separator="\\r\\n")
        with open(path, "rb") as f:
            raw = f.read()
        assert raw == b"a\r\nb"

    def test_invalid_separator(self, tmp_dir):
        """line_separator 传非法值应报错"""
        path = os.path.join(tmp_dir, "bad.txt")
        result = file_tools_write(path, "content", line_separator="invalid")
        assert "失败" in result
    """测试错误处理。"""

    def test_invalid_path(self):
        """路径不存在时的行为（父目录不存在）。"""
        result = file_tools_write("/nonexistent_dir/file.txt", "content")
        # 应该报错
        assert "失败" in result or "出错" in result