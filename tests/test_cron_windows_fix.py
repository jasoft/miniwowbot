import sys
import os
import subprocess
import pytest
from unittest.mock import MagicMock

# 将项目根目录添加到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cron_run_all_dungeons

def test_launch_powershell_windows_mock(monkeypatch):
    """测试 Windows 上的 launch_powershell 逻辑（模拟）"""
    mock_popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    # 强制将 IS_WINDOWS 设置为 True 进行此测试
    monkeypatch.setattr(cron_run_all_dungeons, "IS_WINDOWS", True)
    
    logger = MagicMock()
    session = "test_session"
    cmd = "test_cmd"
    
    result = cron_run_all_dungeons.launch_powershell(session, cmd, logger)
    
    assert result is True
    assert mock_popen.called
    args, kwargs = mock_popen.call_args
    
    # 检查 creationflags 是否包含 CREATE_NEW_CONSOLE
    # 注意：在非 Windows 环境下运行测试时，subprocess 可能没有 CREATE_NEW_CONSOLE 属性
    # 我们检查传给 Popen 的值
    expected_flag = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10)
    assert kwargs.get("creationflags") == expected_flag
    
    # 检查命令列表
    cmd_list = args[0]
    assert "powershell" in cmd_list
    assert "-NoExit" in cmd_list
    assert "-Command" in cmd_list
    
    # 检查标题和命令是否在完整命令字符串中
    full_cmd = cmd_list[-1]
    assert f"$Host.UI.RawUI.WindowTitle = '{session}'" in full_cmd
    assert cmd in full_cmd

def test_launch_ocr_service_windows_command(monkeypatch):
    """测试 launch_ocr_service 是否生成了正确的 Windows 命令"""
    mock_launch_pwsh = MagicMock(return_value=True)
    monkeypatch.setattr(cron_run_all_dungeons, "launch_powershell", mock_launch_pwsh)
    monkeypatch.setattr(cron_run_all_dungeons, "IS_WINDOWS", True)
    
    logger = MagicMock()
    cron_run_all_dungeons.launch_ocr_service(logger)
    
    assert mock_launch_pwsh.called
    # call_args[0] 是位置参数元组
    args = mock_launch_pwsh.call_args[0]
    session_name = args[0]
    docker_cmd = args[1]
    
    assert session_name == "ocr_service"
    # 应该存在端口映射
    assert "-p 8080:8080" in docker_cmd
    # 不应该存在 --network=host
    assert "--network=host" not in docker_cmd
    # 应该使用 ${pwd}
    assert "${pwd}" in docker_cmd
    # 应该包含强制删除容器的命令
    assert "docker rm -f paddlex" in docker_cmd

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
