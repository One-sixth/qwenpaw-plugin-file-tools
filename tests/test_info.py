"""测试信息读取类工具。"""

import json
import os
import shutil
import tempfile

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


def _can_symlink() -> bool:
    """探测当前进程能否创建目录符号链接（需管理员权限或开发者模式）。"""
    probe = tempfile.mkdtemp(prefix="ft_symprobe_")
    try:
        target = os.path.join(probe, "t")
        os.makedirs(target)
        os.symlink(target, os.path.join(probe, "l"), target_is_directory=True)
        return True
    except OSError:
        return False
    finally:
        shutil.rmtree(probe, ignore_errors=True)


_HAS_SYMLINK = _can_symlink()
requires_symlink = pytest.mark.skipif(
    not _HAS_SYMLINK,
    reason="无法创建符号链接（需管理员权限或开发者模式）",
)


class TestListdir:
    def test_basic(self, tmp_dir):
        open(os.path.join(tmp_dir, "a.txt"), "w").close()
        open(os.path.join(tmp_dir, "b.txt"), "w").close()
        result = file_tools_listdir(tmp_dir, recursive=1)
        assert "a.txt" in result.content[0].text
        assert "b.txt" in result.content[0].text

    def test_with_columns(self, tmp_dir):
        open(os.path.join(tmp_dir, "test.txt"), "w").close()
        result = file_tools_listdir(tmp_dir, recursive=1, columns=["size", "type"])
        assert "| name" in result.content[0].text
        assert "| size" in result.content[0].text
        assert "| type" in result.content[0].text
        assert "|---" in result.content[0].text

    def test_recursive_2(self, subdir_structure):
        result = file_tools_listdir(subdir_structure, recursive=2)
        assert "dir_a/sub_file1.txt" in result.content[0].text
        assert "dir_a/sub_dir1/" in result.content[0].text
        assert "dir_b/sub_file2.txt" in result.content[0].text
        assert "file_a.txt" in result.content[0].text
        assert ".hidden" in result.content[0].text

    def test_recursive_minus1(self, subdir_structure):
        result = file_tools_listdir(subdir_structure, recursive=-1)
        assert "dir_a/sub_file1.txt" in result.content[0].text
        assert "dir_a/sub_dir1/" in result.content[0].text
        assert "dir_b/sub_file2.txt" in result.content[0].text

    def test_invalid_recursive(self, tmp_dir):
        result = file_tools_listdir(tmp_dir, recursive=0)
        assert "失败" in result.content[0].text
        assert "不合法" in result.content[0].text

        result = file_tools_listdir(tmp_dir, recursive=-2)
        assert "失败" in result.content[0].text

    def test_nonexistent_dir(self):
        result = file_tools_listdir("/nonexistent_path_xyz")
        assert "失败" in result.content[0].text
        assert "不存在" in result.content[0].text

    def test_hidden_files(self, tmp_dir):
        open(os.path.join(tmp_dir, ".hidden"), "w").close()
        result = file_tools_listdir(tmp_dir, recursive=1)
        assert ".hidden" in result.content[0].text

    def test_sort_order(self, tmp_dir):
        """默认按 name 升序排列，目录和文件混在一起按名称排。"""
        open(os.path.join(tmp_dir, "z_last.txt"), "w").close()
        os.makedirs(os.path.join(tmp_dir, "a_dir"))
        open(os.path.join(tmp_dir, "b_file.txt"), "w").close()
        result = file_tools_listdir(tmp_dir, recursive=1)
        lines = result.content[0].text.strip().split("\n")
        a_idx = next(i for i, l in enumerate(lines) if l == "a_dir/")
        b_idx = next(i for i, l in enumerate(lines) if l == "b_file.txt")
        z_idx = next(i for i, l in enumerate(lines) if l == "z_last.txt")
        assert a_idx < b_idx < z_idx

    def test_markdown_table_format(self, tmp_dir):
        open(os.path.join(tmp_dir, "normal.csv"), "w").close()
        result = file_tools_listdir(tmp_dir, recursive=1, columns=["size"])
        lines = result.content[0].text.strip().split("\n")
        assert lines[0].startswith("| name")
        assert lines[1].startswith("|---")
        assert "normal.csv" in lines[2]

    def test_empty_dir(self, tmp_dir):
        result = file_tools_listdir(tmp_dir, recursive=1)
        assert result.content[0].text == "（空目录，无条目）"

    def test_permission_column(self, tmp_dir):
        open(os.path.join(tmp_dir, "perm.txt"), "w").close()
        result = file_tools_listdir(tmp_dir, recursive=1, columns=["permissions"])
        assert "| permissions" in result.content[0].text
        # 纯文本列表没有表头
        result_no_col = file_tools_listdir(tmp_dir, recursive=1)
        assert "permissions" not in result_no_col.content[0].text

    def test_invalid_sort_by(self, tmp_dir):
        result = file_tools_listdir(tmp_dir, sort_by="invalid")
        assert "失败" in result.content[0].text
        assert "不合法" in result.content[0].text

    def test_invalid_start(self, tmp_dir):
        result = file_tools_listdir(tmp_dir, start=0)
        assert "失败" in result.content[0].text

    def test_invalid_count(self, tmp_dir):
        result = file_tools_listdir(tmp_dir, count=0)
        assert "失败" in result.content[0].text
        result = file_tools_listdir(tmp_dir, count=501)
        assert "失败" in result.content[0].text

    def test_pagination(self, tmp_dir):
        _make_files(tmp_dir, [f"f{i:03d}.txt" for i in range(20)])
        # count=5, start=1 → 第1~5个
        result = file_tools_listdir(tmp_dir, count=5)
        lines = result.content[0].text.strip().split("\n")
        assert len(lines) == 7  # 5文件名 + 1空行 + 1页脚
        assert "f000.txt" in result.content[0].text
        assert "f004.txt" in result.content[0].text
        assert "f005.txt" not in result.content[0].text
        assert "后面还有 15 个条目" in result.content[0].text
        # start=3 → 第3~7个（f002 ~ f006）
        result2 = file_tools_listdir(tmp_dir, start=3, count=5)
        assert "f002.txt" in result2.content[0].text
        assert "f006.txt" in result2.content[0].text
        assert "f001.txt" not in result2.content[0].text
        assert "后面还有 13 个条目" in result2.content[0].text

    def test_pagination_out_of_range(self, tmp_dir):
        _make_files(tmp_dir, [f"f{i}.txt" for i in range(3)])
        result = file_tools_listdir(tmp_dir, start=10)
        assert "没有更多条目" in result.content[0].text
        assert "共 3 个" in result.content[0].text

    def test_sort_ascending_descending(self, tmp_dir):
        _make_files(tmp_dir, ["c.txt", "a.txt", "b.txt"])
        asc = file_tools_listdir(tmp_dir, ascending=True)
        desc = file_tools_listdir(tmp_dir, ascending=False)
        assert asc.content[0].text.strip().split("\n") == ["a.txt", "b.txt", "c.txt"]
        assert desc.content[0].text.strip().split("\n") == ["c.txt", "b.txt", "a.txt"]

    def test_sort_by_type(self, tmp_dir):
        os.makedirs(os.path.join(tmp_dir, "zzz_dir"))
        open(os.path.join(tmp_dir, "aaa_file.txt"), "w").close()
        result = file_tools_listdir(tmp_dir, sort_by="type", ascending=True)
        lines = result.content[0].text.strip().split("\n")
        # "directory" < "file"（字典序）
        assert lines[0] == "zzz_dir/"
        assert lines[1] == "aaa_file.txt"
        # descending
        result2 = file_tools_listdir(tmp_dir, sort_by="type", ascending=False)
        lines2 = result2.content[0].text.strip().split("\n")
        assert lines2[0] == "aaa_file.txt"
        assert lines2[1] == "zzz_dir/"

    def test_sort_by_size(self, tmp_dir):
        open(os.path.join(tmp_dir, "small.txt"), "w").close()
        with open(os.path.join(tmp_dir, "large.txt"), "w") as f:
            f.write("x" * 1000)
        asc = file_tools_listdir(tmp_dir, sort_by="size", ascending=True)
        desc = file_tools_listdir(tmp_dir, sort_by="size", ascending=False)
        lines_asc = asc.content[0].text.strip().split("\n")
        lines_desc = desc.content[0].text.strip().split("\n")
        assert lines_asc[0] == "small.txt"
        assert lines_asc[1] == "large.txt"
        assert lines_desc[0] == "large.txt"
        assert lines_desc[1] == "small.txt"

    def test_sort_by_extension(self, tmp_dir):
        open(os.path.join(tmp_dir, "a.py"), "w").close()
        open(os.path.join(tmp_dir, "b.txt"), "w").close()
        open(os.path.join(tmp_dir, "c.md"), "w").close()
        result = file_tools_listdir(tmp_dir, sort_by="extension", ascending=True)
        lines = result.content[0].text.strip().split("\n")
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
        lines_asc = asc.content[0].text.strip().split("\n")
        lines_desc = desc.content[0].text.strip().split("\n")
        assert lines_asc[0] == "old.txt"
        assert lines_asc[1] == "new.txt"
        assert lines_desc[0] == "new.txt"
        assert lines_desc[1] == "old.txt"

    def test_pagination_last_page(self, tmp_dir):
        _make_files(tmp_dir, [f"f{i:03d}.txt" for i in range(7)])
        result = file_tools_listdir(tmp_dir, start=6, count=5)
        assert "f005.txt" in result.content[0].text
        assert "f006.txt" in result.content[0].text
        assert "f004.txt" not in result.content[0].text
        # 最后一页无剩余，不显示尾部提示
        assert "后面还有" not in result.content[0].text

    def test_pagination_with_columns(self, tmp_dir):
        _make_files(tmp_dir, [f"f{i:03d}.txt" for i in range(20)])
        result = file_tools_listdir(tmp_dir, columns=["size"], count=5)
        lines = result.content[0].text.strip().split("\n")
        assert lines[0].startswith("| name")
        assert lines[1].startswith("|---")
        assert "f000.txt" in lines[2]
        assert "f004.txt" in result.content[0].text
        assert "f005.txt" not in result.content[0].text
        assert "后面还有 15 个条目" in result.content[0].text

    def test_pagination_single_file(self, tmp_dir):
        open(os.path.join(tmp_dir, "only.txt"), "w").close()
        result = file_tools_listdir(tmp_dir, start=1, count=1)
        assert result.content[0].text.strip() == "only.txt"


