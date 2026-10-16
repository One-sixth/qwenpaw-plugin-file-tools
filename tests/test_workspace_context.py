"""工作区解析真实函数体测试（v1.8.3 复查补钉）。

conftest 的 autouse fixture 会 mock 掉 utils.get_workspace_dir /
get_session_dir 模块属性，因此这里在模块导入阶段（fixture 运行前）
保存原始函数引用，直接测试真实函数体：
- import 路径正确性（qwenpaw.config.context）
- ContextVar 读取语义（项目目录 → agent 工作区 → WORKING_DIR）
- agent 工作区未知时的 RuntimeError 分支
"""

import os
from pathlib import Path

import pytest

import utils as utils_mod

# conftest fixture 尚未运行，此时拿到的是真实函数
_REAL_GET_WORKSPACE_DIR = utils_mod.get_workspace_dir
_REAL_GET_SESSION_DIR = utils_mod.get_session_dir


class TestRealWorkspaceContext:
    """真实函数体测试（绕过 conftest mock，直接读 ContextVar）。"""

    def test_session_dir_uses_agent_workspace(self):
        """get_session_dir 基于 agent 工作区（小窝）。"""
        from qwenpaw.config.context import current_workspace_dir

        token = current_workspace_dir.set(Path("/qs_agent_ws"))
        try:
            result = _REAL_GET_SESSION_DIR()
        finally:
            current_workspace_dir.reset(token)
        assert result == os.path.join(str(Path("/qs_agent_ws")), "file_tools_data")

    def test_session_dir_ignores_project_dir(self):
        """备份小窝不跟随项目目录（即使项目目录已绑定）。"""
        from qwenpaw.config.context import current_project_dir, current_workspace_dir

        t1 = current_project_dir.set(Path("/user_project"))
        t2 = current_workspace_dir.set(Path("/qs_agent_ws"))
        try:
            result = _REAL_GET_SESSION_DIR()
        finally:
            current_project_dir.reset(t1)
            current_workspace_dir.reset(t2)
        assert result == os.path.join(str(Path("/qs_agent_ws")), "file_tools_data")

    def test_session_dir_raises_without_context(self):
        """agent 工作区未知（ContextVar 未注入）时抛 RuntimeError。"""
        from qwenpaw.config.context import current_workspace_dir

        token = current_workspace_dir.set(None)
        try:
            with pytest.raises(RuntimeError):
                _REAL_GET_SESSION_DIR()
        finally:
            current_workspace_dir.reset(token)

    def test_workspace_dir_prefers_project_dir(self):
        """用户文件基准：项目目录优先于 agent 工作区。"""
        from qwenpaw.config.context import current_project_dir, current_workspace_dir

        t1 = current_project_dir.set(Path("/user_project"))
        t2 = current_workspace_dir.set(Path("/qs_agent_ws"))
        try:
            result = _REAL_GET_WORKSPACE_DIR()
        finally:
            current_project_dir.reset(t1)
            current_workspace_dir.reset(t2)
        assert result == str(Path("/user_project"))

    def test_workspace_dir_falls_back_to_agent_workspace(self):
        """用户文件基准：项目目录未绑定时落回 agent 工作区。"""
        from qwenpaw.config.context import current_project_dir, current_workspace_dir

        t1 = current_project_dir.set(None)
        t2 = current_workspace_dir.set(Path("/qs_agent_ws"))
        try:
            result = _REAL_GET_WORKSPACE_DIR()
        finally:
            current_project_dir.reset(t1)
            current_workspace_dir.reset(t2)
        assert result == str(Path("/qs_agent_ws"))
