import logging


class Logger(logging.Logger):
    def __init__(self, name, level=logging.NOTSET):
        logging.Logger.__init__(self, name, level)


class SimpleUtils:
    """Простые утилиты"""
    
    @staticmethod
    def format_message(message: str) -> str:
        """Форматировать сообщение"""
        return message.strip()
    
    @staticmethod
    def get_timestamp() -> str:
        """Получить временную метку"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

