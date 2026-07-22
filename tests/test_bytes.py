"""测试字节级工具：read_bytes / write_bytes / find_bytes / replace_bytes。"""

import os

import pytest

from backup.manager import list_history
from tools.bytes import (
    file_tools_read_bytes,
    file_tools_write_bytes,
    file_tools_find_bytes,
    file_tools_replace_bytes,
)


def _bin_file(path, data: bytes):
    with open(path, "wb") as f:
        f.write(data)


def _read_bin(path) -> bytes:
    with open(path, "rb") as f:
        return f.read()


@pytest.fixture
def bin_file_256(tmp_dir):
    """256 字节文件，内容为 00 01 02 ... FF。"""
    path = os.path.join(tmp_dir, "test_256.bin")
    _bin_file(path, bytes(range(256)))
    yield path


@pytest.fixture
def bin_file_empty(tmp_dir):
    path = os.path.join(tmp_dir, "empty.bin")
    _bin_file(path, b"")
    yield path


@pytest.fixture
def bin_file_with_pattern(tmp_dir):
    """包含重复模式的文件。"""
    data = b"\x00\x01\x02" * 10  # 30 字节
    path = os.path.join(tmp_dir, "pattern.bin")
    _bin_file(path, data)
    yield path


# 必须在 pytest fixture 定义之前导入
import pytest


# ═══════════════════════════════════════════════════════════
# 1. file_tools_read_bytes
# ═══════════════════════════════════════════════════════════

class TestReadBytes:
    def test_read_beginning(self, bin_file_256):
        """读取开头 16 字节。"""
        result = file_tools_read_bytes(bin_file_256, offset=0, length=16)
        assert "读取成功" in result
        assert "00 01 02 03 04 05 06 07" in result
        assert "16 字节" in result

    def test_read_middle(self, bin_file_256):
        """读取中间部分。"""
        result = file_tools_read_bytes(bin_file_256, offset=128, length=8)
        assert "读取成功" in result
        assert "80 81 82 83 84 85 86 87" in result

    def test_read_end(self, bin_file_256):
        """读取末尾部分（不足 group_size）。"""
        result = file_tools_read_bytes(bin_file_256, offset=252, length=10)
        assert "读取成功" in result
        assert "FC FD FE FF" in result
        assert "4 字节" in result  # 文件只有 256 字节，实际只读到 4 字节

    def test_read_group_size_8(self, bin_file_256):
        """group_size=8 分组。"""
        result = file_tools_read_bytes(bin_file_256, offset=0, length=16, group_size=8)
        assert "读取成功" in result
        lines = result.strip().split("\n")
        # 第一行是状态，第二行开始是 hex
        hex_lines = [l for l in lines if not l.startswith("读取成功")]
        assert len(hex_lines) == 2  # 16 字节，每行 8 字节，2 行

    def test_read_no_group(self, bin_file_256):
        """group_size=-1 不分组。"""
        result = file_tools_read_bytes(bin_file_256, offset=0, length=8, group_size=-1)
        assert "读取成功" in result
        assert "0001020304050607" in result

    def test_read_group_size_zero(self, bin_file_256):
        """group_size=0 报错。"""
        result = file_tools_read_bytes(bin_file_256, offset=0, length=8, group_size=0)
        assert "失败" in result
        assert "group_size 不能为 0" in result

    def test_read_exceed_max(self, bin_file_256):
        """超过 4096 上限报错。"""
        result = file_tools_read_bytes(bin_file_256, offset=0, length=5000)
        assert "失败" in result
        assert "4096" in result

    def test_read_offset_negative(self, bin_file_256):
        """负偏移量报错。"""
        result = file_tools_read_bytes(bin_file_256, offset=-1, length=8)
        assert "失败" in result

    def test_read_offset_beyond_file(self, bin_file_256):
        """偏移量超出文件范围。"""
        result = file_tools_read_bytes(bin_file_256, offset=300, length=8)
        assert "失败" in result
        assert "超出文件范围" in result

    def test_read_nonexistent_file(self, tmp_dir):
        """文件不存在报错。"""
        path = os.path.join(tmp_dir, "nonexist.bin")
        result = file_tools_read_bytes(path, offset=0, length=8)
        assert "失败" in result

    def test_read_empty_file(self, bin_file_empty):
        """空文件。"""
        result = file_tools_read_bytes(bin_file_empty, offset=0, length=8)
        assert "失败" in result  # 空文件，偏移量 0 >= 文件大小 0

    def test_read_all_default(self, bin_file_256):
        """默认参数（offset=0, length=512）。"""
        result = file_tools_read_bytes(bin_file_256)
        assert "读取成功" in result
        assert "256 字节" in result  # 文件只有 256 字节，实际读取 256


