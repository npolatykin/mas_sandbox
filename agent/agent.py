from langchain_core.prompts import PromptTemplate
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from .core.enums import StageEnum
from .core.models import State
from .core.logger import logger
import os
from uuid import uuid4

class BaseAgent:
    """Базовый класс агента"""
    
    def __init__(self, graph):
        self.graph = graph
        self.task_tools = None
        self._initialize_task_tools()
    
    def _initialize_task_tools(self):
        """Инициализировать инструменты для задач"""
        # Пока оставляем пустым
        pass
    
    def process_task_command(self, message: str) -> str:
        """Обработать команду для задач"""
        # Простая обработка команд
        message_lower = message.lower()
        
        if "задача" in message_lower:
            return "Я помогу вам с задачами! Что нужно сделать?"
        elif "календарь" in message_lower:
            return "Календарь готов к использованию. Какое событие планируете?"
        elif "помощь" in message_lower:
            return "Я умею помогать с задачами, календарем и отвечать на вопросы. Что вас интересует?"
        else:
            return "Не понимаю команду. Введите 'помощь' для получения справки."


class Agent(BaseAgent):
    def __init__(self, graph: StateGraph):
        super().__init__(graph)
        self.graph = graph
        # один и тот же thread_id на всю сессию CLI,
        # чтобы память переписок сохранялась между сообщениями
        self.thread_id = os.getenv("THREAD_ID") or f"cli-session-{uuid4().hex[:8]}"
        
        # Логируем инициализацию агента
        logger.info(f"Агент инициализирован с thread_id: {self.thread_id}", "Agent")

    def process_message(self, message: str) -> str:
        try:
            # Логируем входящее сообщение
            logger.log_user_interaction(message, "", {"thread_id": self.thread_id})
            
            initial_state = {
                "messages": [],
                "user_data": {"user_id": "default"},
                "stage": "start",
                "message_from_user": [message],
                "message_to_user": []
            }

            # Логируем начало обработки
            logger.info(f"Начинаю обработку сообщения через граф", "Agent", {"state": initial_state})

            # >>> ПЕРЕДАЁМ CONFIG С thread_id <<<
            result = self.graph.invoke(
                initial_state,
                config={"configurable": {"thread_id": self.thread_id}}
            )
            
            # Логируем результат
            logger.info(f"Граф обработал сообщение", "Agent", {"result": result})
            print(result)       

            ai_messages = result.get("message_to_user", [])
            
            # Логируем ответ
            logger.log_user_interaction(message, str(ai_messages), {"thread_id": self.thread_id})
            
            return ai_messages

        except Exception as e:
            # Логируем ошибку
            logger.error(f"Ошибка обработки сообщения: {str(e)}", "Agent", {"message": message, "thread_id": self.thread_id})
            return f"Ошибка обработки: {str(e)}"