def _build_cycle_tree(root):
    """构造环 + 合法复用测试树：

    a/fa.txt, a/b/fb.txt, a/b/c/fc.txt, shared/sx.txt, top.txt
    a/b/c/loop -> a          （环：指向祖先）
    x/one      -> shared     （合法复用，非祖先）
    y/two      -> shared     （合法复用）
    """
    os.makedirs(os.path.join(root, "a", "b", "c"))
    os.makedirs(os.path.join(root, "shared"))
    os.makedirs(os.path.join(root, "x"))
    os.makedirs(os.path.join(root, "y"))
    for p in ["top.txt", "a/fa.txt", "a/b/fb.txt", "a/b/c/fc.txt", "shared/sx.txt"]:
        open(os.path.join(root, *p.split("/")), "w").close()
    os.symlink(os.path.join(root, "a"),
               os.path.join(root, "a", "b", "c", "loop"), target_is_directory=True)
    os.symlink(os.path.join(root, "shared"),
               os.path.join(root, "x", "one"), target_is_directory=True)
    os.symlink(os.path.join(root, "shared"),
               os.path.join(root, "y", "two"), target_is_directory=True)


class TestListdirFilters:
    """v1.3.0 过滤器参数、显示格式与 symlink 行为测试。"""

    # ── 显示格式 ──

    def test_display_forward_slash_and_trailing(self, subdir_structure):
        lines = file_tools_listdir(subdir_structure, recursive=-1).content[0].text.splitlines()
        text = "\n".join(lines)
        assert "\\" not in text          # 全正斜杠
        assert "dir_a/" in lines         # 目录带尾斜杠独占一行
        assert "dir_a/sub_dir1/" in lines
        assert "dir_a/sub_file1.txt" in lines

    # ── types ──

    def test_types_file_hides_dirs_keeps_traversal(self, subdir_structure):
        lines = file_tools_listdir(subdir_structure, recursive=-1,
                                   types=["file"]).content[0].text.splitlines()
        assert "dir_a/" not in lines
        assert "dir_a/sub_file1.txt" in lines   # 目录不显示但仍遍历
        assert "file_a.txt" in lines

    def test_types_dir_alias(self, subdir_structure):
        lines = file_tools_listdir(subdir_structure, recursive=1,
                                   types=["dir"]).content[0].text.splitlines()
        assert "dir_a/" in lines and "dir_b/" in lines
        assert "file_a.txt" not in lines

    def test_types_case_insensitive_and_full_word(self, subdir_structure):
        lines = file_tools_listdir(subdir_structure, recursive=1,
                                   types=["DIRECTORY", "File"]).content[0].text.splitlines()
        assert "dir_a/" in lines and "file_a.txt" in lines
        assert ".hidden" in lines          # 无后缀文件，type=file 照样命中
        lines2 = file_tools_listdir(subdir_structure, recursive=1,
                                    types=["directory"]).content[0].text.splitlines()
        assert ".hidden" not in lines2     # 文件被目录过滤器排除

    def test_types_all_and_empty_are_noop(self, tmp_dir):
        open(os.path.join(tmp_dir, "a.txt"), "w").close()
        os.makedirs(os.path.join(tmp_dir, "sub"))
        base = file_tools_listdir(tmp_dir).content[0].text
        assert file_tools_listdir(tmp_dir, types=["all"]).content[0].text == base
        assert file_tools_listdir(tmp_dir, types=[]).content[0].text == base

    def test_types_invalid_value_error(self, tmp_dir):
        r = file_tools_listdir(tmp_dir, types=["folder"])
        assert "失败" in r.content[0].text and "types" in r.content[0].text

    # ── extensions ──

    def test_extensions_basic_dirs_pass_through(self, tmp_dir):
        _make_files(tmp_dir, ["a.txt", "b.py", "d/"])
        open(os.path.join(tmp_dir, "d", "c.py"), "w").close()
        lines = file_tools_listdir(tmp_dir, recursive=2,
                                   extensions=["py"]).content[0].text.splitlines()
        assert "b.py" in lines and "d/c.py" in lines
        assert "d/" in lines                    # 目录直通
        assert "a.txt" not in lines

    def test_extensions_input_tolerance(self, tmp_dir):
        _make_files(tmp_dir, ["x.PY", "y.txt"])
        for token in (".py", "*.py", "py", "PY"):
            lines = file_tools_listdir(tmp_dir,
                                       extensions=[token]).content[0].text.splitlines()
            assert "x.PY" in lines, token
            assert "y.txt" not in lines, token

    def test_extensions_empty_noop(self, tmp_dir):
        _make_files(tmp_dir, ["a.txt", "b.py"])
        base = file_tools_listdir(tmp_dir).content[0].text
        assert file_tools_listdir(tmp_dir, extensions=[]).content[0].text == base

    def test_extensions_dir_named_like_ext_passes(self, tmp_dir):
        _make_files(tmp_dir, ["weird.py/", "only.md"])
        lines = file_tools_listdir(tmp_dir, recursive=1,
                                   extensions=["md"]).content[0].text.splitlines()
        assert "weird.py/" in lines   # 目录直通：不看它的"后缀"
        assert "only.md" in lines

    def test_types_file_plus_extensions_yields_pure_files(self, tmp_dir):
        _make_files(tmp_dir, ["a.py", "d/"])
        lines = file_tools_listdir(tmp_dir, recursive=2, types=["file"],
                                   extensions=["py"]).content[0].text.splitlines()
        assert "d/" not in lines
        assert "a.py" in lines

    # ── contains ──

    def test_contains_matches_full_path(self, subdir_structure):
        lines = file_tools_listdir(subdir_structure, recursive=-1,
                                   contains=["sub_file"]).content[0].text.splitlines()
        assert "dir_a/sub_file1.txt" in lines
        assert "dir_b/sub_file2.txt" in lines
        assert "file_a.txt" not in lines

    def test_contains_case_insensitive(self, tmp_dir):
        _make_files(tmp_dir, ["README.md"])
        assert "README.md" in file_tools_listdir(tmp_dir,
                                                 contains=["readme"]).content[0].text
        assert "README.md" in file_tools_listdir(tmp_dir,
                                                 contains=["ReAdMe"]).content[0].text

    def test_contains_slash_scopes_to_directory(self, subdir_structure):
        lines = file_tools_listdir(subdir_structure, recursive=-1,
                                   contains=["dir_a/"]).content[0].text.splitlines()
        assert "dir_a/" in lines                      # 目录自身串以 dir_a/ 结尾
        assert "dir_a/sub_file1.txt" in lines
        assert "dir_a/sub_dir1/" in lines
        assert "file_a.txt" not in lines
        assert "dir_b/sub_file2.txt" not in lines

    def test_contains_multi_or(self, tmp_dir):
        _make_files(tmp_dir, ["a.txt", "b.md", "c.py"])
        lines = file_tools_listdir(tmp_dir,
                                   contains=["a.txt", ".md"]).content[0].text.splitlines()
        assert "a.txt" in lines and "b.md" in lines
        assert "c.py" not in lines

    # ── regex ──

    def test_regex_search_semantics_unanchored(self, subdir_structure):
        lines = file_tools_listdir(subdir_structure, recursive=-1,
                                   regex="sub_file").content[0].text.splitlines()
        assert "dir_a/sub_file1.txt" in lines   # 片段无锚即可命中

    def test_regex_dollar_separates_file_and_dir(self, tmp_dir):
        _make_files(tmp_dir, ["a.md", "sub.md/"])
        lines = file_tools_listdir(tmp_dir, regex=r"\.md$").content[0].text.splitlines()
        assert "a.md" in lines
        assert "sub.md/" not in lines           # 尾斜杠使 $ 落空
        lines2 = file_tools_listdir(tmp_dir, regex=r"/$").content[0].text.splitlines()
        assert "sub.md/" in lines2
        assert "a.md" not in lines2

    def test_regex_case_sensitive_with_i_flag_escape(self, tmp_dir):
        _make_files(tmp_dir, ["ABC.txt"])
        assert "无匹配" in file_tools_listdir(tmp_dir, regex="abc").content[0].text
        assert "ABC.txt" in file_tools_listdir(tmp_dir, regex="(?i)abc").content[0].text

    def test_regex_invalid_error(self, tmp_dir):
        r = file_tools_listdir(tmp_dir, regex="((")
        assert "失败" in r.content[0].text and "regex" in r.content[0].text

    # ── exclude ──

    def test_exclude_dir_prunes_whole_tree(self, subdir_structure):
        text = file_tools_listdir(subdir_structure, recursive=-1,
                                  exclude=["dir_a"]).content[0].text
        assert "dir_a" not in text              # 目录及其内容全部消失
        assert "dir_b/sub_file2.txt" in text

    def test_exclude_file_glob(self, tmp_dir):
        _make_files(tmp_dir, ["a.txt", "b.log"])
        lines = file_tools_listdir(tmp_dir, exclude=["*.log"]).content[0].text.splitlines()
        assert "a.txt" in lines and "b.log" not in lines

    def test_exclude_path_pattern_keeps_dir_removes_children(self, subdir_structure):
        lines = file_tools_listdir(subdir_structure, recursive=-1,
                                   exclude=["dir_a/*"]).content[0].text.splitlines()
        assert "dir_a/" in lines                # 模式带斜杠，目录自身不命中
        assert "dir_a/sub_file1.txt" not in lines
        assert "dir_a/sub_dir1/" not in lines

    def test_exclude_backslash_pattern_normalized(self, subdir_structure):
        lines = file_tools_listdir(subdir_structure, recursive=-1,
                                   exclude=["dir_a\\sub*"]).content[0].text.splitlines()
        assert "dir_a/" in lines
        assert "dir_a/sub_file1.txt" not in lines

    def test_exclude_empty_noop(self, tmp_dir):
        _make_files(tmp_dir, ["a.txt"])
        base = file_tools_listdir(tmp_dir).content[0].text
        assert file_tools_listdir(tmp_dir, exclude=[]).content[0].text == base

    # ── 组合 / 字符串宽容 / 统计 ──

    def test_and_across_params(self, tmp_dir):
        _make_files(tmp_dir, ["app.py", "app_test.py", "lib.js"])
        lines = file_tools_listdir(tmp_dir, extensions=["py"],
                                   contains=["test"]).content[0].text.splitlines()
        assert lines[0] == "app_test.py"

    def test_all_filter_params_accept_plain_string(self, subdir_structure):
        text = file_tools_listdir(subdir_structure, recursive=-1, types="file",
                                  extensions="txt", contains="sub_file",
                                  exclude="dir_b").content[0].text
        assert "dir_a/sub_file1.txt" in text
        assert "dir_b/sub_file2.txt" not in text

    def test_filter_footer_stats(self, subdir_structure):
        text = file_tools_listdir(subdir_structure, recursive=-1,
                                  contains=["sub_file"]).content[0].text
        assert "过滤统计：共扫描 7 条，匹配 2 条。" in text
        base = file_tools_listdir(subdir_structure, recursive=-1).content[0].text
        assert "过滤统计" not in base          # 无过滤时不加统计行

    def test_no_match_message_with_filter(self, tmp_dir):
        _make_files(tmp_dir, ["a.txt"])
        text = file_tools_listdir(tmp_dir,
                                  contains=["zzz_absent"]).content[0].text
        assert text.startswith("（无匹配条目")

    def test_pagination_over_filtered_set(self, tmp_dir):
        _make_files(tmp_dir, [f"f{i}.txt" for i in range(10)]
                    + [f"m{i}.md" for i in range(3)])
        text = file_tools_listdir(tmp_dir, extensions=["md"],
                                  count=2).content[0].text
        assert "m0.md" in text and "m1.md" in text and "m2.md" not in text
        assert "后面还有 1 个条目" in text
        text2 = file_tools_listdir(tmp_dir, extensions=["md"],
                                   start=5).content[0].text
        assert "没有更多条目，共 3 个条目" in text2

    # ── follow_symlink / 环检测 ──

    @requires_symlink
    def test_symlink_dir_followed_by_default(self, tmp_dir):
        _build_cycle_tree(tmp_dir)
        lines = file_tools_listdir(tmp_dir, recursive=-1).content[0].text.splitlines()
        assert "x/one/" in lines                    # 链接目录按 directory 展开
        assert "x/one/sx.txt" in lines

    @requires_symlink
    def test_symlink_dir_not_followed_leaf(self, tmp_dir):
        _build_cycle_tree(tmp_dir)
        lines = file_tools_listdir(tmp_dir, recursive=-1,
                                   follow_symlink=False).content[0].text.splitlines()
        assert "x/one" in lines                     # symlink 叶子，无尾斜杠
        assert "x/one/" not in lines
        assert "x/one/sx.txt" not in lines          # 不进入

    @requires_symlink
    def test_symlink_file_labelled_symlink(self, tmp_dir):
        _make_files(tmp_dir, ["t.txt"])
        os.symlink(os.path.join(tmp_dir, "t.txt"), os.path.join(tmp_dir, "tlk"))
        lines = file_tools_listdir(tmp_dir, types=["symlink"]).content[0].text.splitlines()
        assert "tlk" in lines
        assert "t.txt" not in lines

    @requires_symlink
    def test_cycle_warning_row_inline(self, tmp_dir):
        _build_cycle_tree(tmp_dir)
        text = file_tools_listdir(tmp_dir, recursive=-1).content[0].text
        assert text.count("<<<警告") == 1
        assert "a/b/c/loop/ <<<警告，发现symlink环嵌套，跳过该文件夹展开>>>" in text
        assert "a/b/c/loop/fa.txt" not in text      # 环未展开

    @requires_symlink
    def test_cycle_warning_hidden_when_filtered(self, tmp_dir):
        _build_cycle_tree(tmp_dir)
        # 警告行是普通目录条目：types=file 时被隐藏，无尾部汇报
        text = file_tools_listdir(tmp_dir, recursive=-1,
                                  types=["file"]).content[0].text
        assert "<<<警告" not in text
        assert "a/fa.txt" in text
        # contains 不命中环路径 → 警告同样消失（后缀不参与匹配，用纯路径判定）
        text2 = file_tools_listdir(tmp_dir, recursive=-1,
                                   contains=["fa.txt"]).content[0].text
        assert "<<<警告" not in text2
        assert "a/b/c/loop" not in text2

    @requires_symlink
    def test_legit_reuse_not_pruned(self, tmp_dir):
        _build_cycle_tree(tmp_dir)
        lines = file_tools_listdir(tmp_dir, recursive=-1).content[0].text.splitlines()
        assert "x/one/sx.txt" in lines
        assert "y/two/sx.txt" in lines              # 两条复用链都完整展开
        assert "shared/sx.txt" in lines

    @requires_symlink
    def test_follow_false_no_cycle_possible(self, tmp_dir):
        _build_cycle_tree(tmp_dir)
        text = file_tools_listdir(tmp_dir, recursive=-1,
                                  follow_symlink=False).content[0].text
        assert "<<<警告" not in text                # 不进入链接 → 不可能成环
        assert "a/b/c/loop" in text                 # 以 symlink 叶子身份列出


