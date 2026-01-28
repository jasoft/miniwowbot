"""
auto_dungeon 依赖容器模块
"""

class DependencyContainer:
    """依赖注入容器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._config_loader = None
        self._system_config = None
        self._ocr_helper = None
        self._game_actions = None
        self._emulator_manager = None
        self._target_emulator = None
        self._config_name = None
        self._error_dialog_monitor = None
        self._initialized = True

    @property
    def config_loader(self):
        return self._config_loader

    @config_loader.setter
    def config_loader(self, value):
        self._config_loader = value

    @property
    def system_config(self):
        return self._system_config

    @system_config.setter
    def system_config(self, value):
        self._system_config = value

    @property
    def ocr_helper(self):
        return self._ocr_helper

    @ocr_helper.setter
    def ocr_helper(self, value):
        self._ocr_helper = value

    @property
    def game_actions(self):
        return self._game_actions

    @game_actions.setter
    def game_actions(self, value):
        self._game_actions = value

    @property
    def emulator_manager(self):
        return self._emulator_manager

    @emulator_manager.setter
    def emulator_manager(self, value):
        self._emulator_manager = value

    @property
    def target_emulator(self):
        return self._target_emulator

    @target_emulator.setter
    def target_emulator(self, value):
        self._target_emulator = value

    @property
    def config_name(self):
        return self._config_name

    @config_name.setter
    def config_name(self, value):
        self._config_name = value

    @property
    def error_dialog_monitor(self):
        return self._error_dialog_monitor

    @error_dialog_monitor.setter
    def error_dialog_monitor(self, value):
        self._error_dialog_monitor = value

    def reset(self):
        """重置所有依赖"""
        self._config_loader = None
        self._system_config = None
        self._ocr_helper = None
        self._game_actions = None
        self._emulator_manager = None
        self._target_emulator = None
        self._config_name = None
        self._error_dialog_monitor = None
        self._initialized = False


# 全局依赖容器
_container = DependencyContainer()


def get_container() -> DependencyContainer:
    """获取依赖容器"""
    return _container
