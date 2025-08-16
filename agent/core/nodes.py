from langchain_core.prompts import PromptTemplate
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from .enums import StageEnum
from .models import State
from .llm import YandexGPT
from .prompts import PROMPTS
from .utils import Logger

logger = Logger("nodes")

class Graph:
    def __init__(self, yandex_gpt: YandexGPT):
        self.gpt = yandex_gpt
        self._memory = MemorySaver()

    def get_graph(self):
        graph = StateGraph(State)
        graph.add_node(StageEnum.ROUTER_NODE, self.router_node)
        graph.add_node(StageEnum.GENERATE_NODE, self.generate_node)
        graph.add_node(StageEnum.OTHER_NODE, self.other_node)

        graph.add_edge(START, StageEnum.ROUTER_NODE)
        graph.add_conditional_edges(
            StageEnum.ROUTER_NODE, 
            self._router_decision,
            {
                StageEnum.GENERATE_NODE: StageEnum.GENERATE_NODE,
                StageEnum.OTHER_NODE: StageEnum.OTHER_NODE,
            }
        )
        graph.add_edge(StageEnum.GENERATE_NODE, END)
        graph.add_edge(StageEnum.OTHER_NODE, END)

        return graph.compile(checkpointer=self._memory)

    def _router_decision(self, state: State) -> str:
        """Определить следующий узел"""
        if state.get('stage') == StageEnum.GENERATE_NODE:
            return StageEnum.GENERATE_NODE
        else:
            return StageEnum.OTHER_NODE

    def router_node(self, state: State) -> Command:
        """Узел маршрутизации"""
        try:
            user_query = state.get('message_from_user', [''])[-1] if state.get('message_from_user') else ''
            
            prompt = PROMPTS["router"]
            response = self.gpt.complete(prompt)
                    
            # Определяем следующий узел на основе ответа LLM
            if "generate_node" in response.lower():
                stage = StageEnum.GENERATE_NODE
            else:
                stage = StageEnum.OTHER_NODE
            
            # Обновляем состояние и переходим к следующему узлу
            updated_state = {
                #"messages": state.get('messages', []) + [f"Маршрутизация: {stage}"],
                "stage": stage
            }
            
            return Command(goto=stage, update=updated_state)
            
        except Exception as e:
            # Fallback на other_node при ошибке
            updated_state = {
                "messages": state.get('messages', []) + [f"Ошибка маршрутизации: {str(e)}"],
                "stage": StageEnum.OTHER_NODE
            }
            return Command(goto=StageEnum.OTHER_NODE, update=updated_state)

    def generate_node(self, state: State) -> Command:
        """Узел генерации ответа"""
        try:
            user_query = state.get('message_from_user', [''])[-1] if state.get('message_from_user') else ''
            
            prompt = PROMPTS["generate_node"] + f"\n\nВопрос пользователя: {user_query}"
            response = self.gpt.complete(prompt)
            
            # Обновляем состояние и переходим к концу
            updated_state = {
                "messages": state.get('messages', []) + [response],
                "message_to_user": response,
                "stage": StageEnum.END
            }
            
            return Command(goto=END, update=updated_state)
            
        except Exception as e:
            # Fallback ответ при ошибке
            response = f"Я понял ваш запрос: '{user_query}'. Это интересный вопрос!"
            updated_state = {
                "messages": state.get('messages', []) + [response],
                "message_to_user": state.get('message_to_user', []) + [response],
                "stage": StageEnum.END
            }
            return Command(goto=END, update=updated_state)

    def other_node(self, state: State) -> Command:
        """Другой узел обработки"""
        try:
            user_query = state.get('message_from_user', [''])[-1] if state.get('message_from_user') else ''
            
            prompt = PROMPTS["other_node"] + f"\n\nЗапрос пользователя: {user_query}"
            response = self.gpt.complete(prompt)
            
            # Обновляем состояние и переходим к концу
            updated_state = {
                "messages": state.get('messages', []) + [response],
                "message_to_user": response,
                "stage": StageEnum.END
            }
            
            return Command(goto=END, update=updated_state)
            
        except Exception as e:
            # Fallback ответ при ошибке
            response = f"Обрабатываю ваш запрос: '{user_query}'. Чем еще могу помочь?"
            updated_state = {
                "messages": state.get('messages', []) + [response],
                "message_to_user": state.get('message_to_user', []) + [response],
                "stage": StageEnum.END
            }
            return Command(goto=END, update=updated_state)

