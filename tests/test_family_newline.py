"""v1.7.0 家族行尾保真钉测（作者裁决：auto=保持目标主行尾，推广自 copy_lines）。

覆盖 6 个读改写工具 + file_tools_write；append 为有意例外（auto=OS），
末尾单独钉住口径防"顺手统一"。
"""

import os

import pytest

from tools.edit import (
    file_tools_append,
    file_tools_delete_lines,
    file_tools_indent_lines,
    file_tools_insert_lines,
    file_tools_regex_replace,
    file_tools_replace,
    file_tools_replace_lines,
)
from tools.write import file_tools_write

OS_NL = os.linesep


def _text(result):
    return result.content[0].text


def _make(path, raw: bytes):
    with open(path, "wb") as f:
        f.write(raw)
    return path


def _bytes(path):
    with open(path, "rb") as f:
        return f.read()


# 每种行尾的基线内容（逻辑行 A1/A2/A3 + 规范结尾）
LF = b"A1\nA2\nA3\n"
CRLF = b"A1\r\nA2\r\nA3\r\n"
CR = b"A1\rA2\rA3\r"
MIXED_CRLF = b"A1\r\nA2\r\nA3\n"  # CRLF 占多数

# 各工具的最小可执行编辑（作用于 A1/A2/A3 基线）
EDITS = {
    "replace_lines": lambda p, **kw: file_tools_replace_lines(p, 1, 1, "X", **kw),
    "insert_lines": lambda p, **kw: file_tools_insert_lines(p, 2, "X", **kw),
    "delete_lines": lambda p, **kw: file_tools_delete_lines(p, 2, 2, **kw),
    "replace": lambda p, **kw: file_tools_replace(p, "A1", "X", **kw),
    "regex_replace": lambda p, **kw: file_tools_regex_replace(p, r"A1", "X", **kw),
    "indent_lines": lambda p, **kw: file_tools_indent_lines(p, **kw),
}
EDIT_IDS = list(EDITS)


@pytest.fixture(params=EDIT_IDS)
def edit(request):
    return EDITS[request.param]


class TestRmwFidelity:
    """读改写 6 工具：auto 编辑不得白改行尾。"""

    def test_lf_preserved(self, tmp_dir, edit):
        p = _make(os.path.join(tmp_dir, "f.txt"), LF)
        assert "成功" in _text(edit(p))
        assert b"\r" not in _bytes(p)

    def test_crlf_preserved(self, tmp_dir, edit):
        p = _make(os.path.join(tmp_dir, "f.txt"), CRLF)
        edit(p)
        raw = _bytes(p)
        assert b"\r\r" not in raw
        # 换行全部为 CRLF：不残留独立 \n
        assert b"\n" not in raw.replace(b"\r\n", b"")
        assert raw.count(b"\r\n") >= 2

    def test_cr_preserved(self, tmp_dir, edit):
        p = _make(os.path.join(tmp_dir, "f.txt"), CR)
        edit(p)
        raw = _bytes(p)
        assert b"\n" not in raw, raw  # 老麦文件编辑后仍无 LF
        assert raw.count(b"\r") >= 2

    def test_mixed_folds_to_dominant(self, tmp_dir, edit):
        p = _make(os.path.join(tmp_dir, "f.txt"), MIXED_CRLF)
        edit(p)
        raw = _bytes(p)
        assert b"\r\r" not in raw
        assert b"\n" not in raw.replace(b"\r\n", b"")  # 统一为多数者 CRLF


class TestExplicitSeparatorsUnchanged:
    """显式 \\n / \\r\\n 参数优先，不受保真影响。"""

    @pytest.mark.parametrize("sep", ["\\n", "\\r\\n"])
    def test_forced_beats_file_dominant(self, tmp_dir, edit, sep):
        src = CRLF if sep == "\\n" else LF
        p = _make(os.path.join(tmp_dir, "f.txt"), src)
        edit(p, line_separator=sep)
        raw = _bytes(p)
        if sep == "\\n":
            assert b"\r" not in raw
        else:
            assert b"\r\r" not in raw
            assert b"\n" not in raw.replace(b"\r\n", b"")
            assert raw.count(b"\r\n") >= 2


