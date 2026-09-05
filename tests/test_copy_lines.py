"""测试跨文件行复制工具 file_tools_copy_lines。"""

import os

import pytest

import tools.copy_lines as copy_lines_mod
from backup.manager import list_history
from tools.copy_lines import file_tools_copy_lines


def _text(result):
    return result.content[0].text


def _make(path, content, newline="\n", encoding="utf-8"):
    with open(path, "w", encoding=encoding, newline=newline) as f:
        f.write(content)
    return path


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def _read_lines(path, encoding="utf-8"):
    with open(path, "r", encoding=encoding) as f:
        return f.read().splitlines()


@pytest.fixture
def src_file(tmp_dir):
    """5 行 + 末尾换行。"""
    return _make(os.path.join(tmp_dir, "src.txt"), "A1\nA2\nA3\nA4\nA5\n")


@pytest.fixture
def dst_file(tmp_dir):
    """3 行 + 末尾换行。"""
    return _make(os.path.join(tmp_dir, "dst.txt"), "B1\nB2\nB3\n")


class TestCrossFileBasics:
    def test_append_default(self, src_file, dst_file):
        result = file_tools_copy_lines(src_file, 2, 3, dst_file)
        assert "末尾追加" in _text(result)
        assert "文件从 4 行变为 6 行" in _text(result)
        assert _read_lines(dst_file) == ["B1", "B2", "B3", "A2", "A3"]

    def test_append_explicit_negative(self, src_file, dst_file):
        file_tools_copy_lines(src_file, 1, 1, dst_file, insert_line=-1)
        assert _read_lines(dst_file) == ["B1", "B2", "B3", "A1"]

    def test_insert_before_line(self, src_file, dst_file):
        result = file_tools_copy_lines(src_file, 2, 3, dst_file, insert_line=2)
        assert "第 2 行之前" in _text(result)
        assert _read_lines(dst_file) == ["B1", "A2", "A3", "B2", "B3"]

    def test_insert_at_head(self, src_file, dst_file):
        file_tools_copy_lines(src_file, 4, 5, dst_file, insert_line=1)
        assert _read_lines(dst_file) == ["A4", "A5", "B1", "B2", "B3"]

    def test_insert_before_trailing_empty_equals_append(self, src_file, dst_file):
        """带末尾换行的文件共 4 行（含末尾空行），第 4 行前插入 == 追加。"""
        file_tools_copy_lines(src_file, 1, 1, dst_file, insert_line=4)
        assert _read_lines(dst_file) == ["B1", "B2", "B3", "A1"]

    def test_end_line_clamped(self, src_file, dst_file):
        """list 模型：5 内容行 + 末尾空行 = 共 6 行，钳位含末尾空行。"""
        result = file_tools_copy_lines(src_file, 4, 999, dst_file)
        assert "第 4-6 行（3 行）" in _text(result)
        raw = _read_bytes(dst_file).decode("utf-8")
        assert raw == "B1\nB2\nB3\nA4\nA5\n\n"

    def test_single_line(self, src_file, dst_file):
        file_tools_copy_lines(src_file, 3, 3, dst_file)
        assert _read_lines(dst_file)[-1] == "A3"

    def test_src_unchanged(self, src_file, dst_file):
        before = _read_bytes(src_file)
        file_tools_copy_lines(src_file, 1, 999, dst_file)
        assert _read_bytes(src_file) == before

    def test_diff_preview(self, src_file, dst_file):
        result = file_tools_copy_lines(src_file, 2, 3, dst_file, insert_line=2)
        text = _text(result)
        assert "  1 > B1" in text
        assert "+ 2 > A2" in text
        assert "+ 3 > A3" in text
        assert "  4 > B2" in text

    def test_no_blank_line_between(self, src_file, dst_file):
        """追加落在末尾空行之前，不产生多余空行。"""
        file_tools_copy_lines(src_file, 1, 1, dst_file,
                              dst_line_separator="\\n")
        raw = _read_bytes(dst_file).decode("utf-8")
        assert "\n\n" not in raw
        assert raw.endswith("B3\nA1\n")

    def test_string_numbers_accepted(self, src_file, dst_file):
        file_tools_copy_lines(src_file, "2", "3", dst_file, insert_line="2")
        assert _read_lines(dst_file) == ["B1", "A2", "A3", "B2", "B3"]

    def test_insert_line_none_means_append(self, src_file, dst_file):
        file_tools_copy_lines(src_file, 1, 1, dst_file, insert_line=None)
        assert _read_lines(dst_file) == ["B1", "B2", "B3", "A1"]


