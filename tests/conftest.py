"""测试夹具和辅助函数。

注意：通过 sys.path 添加项目根目录以支持测试中的绝对导入。
项目内代码使用相对导入（from ..utils import），
插件动态加载时正常，但 pytest 直接运行时需要 sys.path 辅助。
"""

import os
import shutil
import sys
import tempfile
from typing import Generator

import pytest

# 将项目根目录添加到 sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


@pytest.fixture(autouse=True)
def _mock_session_dir(monkeypatch: pytest.MonkeyPatch, tmp_dir: str) -> None:
    """测试环境中 mock get_session_dir，使其返回临时目录下的路径。

    需要覆盖所有模块的导入绑定，因为各模块通过
    ``from ..utils import get_session_dir`` 值绑定了引用。
    """
    backup_root = os.path.join(tmp_dir, "_file_tools")

    # 先导入各模块，让它们完成 import 绑定
    import utils as utils_mod
    import backup.manager
    import tools.edit
    import tools.info
    import tools.history
    import tools.write
    import tools.bytes

    # 覆盖每个模块的 get_session_dir 引用
    utils_mod.get_session_dir = lambda: backup_root
    backup.manager.get_session_dir = lambda: backup_root
    tools.edit.get_session_dir = lambda: backup_root
    tools.info.get_session_dir = lambda: backup_root
    tools.history.get_session_dir = lambda: backup_root
    tools.write.get_session_dir = lambda: backup_root
    tools.bytes.get_session_dir = lambda: backup_root


@pytest.fixture
def tmp_dir() -> Generator[str, None, None]:
    tmp = tempfile.mkdtemp(prefix="file_tools_test_")
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def tmp_file(tmp_dir: str) -> Generator[str, None, None]:
    path = os.path.join(tmp_dir, "test.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("line1\nline2\nline3\nline4\nline5\n")
    yield path


@pytest.fixture
def multi_line_file(tmp_dir: str) -> Generator[str, None, None]:
    path = os.path.join(tmp_dir, "multi.txt")
    lines = [f"line{i}" for i in range(1, 21)]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    yield path


@pytest.fixture
def cross_line_regex_file(tmp_dir: str) -> Generator[str, None, None]:
    """跨行正则匹配测试文件。"""
    path = os.path.join(tmp_dir, "cross_line.py")
    content = "def foo(x):\n    return x + 1\n\ndef bar():\n    return 42\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    yield path


@pytest.fixture
def long_matched_file(tmp_dir: str) -> Generator[str, None, None]:
    """超长匹配内容测试文件（一行 300 个 x）。"""
    path = os.path.join(tmp_dir, "long_matched.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("x" * 300 + "\n")
    yield path


@pytest.fixture
def empty_file(tmp_dir: str) -> Generator[str, None, None]:
    path = os.path.join(tmp_dir, "empty.txt")
    open(path, "w").close()
    yield path


@pytest.fixture
def gbk_file(tmp_dir: str) -> Generator[str, None, None]:
    path = os.path.join(tmp_dir, "gbk.txt")
    content = "你好世界\n第二行\n第三行\n"
    with open(path, "w", encoding="gbk") as f:
        f.write(content)
    yield path


@pytest.fixture
def crlf_file(tmp_dir: str) -> Generator[str, None, None]:
    path = os.path.join(tmp_dir, "crlf.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("line1\nline2\nline3\n")
    yield path


@pytest.fixture
def subdir_structure(tmp_dir: str) -> Generator[str, None, None]:
    open(os.path.join(tmp_dir, "file_a.txt"), "w").close()
    open(os.path.join(tmp_dir, ".hidden"), "w").close()

    dir_a = os.path.join(tmp_dir, "dir_a")
    os.makedirs(dir_a)
    open(os.path.join(dir_a, "sub_file1.txt"), "w").close()
    os.makedirs(os.path.join(dir_a, "sub_dir1"))

    dir_b = os.path.join(tmp_dir, "dir_b")
    os.makedirs(dir_b)
    open(os.path.join(dir_b, "sub_file2.txt"), "w").close()

    yield tmp_dir


@pytest.fixture
def long_line_file(tmp_dir: str) -> Generator[str, None, None]:
    path = os.path.join(tmp_dir, "long.txt")
    long = "x" * 300
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"short_line\n{long}\nlast_line\n")
    yield path


@pytest.fixture
def chinese_file(tmp_dir: str) -> Generator[str, None, None]:
    path = os.path.join(tmp_dir, "chinese.txt")
    content = "这是第一行\n这是第二行\n这是第三行\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    yield path


@pytest.fixture
def many_medium_lines_file(tmp_dir: str) -> Generator[str, None, None]:
    """30 行，每行 ~50 字符，适合测试 max_chars 截断在中间行。"""
    path = os.path.join(tmp_dir, "many_medium.txt")
    lines = [f"第{i}行 - 这是一段测试文本，用来测试截断提示行号功能。" for i in range(1, 31)]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    yield path


@pytest.fixture
def cross_line_regex_file(tmp_dir: str) -> Generator[str, None, None]:
    """跨行正则匹配测试文件。"""
    path = os.path.join(tmp_dir, "cross_line.py")
    content = "def foo(x):\n    return x + 1\n\ndef bar():\n    return 42\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    yield path


@pytest.fixture
def long_matched_file(tmp_dir: str) -> Generator[str, None, None]:
    """超长匹配内容测试文件（一行 300 个 x）。"""
    path = os.path.join(tmp_dir, "long_matched.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("x" * 300 + "\n")
    yield path
