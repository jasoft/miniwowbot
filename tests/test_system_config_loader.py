#!/usr/bin/env python3
# -*- encoding=utf8 -*-
"""系统配置加载路径测试"""

import pytest

from project_paths import resolve_project_path
from system_config_loader import load_system_config


class TestSystemConfigLoaderPaths:
    """验证系统配置文件路径解析"""

    def test_load_system_config_after_changing_cwd(self, tmp_path, monkeypatch):
        """切换工作目录后也能找到 system_config.json"""
        monkeypatch.chdir(tmp_path)
        loader = load_system_config()
        assert loader.config_file == str(resolve_project_path("system_config.json"))
        assert loader.get_bark_config() is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