class TestNewDst:
    def test_new_file_created(self, src_file, tmp_dir):
        dst = os.path.join(tmp_dir, "out.txt")
        result = file_tools_copy_lines(src_file, 1, 2, dst, dst_line_separator="\\n")
        assert "新建" in _text(result)
        # 选区止于文件中途 → 新文件裸尾，不补末尾换行（作者裁决）
        assert _read_bytes(dst) == b"A1\nA2"

    def test_no_backup_for_new(self, src_file, tmp_dir):
        dst = os.path.join(tmp_dir, "out.txt")
        file_tools_copy_lines(src_file, 1, 1, dst)
        assert list_history(dst) == []

    def test_parent_dir_auto_created(self, src_file, tmp_dir):
        dst = os.path.join(tmp_dir, "a", "b", "deep", "out.txt")
        file_tools_copy_lines(src_file, 1, 1, dst)
        assert os.path.isfile(dst)

    def test_insert_line_converges_for_new(self, src_file, tmp_dir):
        """新建无既有行：合法 insert_line 自然收敛为整体新建；非法落点与已存在目标同规报错。"""
        for i, ok in enumerate((99, 1, -1, None)):
            dst = os.path.join(tmp_dir, f"out{i}.txt")  # 每轮都是新建
            r = file_tools_copy_lines(src_file, 1, 2, dst, insert_line=ok)
            assert "失败" not in _text(r), f"insert_line={ok} 应收敛为新建"
            assert _read_lines(dst) == ["A1", "A2"]
        for bogus in (0, -2):
            dst = os.path.join(tmp_dir, f"bad{bogus}.txt")
            r = file_tools_copy_lines(src_file, 1, 2, dst, insert_line=bogus)
            assert "不合法" in _text(r), f"insert_line={bogus} 应与已存在目标同规报错"
            assert not os.path.exists(dst)  # 校验先于创建，零污染

    def test_empty_dst_any_line_lands_alone(self, src_file, tmp_dir):
        """空文件目标无需特判：任意合法 insert_line 都落在唯一位置。"""
        dst = _make(os.path.join(tmp_dir, "e.txt"), "")
        for line in (1, 2, 99):
            r = file_tools_copy_lines(src_file, 1, 1, dst, insert_line=line)
            assert "失败" not in _text(r)
        assert _read_lines(dst) == ["A1", "A1", "A1"]  # 每轮都追加在空位

    def test_empty_existing_dst(self, src_file, tmp_dir):
        """空文件目标无需特判：幻影空行基线自然产出规范换行，仍照旧备份。"""
        dst = _make(os.path.join(tmp_dir, "e.txt"), "")
        result = file_tools_copy_lines(src_file, 2, 3, dst, insert_line=7,
                                       dst_line_separator="\\n")
        text = _text(result)
        assert "新建" not in text and "末尾追加" in text
        assert _read_bytes(dst) == b"A2\nA3\n"
        assert len(list_history(dst)) == 1