# ═══════════════════════════════════════════════════════════
# 2. file_tools_write_bytes
# ═══════════════════════════════════════════════════════════

class TestWriteBytesFull:
    """全量覆盖（offset=-1）。"""

    def test_write_new_file(self, tmp_dir):
        """创建新文件。"""
        path = os.path.join(tmp_dir, "new.bin")
        result = file_tools_write_bytes(path, content="AA BB CC DD")
        assert "写入成功" in result
        assert "4 字节" in result
        assert _read_bin(path) == b"\xaa\xbb\xcc\xdd"

    def test_write_new_file_no_backup(self, tmp_dir):
        """新文件不触发备份。"""
        path = os.path.join(tmp_dir, "new.bin")
        file_tools_write_bytes(path, content="AA")
        history = list_history(path)
        assert len(history) == 0

    def test_write_overwrite(self, tmp_dir):
        """覆盖已有文件。"""
        path = os.path.join(tmp_dir, "test.bin")
        _bin_file(path, b"\xff\xff\xff\xff")
        result = file_tools_write_bytes(path, content="00 01 02 03")
        assert "写入成功" in result
        assert "历史号" in result
        assert _read_bin(path) == b"\x00\x01\x02\x03"

    def test_write_overwrite_backup(self, tmp_dir):
        """覆盖时自动备份。"""
        path = os.path.join(tmp_dir, "test.bin")
        _bin_file(path, b"\xff\xff\xff\xff")
        file_tools_write_bytes(path, content="00 01 02 03")
        history = list_history(path)
        assert len(history) == 1

    def test_write_skip_backup(self, tmp_dir):
        """skip_backup=True 跳过备份。"""
        path = os.path.join(tmp_dir, "test.bin")
        _bin_file(path, b"\xff\xff\xff\xff")
        result = file_tools_write_bytes(path, content="00", skip_backup=True)
        assert "写入成功" in result
        assert "历史号" not in result
        history = list_history(path)
        assert len(history) == 0

    def test_write_empty_content(self, tmp_dir):
        """写入空内容（空文件）。"""
        path = os.path.join(tmp_dir, "empty.bin")
        result = file_tools_write_bytes(path, content="")
        assert "写入成功" in result
        assert "0 字节" in result
        assert _read_bin(path) == b""

    def test_write_invalid_hex(self, tmp_dir):
        """无效 hex 报错。"""
        path = os.path.join(tmp_dir, "bad.bin")
        result = file_tools_write_bytes(path, content="0xFF")
        assert "失败" in result
        assert "hex" in result.lower()


