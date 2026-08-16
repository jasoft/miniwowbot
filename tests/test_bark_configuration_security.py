"""Bark 配置安全回归测试。"""

import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_system_config_does_not_contain_bark_credentials() -> None:
    """仓库内的默认 JSON 配置不得包含 Bark 地址或启用通知。"""
    config = json.loads((PROJECT_ROOT / "system_config.json").read_text(encoding="utf-8"))

    assert config["bark"]["enabled"] is False
    assert config["bark"]["server"] == ""


def test_bark_url_is_loaded_from_environment(monkeypatch) -> None:
    """Bark 地址应由环境变量提供，而不是硬编码在 levelup 配置中。"""
    monkeypatch.setenv("BARK_SERVER", "https://example.invalid/device-key")

    module_path = PROJECT_ROOT / "levelup.air" / "config.py"
    spec = importlib.util.spec_from_file_location("levelup_config_security_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.BARK_URL == "https://example.invalid/device-key"