class TestValidation:
    def test_src_not_exist(self, tmp_dir, dst_file):
        result = file_tools_copy_lines(
            os.path.join(tmp_dir, "nope.txt"), 1, 1, dst_file
        )
        assert "失败" in _text(result)
        assert "源文件" in _text(result) and "不存在" in _text(result)

    def test_start_line_zero(self, src_file, dst_file):
        result = file_tools_copy_lines(src_file, 0, 2, dst_file)
        assert "行号必须 >= 1" in _text(result)

    def test_start_gt_end(self, src_file, dst_file):
        result = file_tools_copy_lines(src_file, 3, 2, dst_file)
        assert "大于结束行号" in _text(result)

    def test_start_over_total(self, src_file, dst_file):
        result = file_tools_copy_lines(src_file, 7, 8, dst_file)
        assert "超出源文件范围（共 6 行）" in _text(result)

    def test_start_at_trailing_empty_line_legal(self, src_file, dst_file):
        """末尾空行是真实行：可入选区，拷到已终止目标=追加一个空行。"""
        result = file_tools_copy_lines(src_file, 6, 6, dst_file)
        assert "第 6-6 行（1 行）" in _text(result)
        assert _read_lines(dst_file) == ["B1", "B2", "B3", ""]

    def test_insert_zero_with_hint(self, src_file, dst_file):
        result = file_tools_copy_lines(src_file, 1, 1, dst_file, insert_line=0)
        text = _text(result)
        assert "失败" in text
        assert "行号从 1 开始" in text
        assert "-1" in text  # 追加提示

    def test_insert_over_total_appends(self, src_file, dst_file):
        """作者裁决修订：超过总行数与 -1 同意，自动末尾追加不报错。"""
        r5 = file_tools_copy_lines(src_file, 1, 1, dst_file, insert_line=5)
        assert "末尾追加" in _text(r5)
        r99 = file_tools_copy_lines(src_file, 2, 2, dst_file, insert_line=99)
        assert "末尾追加" in _text(r99)
        assert _read_lines(dst_file) == ["B1", "B2", "B3", "A1", "A2"]

    def test_dst_is_directory(self, src_file, tmp_dir):
        result = file_tools_copy_lines(src_file, 1, 1, tmp_dir)
        assert "不是文件" in _text(result)

    def test_bool_rejected(self, src_file, dst_file):
        result = file_tools_copy_lines(src_file, True, 2, dst_file)
        assert "应当输入整数" in _text(result)

    def test_float_insert_rejected(self, src_file, dst_file):
        result = file_tools_copy_lines(src_file, 1, 1, dst_file, insert_line=2.5)
        assert "应当输入整数" in _text(result)

    def test_error_leaves_no_trace(self, src_file, dst_file):
        """行号报错发生在备份之前：目标内容与备份都不动。"""
        before = _read_bytes(dst_file)
        file_tools_copy_lines(src_file, 1, 1, dst_file, insert_line=0)
        assert _read_bytes(dst_file) == before
        assert list_history(dst_file) == []

    def test_end_line_not_a_number(self, src_file, dst_file):
        result = file_tools_copy_lines(src_file, 1, "x", dst_file)
        assert "end_line 参数应当输入整数" in _text(result)


class TestIoErrors:
    """读写异常路径的中文报错面。"""

    def test_dst_read_failure(self, tmp_dir):
        """dst 强制错误编码解码失败 → 读取目标文件报错。"""
        src = _make(os.path.join(tmp_dir, "s.txt"), "A1\nA2\n")
        dst = os.path.join(tmp_dir, "d.txt")
        with open(dst, "wb") as f:
            f.write("中文字符串测试内容行一二三\n".encode("gbk"))
        result = file_tools_copy_lines(src, 1, 1, dst, dst_encoding="utf-8")
        text = _text(result)
        assert "失败" in text and "读取目标文件" in text

    def test_makedirs_failure_under_file_parent(self, src_file):
        """dst 的父路径是个文件 → 建目录失败报错。"""
        dst = os.path.join(src_file, "impossible.txt")
        result = file_tools_copy_lines(src_file, 1, 1, dst)
        text = _text(result)
        assert "失败" in text and "创建目标目录" in text

    def test_write_failure_bad_dst_encoding(self, src_file, tmp_dir):
        dst = os.path.join(tmp_dir, "out.txt")
        result = file_tools_copy_lines(src_file, 1, 1, dst,
                                       dst_encoding="no-such-codec")
        text = _text(result)
        assert "失败" in text and "写入目标文件" in text

    def test_newline_detect_failure_falls_back_to_os(self, tmp_dir, monkeypatch):
        """目标主行尾探测失败 → 按无行尾处理落回 OS，操作照常不陪绑。"""
        real = copy_lines_mod._dominant_newline

        def selective(content):
            if "B1" in content:  # 只在探测 dst（B1 基线）时炸
                raise OSError("stub")
            return real(content)

        monkeypatch.setattr(copy_lines_mod, "_dominant_newline", selective)
        try:
            src = _make(os.path.join(tmp_dir, "s.txt"), "A1\n")
            dst = _make(os.path.join(tmp_dir, "d.txt"), "B1\n", newline="")
            r = file_tools_copy_lines(src, 1, 1, dst)
        finally:
            monkeypatch.undo()
        assert "失败" not in _text(r)
        expect = b"B1\r\nA1\r\n" if os.name == "nt" else b"B1\nA1\n"
        assert _read_bytes(dst) == expect