class TestListdirCapsAndFixes:
    """独立审查发现项的回归测试（双上限路径用 monkeypatch 压低模块级上限）。"""

    @staticmethod
    def _patch_caps(monkeypatch, match=None, visit=None):
        import tools.info as info_mod
        if match is not None:
            monkeypatch.setattr(info_mod, "_LISTDIR_MAX_MATCH", match)
        if visit is not None:
            monkeypatch.setattr(info_mod, "_LISTDIR_MAX_VISIT", visit)

    # ── Bug1 回归：早退路径不得吞掉截断提示/统计 ──

    def test_visit_cap_hint_on_zero_match(self, tmp_dir, monkeypatch):
        self._patch_caps(monkeypatch, visit=10)
        _make_files(tmp_dir, [f"f{i}.txt" for i in range(25)])
        text = file_tools_listdir(tmp_dir, contains=["nothing_here"]).content[0].text
        assert text.startswith("（无匹配条目")
        assert "提前停止扫描" in text and "exclude" in text

    def test_visit_cap_hint_with_matches(self, tmp_dir, monkeypatch):
        self._patch_caps(monkeypatch, visit=10)
        _make_files(tmp_dir, [f"f{i}.txt" for i in range(25)])
        # ".txt" 全命中 → 必然走"有匹配但检查数触顶"路径（顺序无关，确定性强）
        text = file_tools_listdir(tmp_dir, contains=[".txt"]).content[0].text
        assert "过滤统计" in text and "提前停止扫描" in text

    def test_match_cap_message_and_stats(self, tmp_dir, monkeypatch):
        self._patch_caps(monkeypatch, match=5)
        _make_files(tmp_dir, [f"f{i:02d}.txt" for i in range(10)])
        text = file_tools_listdir(tmp_dir, extensions=["txt"]).content[0].text
        assert "搜索文件超过5条" in text
        assert "过滤统计" in text

    def test_start_out_of_range_with_filter_has_stats(self, tmp_dir):
        _make_files(tmp_dir, ["m0.md", "m1.md", "m2.md", "z.txt"])
        text = file_tools_listdir(tmp_dir, extensions=["md"],
                                  start=10).content[0].text
        assert "没有更多条目，共 3 个条目" in text
        assert "过滤统计" in text

    def test_start_out_of_range_no_filter_verbatim(self, tmp_dir):
        """无过滤器时早退消息必须与 v1.2.4 逐字一致（不追加任何新行）。"""
        _make_files(tmp_dir, ["a.txt", "b.txt"])
        text = file_tools_listdir(tmp_dir, start=10).content[0].text
        assert text == "（没有更多条目，共 2 个条目，当前从第 10 个开始）"

    # ── Bug2 回归：all 与非法值混合不受顺序影响 ──

    def test_types_all_with_bogus_still_errors(self, tmp_dir):
        for combo in (["all", "bogus"], ["bogus", "all"], ["file", "all", "x"]):
            r = file_tools_listdir(tmp_dir, types=combo)
            assert "失败" in r.content[0].text, combo
            assert "types" in r.content[0].text, combo

    # ── Bug4 回归：空 token 后缀 = 不过滤 ──

    def test_extensions_invalid_dot_tokens_noop(self, tmp_dir):
        _make_files(tmp_dir, ["README", "a.py"])
        base = file_tools_listdir(tmp_dir).content[0].text
        for token in (".", "*.", "*."):
            r = file_tools_listdir(tmp_dir, extensions=[token]).content[0].text
            assert r == base, token

    # ── Bug5：link 别名承诺化 ──

    def test_types_link_alias_valid(self, tmp_dir):
        _make_files(tmp_dir, ["a.txt"])
        r = file_tools_listdir(tmp_dir, types=["link"]).content[0].text
        assert "不合法" not in r
        assert "无匹配条目" in r          # 普通目录无 symlink，走过滤而非报错

    # ── 尾斜杠排序顺序固化 ──

    def test_sort_trailing_slash_order(self, tmp_dir):
        _make_files(tmp_dir, ["a_dir.txt", "a_dir/"])
        lines = file_tools_listdir(tmp_dir).content[0].text.splitlines()
        # '.'(0x2E) < '/'(0x2F)：同前缀文件排在目录前
        assert lines == ["a_dir.txt", "a_dir/"]

    # ── Bug3 裁决：断链符号链接可见（type=symlink、元数据空） ──

    @requires_symlink
    def test_broken_symlink_is_listed(self, tmp_dir):
        _make_files(tmp_dir, ["ok.txt"])
        os.symlink(os.path.join(tmp_dir, "no_such_target_xyz"),
                   os.path.join(tmp_dir, "dangling"))
        os.symlink(os.path.join(tmp_dir, "ok.txt"),
                   os.path.join(tmp_dir, "good"))
        text = file_tools_listdir(tmp_dir).content[0].text
        assert "dangling <<<警告，符号链接目标不可达>>>" in text
        assert "good <<<" not in text               # 健康链接无警告
        assert "ok.txt" in text
        # follow=False 同样判断（可达性与遍历策略无关）
        text2 = file_tools_listdir(tmp_dir, follow_symlink=False).content[0].text
        assert "dangling <<<警告，符号链接目标不可达>>>" in text2
        # columns 下不崩溃：size 为 0、type 照常 symlink
        text3 = file_tools_listdir(tmp_dir, columns=["size", "type"]).content[0].text
        assert "| 0 | symlink |" in text3

    @requires_symlink
    def test_broken_suffix_not_in_matching(self, tmp_dir):
        _make_files(tmp_dir, ["ok.txt"])
        os.symlink(os.path.join(tmp_dir, "gone_xyz"),
                   os.path.join(tmp_dir, "dangling"))
        # contains 搜警告文字 → 不命中（匹配只看纯路径）
        assert "无匹配条目" in file_tools_listdir(
            tmp_dir, contains=["不可达"]).content[0].text
        # regex `dangling$` 纯路径锚定照常命中（警告后缀不挡 $）
        lines = file_tools_listdir(tmp_dir,
                                   regex=r"dangling$").content[0].text.splitlines()
        assert any(l.startswith("dangling <<<") for l in lines)
        # exclude 按纯路径排除断链
        text = file_tools_listdir(tmp_dir,
                                  exclude=["dangling"]).content[0].text
        assert "dangling" not in text

    # ── 环警告与 Markdown 表格共存 ──

    @requires_symlink
    def test_cycle_warning_in_markdown_table(self, tmp_dir):
        _build_cycle_tree(tmp_dir)
        text = file_tools_listdir(tmp_dir, recursive=-1,
                                  columns=["type"]).content[0].text
        warn_lines = [l for l in text.splitlines() if "警告" in l]
        assert len(warn_lines) == 1
        assert warn_lines[0].startswith("| a/b/c/loop/ <<<警告")
        assert "| directory |" in warn_lines[0]      # 仅 name 列带警告

    @requires_symlink
    def test_no_cycle_warning_when_depth_insufficient(self, tmp_dir):
        _build_cycle_tree(tmp_dir)
        # loop 位于深度 4；recursive=2 遍历到不了 → 无环判定机会，也不应告警
        text = file_tools_listdir(tmp_dir, recursive=2).content[0].text
        assert "警告" not in text
        assert "a/b/" in text
        assert "a/b/c/" not in text


