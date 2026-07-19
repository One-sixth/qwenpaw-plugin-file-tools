"""测试历史回滚工具和备份管理器。"""

import json
import os

from backup.manager import backup_file, get_history_count, list_history, restore_file
from tools.edit import file_tools_replace, file_tools_replace_lines
from tools.history import file_tools_undo


class TestBackupManager:
    def test_backup_file(self, tmp_file):
        number = backup_file(tmp_file)
        assert number is not None
        assert number == 1

    def test_multiple_backups(self, tmp_file):
        n1 = backup_file(tmp_file)
        assert n1 == 1
        with open(tmp_file, "a") as f:
            f.write("modified\n")
        n2 = backup_file(tmp_file)
        assert n2 == 2
        with open(tmp_file, "a") as f:
            f.write("modified again\n")
        n3 = backup_file(tmp_file)
        assert n3 == 3

    def test_list_history(self, tmp_file):
        backup_file(tmp_file)
        with open(tmp_file, "a") as f:
            f.write("v2\n")
        backup_file(tmp_file)
        history = list_history(tmp_file)
        assert len(history) == 2
        assert history[0]["number"] == 1
        assert history[1]["number"] == 2
        assert "created_at" in history[0]

    def test_get_count(self, tmp_file):
        backup_file(tmp_file)
        backup_file(tmp_file)
        assert get_history_count(tmp_file) == 2

    def test_no_history(self, tmp_file):
        assert get_history_count(tmp_file) == 0
        assert list_history(tmp_file) == []

    def test_nonexistent_file(self):
        number = backup_file("/nonexistent_xyz")
        assert number is None

    def test_restore(self, tmp_file):
        with open(tmp_file, "r") as f:
            original = f.read()
        backup_file(tmp_file)

        with open(tmp_file, "w") as f:
            f.write("modified content\n")

        assert restore_file(tmp_file, 1) is True
        with open(tmp_file, "r") as f:
            restored = f.read()
        assert restored == original

    def test_restore_nonexistent_version(self, tmp_file):
        backup_file(tmp_file)
        assert restore_file(tmp_file, 99) is False

    def test_backup_directory_created(self, tmp_file):
        """备份后应能查看到历史。"""
        backup_file(tmp_file)
        history = list_history(tmp_file)
        assert len(history) >= 1


class TestUndo:
    def test_undo_basic(self, tmp_file):
        with open(tmp_file, "r") as f:
            original = f.read()

        file_tools_replace(tmp_file, "line1", "MODIFIED")

        result = file_tools_undo(tmp_file, history_number=1)
        assert "已恢复" in result

        with open(tmp_file, "r") as f:
            restored = f.read()
        assert restored == original

    def test_undo_no_history(self, tmp_file):
        result = file_tools_undo(tmp_file, history_number=1)
        assert "失败" in result
        assert "没有历史版本" in result

    def test_undo_invalid_number(self, tmp_file):
        file_tools_replace(tmp_file, "line1", "X")

        result = file_tools_undo(tmp_file, history_number=99)
        assert "失败" in result
        assert "共有" in result

    def test_undo_nonexistent_file(self):
        result = file_tools_undo("/nonexistent_xyz", 1)
        assert "失败" in result

    def test_undo_multiple_versions(self, multi_line_file):
        with open(multi_line_file, "r") as f:
            original = f.read()

        # 第一次修改：替换第1行
        file_tools_replace_lines(multi_line_file, 1, 1, "v1_first_line")

        with open(multi_line_file, "r") as f:
            after_v1 = f.read()

        # 第二次修改：替换第2行
        file_tools_replace_lines(multi_line_file, 2, 2, "v2_second_line")

        with open(multi_line_file, "r") as f:
            after_v2 = f.read()

        # 确认备份版本存在
        assert get_history_count(multi_line_file) == 2  # 2次修改前各备份1次

        # 恢复到 #1（最初的原始内容）
        file_tools_undo(multi_line_file, history_number=1)
        with open(multi_line_file, "r") as f:
            restored_1 = f.read()
        assert restored_1 == original

        # 恢复到 #2（第一次修改前的备份 = 第一次修改后的文件？不对）
        # backup 在每次修改前调用，所以 #1 = 原始，#2 = 第一次修改后（第一次修改前的状态）
        file_tools_undo(multi_line_file, history_number=2)
        with open(multi_line_file, "r") as f:
            restored_2 = f.read()
        # #2 是第一次修改前备份的 = 原始文件...不对，backup 在修改前调用，
        # 第一次修改前备份 → #1（原始），第一次修改后文件变了
        # 第二次修改前备份 → #2（第一次修改后的文件）
        assert restored_2 == after_v1