class TestAdversarialFixes:
    """零上下文对抗审查抓漏（M1-M4/m3）的回归钉。"""

    def test_m1_strict_split_auto_dst_no_cr_doubling(self, tmp_dir):
        """M1：strict 拆行带入 \\r 进行内容，auto 写回不得产生 \\r\\r\\n 腐蚀。"""
        src = _make(os.path.join(tmp_dir, "c.txt"),
                    "A1\r\nA2\r\nA3\r\n", newline="")
        dst = os.path.join(tmp_dir, "out.txt")
        file_tools_copy_lines(src, 1, 2, dst, src_line_separator="\\n")
        raw = _read_bytes(dst)
        assert b"\r\r\n" not in raw
        # 新建不补换行：行尾裸 \r 是 strict 行内容，缝隙按 OS 复原
        assert raw in (b"A1\r\nA2\r", b"A1\nA2\r")

    def test_m1_append_existing_crlf_dst(self, tmp_dir):
        src = _make(os.path.join(tmp_dir, "c.txt"), "A1\r\nA2\r\n", newline="")
        dst = _make(os.path.join(tmp_dir, "d.txt"), "B1\r\nB2\r\n", newline="")
        file_tools_copy_lines(src, 1, 2, dst, src_line_separator="\\n")
        raw = _read_bytes(dst)
        assert b"\r\r" not in raw
        assert raw.replace(b"\r\n", b"\n").endswith(b"A1\nA2\n")

    def test_m2_fresh_single_empty_line(self, tmp_dir):
        """M2（list 模型修正）：拷一条空行 → 0 字节目标，0 字节文件本身就是一行空行，摘要与重读域一致。"""
        src = _make(os.path.join(tmp_dir, "s.txt"), "a\n\nb\n")
        dst = os.path.join(tmp_dir, "out.txt")
        result = file_tools_copy_lines(src, 2, 2, dst,
                                       dst_line_separator="\\n")
        assert _read_bytes(dst) == b""
        assert "共 1 行" in _text(result)
        assert _read_bytes(dst).decode("utf-8").split("\n") == [""]

    def test_m3_empty_dst_inherits_src_encoding(self, tmp_dir):
        """M3：空文件「视为新建」则编码沿用也要同果。"""
        src = os.path.join(tmp_dir, "g.txt")
        with open(src, "wb") as f:
            f.write("中文第一行\n".encode("gbk"))
        dst = _make(os.path.join(tmp_dir, "e.txt"), "")
        file_tools_copy_lines(src, 1, 1, dst, dst_line_separator="\\n")
        # 已存在的空文件 = 一行末尾空行（list 模型）；填入内容后空行让位行尾
        assert _read_bytes(dst) == "中文第一行\n".encode("gbk")

    @pytest.mark.skipif(os.name != "nt", reason="Windows 符号链接需开发者模式/管理员")
    def test_m4_symlink_not_self_copy(self, tmp_dir):
        """M4：指向 src 的链接不判自复制（避免成功文案与实际效果分裂）。"""
        src = _make(os.path.join(tmp_dir, "s.txt"), "A1\nA2\n")
        link = os.path.join(tmp_dir, "link.txt")
        try:
            os.symlink(src, link)
        except OSError:
            pytest.skip("当前环境无权创建符号链接")
        before = _read_bytes(src)
        result = file_tools_copy_lines(src, 1, 1, link)
        assert "失败" not in _text(result)
        assert _read_bytes(src) == before  # src 不动，链接按普通目标写
        assert _read_lines(link) == ["A1", "A2", "A1"]


class TestBackup:
    def test_existing_dst_backed_up(self, src_file, dst_file):
        result = file_tools_copy_lines(src_file, 1, 1, dst_file)
        assert len(list_history(dst_file)) == 1
        assert "历史号 #1" in _text(result)
        assert "file_tools_undo" in _text(result)

    def test_backup_failure(self, src_file, dst_file, monkeypatch):
        monkeypatch.setattr(copy_lines_mod, "backup_file", lambda p: None)
        try:
            result = file_tools_copy_lines(src_file, 1, 1, dst_file)
        finally:
            monkeypatch.undo()
        assert "备份原文件失败" in _text(result)
        assert _read_lines(dst_file) == ["B1", "B2", "B3"]


