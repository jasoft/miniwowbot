import sys
import os
from unittest.mock import MagicMock, patch
import pytest

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cron_run_all_dungeons

def test_launch_powershell():
    logger = MagicMock()
    with patch("subprocess.run") as mock_run:
        cron_run_all_dungeons.launch_powershell("test_session", "echo hello", logger)
        
        # 验证 subprocess.run 是否被调用，且包含 powershell 和 Start-Process
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "powershell" in args
        assert "Start-Process" in args[2]
        assert "test_session" in args[2]
        assert "echo hello" in args[2]

def test_launch_ocr_service_windows():
    logger = MagicMock()
    # 强制设置 IS_WINDOWS 为 True
    with patch("cron_run_all_dungeons.IS_WINDOWS", True), \
         patch("cron_run_all_dungeons.launch_powershell") as mock_launch:
        
        cron_run_all_dungeons.launch_ocr_service(logger)
        mock_launch.assert_called_once()
        args = mock_launch.call_args[0]
        assert args[0] == "ocr_service"
        assert "docker ps" in args[1]
        assert "Write-Host" in args[1]
        assert "Select-String" in args[1]

def test_main_logic_windows():
    logger = MagicMock()
    mock_sessions = [
        {"name": "test1", "emulator": "127.0.0.1:5555", "configs": ["mage"]}
    ]
    
    with patch("cron_run_all_dungeons.setup_logger", return_value=logger), \
         patch("cron_run_all_dungeons.load_sessions_from_json", return_value=mock_sessions), \
         patch("cron_run_all_dungeons.launch_ocr_service", return_value=True), \
         patch("cron_run_all_dungeons.launch_powershell", return_value=True), \
         patch("cron_run_all_dungeons.IS_WINDOWS", True), \
         patch("time.sleep"):
        
        result = cron_run_all_dungeons.main()
        assert result == 0
        logger.info.assert_any_call("🚀 启动 PowerShell 窗口（JSON 驱动）")