class TestListdirEdgeCorners:
    """行覆盖审计后的补网测试：防御分支、上限×分页组合、语义固化。"""

    @staticmethod
    def _cap(monkeypatch, match=None, visit=None):
        import tools.info as info_mod
        if match is not None:
            monkeypatch.setattr(info_mod, "_LISTDIR_MAX_MATCH", match)
        if visit is not None:
            monkeypatch.setattr(info_mod, "_LISTDIR_MAX_VISIT", visit)

    # ── parse_int 字符串非法路径（recursive/start，count 旧已有）──

    def test_recursive_illegal_string(self, tmp_dir):
        r = file_tools_listdir(tmp_dir, recursive="abc")
        assert "失败" in r.content[0].text

    def test_start_illegal_string(self, tmp_dir):
        r = file_tools_listdir(tmp_dir, start="1.5")
        assert "失败" in r.content[0].text

    # ── created_at 列首次实弹 ──

    def test_created_at_column(self, tmp_dir):
        _make_files(tmp_dir, ["a.txt"])
        text = file_tools_listdir(tmp_dir, columns=["created_at", "type"]).content[0].text
        assert "| created_at |" in text
        assert "a.txt" in text and "20" in text      # 年份数字存在
        # sort_by=created_at 的隐式收集也走同一路径
        text2 = file_tools_listdir(tmp_dir, sort_by="created_at",
                                   ascending=False).content[0].text
        assert "a.txt" in text2

    # ── 防御性 OSError 分支 ──

    def test_entry_type_probe_failure_falls_back_to_file(self, tmp_dir, monkeypatch):
        class _ErrEntry:
            def __init__(self, base):
                self.name = "boom"
                self.path = os.path.join(base, "boom")

            def is_symlink(self):
                raise OSError("probe fail")

            def is_dir(self, follow_symlinks=True):
                raise OSError("probe fail")

            def stat(self):
                raise OSError("probe fail")

        import os as os_mod

        real_scandir = os_mod.scandir

        def fake_scandir(p):
            if os.path.abspath(p) == os.path.abspath(tmp_dir):
                return iter([_ErrEntry(tmp_dir)])
            return real_scandir(p)

        monkeypatch.setattr(os_mod, "scandir", fake_scandir)
        try:
            text = file_tools_listdir(tmp_dir).content[0].text
        finally:
            # 立即还原：tmp_dir fixture 的 rmtree 会在 teardown 期调用 os.scandir
            monkeypatch.undo()
        assert "boom" in text                        # 探测失败按 file 处理不丢弃

    def test_scandir_oserror_skips_dir(self, tmp_dir, monkeypatch):
        import os as os_mod

        def boom(p):
            raise PermissionError("denied")

        monkeypatch.setattr(os_mod, "scandir", boom)
        try:
            text = file_tools_listdir(tmp_dir).content[0].text
        finally:
            monkeypatch.undo()          # 别让 rmtree 清理也吃 PermissionError
        assert text == "（空目录，无条目）"            # 静默跳过，不崩溃

    def test_realpath_failure_no_crash(self, tmp_dir, monkeypatch):
        """根/子目录 realpath 全炸：靠双守卫降级为"不防环"，功能不中断。"""
        _make_files(tmp_dir, ["a.txt", "sub/"])
        import os as os_mod

        def boom(p):
            raise OSError("rp down")

        monkeypatch.setattr(os_mod.path, "realpath", boom)
        try:
            text = file_tools_listdir(tmp_dir, recursive=2).content[0].text
        finally:
            monkeypatch.undo()
        assert "a.txt" in text and "sub/" in text

    # ── 上限 × 递归 / 上限 × 越界分页 ──

    def test_match_cap_inside_recursion(self, tmp_dir, monkeypatch):
        self._cap(monkeypatch, match=2)
        _make_files(tmp_dir, ["sub/", "sub/f1.txt", "sub/f2.txt", "sub/f3.txt"])
        text = file_tools_listdir(tmp_dir, recursive=-1,
                                  extensions=["txt"]).content[0].text
        assert "搜索文件超过2条" in text

    def test_match_cap_with_start_out_of_range(self, tmp_dir, monkeypatch):
        self._cap(monkeypatch, match=3)
        _make_files(tmp_dir, [f"t{i}.txt" for i in range(10)])
        text = file_tools_listdir(tmp_dir, extensions=["txt"],
                                  start=100).content[0].text
        assert "没有更多条目，共 3 个条目" in text
        assert "过滤统计" in text and "搜索文件超过3条" in text

    def test_visit_cap_with_start_out_of_range(self, tmp_dir, monkeypatch):
        self._cap(monkeypatch, visit=8)
        _make_files(tmp_dir, [f"t{i}.txt" for i in range(20)])
        text = file_tools_listdir(tmp_dir, contains=[".txt"],
                                  start=100).content[0].text
        assert "没有更多条目" in text and "过滤统计" in text
        assert "提前停止扫描" in text

    # ── 参数语义固化（LLM 易踩的角落）──

    def test_contains_is_literal_not_glob(self, tmp_dir):
        _make_files(tmp_dir, ["ab.txt"])
        assert "无匹配条目" in file_tools_listdir(
            tmp_dir, contains=["a*"]).content[0].text      # "*" 是字面量非通配

    def test_extension_semantics_dotfile_and_multidot(self, tmp_dir):
        _make_files(tmp_dir, [".hidden", "plain", "a.tar.gz", "x.tar"])
        lines = file_tools_listdir(tmp_dir, extensions=["gz"]).content[0].text.splitlines()
        assert "a.tar.gz" in lines                 # 多后缀取最后一段
        assert "x.tar" not in lines
        assert ".hidden" not in lines              # dotfile 无后缀
        hidden_view = file_tools_listdir(tmp_dir,
                                         extensions=["hidden"]).content[0].text
        assert "无匹配条目" in hidden_view            # "hidden" 不是它的后缀
        plain_view = file_tools_listdir(tmp_dir,
                                        extensions=["plain"]).content[0].text
        assert "无匹配条目" in plain_view             # 无点裸名不算后缀

    def test_empty_or_whitespace_filters_are_noop(self, tmp_dir):
        _make_files(tmp_dir, ["a.txt"])
        base = file_tools_listdir(tmp_dir).content[0].text
        for kw in ({"regex": ""}, {"regex": "  "}, {"contains": ""},
                   {"contains": ["", "  "]}, {"extensions": " "},
                   {"exclude": ""}, {"types": "  "}):
            got = file_tools_listdir(tmp_dir, **kw).content[0].text
            assert got == base, kw                 # 全空输入 = 不过滤且无统计行

    def test_regex_mid_global_flag_reports_error(self, tmp_dir):
        r = file_tools_listdir(tmp_dir, regex="a(?i)b")  # 全局标志必须在开头
        assert "失败" in r.content[0].text and "regex" in r.content[0].text

    def test_regex_local_case_group_works(self, tmp_dir):
        _make_files(tmp_dir, ["ABC.txt"])
        text = file_tools_listdir(tmp_dir, regex=r"(?i:abc)\.txt").content[0].text
        assert "ABC.txt" in text                   # 局部不区分大小写组可用

    def test_regex_lookahead_expresses_contains_and(self, tmp_dir):
        _make_files(tmp_dir, ["a_b.txt", "solo.txt"])
        text = file_tools_listdir(tmp_dir, regex=r"^(?=.*a)(?=.*b)[^/]+$").content[0].text
        assert "a_b.txt" in text and "solo.txt" not in text   # AND 需求交给前瞻

    def test_regex_exact_directory_anchor(self, subdir_structure):
        text = file_tools_listdir(subdir_structure, recursive=-1,
                                  regex=r"^dir_a/$").content[0].text
        assert "dir_a/" in text                    # 精确锚定只命中目录自身
        assert "sub_file1" not in text

    def test_exclude_star_excludes_everything(self, tmp_dir):
        _make_files(tmp_dir, ["a.txt", "d/"])
        text = file_tools_listdir(tmp_dir, recursive=2,
                                  exclude=["*"]).content[0].text
        assert text.startswith("（无匹配条目")


    def test_exclude_question_mark_glob(self, tmp_dir):
        _make_files(tmp_dir, ["a.txt", "ab.txt"])
        lines = file_tools_listdir(tmp_dir, exclude=["a?.txt"]).content[0].text.splitlines()
        assert "a.txt" in lines and "ab.txt" not in lines

    def test_exclude_trailing_slash_dir_only(self, subdir_structure):
        """gitignore 语义：`dir_a/` 命中目录并整树剪枝（v1.3 时代它是死模式）。"""
        text = file_tools_listdir(subdir_structure, recursive=-1,
                                  exclude=["dir_a/"]).content[0].text
        assert "dir_a" not in text                      # 目录整树消失
        assert "dir_b" in text                          # 其余不受影响

    def test_exclude_negation_reinclude(self, tmp_dir):
        """gitignore 取反：`!keep.log` 在 `*.log` 排除中豁免特定文件。"""
        _make_files(tmp_dir, ["a.log", "keep.log", "b.txt"])
        lines = file_tools_listdir(
            tmp_dir, exclude=["*.log", "!keep.log"]).content[0].text.splitlines()
        assert "keep.log" in lines and "a.log" not in lines and "b.txt" in lines

    def test_exclude_root_anchored_slash(self, tmp_dir):
        """gitignore 锚根：`/top.txt` 只命中根层，深层同名不中。"""
        _make_files(tmp_dir, ["sub/", "top.txt", "sub/top.txt"])
        lines = file_tools_listdir(tmp_dir, recursive=-1,
                                   exclude=["/top.txt"]).content[0].text.splitlines()
        assert "top.txt" not in lines and "sub/top.txt" in lines

    def test_exclude_no_reinclude_inside_pruned_dir(self, tmp_dir):
        """命中目录整树剪枝后，子项 `!` 豁免无法复活（与 git 行为一致）。"""
        _make_files(tmp_dir, ["dist/", "dist/app.js", "dist/keep.js"])
        text = file_tools_listdir(tmp_dir, recursive=-1,
                                  exclude=["dist/", "!dist/keep.js"]).content[0].text
        assert "dist" not in text and "keep.js" not in text

    def test_exclude_invalid_pattern_chinese_error(self, tmp_dir):
        """F1 钉死：半截 `!` 等非法模式必须走中文报错，不许抛异常/英文 traceback。"""
        for bad in ("!", "! ", "[z-a]"):
            text = file_tools_listdir(tmp_dir, exclude=[bad]).content[0].text
            assert "失败" in text and "exclude" in text and "gitignore" in text, bad

    def test_exclude_hash_is_comment(self, tmp_dir):
        """行为漂移钉：`#` 开头模式按 gitignore 注释忽略，不排除同名文件。"""
        _make_files(tmp_dir, ["#flag", "keep.txt"])
        lines = file_tools_listdir(tmp_dir, exclude=["#flag"]).content[0].text.splitlines()
        assert "#flag" in lines and "keep.txt" in lines

    def test_exclude_case_insensitive(self, tmp_dir):
        """双 lower 胶水钉：模式大小写与路径大小写互不敏感（Windows 语义）。"""
        _make_files(tmp_dir, ["BIG/", "BIG/x.log", "Y.log"])
        text = file_tools_listdir(tmp_dir, recursive=-1,
                                  exclude=["big/", "*.LOG"]).content[0].text
        assert "BIG" not in text and "y.log" not in text.lower().replace("big", "")
        # 上层小写模式吞大写目录 + 大写后缀模式吞小写文件，两向都过

    def test_exclude_barename_nested_prune(self, subdir_structure):
        """gitignore 核心承诺补钉：裸名在嵌套层同样整树剪枝。"""
        text = file_tools_listdir(subdir_structure, recursive=-1,
                                  exclude=["sub_dir1"]).content[0].text
        assert "sub_dir1" not in text                  # 根下 dir_a 里的嵌套目录被剪
        assert "dir_a/sub_file1.txt" in text            # 兄弟不波及


    def test_footer_order_pagination_before_stats(self, tmp_dir):
        _make_files(tmp_dir, [f"f{i}.txt" for i in range(10)])
        text = file_tools_listdir(tmp_dir, contains=[".txt"], count=3).content[0].text
        assert text.index("当前列出的条目") < text.index("过滤统计")

    def test_unicode_chinese_names_match(self, tmp_dir):
        _make_files(tmp_dir, ["中文测试.txt", "other.txt"])
        t1 = file_tools_listdir(tmp_dir, contains=["中文"]).content[0].text
        assert "中文测试.txt" in t1 and "other.txt" not in t1
        t2 = file_tools_listdir(tmp_dir, regex="中文").content[0].text
        assert "中文测试.txt" in t2

    # ── symlink 边角 ──

    @requires_symlink
    def test_symlink_ext_by_link_name_size_follows_target(self, tmp_dir):
        with open(os.path.join(tmp_dir, "big.bin"), "w") as f:
            f.write("x" * 100)
        os.symlink(os.path.join(tmp_dir, "big.bin"),
                   os.path.join(tmp_dir, "lnk.py"))
        text = file_tools_listdir(tmp_dir, extensions=["py"]).content[0].text
        assert "lnk.py" in text and "big.bin" not in text   # 后缀按链接名
        text2 = file_tools_listdir(tmp_dir, columns=["size", "type"]).content[0].text
        assert "| 100 | symlink |" in text2                 # 元数据随目标

    @requires_symlink
    def test_self_loop_pointing_to_scan_root(self, tmp_dir):
        os.symlink(tmp_dir, os.path.join(tmp_dir, "me"), target_is_directory=True)
        _make_files(tmp_dir, ["in.txt"])
        text = file_tools_listdir(tmp_dir, recursive=-1).content[0].text
        assert "me/ <<<警告，发现symlink环嵌套" in text       # 指向遍历根本身也算环
        assert text.count("<<<警告") == 1
        assert "me/me" not in text and "me/in.txt" not in text

    # ── 分支覆盖补网（coverage.py 揪出）──

    def test_non_sequence_filter_values_are_noop(self, tmp_dir):
        """_listdir_as_str_list 的"既非 str 也非 list/tuple"兜底分支。"""
        _make_files(tmp_dir, ["a.txt"])
        base = file_tools_listdir(tmp_dir).content[0].text
        for kw in ({"extensions": 123}, {"contains": {"k": "v"}},
                   {"exclude": 3.5}, {"extensions": ["*"]}):
            got = file_tools_listdir(tmp_dir, **kw).content[0].text
            assert got == base, kw     # 不可识别输入与裸 "*" 均 = 不过滤

    def test_all_columns_markdown(self, tmp_dir):
        """六列全开：走满 gather_set 多列循环（含 extension 之后的回路）。"""
        _make_files(tmp_dir, ["a.txt"])
        text = file_tools_listdir(
            tmp_dir, columns=["size", "permissions", "type",
                              "modified_at", "created_at", "extension"]
        ).content[0].text
        lines = text.strip().splitlines()
        assert lines[0] == ("| name | size | permissions | type | "
                            "modified_at | created_at | extension |")
        row = lines[2]
        assert row.startswith("| a.txt | 0 |")
        assert "| file |" in row
        assert row.endswith("| .txt |")   # extension 列保留前导点（旧口径）

    # ── 联机验收事故回归：通道把数组序列化成字符串 ──

    def test_json_encoded_string_arrays_restore(self, subdir_structure):
        """'["py"]' 这类字符串化数组必须还原为真数组（联机事故复现）。"""
        text = file_tools_listdir(subdir_structure, recursive=-1,
                                  extensions='["txt"]',
                                  exclude='["dir_a", "dir_b"]',
                                  types='["file"]').content[0].text
        assert "file_a.txt" in text
        assert "dir_a" not in text and "dir_b" not in text
        assert "过滤统计" in text          # 过滤器真实激活

    def test_json_string_single_element(self, tmp_dir):
        _make_files(tmp_dir, ["a.py", "b.txt"])
        text = file_tools_listdir(tmp_dir,
                                  extensions='["py"]').content[0].text
        assert "a.py" in text and "b.txt" not in text
        text2 = file_tools_listdir(tmp_dir,
                                   contains='[".md"]').content[0].text
        assert "无匹配条目" in text2      # 解析后确无 .md 命中

    def test_columns_json_string(self, tmp_dir):
        _make_files(tmp_dir, ["a.txt"])
        text = file_tools_listdir(tmp_dir,
                                  columns='["size", "type"]').content[0].text
        assert "| name | size | type |" in text     # 不再是逐字符空转

    def test_malformed_bracket_string_stays_literal(self, tmp_dir):
        """JSON 解析失败/非数组的方括号串退回字面量 token，不炸不猜。"""
        _make_files(tmp_dir, ["a.txt"])
        text = file_tools_listdir(tmp_dir,
                                  contains='["unclosed').content[0].text
        assert "无匹配条目" in text                  # 按字面子串处理
        text2 = file_tools_listdir(tmp_dir, exclude='{}').content[0].text
        assert "a.txt" in text2                      # 字面 glob 无人命中
        base = file_tools_listdir(tmp_dir).content[0].text
        assert file_tools_listdir(tmp_dir, exclude='[]').content[0].text == base
        # '[]' 解析为空数组 = 不过滤（无统计行，与基线逐字一致）