class TestEmptyAndFresh:
    """空文件/探测不到行尾 → 落回 OS 口径。"""

    def test_replace_lines_on_empty_uses_os(self, tmp_dir):
        p = _make(os.path.join(tmp_dir, "f.txt"), b"")
        r = file_tools_replace_lines(p, 1, 1, "X1\nX2\nX3\n")
        assert "成功" in _text(r)
        assert _bytes(p) == b"X1" + OS_NL.encode() + b"X2" + OS_NL.encode() + b"X3" + OS_NL.encode()

    def test_write_fresh_file_uses_os(self, tmp_dir):
        p = os.path.join(tmp_dir, "fresh.txt")
        file_tools_write(p, "A\nB\n")
        raw = _bytes(p)
        assert raw == f"A{OS_NL}B{OS_NL}".encode()

    def test_detect_failure_falls_back_to_os(self, tmp_dir):
        """utils 版探测失败（编码解不动）→ 按无行尾落回 OS，写入照常。"""
        p = os.path.join(tmp_dir, "gbk.txt")
        with open(p, "wb") as f:
            f.write("甲\n乙\n".encode("gbk"))
        r = file_tools_write(p, "Z1\nZ2\n", encoding="ascii")
        assert "成功" in _text(r)
        assert _bytes(p) == f"Z1{OS_NL}Z2{OS_NL}".encode()


class TestWriteOverwrite:
    """file_tools_write 整覆盖：auto=保持旧文件主行尾（作者拍板 A 案）。"""

    def test_lf_kept(self, tmp_dir):
        p = _make(os.path.join(tmp_dir, "f.txt"), LF)
        file_tools_write(p, "Z1\nZ2\n")
        raw = _bytes(p)
        assert b"\r" not in raw and raw.endswith(b"\n")

    def test_crlf_kept(self, tmp_dir):
        p = _make(os.path.join(tmp_dir, "f.txt"), CRLF)
        file_tools_write(p, "Z1\nZ2\n")
        raw = _bytes(p)
        assert raw.count(b"\n") == raw.count(b"\r\n") == 2

    def test_cr_kept(self, tmp_dir):
        p = _make(os.path.join(tmp_dir, "f.txt"), CR)
        file_tools_write(p, "Z1\nZ2\n")
        raw = _bytes(p)
        assert b"\n" not in raw and raw.count(b"\r") == 2


class TestFoldGuard:
    """new_text/replacement 自带 \\r\\n 时不得叠成 \\r\\r\\n。"""

    def test_replace_with_crlf_text_into_crlf_file(self, tmp_dir):
        p = _make(os.path.join(tmp_dir, "f.txt"), CRLF)
        r = file_tools_replace(p, "A1", "X1\r\nX2\r\n")
        assert "成功" in _text(r)
        raw = _bytes(p)
        assert b"\r\r" not in raw, raw
        assert raw.count(b"\n") == raw.count(b"\r\n")

    def test_insert_crlf_content_into_lf_file(self, tmp_dir):
        p = _make(os.path.join(tmp_dir, "f.txt"), LF)
        r = file_tools_insert_lines(p, 2, "X1\r\nX2")
        assert "成功" in _text(r)
        assert b"\r" not in _bytes(p), _bytes(p)


class TestAppendIntentionalDivergence:
    """append 保持原样（作者裁决）：auto=OS 行分隔符，本钉防误"统一"。"""

    def test_append_auto_is_os(self, tmp_dir):
        p = _make(os.path.join(tmp_dir, "f.txt"), b"A1\n")
        r = file_tools_append(p, "A2\n")
        assert "成功" in _text(r)
        expect = b"A1\n" + b"A2" + OS_NL.encode()
        assert _bytes(p) == expect
