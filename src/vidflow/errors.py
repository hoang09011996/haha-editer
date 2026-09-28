class VidflowError(Exception):
    """Lỗi người dùng xử lý được; CLI in thông báo, không in traceback."""


class ScriptError(VidflowError):
    pass


class ConfigError(VidflowError):
    pass


class BudgetError(VidflowError):
    pass


class CapCutRunningError(VidflowError):
    pass