class TestInfo:
    def test_file(self, tmp_file):
        result = file_tools_info(tmp_file)
        data = json.loads(result.content[0].text)
        assert data["exists"] is True
        assert data["is_file"] is True
        assert data["size"] > 0
        assert "path" in data

    def test_directory(self, tmp_dir):
        result = file_tools_info(tmp_dir)
        data = json.loads(result.content[0].text)
        assert data["exists"] is True
        assert data["is_dir"] is True

    def test_nonexistent(self):
        result = file_tools_info("/nonexistent_xyz_789")
        assert "失败" in result.content[0].text
        assert "不存在" in result.content[0].text

    def test_fields(self, tmp_file):
        result = file_tools_info(tmp_file)
        data = json.loads(result.content[0].text)
        assert "permissions" in data
        assert "created_at" in data
        assert "modified_at" in data

    def test_json_format(self, tmp_file):
        result = file_tools_info(tmp_file)
        json.loads(result.content[0].text)

    def test_chinese_filename(self, tmp_dir):
        """中文文件名路径应正确返回信息。"""
        path = os.path.join(tmp_dir, "测试文件.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("test")
        result = file_tools_info(path)
        data = json.loads(result.content[0].text)
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
        data = json.loads(result.content[0].text)
        assert data["exists"] is True
        assert data["is_link"] is True


class TestGuess:
    def test_text_file(self, tmp_file):
        result = file_tools_guess(tmp_file)
        data = json.loads(result.content[0].text)
        assert data["type"] == "text"

    def test_directory(self, tmp_dir):
        result = file_tools_guess(tmp_dir)
        data = json.loads(result.content[0].text)
        assert data["type"] == "directory"

    def test_nonexistent(self):
        result = file_tools_guess("/nonexistent_xyz_789")
        data = json.loads(result.content[0].text)
        assert "error" in data

    def test_encoding_present(self, tmp_file):
        result = file_tools_guess(tmp_file)
        data = json.loads(result.content[0].text)
        assert data.get("encoding") is not None

    def test_gbk_file(self, gbk_file):
        """GBK 编码文件应正确检测编码。"""
        result = file_tools_guess(gbk_file)
        data = json.loads(result.content[0].text)
        assert data["type"] == "text"
        encoding = data.get("encoding", "").lower()
        assert "gb" in encoding or "utf-8" in encoding


class TestDiff:
    def test_same_file(self, tmp_file):
        result = file_tools_diff(tmp_file, tmp_file)
        assert "文件相同" in result.content[0].text

    def test_different_files(self, tmp_dir):
        a = os.path.join(tmp_dir, "a.txt")
        b = os.path.join(tmp_dir, "b.txt")
        with open(a, "w") as f:
            f.write("hello\nworld\n")
        with open(b, "w") as f:
            f.write("hello\npython\nworld\n")
        result = file_tools_diff(a, b)
        assert "python" in result.content[0].text
        assert "@@" in result.content[0].text

    def test_nonexistent(self):
        result = file_tools_diff("/nonexist_a", "/nonexist_b")
        assert "失败" in result.content[0].text

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
        assert "第 2" in result.content[0].text or "changed" in result.content[0].text

    def test_max_chars(self, tmp_dir):
        a = os.path.join(tmp_dir, "a.txt")
        b = os.path.join(tmp_dir, "b.txt")
        with open(a, "w") as f:
            f.write("a\n" * 1000)
        with open(b, "w") as f:
            f.write("b\n" * 1000)
        result = file_tools_diff(a, b, max_chars=100)
        assert "<<truncated>>" in result.content[0].text or len(result.content[0].text) <= 150

    def test_start_lt_1(self, tmp_dir):
        """diff 的 start<1 应报错"""
        a = os.path.join(tmp_dir, "a.txt")
        b = os.path.join(tmp_dir, "b.txt")
        with open(a, "w", encoding="utf-8") as f:
            f.write("hello\nworld\n")
        with open(b, "w", encoding="utf-8") as f:
            f.write("hello\nuniverse\n")
        result = file_tools_diff(a, b, start=0)
        assert "失败" in result.content[0].text
        assert "start" in result.content[0].text
        assert "。。" not in result.content[0].text  # 无双句号

    def test_count_lt_1(self, tmp_dir):
        """diff 的 count<1 应报错"""
        a = os.path.join(tmp_dir, "a.txt")
        b = os.path.join(tmp_dir, "b.txt")
        with open(a, "w", encoding="utf-8") as f:
            f.write("hello\nworld\n")
        with open(b, "w", encoding="utf-8") as f:
            f.write("hello\nuniverse\n")
        result = file_tools_diff(a, b, count=0)
        assert "失败" in result.content[0].text
        assert "count" in result.content[0].text

    def test_start_gt_total_hunks(self, tmp_dir):
        """diff 的 start>total_hunks 应报错"""
        a = os.path.join(tmp_dir, "a.txt")
        b = os.path.join(tmp_dir, "b.txt")
        with open(a, "w", encoding="utf-8") as f:
            f.write("hello\nworld\n")
        with open(b, "w", encoding="utf-8") as f:
            f.write("hello\nuniverse\n")
        result = file_tools_diff(a, b, start=999)
        assert "失败" in result.content[0].text
        assert "超出" in result.content[0].text


class TestHistory:
    def test_no_history(self, tmp_file):
        result = file_tools_history(tmp_file)
        data = json.loads(result.content[0].text)
        assert data["history"] == []

    def test_nonexistent(self):
        result = file_tools_history("/nonexistent_xyz")
        data = json.loads(result.content[0].text)
        assert "error" in data

    def test_after_modifications(self, tmp_file):
        """多次修改文件后，历史记录应包含对应版本。"""
        from tools.edit import file_tools_append, file_tools_replace_lines

        file_tools_append(tmp_file, "new_line\n")
        file_tools_replace_lines(tmp_file, 1, 1, "modified\n")
        result = file_tools_history(tmp_file)
        data = json.loads(result.content[0].text)
        assert len(data["history"]) >= 2
        for entry in data["history"]:
            assert "number" in entry or "history_number" in entry
            assert "created_at" in entry

class TestStrNumParams:
    """数字参数兼容字符串输入。"""

    def test_listdir_string_params_ok(self, tmp_dir):
        os.makedirs(os.path.join(tmp_dir, "sub1"), exist_ok=True)
        result = file_tools_listdir(tmp_dir, recursive="2", start="1", count="500")
        assert "sub1" in result.content[0].text

    def test_listdir_illegal_count(self, tmp_dir):
        result = file_tools_listdir(tmp_dir, count="abc")
        assert "失败" in result.content[0].text
        assert "count 参数应当输入整数" in result.content[0].text

    def test_diff_string_params_ok(self, tmp_dir):
        path_a = os.path.join(tmp_dir, "a.txt")
        path_b = os.path.join(tmp_dir, "b.txt")
        with open(path_a, "w", encoding="utf-8") as f:
            f.write("line1\nline2\n")
        with open(path_b, "w", encoding="utf-8") as f:
            f.write("line1\nCHANGED\n")
        result = file_tools_diff(path_a, path_b, start="1", count="10", max_chars="2048")
        assert "CHANGED" in result.content[0].text

    def test_diff_illegal_start(self, tmp_dir):
        path_a = os.path.join(tmp_dir, "a.txt")
        path_b = os.path.join(tmp_dir, "b.txt")
        with open(path_a, "w", encoding="utf-8") as f:
            f.write("line1\n")
        with open(path_b, "w", encoding="utf-8") as f:
            f.write("line2\n")
        result = file_tools_diff(path_a, path_b, start="x")
        assert "失败" in result.content[0].text
        assert "start 参数应当输入整数" in result.content[0].text


# ── v1.3.1 文案钉死：listdir 以「条目」计（零上下文盲测反馈）──

class TestEntryWording:
    """钉死盲测反馈换来的运行时文案与 docstring 关键句；改动措辞须同步改这里。"""

    def test_pagination_footer_exact(self, tmp_dir):
        _make_files(tmp_dir, [f"f{i}.txt" for i in range(3)])
        text = file_tools_listdir(tmp_dir, count=2).content[0].text
        assert "当前列出的条目 1~2，后面还有 1 个条目。" in text

    def test_start_error_says_entries(self, tmp_dir):
        text = file_tools_listdir(tmp_dir, start=0).content[0].text
        assert "start 表示「从第几个条目开始显示」" in text

    def test_dir_size_column_zero_on_windows(self, tmp_dir):
        if os.sep != "\\":
            pytest.skip("Windows 特有语义：目录 st_size 恒为 0")
        _make_files(tmp_dir, ["d/", "e.txt"])
        text = file_tools_listdir(tmp_dir, columns=["size"]).content[0].text
        assert "| d/ | 0 |" in text            # size 语义写进文档后，行为同步钉死

    def test_docstring_minimal_contract(self):
        """v1.3.3 极简文档契约：只留直觉级说明，注意事项禁止回流。"""
        doc = file_tools_listdir.__doc__
        # 六个一词级保留点（实战价值浓缩）
        assert "只影响显示，不影响遍历" in doc     # types 语义
        assert "目录不受影响" in doc               # extensions 目录直通
        assert "整树跳过" in doc                   # exclude 剪枝
        assert "<<<警告>>>" in doc                 # 环/断链行内标注预告
        assert "别名" in doc                       # dir/symlink 兼容直觉词
        assert "re.search" in doc                  # regex 语义一词
        # 裹脚布不得回流（v1.3.0~1.3.2 堆过的注意事项类）
        for banned in ("所见即所搜", "先校验", "祖先链", "稳定排序",
                       "类型判定速查", "恒为 0", "输出末尾可能依次出现"):
            assert banned not in doc, banned

