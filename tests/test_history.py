"""测试历史回滚工具和备份管理器。"""

import json
import os
import time

from backup.manager import (
    backup_file,
    cleanup_old_backups,
    get_history_count,
    list_history,
    restore_file,
)
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
        assert "已恢复" in result.content[0].text

        with open(tmp_file, "r") as f:
            restored = f.read()
        assert restored == original

    def test_undo_no_history(self, tmp_file):
        result = file_tools_undo(tmp_file, history_number=1)
        assert "失败" in result.content[0].text
        assert "没有历史版本" in result.content[0].text

    def test_undo_invalid_number(self, tmp_file):
        file_tools_replace(tmp_file, "line1", "X")

        result = file_tools_undo(tmp_file, history_number=99)
        assert "失败" in result.content[0].text
        assert "共有" in result.content[0].text

    def test_undo_nonexistent_file(self):
        result = file_tools_undo("/nonexistent_xyz", 1)
        assert "失败" in result.content[0].text

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
        # 第一次修改前备份 → #1（原始），第一次修改后文件变了
        assert restored_2 == after_v1


class TestCleanupOldBackups:
    def test_no_history_dir(self, tmp_dir):
        """history 目录不存在时不应报错。"""
        # 不创建任何备份，直接清理
        cleanup_old_backups(days=30)
        # 不应抛异常

    def test_remove_old_backups(self, tmp_dir):
        """超过保留天数的备份应被移除。"""
        # 创建备份目录（mock 的 get_session_dir 返回 tmp_dir/_file_tools）
        backup_root = os.path.join(tmp_dir, "_file_tools")
        history_dir = os.path.join(backup_root, "history")
        enc_dir = os.path.join(history_dir, "test123")
        os.makedirs(enc_dir)

        # 创建旧备份文件（修改时间为 31 天前）
        old_file = os.path.join(enc_dir, "1")
        with open(old_file, "w") as f:
            f.write("old backup")
        old_time = time.time() - 31 * 86400
        os.utime(old_file, (old_time, old_time))

        # 创建新备份文件（修改时间为 1 天前）
        new_file = os.path.join(enc_dir, "2")
        with open(new_file, "w") as f:
            f.write("new backup")
        new_time = time.time() - 1 * 86400
        os.utime(new_file, (new_time, new_time))

        # 执行清理
        cleanup_old_backups(days=30)

        # 旧文件应被移除，新文件应保留
        assert not os.path.isfile(old_file), "旧备份文件应被移除"
        assert os.path.isfile(new_file), "新备份文件应保留"

    def test_remove_empty_dir(self, tmp_dir):
        """所有备份文件被移除后，空目录应被删除。"""
        backup_root = os.path.join(tmp_dir, "_file_tools")
        history_dir = os.path.join(backup_root, "history")
        enc_dir = os.path.join(history_dir, "test456")
        os.makedirs(enc_dir)

        # 创建仅一个旧备份
        old_file = os.path.join(enc_dir, "1")
        with open(old_file, "w") as f:
            f.write("old")
        old_time = time.time() - 31 * 86400
        os.utime(old_file, (old_time, old_time))

        cleanup_old_backups(days=30)

        # 目录也应被移除
        assert not os.path.isdir(enc_dir), "空备份目录应被移除"

    def test_cleanup_files_json(self, tmp_dir):
        """清理后 files.json 中的无效条目应被移除。"""
        backup_root = os.path.join(tmp_dir, "_file_tools")
        history_dir = os.path.join(backup_root, "history")
        os.makedirs(history_dir)

        # 创建 files.json 包含两个条目，一个有效一个无效
        valid_dir = os.path.join(history_dir, "validhash")
        os.makedirs(valid_dir)
        # 在 valid_dir 中放一个备份文件
        backup_file_path = os.path.join(valid_dir, "1")
        with open(backup_file_path, "w") as f:
            f.write("backup")
        # 确保文件不是旧的
        os.utime(backup_file_path, (time.time(), time.time()))

        files_json = os.path.join(history_dir, "files.json")
        with open(files_json, "w", encoding="utf-8") as f:
            json.dump({"validhash": "/path/to/file", "stalehash": "/path/to/stale"}, f)

        cleanup_old_backups(days=30)

        # stalehash 条目应被移除
        with open(files_json, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        assert "validhash" in mapping
        assert "stalehash" not in mapping, "无效的 files.json 条目应被移除"
class TestUndoStrParams:
    """history_number 兼容字符串输入。"""

    def test_undo_string_ok(self, tmp_file):
        file_tools_replace_lines(tmp_file, "1", "1", "MODIFIED")
        result = file_tools_undo(tmp_file, "1")
        assert "已恢复" in result.content[0].text
        assert "line1" in open(tmp_file, encoding="utf-8").read()

    def test_undo_illegal_string(self, tmp_file):
        file_tools_replace_lines(tmp_file, "1", "1", "MODIFIED")
        result = file_tools_undo(tmp_file, "abc")
        assert "失败" in result.content[0].text
        assert "history_number 参数应当输入整数" in result.content[0].text
