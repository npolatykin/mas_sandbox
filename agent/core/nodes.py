from langchain_core.prompts import PromptTemplate
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from .enums import StageEnum
from .models import State
from .llm import YandexGPT
from .prompts import PROMPTS
from .logger import logger
from .tools import TaskManager
import json
from datetime import datetime

class Graph:
    def __init__(self, yandex_gpt: YandexGPT):
        self.gpt = yandex_gpt
        self._memory = MemorySaver()
        
        # Логируем инициализацию графа
        logger.info("Граф инициализирован", "Graph", {"gpt_available": yandex_gpt is not None})

    def get_graph(self):
        graph = StateGraph(State)
        graph.add_node(StageEnum.ROUTER_NODE, self.router_node)
        graph.add_node(StageEnum.GENERATE_NODE, self.generate_node)
        graph.add_node(StageEnum.OTHER_NODE, self.other_node)
        graph.add_node(StageEnum.TASK_CREATE_NODE, self.task_create_node)
        graph.add_node(StageEnum.TASK_DELETE_NODE, self.task_delete_node)
        graph.add_node(StageEnum.TASK_UPDATE_NODE, self.task_update_node)
        graph.add_node(StageEnum.TASK_SEARCH_NODE, self.task_search_node)

        graph.add_edge(START, StageEnum.ROUTER_NODE)
        graph.add_conditional_edges(
            StageEnum.ROUTER_NODE, 
            self._router_decision,
            {
                StageEnum.GENERATE_NODE: StageEnum.GENERATE_NODE,
                StageEnum.OTHER_NODE: StageEnum.OTHER_NODE,
                StageEnum.TASK_CREATE_NODE: StageEnum.TASK_CREATE_NODE,
                StageEnum.TASK_DELETE_NODE: StageEnum.TASK_DELETE_NODE,
                StageEnum.TASK_UPDATE_NODE: StageEnum.TASK_UPDATE_NODE,
                StageEnum.TASK_SEARCH_NODE: StageEnum.TASK_SEARCH_NODE,
            }
        )
        graph.add_edge(StageEnum.GENERATE_NODE, END)
        graph.add_edge(StageEnum.OTHER_NODE, END)
        graph.add_edge(StageEnum.TASK_CREATE_NODE, END)
        graph.add_edge(StageEnum.TASK_DELETE_NODE, END)
        graph.add_edge(StageEnum.TASK_UPDATE_NODE, END)
        graph.add_edge(StageEnum.TASK_SEARCH_NODE, END)

        logger.info("Граф скомпилирован", "Graph")
        return graph.compile(checkpointer=self._memory)

    def _router_decision(self, state: State) -> str:
        """Определить следующий узел"""
        stage = state.get('stage')
        if stage == StageEnum.GENERATE_NODE:
            return StageEnum.GENERATE_NODE
        elif stage == StageEnum.TASK_CREATE_NODE:
            return StageEnum.TASK_CREATE_NODE
        elif stage == StageEnum.TASK_SEARCH_NODE:
            return StageEnum.TASK_SEARCH_NODE
        elif stage == StageEnum.TASK_UPDATE_NODE:
            return StageEnum.TASK_UPDATE_NODE
        elif stage == StageEnum.TASK_DELETE_NODE:
            return StageEnum.TASK_DELETE_NODE
        else:
            return StageEnum.OTHER_NODE

    def router_node(self, state: State) -> Command:
        """Узел маршрутизации"""
        try:
            user_query = state.get('message_from_user', [''])[-1] if state.get('message_from_user') else ''
            
            logger.log_graph_node("Router", f"Обрабатываю запрос: {user_query[:50]}...")
            
            prompt = PROMPTS["router"] + f"\n\nЗапрос пользователя: {user_query}"
            response = self.gpt.complete(prompt)
                   
            # Определяем следующий узел на основе ответа LLM
            if "generate_node" in response.lower():
                stage = StageEnum.GENERATE_NODE
            elif "task_create" in response.lower():
                stage = StageEnum.TASK_CREATE_NODE
            elif "task_search" in response.lower():
                stage = StageEnum.TASK_SEARCH_NODE
            elif "task_update" in response.lower():
                stage = StageEnum.TASK_UPDATE_NODE
            elif "task_delete" in response.lower():
                stage = StageEnum.TASK_DELETE_NODE
            else:
                stage = StageEnum.OTHER_NODE
            
            # Токены уже залогированы в YandexGPT.complete
            logger.log_graph_node("Router", f"Маршрутизация на узел: {stage}")
            
            # Обновляем состояние и переходим к следующему узлу
            updated_state = {
                #"messages": state.get('messages', []) + [f"Маршрутизация: {stage}"],
                "stage": stage
            }
            
            return Command(goto=stage, update=updated_state)
            
        except Exception as e:
            # Fallback на other_node при ошибке
            logger.error(f"Ошибка в узле маршрутизации: {str(e)}", "Graph", {"node": "Router", "user_query": user_query})
            
            updated_state = {
                "messages": state.get('messages', []) + [f"Ошибка маршрутизации: {str(e)}"],
                "stage": StageEnum.OTHER_NODE
            }
            return Command(goto=StageEnum.OTHER_NODE, update=updated_state)

    def generate_node(self, state: State) -> Command:
        """Узел генерации ответа"""
        try:
            user_query = state.get('message_from_user', [''])[-1] if state.get('message_from_user') else ''
            
            logger.log_graph_node("Generate", f"Генерирую ответ на: {user_query[:50]}...")
            
            prompt = PROMPTS["generate_node"] + f"\n\nВопрос пользователя: {user_query}"
            response = self.gpt.complete(prompt)
            
            # Логируем вызов LLM (токены уже залогированы в YandexGPT.complete)
            logger.log_graph_node("Generate", "Ответ сгенерирован успешно")
            
            # Обновляем состояние и переходим к концу
            updated_state = {
                "messages": state.get('messages', []) + [response],
                "message_to_user": response,
                "stage": StageEnum.END
            }
            
            return Command(goto=END, update=updated_state)
            
        except Exception as e:
            # Fallback ответ при ошибке
            logger.error(f"Ошибка в узле генерации: {str(e)}", "Graph", {"node": "Generate", "user_query": user_query})
            
            response = f"Я понял ваш запрос: '{user_query}'. Это интересный вопрос!"
            updated_state = {
                "messages": state.get('messages', []) + [response],
                "message_to_user": response,
                "stage": StageEnum.END
            }
            return Command(goto=END, update=updated_state)

    def other_node(self, state: State) -> Command:
        """Другой узел обработки"""
        try:
            user_query = state.get('message_from_user', [''])[-1] if state.get('message_from_user') else ''
            
            logger.log_graph_node("Other", f"Обрабатываю запрос: {user_query[:50]}...")
            
            prompt = PROMPTS["other_node"] + f"\n\nЗапрос пользователя: {user_query}"
            response = self.gpt.complete(prompt)
            
            # Логируем вызов LLM (токены уже залогированы в YandexGPT.complete)
            logger.log_graph_node("Other", "Запрос обработан успешно")
            
            # Обновляем состояние и переходим к концу
            updated_state = {
                "messages": state.get('messages', []) + [response],
                "message_to_user": response,
                "stage": StageEnum.END
            }
            
            return Command(goto=END, update=updated_state)
            
        except Exception as e:
            # Fallback ответ при ошибке
            logger.error(f"Ошибка в узле Other: {str(e)}", "Graph", {"node": "Other", "user_query": user_query})
            
            response = f"Обрабатываю ваш запрос: '{user_query}'. Чем еще могу помочь?"
            updated_state = {
                "messages": state.get('messages', []) + [response],
                "message_to_user": response,
                "stage": StageEnum.END
            }
            return Command(goto=END, update=updated_state)

    def task_create_node(self, state: State) -> Command:
        """Узел создания задачи"""
        try:
            user_query = state.get('message_from_user', [''])[-1] if state.get('message_from_user') else ''
            
            logger.log_graph_node("TaskCreate", f"Создаю задачу для запроса: {user_query[:50]}...")
            
            # Промпт для извлечения параметров
            prompt = PROMPTS["task_create"] + f"\n\nЗапрос пользователя: {user_query}"
            response = self.gpt.complete(prompt)
            
            # Очищаем ответ от markdown разметки
            cleaned_response = response.strip()
            if cleaned_response.startswith('```'):
                # Убираем markdown блок
                lines = cleaned_response.split('\n')
                lines = lines[1:]  # Убираем первую строку с ```
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]  # Убираем последнюю строку с ```
                cleaned_response = '\n'.join(lines)
            
            # Исправляем двойные фигурные скобки (из-за экранирования в f-строках промптов)
            cleaned_response = cleaned_response.replace('{{', '{').replace('}}', '}')
            
            # Парсим JSON ответ от YandexGPT
            try:
                params = json.loads(cleaned_response)
                logger.log_graph_node("TaskCreate", f"JSON от YandexGPT: {params}")
            except json.JSONDecodeError as e:
                # Если JSON невалидный - просим переписать
                logger.error(f"JSONDecodeError: {str(e)}", "Graph", {"node": "TaskCreate", "response": response})
                message = "❌ Не удалось распознать данные для создания задачи.\n\nПожалуйста, напишите запрос заново в формате:\n'Создай для пользователя с id [ID] задачу \"[Название]\" с описанием \"[Описание]\"'"
                updated_state = {
                    "message_to_user": message,
                    "stage": StageEnum.END
                }
                return Command(goto=END, update=updated_state)
            
            # Извлекаем параметры из JSON
            user_id = params.get("user_id")
            task_name = params.get("task_name")
            task_description = params.get("task_description")
            
            # Проверяем обязательные поля
            if not user_id or not task_name or not task_description:
                missing_fields = []
                if not user_id: missing_fields.append("user_id")
                if not task_name: missing_fields.append("task_name") 
                if not task_description: missing_fields.append("task_description")
                
                missing_list = ", ".join(missing_fields)
                message = f"❌ Вы ввели не все данные для создания задачи.\n\nНедостающие поля: {missing_list}\n\nПожалуйста, напишите запрос заново с указанием всех полей:\n- user_id (ID пользователя)\n- task_name (Название задачи)\n- task_description (Описание задачи)\n- date (Дата, опционально)"
                updated_state = {
                    "message_to_user": message,
                    "stage": StageEnum.END
                }
                return Command(goto=END, update=updated_state)
            
            # Обрабатываем дату
            user_date = params.get("date")
            if (user_date and 
                user_date != "null" and 
                user_date != "None" and 
                user_date.strip() and
                user_date.strip() != ""):
                date = user_date.strip()
                logger.log_graph_node("TaskCreate", f"Используем дату пользователя: {date}")
            else:
                date = datetime.now().strftime("%Y-%m-%d")
                logger.log_graph_node("TaskCreate", f"Используем текущую дату: {date}")
            
            # Проверяем существование пользователя
            task_manager = TaskManager()
            
            # Проверяем что пользователь существует в системе
            if not task_manager.user_exists(user_id):
                message = f"❌ Пользователь с ID '{user_id}' не найден.\n\nПожалуйста, убедитесь, что указан правильный ID пользователя."
                updated_state = {
                    "message_to_user": message,
                    "stage": StageEnum.END
                }
                return Command(goto=END, update=updated_state)
            
            # Все данные есть - создаем задачу
            task_id = task_manager.create_task(
                user_id=user_id,
                task_name=task_name,
                description=task_description,
                date=date
            )
            
            if task_id:
                success_message = f"✅ Задача успешно создана!\nID: {task_id}\nНазвание: {task_name}\nОписание: {task_description}\nДата: {date}"
                updated_state = {
                    "message_to_user": success_message,
                    "stage": StageEnum.END
                }
            else:
                error_message = "❌ Ошибка создания задачи. Попробуйте еще раз."
                updated_state = {
                    "message_to_user": error_message,
                    "stage": StageEnum.END
                }
            
            return Command(goto=END, update=updated_state)
            
        except Exception as e:
            # Fallback ответ при ошибке
            logger.error(f"Ошибка в узле создания задачи: {str(e)}", "Graph", {"node": "TaskCreate", "user_query": user_query})
            
            error_message = f"❌ Ошибка создания задачи: {str(e)}"
            updated_state = {
                "message_to_user": error_message,
                "stage": StageEnum.END
            }
            return Command(goto=END, update=updated_state)

    def task_delete_node(self, state: State) -> Command:
        """Узел удаления задачи"""
        try:
            user_query = state.get('message_from_user', [''])[-1] if state.get('message_from_user') else ''
            
            logger.log_graph_node("TaskDelete", f"Удаляю задачу для запроса: {user_query[:50]}...")
            
            # Промпт для извлечения task_id
            prompt = PROMPTS["task_delete"] + f"\n\nЗапрос пользователя: {user_query}"
            response = self.gpt.complete(prompt)
            
            # Отладочная информация
            logger.log_graph_node("TaskDelete", f"Ответ YandexGPT: '{response}'")
            
            # Очищаем ответ от markdown разметки
            cleaned_response = response.strip()
            if cleaned_response.startswith('```'):
                # Убираем markdown блок
                lines = cleaned_response.split('\n')
                lines = lines[1:]  # Убираем первую строку с ```
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]  # Убираем последнюю строку с ```
                cleaned_response = '\n'.join(lines)
            
            # Исправляем двойные фигурные скобки (из-за экранирования в f-строках промптов)
            cleaned_response = cleaned_response.replace('{{', '{').replace('}}', '}')
            
            # Парсим JSON ответ от YandexGPT
            try:
                params = json.loads(cleaned_response)
                logger.log_graph_node("TaskDelete", f"JSON от YandexGPT: {params}")
            except json.JSONDecodeError as e:
                # Попытка исправить JSON с одинарными кавычками
                try:
                    # Заменяем одинарные кавычки на двойные (только в ключах и значениях)
                    fixed_response = cleaned_response.replace("'", '"')
                    params = json.loads(fixed_response)
                    logger.log_graph_node("TaskDelete", f"JSON исправлен и распарсен: {params}")
                except json.JSONDecodeError:
                    # Если JSON невалидный - просим переписать
                    logger.error(f"JSONDecodeError: {str(e)}", "Graph", {"node": "TaskDelete", "response": response, "cleaned_response": cleaned_response})
                    message = "❌ Не удалось распознать данные для удаления задачи.\n\nПожалуйста, напишите запрос заново в формате:\n'Удали задачу с id [ID]'"
                    updated_state = {
                        "message_to_user": message,
                        "stage": StageEnum.END
                    }
                    return Command(goto=END, update=updated_state)
            
            # Извлекаем task_id
            task_id = params.get("task_id")
            
            # Проверяем обязательное поле
            if not task_id:
                message = "❌ Не указан ID задачи для удаления.\n\nПожалуйста, напишите запрос заново с указанием ID задачи:\n'Удали задачу с id [ID]'"
                updated_state = {
                    "message_to_user": message,
                    "stage": StageEnum.END
                }
                return Command(goto=END, update=updated_state)
            
            # Проверяем, существует ли задача перед удалением
            task_manager = TaskManager()
            task = task_manager.get_task_by_id(task_id)
            
            if not task:
                message = f"❌ Задача с ID '{task_id}' не найдена.\n\nПроверьте правильность ID и попробуйте еще раз."
                updated_state = {
                    "message_to_user": message,
                    "stage": StageEnum.END
                }
                return Command(goto=END, update=updated_state)
            
            # Удаляем задачу
            success = task_manager.delete_task(task_id)
            
            if success:
                success_message = f"✅ Задача успешно удалена!\nID: {task_id}\nНазвание: {task.get('task_name', 'N/A')}"
                updated_state = {
                    "message_to_user": success_message,
                    "stage": StageEnum.END
                }
            else:
                error_message = f"❌ Ошибка удаления задачи с ID '{task_id}'. Попробуйте еще раз."
                updated_state = {
                    "message_to_user": error_message,
                    "stage": StageEnum.END
                }
            
            return Command(goto=END, update=updated_state)
            
        except Exception as e:
            # Fallback ответ при ошибке
            logger.error(f"Ошибка в узле удаления задачи: {str(e)}", "Graph", {"node": "TaskDelete", "user_query": user_query})
            
            error_message = f"❌ Ошибка удаления задачи: {str(e)}"
            updated_state = {
                "message_to_user": error_message,
                "stage": StageEnum.END
            }
            return Command(goto=END, update=updated_state)

    def task_update_node(self, state: State) -> Command:
        """Узел обновления задачи"""
        try:
            user_query = state.get('message_from_user', [''])[-1] if state.get('message_from_user') else ''
            
            logger.log_graph_node("TaskUpdate", f"Обновляю задачу для запроса: {user_query[:50]}...")
            
            # Промпт для извлечения параметров
            prompt = PROMPTS["task_update"] + f"\n\nЗапрос пользователя: {user_query}"
            response = self.gpt.complete(prompt)
            
            # Отладочная информация
            logger.log_graph_node("TaskUpdate", f"Ответ YandexGPT: '{response}'")
            
            # Очищаем ответ от markdown разметки
            cleaned_response = response.strip()
            if cleaned_response.startswith('```'):
                # Убираем markdown блок
                lines = cleaned_response.split('\n')
                lines = lines[1:]  # Убираем первую строку с ```
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]  # Убираем последнюю строку с ```
                cleaned_response = '\n'.join(lines)
            
            # Исправляем двойные фигурные скобки (из-за экранирования в f-строках промптов)
            cleaned_response = cleaned_response.replace('{{', '{').replace('}}', '}')
            
            # Парсим JSON ответ от YandexGPT
            try:
                params = json.loads(cleaned_response)
                logger.log_graph_node("TaskUpdate", f"JSON от YandexGPT: {params}")
            except json.JSONDecodeError as e:
                # Попытка исправить JSON с одинарными кавычками
                try:
                    # Заменяем одинарные кавычки на двойные (только в ключах и значениях)
                    fixed_response = cleaned_response.replace("'", '"')
                    params = json.loads(fixed_response)
                    logger.log_graph_node("TaskUpdate", f"JSON исправлен и распарсен: {params}")
                except json.JSONDecodeError:
                    # Если JSON невалидный - просим переписать
                    logger.error(f"JSONDecodeError: {str(e)}", "Graph", {"node": "TaskUpdate", "response": response, "cleaned_response": cleaned_response})
                    message = "❌ Не удалось распознать данные для обновления задачи.\n\nПожалуйста, напишите запрос заново в формате:\n'Измени задачу с id [ID]: [что изменить]'"
                    updated_state = {
                        "message_to_user": message,
                        "stage": StageEnum.END
                    }
                    return Command(goto=END, update=updated_state)
            
            # Извлекаем task_id (обязательное поле)
            task_id = params.get("task_id")
            
            # Проверяем обязательное поле
            if not task_id:
                message = "❌ Не указан ID задачи для обновления.\n\nПожалуйста, напишите запрос заново с указанием ID задачи:\n'Измени задачу с id [ID]: [что изменить]'"
                updated_state = {
                    "message_to_user": message,
                    "stage": StageEnum.END
                }
                return Command(goto=END, update=updated_state)
            
            # Проверяем, существует ли задача перед обновлением
            task_manager = TaskManager()
            task = task_manager.get_task_by_id(task_id)
            
            if not task:
                message = f"❌ Задача с ID '{task_id}' не найдена.\n\nПроверьте правильность ID и попробуйте еще раз."
                updated_state = {
                    "message_to_user": message,
                    "stage": StageEnum.END
                }
                return Command(goto=END, update=updated_state)
            
            # Фильтруем обновления: убираем null значения и task_id
            updates = {}
            updateable_fields = ["task_name", "task_description", "task_status", "date"]
            
            for field in updateable_fields:
                value = params.get(field)
                if value and value != "null" and value != "None" and value.strip():
                    updates[field] = value.strip()
            
            # Проверяем, есть ли что обновлять
            if not updates:
                message = "❌ Не указаны поля для обновления.\n\nПожалуйста, укажите что именно нужно изменить:\n- task_name (название)\n- task_description (описание)\n- task_status (статус: pending, in_progress, completed)\n- date (дата в формате YYYY-MM-DD)"
                updated_state = {
                    "message_to_user": message,
                    "stage": StageEnum.END
                }
                return Command(goto=END, update=updated_state)
            
            # Валидация статуса
            if "task_status" in updates:
                valid_statuses = ["pending", "in_progress", "completed", "cancelled"]
                status = updates["task_status"].lower()
                if status not in valid_statuses:
                    message = f"❌ Неверный статус '{status}'.\n\nДопустимые статусы: {', '.join(valid_statuses)}"
                    updated_state = {
                        "message_to_user": message,
                        "stage": StageEnum.END
                    }
                    return Command(goto=END, update=updated_state)
                updates["task_status"] = status
            
            # Валидация даты
            if "date" in updates:
                date_str = updates["date"]
                try:
                    # Проверяем формат YYYY-MM-DD
                    datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    message = f"❌ Неверный формат даты '{date_str}'.\n\nИспользуйте формат YYYY-MM-DD (например: 2025-12-25)"
                    updated_state = {
                        "message_to_user": message,
                        "stage": StageEnum.END
                    }
                    return Command(goto=END, update=updated_state)
            
            # Обновляем задачу
            success = task_manager.update_task(task_id, **updates)
            
            if success:
                # Формируем список измененных полей для отчета
                updated_fields_list = []
                for field in updates.keys():
                    field_name = {
                        "task_name": "название",
                        "task_description": "описание",
                        "task_status": "статус",
                        "date": "дата"
                    }.get(field, field)
                    updated_fields_list.append(field_name)
                
                updated_fields_str = ", ".join(updated_fields_list)
                success_message = f"✅ Задача успешно обновлена!\n\nID: {task_id}\nНазвание: {task.get('task_name', 'N/A')}\nИзмененные поля: {updated_fields_str}"
                
                updated_state = {
                    "message_to_user": success_message,
                    "stage": StageEnum.END
                }
            else:
                error_message = f"❌ Ошибка обновления задачи с ID '{task_id}'. Попробуйте еще раз."
                updated_state = {
                    "message_to_user": error_message,
                    "stage": StageEnum.END
                }
            
            return Command(goto=END, update=updated_state)
            
        except Exception as e:
            # Fallback ответ при ошибке
            logger.error(f"Ошибка в узле обновления задачи: {str(e)}", "Graph", {"node": "TaskUpdate", "user_query": user_query})
            
            error_message = f"❌ Ошибка обновления задачи: {str(e)}"
            updated_state = {
                "message_to_user": error_message,
                "stage": StageEnum.END
            }
            return Command(goto=END, update=updated_state)

    def task_search_node(self, state: State) -> Command:
        """Узел поиска задач с семантическим поиском"""
        try:
            user_query = state.get('message_from_user', [''])[-1] if state.get('message_from_user') else ''
            
            logger.log_graph_node("TaskSearch", f"Ищу задачи для запроса: {user_query[:50]}...")
            
            # Промпт для извлечения параметров поиска
            prompt = PROMPTS["task_search"] + f"\n\nЗапрос пользователя: {user_query}"
            response = self.gpt.complete(prompt)
            
            # Отладочная информация
            logger.log_graph_node("TaskSearch", f"Ответ YandexGPT: '{response}'")
            
            # Очищаем ответ от markdown разметки
            cleaned_response = response.strip()
            if cleaned_response.startswith('```'):
                # Убираем markdown блок
                lines = cleaned_response.split('\n')
                lines = lines[1:]  # Убираем первую строку с ```
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]  # Убираем последнюю строку с ```
                cleaned_response = '\n'.join(lines)
            
            # Исправляем двойные фигурные скобки (из-за экранирования в f-строках промптов)
            cleaned_response = cleaned_response.replace('{{', '{').replace('}}', '}')
            
            # Парсим JSON ответ от YandexGPT
            try:
                params = json.loads(cleaned_response)
                logger.log_graph_node("TaskSearch", f"JSON от YandexGPT: {params}")
            except json.JSONDecodeError as e:
                # Попытка исправить JSON с одинарными кавычками
                try:
                    # Заменяем одинарные кавычки на двойные (только в ключах и значениях)
                    fixed_response = cleaned_response.replace("'", '"')
                    params = json.loads(fixed_response)
                    logger.log_graph_node("TaskSearch", f"JSON исправлен и распарсен: {params}")
                except json.JSONDecodeError:
                    # Если JSON невалидный - просим переписать
                    logger.error(f"JSONDecodeError: {str(e)}", "Graph", {"node": "TaskSearch", "response": response, "cleaned_response": cleaned_response})
                    message = "❌ Не удалось распознать данные для поиска задач.\n\nПожалуйста, напишите запрос заново."
                    updated_state = {
                        "message_to_user": message,
                        "stage": StageEnum.END
                    }
                    return Command(goto=END, update=updated_state)
            
            # Извлекаем параметры поиска
            task_id = params.get("task_id")
            task_name = params.get("task_name")
            task_description = params.get("task_description")
            task_status = params.get("task_status")
            date = params.get("date")
            date_from = params.get("date_from")
            date_to = params.get("date_to")
            user_id = params.get("user_id")
            
            # Проверяем, что указан хотя бы один критерий поиска
            search_criteria = [task_id, task_name, task_description, task_status, date, date_from, date_to, user_id]
            if not any(criteria for criteria in search_criteria if criteria and criteria != "null"):
                message = "❌ Не указаны критерии для поиска.\n\nПожалуйста, укажите хотя бы один критерий:\n- Название задачи\n- Описание задачи\n- Статус\n- Дата или период\n- ID задачи"
                updated_state = {
                    "message_to_user": message,
                    "stage": StageEnum.END
                }
                return Command(goto=END, update=updated_state)
            
            # Выполняем поиск с семантическим поиском и поддержкой периода дат
            task_manager = TaskManager()
            results = task_manager.search_tasks(
                user_id=user_id if user_id and user_id != "null" else None,
                task_id=task_id if task_id and task_id != "null" else None,
                task_name=task_name if task_name and task_name != "null" else None,
                task_description=task_description if task_description and task_description != "null" else None,
                task_status=task_status if task_status and task_status != "null" else None,
                date=date if date and date != "null" else None,
                date_from=date_from if date_from and date_from != "null" else None,
                date_to=date_to if date_to and date_to != "null" else None,
                use_semantic_search=True
            )
            
            # Форматируем результаты
            if not results:
                message = "❌ Задачи не найдены по указанным критериям."
                updated_state = {
                    "message_to_user": message,
                    "stage": StageEnum.END
                }
                return Command(goto=END, update=updated_state)
            
            # Красивое форматирование результатов
            result_parts = [f"✅ Найдено задач: {len(results)}\n"]
            
            for i, task in enumerate(results, 1):
                result_parts.append("─" * 40)
                result_parts.append(f"Задача #{i}")
                result_parts.append(f"ID: {task.get('task_id', 'N/A')}")
                result_parts.append(f"Название: {task.get('task_name', 'N/A')}")
                result_parts.append(f"Описание: {task.get('task_description', 'N/A')}")
                result_parts.append(f"Статус: {task.get('task_status', 'N/A')}")
                result_parts.append(f"Дата: {task.get('date', 'N/A')}")
                
                if i < len(results):
                    result_parts.append("")  # Пустая строка между задачами
            
            result_parts.append("─" * 40)
            
            message = "\n".join(result_parts)
            
            updated_state = {
                "message_to_user": message,
                "stage": StageEnum.END
            }
            
            logger.log_graph_node("TaskSearch", f"Найдено задач: {len(results)}")
            
            return Command(goto=END, update=updated_state)
            
        except Exception as e:
            # Fallback ответ при ошибке
            logger.error(f"Ошибка в узле поиска задач: {str(e)}", "Graph", {"node": "TaskSearch", "user_query": user_query})
            
            error_message = f"❌ Ошибка поиска задач: {str(e)}"
            updated_state = {
                "message_to_user": error_message,
                "stage": StageEnum.END
            }
            return Command(goto=END, update=updated_state)