class TestSelfCopy:
    def test_none_appends_at_end(self, src_file):
        result = file_tools_copy_lines(src_file, 1, 2)
        assert "末尾追加" in _text(result)
        assert _read_lines(src_file) == ["A1", "A2", "A3", "A4", "A5", "A1", "A2"]

    def test_none_insert_before(self, src_file):
        file_tools_copy_lines(src_file, 1, 2, insert_line=3)
        assert _read_lines(src_file) == ["A1", "A2", "A1", "A2", "A3", "A4", "A5"]

    def test_insert_inside_selection(self, src_file):
        """落点落在选中区内部：行号以改前为准，粘贴语义确定。"""
        file_tools_copy_lines(src_file, 2, 4, insert_line=3)
        assert _read_lines(src_file) == [
            "A1", "A2", "A2", "A3", "A4", "A3", "A4", "A5",
        ]

    def test_single_backup_for_self(self, src_file):
        file_tools_copy_lines(src_file, 1, 1)
        assert len(list_history(src_file)) == 1

    def test_explicit_same_path_is_self_copy(self, src_file):
        result = file_tools_copy_lines(src_file, 1, 1, src_file)
        text = _text(result)
        assert "新建" not in text and "末尾追加" in text
        assert _read_lines(src_file) == ["A1", "A2", "A3", "A4", "A5", "A1"]
        assert len(list_history(src_file)) == 1  # 只备份一次

    @pytest.mark.skipif(os.name != "nt", reason="Windows 大小写不敏感特性")
    def test_case_insensitive_same_file(self, src_file):
        result = file_tools_copy_lines(src_file, 1, 1, src_file.swapcase())
        text = _text(result)
        assert "新建" not in text  # 换大小写的同路径必须识别为自复制
        assert _read_lines(src_file) == ["A1", "A2", "A3", "A4", "A5", "A1"]

    def test_no_trailing_newline_src(self, tmp_dir):
        src = _make(os.path.join(tmp_dir, "n.txt"), "A1\nA2\nA3")
        file_tools_copy_lines(src, 1, 1, dst_line_separator="\\n")
        assert _read_bytes(src) == b"A1\nA2\nA3\nA1"

    def test_error_before_mutation(self, src_file):
        before = _read_bytes(src_file)
        file_tools_copy_lines(src_file, 9, 9)
        assert _read_bytes(src_file) == before
        assert list_history(src_file) == []


class TestSelfCopyNewlinePreserve:
    """第三裁决：dst auto = 保持目标文件主行尾（自复制目标即源文件）。"""

    def test_self_lf_stays_lf(self, tmp_dir):
        src = _make(os.path.join(tmp_dir, "l.txt"), "A1\nA2\nA3\n", newline="")
        file_tools_copy_lines(src, 1, 1)
        assert _read_bytes(src) == b"A1\nA2\nA3\nA1\n"

    def test_self_crlf_stays_crlf(self, tmp_dir):
        src = _make(os.path.join(tmp_dir, "c.txt"), "A1\r\nA2\r\n", newline="")
        file_tools_copy_lines(src, 1, 1)
        assert _read_bytes(src) == b"A1\r\nA2\r\nA1\r\n"

    def test_self_cr_only_preserved(self, tmp_dir):
        src = _make(os.path.join(tmp_dir, "r.txt"), "A1\rA2\r", newline="")
        file_tools_copy_lines(src, 1, 1)
        assert _read_bytes(src) == b"A1\rA2\rA1\r"

    def test_self_mixed_dominant_crlf(self, tmp_dir):
        """混合行尾按主行尾归一（CRLF 2 : LF 1）。"""
        src = _make(os.path.join(tmp_dir, "m.txt"),
                    "A1\r\nA2\nA3\r\n", newline="")
        file_tools_copy_lines(src, 1, 1)
        assert _read_bytes(src) == b"A1\r\nA2\r\nA3\r\nA1\r\n"

    def test_self_no_newline_src_falls_os(self, tmp_dir):
        src = _make(os.path.join(tmp_dir, "s.txt"), "ONLY", newline="")
        file_tools_copy_lines(src, 1, 1)
        assert _read_lines(src) == ["ONLY", "ONLY"]  # 无行尾可跟，落回 OS

    def test_self_explicit_src_sep_followed(self, tmp_dir):
        """显式 src_line_separator 时，自复制 auto 跟随该参数值。"""
        src = _make(os.path.join(tmp_dir, "c.txt"), "A1\r\nA2\r\n", newline="")
        file_tools_copy_lines(src, 1, 1, src_line_separator="\\r\\n")
        assert _read_bytes(src) == b"A1\r\nA2\r\nA1\r\n"

    def test_cross_file_auto_keeps_dst_lf(self, tmp_dir):
        """第三裁决：跨文件 dst auto + 有内容 = 保持目标文件主行尾，LF 不再被转 CRLF。"""
        src = _make(os.path.join(tmp_dir, "s.txt"), "A1\n")
        dst = _make(os.path.join(tmp_dir, "d.txt"), "B1\n", newline="")
        file_tools_copy_lines(src, 1, 1, dst)
        assert _read_bytes(dst) == b"B1\nA1\n"

    def test_cross_file_auto_keeps_dst_crlf(self, tmp_dir):
        src = _make(os.path.join(tmp_dir, "s.txt"), "A1\n")
        dst = _make(os.path.join(tmp_dir, "d.txt"), "B1\r\n", newline="")
        file_tools_copy_lines(src, 1, 1, dst)
        assert _read_bytes(dst) == b"B1\r\nA1\r\n"

    def test_new_dst_auto_still_os(self, tmp_dir):
        """无内容可保持（新建）→ 行尾字符仍 OS 口径；选区止于中途行则裸尾。"""
        src = _make(os.path.join(tmp_dir, "s.txt"), "A1\nA2\n")
        dst = os.path.join(tmp_dir, "brand_new.txt")
        file_tools_copy_lines(src, 1, 2, dst)
        expect = b"A1\r\nA2" if os.name == "nt" else b"A1\nA2"
        assert _read_bytes(dst) == expect
        # 选区含末尾空行（第 3 行）→ 自带末尾终止换行
        dst2 = os.path.join(tmp_dir, "brand_new2.txt")
        file_tools_copy_lines(src, 1, 3, dst2)
        expect2 = b"A1\r\nA2\r\n" if os.name == "nt" else b"A1\nA2\n"
        assert _read_bytes(dst2) == expect2