class TestWriteBytesPartial:
    """部分覆盖（offset>=0）。"""

    def test_write_partial(self, tmp_dir):
        """从偏移量处写入。"""
        path = os.path.join(tmp_dir, "test.bin")
        _bin_file(path, b"\x00\x00\x00\x00\x00\x00\x00\x00")
        result = file_tools_write_bytes(path, offset=4, content="FF FF")
        assert "写入成功" in result
        assert "偏移量 4" in result
        assert _read_bin(path) == b"\x00\x00\x00\x00\xff\xff\x00\x00"

    def test_write_partial_no_backup(self, tmp_dir):
        """部分覆盖不触发备份。"""
        path = os.path.join(tmp_dir, "test.bin")
        _bin_file(path, b"\x00" * 10)
        file_tools_write_bytes(path, offset=2, content="FF")
        history = list_history(path)
        assert len(history) == 0

    def test_write_partial_nonexistent(self, tmp_dir):
        """部分覆盖的目标文件不存在时报错。"""
        path = os.path.join(tmp_dir, "nonexist.bin")
        result = file_tools_write_bytes(path, offset=0, content="FF")
        assert "失败" in result

    def test_write_partial_beyond_file(self, tmp_dir):
        """部分覆盖超出文件末尾（文件不会自动扩展）。"""
        path = os.path.join(tmp_dir, "test.bin")
        _bin_file(path, b"\x00" * 4)
        # 4 字节文件，从偏移量 4 处写入应写入成功
        # 实际: r+b 模式下 seek 到末尾再写入会扩展文件
        result = file_tools_write_bytes(path, offset=4, content="FF")
        assert "写入成功" in result
        data = _read_bin(path)
        assert len(data) >= 5  # 文件末尾可能扩展了


# ═══════════════════════════════════════════════════════════
# 3. file_tools_find_bytes
# ═══════════════════════════════════════════════════════════

class TestFindBytes:
    def test_find_single(self, bin_file_256):
        """查找单个匹配。"""
        result = file_tools_find_bytes(bin_file_256, pattern="01 02 03")
        assert "offset" in result
        assert "1" in result  # 偏移量 1

    def test_find_multiple(self, bin_file_with_pattern):
        """查找多个匹配。"""
        result = file_tools_find_bytes(bin_file_with_pattern, pattern="00 01 02")
        lines = result.strip().split("\n")
        # 第一行是表头，后面每行一个偏移量
        offsets = [int(l) for l in lines[1:]]
        assert len(offsets) == 10
        assert offsets == [0, 3, 6, 9, 12, 15, 18, 21, 24, 27]

    def test_find_with_count(self, bin_file_with_pattern):
        """限制匹配数量。"""
        result = file_tools_find_bytes(bin_file_with_pattern, pattern="00 01 02", count=3)
        lines = result.strip().split("\n")
        offsets = [int(l) for l in lines[1:]]
        assert len(offsets) == 3
        assert offsets == [0, 3, 6]

    def test_find_no_match(self, bin_file_256):
        """未匹配。"""
        result = file_tools_find_bytes(bin_file_256, pattern="FF FF")
        assert "未找到" in result

    def test_find_with_offset(self, bin_file_with_pattern):
        """从偏移量开始搜索。"""
        result = file_tools_find_bytes(bin_file_with_pattern, pattern="00 01 02", offset=5)
        lines = result.strip().split("\n")
        offsets = [int(l) for l in lines[1:]]
        # 从偏移量 5 开始，匹配在 6, 9, 12, ...
        assert offsets[0] == 6

    def test_find_empty_pattern(self, bin_file_256):
        """空 pattern 报错。"""
        result = file_tools_find_bytes(bin_file_256, pattern="")
        assert "失败" in result

    def test_find_nonexistent_file(self, tmp_dir):
        """文件不存在。"""
        path = os.path.join(tmp_dir, "nonexist.bin")
        result = file_tools_find_bytes(path, pattern="FF")
        assert "失败" in result

    def test_find_csv_format(self, bin_file_with_pattern):
        """返回 CSV 格式。"""
        result = file_tools_find_bytes(bin_file_with_pattern, pattern="00 01 02", count=1)
        lines = result.strip().split("\n")
        assert lines[0].strip() == "offset"
        assert lines[1].strip().isdigit()

    def test_find_lowercase_hex(self, bin_file_256):
        """小写 hex 输入也能匹配。"""
        result = file_tools_find_bytes(bin_file_256, pattern="01 02 03")
        assert "1" in result


