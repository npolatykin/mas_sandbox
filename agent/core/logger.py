"""
Модуль логгера для мультиагентной системы
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

# Импортируем конфигурацию цен
try:
    from .llm_config import YANDEX
except ImportError:
    YANDEX = {}


class LogLevel(Enum):
    """Уровни логирования"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StreamlitLogger:
    """Логгер для интеграции со Streamlit"""
    
    def __init__(self):
        self.logs: List[Dict[str, Any]] = []
        self.max_logs = 1000  # Максимальное количество логов в памяти
        
    def _add_log(self, level: LogLevel, message: str, source: str = "System", details: Optional[Dict] = None):
        """Добавляет лог в память"""
        log_entry = {
            'timestamp': datetime.now().strftime("%H:%M:%S"),
            'level': level.value,
            'message': message,
            'source': source,
            'details': details or {}
        }
        
        self.logs.append(log_entry)
        
        # Ограничиваем количество логов в памяти
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)
    
    def debug(self, message: str, source: str = "System", details: Optional[Dict] = None):
        """Логирование отладочной информации"""
        self._add_log(LogLevel.DEBUG, message, source, details)
        logging.debug(f"[{source}] {message}")
    
    def info(self, message: str, source: str = "System", details: Optional[Dict] = None):
        """Логирование информационных сообщений"""
        self._add_log(LogLevel.INFO, message, source, details)
        logging.info(f"[{source}] {message}")
    
    def warning(self, message: str, source: str = "System", details: Optional[Dict] = None):
        """Логирование предупреждений"""
        self._add_log(LogLevel.WARNING, message, source, details)
        logging.warning(f"[{source}] {message}")
    
    def error(self, message: str, source: str = "System", details: Optional[Dict] = None):
        """Логирование ошибок"""
        self._add_log(LogLevel.ERROR, message, source, details)
        logging.error(f"[{source}] {message}")
    
    def critical(self, message: str, source: str = "System", details: Optional[Dict] = None):
        """Логирование критических ошибок"""
        self._add_log(LogLevel.CRITICAL, message, source, details)
        logging.critical(f"[{source}] {message}")
    
    def log_agent_action(self, action: str, agent_name: str = "Agent", details: Optional[Dict] = None):
        """Логирование действий агента"""
        self.info(f"Действие агента: {action}", f"Agent:{agent_name}", details)
    
    def log_graph_node(self, node_name: str, action: str, details: Optional[Dict] = None):
        """Логирование работы узлов графа"""
        self.info(f"Узел {node_name}: {action}", "Graph", details)
    
    def log_llm_call(self, prompt: str, response: str, model: str = "YandexGPT", details: Optional[Dict] = None):
        """Логирование вызовов LLM"""
        self.info(f"LLM вызов ({model}): {prompt[:100]}...", "LLM", {
            'prompt': prompt,
            'response': response,
            'model': model,
            **(details or {})
        })

    def log_llm(self, response: str, model: str):
        """Логирование вызовов LLM с автоматическим извлечением токенов"""
        # Извлекаем информацию о токенах из объекта ответа
        input_tokens = getattr(response.usage, 'input_text_tokens', 0)
        completion_tokens = getattr(response.usage, 'completion_tokens', 0)
        total_tokens = getattr(response.usage, 'total_tokens', 0)
        reasoning_tokens = getattr(response.usage, 'reasoning_tokens', 0)
        model_version = getattr(response, 'model_version', 'unknown')
        
        # Получаем текст ответа
        response_text = response.alternatives[0].text if hasattr(response, 'alternatives') else str(response)
        
        # Определяем точное название модели для расчета стоимости
        model_key = self._get_model_key(model)
        
        # Логируем с детальной информацией о токенах
        self.log_llm_call_with_tokens(
            prompt="[Автоматически извлечено]",  # Промпт не доступен в этом контексте
            response=response_text,
            model=model_key,
            input_tokens=input_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            reasoning_tokens=reasoning_tokens,
            model_version=model_version,
            details={"response_length": len(response_text)}
        )
    
    def log_llm_call_with_tokens(self, prompt: str, response: str, model: str = "YandexGPT", 
                                input_tokens: int = 0, completion_tokens: int = 0, 
                                total_tokens: int = 0, reasoning_tokens: int = 0, 
                                model_version: str = "", details: Optional[Dict] = None):
        """Логирование вызовов LLM с детальной информацией о токенах"""
        # Рассчитываем стоимость в рублях
        cost_rub = self._calculate_cost_rub(model, total_tokens)
        
        token_info = {
            'input_tokens': input_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': total_tokens,
            'reasoning_tokens': reasoning_tokens,
            'model_version': model_version,
            'cost_rub': cost_rub
        }
        
        self.info(f"LLM вызов ({model}): {prompt[:100]}...", "LLM", {
            'prompt': prompt,
            'response': response,
            'model': model,
            'tokens': token_info,
            **(details or {})
        })
    
    def _calculate_cost_rub(self, model: str, total_tokens: int) -> float:
        """Рассчитывает стоимость в рублях на основе количества токенов"""
        if not total_tokens or model not in YANDEX:
            return 0.0
        
        # Получаем цену за 1000 токенов для модели
        price_per_1000 = YANDEX[model].get("price_per_1000_tokens", 0)
        
        if price_per_1000 == 0:
            return 0.0
        
        # Рассчитываем стоимость: (токены / 1000) * цена_за_1000
        cost = (total_tokens / 1000) * price_per_1000
        return round(cost, 4)  # Округляем до 4 знаков после запятой
    
    def log_user_interaction(self, user_input: str, response: str, details: Optional[Dict] = None):
        """Логирование взаимодействий с пользователем"""
        self.info(f"Пользователь: {user_input[:50]}...", "User", {
            'input': user_input,
            'response': response,
            **(details or {})
        })
    
    def get_logs(self, level: Optional[LogLevel] = None, source: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Получение логов с фильтрацией"""
        filtered_logs = self.logs
        
        if level:
            filtered_logs = [log for log in filtered_logs if log['level'] == level.value]
        
        if source:
            filtered_logs = [log for log in filtered_logs if source in log['source']]
        
        if limit:
            filtered_logs = filtered_logs[-limit:]
        
        return filtered_logs
    
    def get_logs_by_level(self) -> Dict[str, int]:
        """Получение статистики по уровням логирования"""
        stats = {}
        for log in self.logs:
            level = log['level']
            stats[level] = stats.get(level, 0) + 1
        return stats
    
    def clear_logs(self):
        """Очистка всех логов"""
        self.logs.clear()
    
    def export_logs(self) -> str:
        """Экспорт логов в текстовом формате"""
        if not self.logs:
            return "Логи отсутствуют"
        
        export_text = "=== Логи системы ===\n\n"
        for log in self.logs:
            export_text += f"[{log['timestamp']}] {log['level']} [{log['source']}]: {log['message']}\n"
            if log['details']:
                export_text += f"  Детали: {log['details']}\n"
            export_text += "\n"
        
        return export_text

    def get_token_statistics(self) -> Dict[str, Any]:
        """Получение статистики по токенам и стоимости"""
        total_input = 0
        total_completion = 0
        total_reasoning = 0
        total_cost = 0.0
        
        for log in self.logs:
            if log['source'] == 'LLM' and 'tokens' in log.get('details', {}):
                tokens = log['details']['tokens']
                total_input += tokens.get('input_tokens', 0)
                total_completion += tokens.get('completion_tokens', 0)
                total_reasoning += tokens.get('reasoning_tokens', 0)
                total_cost += tokens.get('cost_rub', 0.0)
        
        return {
            'input_tokens': total_input,
            'completion_tokens': total_completion,
            'reasoning_tokens': total_reasoning,
            'total_tokens': total_input + total_completion + total_reasoning,
            'total_cost_rub': round(total_cost, 4)
        }

    def _get_model_key(self, model_name: str) -> str:
        """Определяет ключ модели для конфигурации цен"""
        # Приводим к нижнему регистру и ищем соответствие
        model_lower = model_name.lower()
        
        if "lite" in model_lower:
            return "yandexgpt-lite"
        elif "pro" in model_lower:
            return "yandexgpt-pro"
        else:
            # Возвращаем оригинальное название, если не найдено соответствие
            return model_name


# Глобальный экземпляр логгера
logger = StreamlitLogger()

# Настройка стандартного логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
