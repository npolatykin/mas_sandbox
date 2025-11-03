"""
Инструменты для работы с задачами (многопользовательская версия)
"""
import json
import os
from typing import List, Dict, Optional
from datetime import datetime

# Импортируем семантический поиск (опционально)
try:
    from .embeddings import SemanticSearch
    SEMANTIC_SEARCH_AVAILABLE = True
except ImportError as e:
    SEMANTIC_SEARCH_AVAILABLE = False
    SemanticSearch = None


class TaskManager:
    """Менеджер для работы с задачами в многопользовательской системе"""
    
    def __init__(self, data_file: str = "agent/core/data/data.json"):
        self.data_file = data_file
        self.data = self._load_data()
        
        # Инициализируем семантический поиск (если доступен)
        self.semantic_search = None
        if SEMANTIC_SEARCH_AVAILABLE:
            try:
                self.semantic_search = SemanticSearch(data_file=data_file)
            except Exception as e:
                # Используется простой текстовый поиск вместо семантического
                self.semantic_search = None
        # Если SEMANTIC_SEARCH_AVAILABLE = False, используется простой поиск автоматически
    
    def _load_data(self) -> Dict:
        """Загрузить данные из JSON"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Миграция старой структуры в новую
                if "users" not in data:
                    # Старая структура с одним пользователем
                    if "user_id" in data:
                        user = {
                            "user_id": data.get("user_id", ""),
                            "user_name": data.get("user_name", ""),
                            "user_email": data.get("user_email", ""),
                            "user_phone": data.get("user_phone", ""),
                            "user_address": data.get("user_address", ""),
                            "user_city": data.get("user_city", ""),
                            "user_state": data.get("user_state", ""),
                            "user_zip": data.get("user_zip", ""),
                            "user_country": data.get("user_country", ""),
                            "tasks": data.get("tasks", [])
                        }
                        # Добавляем user_id в каждую задачу
                        for task in user["tasks"]:
                            if "user_id" not in task:
                                task["user_id"] = user["user_id"]
                        data = {"users": [user]}
                        # Сохраняем миграцию
                        self._save_data_migration(data)
                return data
        except FileNotFoundError:
            return {"users": []}
        except json.JSONDecodeError:
            return {"users": []}
    
    def _save_data_migration(self, data: Dict):
        """Сохранить данные после миграции (временный метод)"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Ошибка сохранения данных при миграции: {e}")
    
    def _save_data(self):
        """Сохранить данные в JSON"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Ошибка сохранения данных: {e}")
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """Получить пользователя по ID"""
        try:
            users = self.data.get("users", [])
            for user in users:
                if user.get("user_id") == user_id:
                    return user
            return None
        except Exception as e:
            print(f"Ошибка получения пользователя: {e}")
            return None
    
    def user_exists(self, user_id: str) -> bool:
        """Проверить существование пользователя"""
        return self.get_user(user_id) is not None
    
    def _get_all_tasks(self) -> List[Dict]:
        """Получить все задачи всех пользователей"""
        tasks = []
        users = self.data.get("users", [])
        for user in users:
            user_tasks = user.get("tasks", [])
            # Убеждаемся, что каждая задача имеет user_id
            for task in user_tasks:
                if "user_id" not in task:
                    task["user_id"] = user.get("user_id")
            tasks.extend(user_tasks)
        return tasks
    
    def _generate_task_id(self) -> str:
        """Генерировать уникальный ID задачи"""
        all_tasks = self._get_all_tasks()
        if not all_tasks:
            return "1"
        # Находим максимальный числовой ID
        max_id = 0
        for task in all_tasks:
            try:
                task_id_num = int(task.get("task_id", "0"))
                if task_id_num > max_id:
                    max_id = task_id_num
            except (ValueError, TypeError):
                continue
        return str(max_id + 1)
    
    def create_task(self, user_id: str, task_name: str, description: str, date: str = None) -> str:
        """Создать новую задачу для пользователя"""
        try:
            # Проверяем существование пользователя
            user = self.get_user(user_id)
            if not user:
                print(f"Ошибка: пользователь с ID '{user_id}' не найден")
                return None
            
            # Генерируем уникальный ID задачи
            task_id = self._generate_task_id()
            
            # Если дата не указана, используем сегодняшнюю
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")
            
            new_task = {
                "task_id": task_id,
                "user_id": user_id,
                "date": date,
                "task_name": task_name,
                "task_description": description,
                "task_status": "pending"
            }
            
            # Инициализируем структуру если нужно
            if "tasks" not in user:
                user["tasks"] = []
            
            # Добавляем задачу к пользователю
            user["tasks"].append(new_task)
            
            # Сохраняем данные
            self._save_data()
            
            # Обновляем индекс семантического поиска
            if self.semantic_search:
                try:
                    self.semantic_search.update_index(new_task, operation="add")
                except Exception as e:
                    print(f"Предупреждение: не удалось обновить индекс: {e}")
            
            return task_id
            
        except Exception as e:
            print(f"Ошибка создания задачи: {e}")
            return None
    
    def update_task(self, task_id: str, user_id: str = None, **updates) -> bool:
        """Обновить задачу"""
        try:
            all_tasks = self._get_all_tasks()
            for task in all_tasks:
                if task.get("task_id") == task_id:
                    # Если указан user_id, проверяем что задача принадлежит этому пользователю
                    if user_id and task.get("user_id") != user_id:
                        continue
                    
                    task.update(updates)
                    
                    # Находим пользователя и обновляем задачу в его списке
                    task_user_id = task.get("user_id")
                    user = self.get_user(task_user_id)
                    if user:
                        user_tasks = user.get("tasks", [])
                        for i, user_task in enumerate(user_tasks):
                            if user_task.get("task_id") == task_id:
                                user_tasks[i] = task
                                break
                    
                    self._save_data()
                    
                    # Обновляем индекс семантического поиска
                    if self.semantic_search:
                        try:
                            self.semantic_search.update_index(task, operation="update")
                        except Exception as e:
                            print(f"Предупреждение: не удалось обновить индекс: {e}")
                    
                    return True
            return False
        except Exception as e:
            print(f"Ошибка обновления задачи: {e}")
            return False
    
    def delete_task(self, task_id: str, user_id: str = None) -> bool:
        """Удалить задачу"""
        try:
            all_tasks = self._get_all_tasks()
            task_to_delete = None
            
            # Находим задачу
            for task in all_tasks:
                if task.get("task_id") == task_id:
                    # Если указан user_id, проверяем что задача принадлежит этому пользователю
                    if user_id and task.get("user_id") != user_id:
                        continue
                    task_to_delete = task
                    break
            
            if not task_to_delete:
                return False
            
            # Находим пользователя и удаляем задачу из его списка
            task_user_id = task_to_delete.get("user_id")
            user = self.get_user(task_user_id)
            if user:
                user_tasks = user.get("tasks", [])
                user["tasks"] = [t for t in user_tasks if t.get("task_id") != task_id]
                self._save_data()
                
                # Обновляем индекс семантического поиска
                if self.semantic_search:
                    try:
                        self.semantic_search.update_index(task_to_delete, operation="delete")
                    except Exception as e:
                        print(f"Предупреждение: не удалось обновить индекс: {e}")
                
                return True
            
            return False
        except Exception as e:
            print(f"Ошибка удаления задачи: {e}")
            return False
    
    def search_tasks(
        self,
        user_id: str = None,
        task_id: str = None,
        task_name: str = None,
        task_description: str = None,
        task_status: str = None,
        date: str = None,
        date_from: str = None,
        date_to: str = None,
        use_semantic_search: bool = True
    ) -> List[Dict]:
        """
        Поиск задач по различным критериям с поддержкой семантического поиска и поиска по периоду
        
        Args:
            user_id: ID пользователя (точное совпадение)
            task_id: ID задачи (точное совпадение)
            task_name: Название задачи (семантический поиск, если use_semantic_search=True)
            task_description: Описание задачи (семантический поиск, если use_semantic_search=True)
            task_status: Статус задачи (точное совпадение)
            date: Точная дата задачи в формате YYYY-MM-DD (точное совпадение)
            date_from: Начало периода поиска в формате YYYY-MM-DD (включительно)
            date_to: Конец периода поиска в формате YYYY-MM-DD (включительно)
            use_semantic_search: Использовать семантический поиск для текстовых полей
        
        Returns:
            Список найденных задач
        """
        try:
            # Получаем все задачи всех пользователей
            all_tasks = self._get_all_tasks()
            result = []
            
            # Если есть семантический поиск по текстовым полям
            if (use_semantic_search and self.semantic_search and 
                (task_name or task_description)):
                # Используем семантический поиск
                # Формируем запрос для семантического поиска
                query_parts = []
                if task_name:
                    query_parts.append(task_name)
                if task_description:
                    query_parts.append(task_description)
                
                semantic_query = " ".join(query_parts)
                
                # Выполняем семантический поиск
                semantic_results = self.semantic_search.search(
                    query=semantic_query,
                    top_k=100,  # Берем больше, потом отфильтруем
                    threshold=0.3  # Минимальная схожесть
                )
                
                # Получаем task_id из результатов семантического поиска
                semantic_task_ids = {task[0].get("task_id") for task in semantic_results}
                
                # Фильтруем задачи по результатам семантического поиска
                candidate_tasks = []
                for task in all_tasks:
                    if task.get("task_id") in semantic_task_ids:
                        candidate_tasks.append(task)
            else:
                # Используем все задачи как кандидатов
                candidate_tasks = all_tasks
            
            # Применяем дополнительные фильтры (точные совпадения)
            for task in candidate_tasks:
                # Проверяем user_id если указан
                if user_id and task.get("user_id") != user_id:
                    continue
                
                # Проверяем task_id если указан
                if task_id and task.get("task_id") != task_id:
                    continue
                
                # Проверяем дату если указана (точное совпадение)
                if date and task.get("date") != date:
                    continue
                
                # Проверяем период дат (date_from и date_to)
                task_date = task.get("date")
                if task_date:
                    try:
                        task_date_obj = datetime.strptime(task_date, "%Y-%m-%d").date()
                        
                        # Если указан date_from, проверяем что задача не раньше начала периода
                        if date_from:
                            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
                            if task_date_obj < date_from_obj:
                                continue
                        
                        # Если указан date_to, проверяем что задача не позже конца периода
                        if date_to:
                            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
                            if task_date_obj > date_to_obj:
                                continue
                    except (ValueError, TypeError):
                        # Если дата в неверном формате, пропускаем проверку периода
                        pass
                
                # Проверяем статус если указан
                if task_status and task.get("task_status") != task_status:
                    continue
                
                # Если семантический поиск не использовался, применяем простой текстовый поиск
                if not use_semantic_search or not self.semantic_search:
                    if task_name:
                        task_name_lower = task.get("task_name", "").lower()
                        if task_name.lower() not in task_name_lower:
                            continue
                    
                    if task_description:
                        task_desc_lower = task.get("task_description", "").lower()
                        if task_description.lower() not in task_desc_lower:
                            continue
                
                result.append(task)
            
            return result
            
        except Exception as e:
            print(f"Ошибка поиска задач: {e}")
            return []
    
    def get_task_by_id(self, task_id: str, user_id: str = None) -> Optional[Dict]:
        """Получить задачу по ID"""
        try:
            all_tasks = self._get_all_tasks()
            for task in all_tasks:
                if task.get("task_id") == task_id:
                    # Если указан user_id, проверяем что задача принадлежит этому пользователю
                    if user_id and task.get("user_id") != user_id:
                        continue
                    return task
            return None
        except Exception as e:
            print(f"Ошибка получения задачи: {e}")
            return None
