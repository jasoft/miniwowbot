# -*- encoding=utf8 -*-
"""
错误对话框监控器
在后台线程中循环检测指定的错误弹窗并自动点击确认
"""

import threading
import time
from typing import Iterable, Optional, Sequence

from airtest.core.api import Template, exists, touch, wait


class ErrorDialogMonitor:
    """后台线程监控常见错误弹窗并自动关闭"""

    def __init__(
        self,
        logger,
        error_templates: Optional[Sequence[Template]] = None,
        ok_button_template: Optional[Template] = None,
        check_interval: float = 0.5,
    ):
        """
        Args:
            logger: 用于输出日志的 logger 实例
            error_templates: 要检测的错误弹窗模板列表
            ok_button_template: 关闭弹窗的确认按钮模板
            check_interval: 检测间隔（秒）
        """
        self.logger = logger
        self.check_interval = max(0.1, check_interval)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        default_error_templates: Iterable[Template] = error_templates or [
            Template(r"images/error_duplogin.png", resolution=(720, 1280)),
            Template(r"images/error_network.png", resolution=(720, 1280)),
        ]
        self.error_templates = list(default_error_templates)

        self.ok_button_template = ok_button_template or Template(
            r"images/ok_button.png", resolution=(720, 1280)
        )

    def start(self):
        """启动后台监控线程"""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="ErrorDialogMonitor", daemon=True
        )
        self._thread.start()
        self.logger.debug("错误对话框监控线程已启动")

    def stop(self):
        """停止后台监控线程"""
        if not self._thread:
            return

        self._stop_event.set()
        self._thread.join(timeout=self.check_interval + 1)
        if self._thread.is_alive():
            self.logger.warning("⚠️ 错误对话框监控线程未能在预期时间内停止")
        self._thread = None
        self.logger.debug("错误对话框监控线程已停止")

    def handle_once(self):
        """立即检测一次错误弹窗（同步调用）"""
        self._handle_dialogs()

    def _handle_dialogs(self):
        try:
            for template in self.error_templates:
                if exists(template):
                    self.logger.warning("⚠️ 检测到错误对话框")
                    try:
                        if wait(self.ok_button_template, timeout=1, interval=0.1):
                            touch(self.ok_button_template)
                            self.logger.info("✅ 点击OK按钮关闭错误对话框")
                            time.sleep(1)
                    except Exception:
                        self.logger.debug("关闭错误对话框时出现异常", exc_info=True)
                    break
        except Exception:
            self.logger.debug("错误对话框监控出现异常", exc_info=True)

    def _run(self):
        while not self._stop_event.is_set():
            self._handle_dialogs()
            if self._stop_event.wait(self.check_interval):
                break