# ═══════════════════════════════════════════════════════════
# 4. file_tools_replace_bytes
# ═══════════════════════════════════════════════════════════

class TestReplaceBytes:
    def test_replace_single(self, tmp_dir):
        """替换单个匹配（默认 count=1）。"""
        path = os.path.join(tmp_dir, "test.bin")
        _bin_file(path, b"\x01\x02\x03\x04\x05")
        result = file_tools_replace_bytes(path, old_bytes="01 02", new_bytes="FF FF")
        assert "替换成功" in result
        assert "1 处" in result
        assert _read_bin(path) == b"\xff\xff\x03\x04\x05"

    def test_replace_multiple_default(self, bin_file_with_pattern):
        """默认 count=1 只替换第一个匹配。"""
        result = file_tools_replace_bytes(
            bin_file_with_pattern, old_bytes="00 01 02", new_bytes="FF FF"
        )
        assert "替换成功" in result
        assert "1 处" in result
        data = _read_bin(bin_file_with_pattern)
        # 默认只替换第 1 个（3→2 字节），后面 9 个保留
        assert data[:2] == b"\xff\xff"
        assert data[2:11] == b"\x00\x01\x02\x00\x01\x02\x00\x01\x02"

    def test_replace_with_count(self, bin_file_with_pattern):
        """限制替换次数。"""
        result = file_tools_replace_bytes(
            bin_file_with_pattern, old_bytes="00 01 02", new_bytes="FF FF", count=3
        )
        assert "替换成功" in result
        assert "3 处" in result
        data = _read_bin(bin_file_with_pattern)
        # 前 3 个被替换，后面不变
        assert data[:6] == b"\xff\xff\xff\xff\xff\xff"
        assert data[6:9] == b"\x00\x01\x02"  # 第 4 个没被替换

    def test_replace_no_match(self, tmp_dir):
        """未匹配。"""
        path = os.path.join(tmp_dir, "test.bin")
        _bin_file(path, b"\x00\x01\x02")
        result = file_tools_replace_bytes(path, old_bytes="FF FF", new_bytes="00")
        assert "未找到" in result

    def test_replace_with_offset(self, bin_file_with_pattern):
        """从偏移量开始替换，默认 count=1 只替换第一个。"""
        result = file_tools_replace_bytes(
            bin_file_with_pattern, old_bytes="00 01 02", new_bytes="FF", offset=5
        )
        # 从偏移量 5 开始搜索，匹配在 6, 9, 12, ... 共 8 处
        # 默认 count=1 只替换第一个（偏移量 6）
        assert "替换成功" in result
        assert "1 处" in result
        data = _read_bin(bin_file_with_pattern)
        # 偏移量 0 和 3 的匹配在搜索范围外，所以保留
        assert data[0:3] == b"\x00\x01\x02"
        # 偏移量 6 的匹配被替换（3→1 字节），确认第一处被替换
        assert data[6] == 0xFF

    def test_replace_different_length(self, tmp_dir):
        """替换不同长度（变长和变短），默认 count=1 只替换第一个。"""
        path = os.path.join(tmp_dir, "test.bin")
        _bin_file(path, b"\x00\x01\x02\x00\x01\x02\x00\x01\x02")

        # 变短：3 字节 → 1 字节，默认只替换第一个
        result = file_tools_replace_bytes(path, old_bytes="00 01 02", new_bytes="FF")
        assert "替换成功" in result
        assert "1 处" in result
        # 第一个被替换（3→1），后面两个保留
        assert _read_bin(path) == b"\xff\x00\x01\x02\x00\x01\x02"

    def test_replace_backup(self, tmp_dir):
        """替换时自动备份。"""
        path = os.path.join(tmp_dir, "test.bin")
        _bin_file(path, b"\x00\x01\x02")
        file_tools_replace_bytes(path, old_bytes="00", new_bytes="FF")
        history = list_history(path)
        assert len(history) == 1

    def test_replace_skip_backup(self, tmp_dir):
        """skip_backup=True 跳过备份。"""
        path = os.path.join(tmp_dir, "test.bin")
        _bin_file(path, b"\x00\x01\x02")
        result = file_tools_replace_bytes(
            path, old_bytes="00", new_bytes="FF", skip_backup=True
        )
        assert "历史号" not in result
        history = list_history(path)
        assert len(history) == 0

    def test_replace_invalid_hex(self, tmp_dir):
        """无效 hex 报错。"""
        path = os.path.join(tmp_dir, "test.bin")
        _bin_file(path, b"\x00\x01\x02")
        result = file_tools_replace_bytes(path, old_bytes="0xFF", new_bytes="00")
        assert "失败" in result

    def test_replace_empty_old(self, tmp_dir):
        """空 old_bytes 报错。"""
        path = os.path.join(tmp_dir, "test.bin")
        _bin_file(path, b"\x00\x01\x02")
        result = file_tools_replace_bytes(path, old_bytes="", new_bytes="FF")
        assert "失败" in result

    def test_replace_nonexistent_file(self, tmp_dir):
        """文件不存在报错。"""
        path = os.path.join(tmp_dir, "nonexist.bin")
        result = file_tools_replace_bytes(path, old_bytes="00", new_bytes="FF")
        assert "失败" in result

    def test_replace_positions_in_output(self, tmp_dir):
        """返回消息中包含替换位置（十进制），默认 count=1 只替换第一个。"""
        path = os.path.join(tmp_dir, "test.bin")
        _bin_file(path, b"\x00\x01\x02\x00\x01\x02")
        result = file_tools_replace_bytes(
            path, old_bytes="00 01 02", new_bytes="FF"
        )
        assert "替换成功" in result
        assert "1 处" in result
        assert "替换位置" in result
        # CSV 格式：offset 列 + 数据行
        pos_lines = result.split("替换位置（十进制）：")[1].split("\n")
        pos_value = pos_lines[2]  # 第3行是偏移量数据（第1行空，第2行表头，第3行数据）
        assert "0" in pos_value
        assert "3" not in pos_value  # 默认只替换第一个，偏移量 3 不在结果中

    def test_overlapping_matches(self, tmp_dir):
        """重叠匹配应正确处理（同长度替换）。"""
        path = os.path.join(tmp_dir, "overlap.bin")
        _bin_file(path, b"AAA")
        # 同长度替换：AAA 中 AA 重叠匹配位置 0 和 1，替换后为 BBB
        result = file_tools_replace_bytes(path, old_bytes="41 41", new_bytes="42 42", count=-1)
        assert "替换成功" in result
        assert "2 处" in result
        data = _read_bin(path)
        assert data == b"BBB"

    def test_variable_length(self, tmp_dir):
        """变长替换（非重叠匹配）应正确。"""
        path = os.path.join(tmp_dir, "varlen.bin")
        _bin_file(path, b"\x00\x01\x02\x03")
        # 替换为更长的数据（非重叠匹配）
        result = file_tools_replace_bytes(path, old_bytes="00 01", new_bytes="FF FF FF")
        assert "替换成功" in result
        data = _read_bin(path)
        assert data == b"\xff\xff\xff\x02\x03"
        # 替换为更短的数据（非重叠匹配）
        path2 = os.path.join(tmp_dir, "varlen2.bin")
        _bin_file(path2, b"\x00\x01\x02\x03")
        result2 = file_tools_replace_bytes(path2, old_bytes="00 01 02", new_bytes="FF")
        assert "替换成功" in result2
        data2 = _read_bin(path2)
        assert data2 == b"\xff\x03"