class TestEncoding:
    GBK_TEXT = "中文第一行\n中文第二行\n中文第三行\n"

    def _make_gbk(self, path):
        with open(path, "wb") as f:
            f.write(self.GBK_TEXT.encode("gbk"))
        return path

    def test_new_dst_inherits_src_encoding(self, tmp_dir):
        src = self._make_gbk(os.path.join(tmp_dir, "g.txt"))
        dst = os.path.join(tmp_dir, "out.txt")
        file_tools_copy_lines(src, 1, 1, dst, dst_line_separator="\\n")
        assert _read_bytes(dst).decode("gbk") == "中文第一行"

    def test_explicit_dst_encoding_transcodes(self, tmp_dir):
        src = self._make_gbk(os.path.join(tmp_dir, "g.txt"))
        dst = os.path.join(tmp_dir, "out.txt")
        file_tools_copy_lines(src, 1, 2, dst, dst_encoding="utf-8",
                              dst_line_separator="\\n")
        assert _read_bytes(dst).decode("utf-8") == "中文第一行\n中文第二行"

    def test_existing_dst_keeps_own_encoding(self, tmp_dir):
        src = _make(os.path.join(tmp_dir, "u.txt"), "U1\nU2\n")
        dst = self._make_gbk(os.path.join(tmp_dir, "d.txt"))
        file_tools_copy_lines(src, 1, 1, dst)
        assert _read_lines(dst, encoding="gbk")[:2] == ["中文第一行", "中文第二行"]
        assert _read_lines(dst, encoding="gbk")[-1] == "U1"

    def test_wrong_forced_src_encoding_errors(self, tmp_dir):
        src = self._make_gbk(os.path.join(tmp_dir, "g.txt"))
        result = file_tools_copy_lines(src, 1, 1, src_encoding="utf-8")
        text = _text(result)
        assert "失败" in text and "读取源文件" in text


class TestSeparators:
    def test_dst_forced_lf(self, src_file, dst_file):
        file_tools_copy_lines(src_file, 1, 1, dst_file,
                              dst_line_separator="\\n")
        assert b"\r" not in _read_bytes(dst_file)

    def test_dst_forced_crlf(self, src_file, dst_file):
        file_tools_copy_lines(src_file, 1, 1, dst_file,
                              dst_line_separator="\\r\\n")
        raw = _read_bytes(dst_file)
        assert b"A1\r\n" in raw and b"B1\r\n" in raw

    def test_crlf_src_normalized_in_auto(self, src_file, dst_file):
        crlf = _make(src_file, "A1\r\nA2\r\nA3\r\nA4\r\nA5\r\n", newline="")
        file_tools_copy_lines(crlf, 1, 1, dst_file, dst_line_separator="\\n")
        assert b"\r" not in _read_bytes(dst_file)

    def test_strict_crlf_split_on_lf_file(self, src_file, tmp_dir):
        """显式 \\r\\n 拆行：LF 文件整体成一行的行内容，换行符原样保留。"""
        dst = os.path.join(tmp_dir, "out.txt")
        result = file_tools_copy_lines(src_file, 1, 1, dst,
                                       src_line_separator="\\r\\n",
                                       dst_line_separator="\\n")
        assert "（1 行）" in _text(result)
        # 整文件就是这一行的内容（含内部与末尾 \n），新建不补 → 字节原样
        assert _read_bytes(dst) == b"A1\nA2\nA3\nA4\nA5\n"

    def test_strict_lf_split_on_crlf_file_roundtrip(self, tmp_dir):
        """显式 \\n 拆 CRLF 文件：\\r 留在行内容中，新建目标字节级还原。"""
        src = _make(os.path.join(tmp_dir, "c.txt"),
                    "A1\r\nA2\r\nA3\r\n", newline="")
        dst = os.path.join(tmp_dir, "out.txt")
        file_tools_copy_lines(src, 1, 2, dst,
                              src_line_separator="\\n",
                              dst_line_separator="\\n")
        assert _read_bytes(dst) == b"A1\r\nA2\r"

    def test_invalid_src_separator_falls_back(self, src_file, dst_file):
        file_tools_copy_lines(src_file, 1, 1, dst_file,
                              src_line_separator="\\t")
        assert _read_lines(dst_file)[-1] == "A1"


class TestEdgeCases:
    def test_empty_src_is_one_trailing_line(self, tmp_dir, dst_file):
        """0 字节文件 = 一行真实空行（list 模型公理）；拷它 = 给目标追加一个空行。"""
        src = _make(os.path.join(tmp_dir, "e.txt"), "")
        result = file_tools_copy_lines(src, 1, 1, dst_file)
        assert "第 1-1 行（1 行）" in _text(result)
        assert _read_lines(dst_file) == ["B1", "B2", "B3", ""]
        result2 = file_tools_copy_lines(src, 2, 2, dst_file)
        assert "超出源文件范围" in _text(result2)

    def test_large_block_preview_omitted(self, tmp_dir):
        src = _make(os.path.join(tmp_dir, "big.txt"),
                    "\n".join(f"L{i}" for i in range(1, 31)) + "\n")
        dst = os.path.join(tmp_dir, "out.txt")
        result = file_tools_copy_lines(src, 1, 30, dst)
        assert "中间省略 10 行" in _text(result)
        assert _read_lines(dst) == [f"L{i}" for i in range(1, 31)]

    def test_insert_last_line_of_selection_adjacent(self, src_file, dst_file):
        """复制块与落点相邻：插到第 4 行前 + 复制 1-3 行，结果可读。"""
        file_tools_copy_lines(src_file, 1, 3, dst_file, insert_line=4)
        assert _read_lines(dst_file) == ["B1", "B2", "B3", "A1", "A2", "A3"]


class TestDocstringContract:
    """极简契约：关键语义必留 + 篇幅上限（裹脚布禁回流）。"""

    MUST_KEEP = [
        "不经过对话上下文",
        "自动新建",
        "修改前自动备份",
        "自复制",
        "连同父目录",
        "1 = 插入到开头",
        "末尾追加",
        "沿用源文件编码",
        "仅按该行尾拆行",
        "超过总行数与 -1 同意",
        "自然收敛为整体新建",
        "保持目标文件主行尾",
    ]

    def test_must_keep_phrases(self):
        doc = file_tools_copy_lines.__doc__
        for phrase in self.MUST_KEEP:
            assert phrase in doc, f"关键语义短语流失：{phrase}"

    def test_first_paragraph_budget(self):
        first = file_tools_copy_lines.__doc__.strip().split("\n\n")[0]
        assert len(first) <= 300, f"首段裹脚布化：{len(first)} 字符"

    def test_total_docstring_budget(self):
        assert len(file_tools_copy_lines.__doc__) <= 1400, "docstring 总量超标"
