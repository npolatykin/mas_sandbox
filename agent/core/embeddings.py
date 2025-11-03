"""
Модуль для работы с embeddings и FAISS для семантического поиска задач
"""
import os
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
from typing import List, Dict, Tuple, Optional
from .logger import logger


class SemanticSearch:
    """Класс для семантического поиска с использованием embeddings и FAISS"""
    
    def __init__(self, data_file: str = "agent/core/data/data.json", 
                 index_file: str = "agent/core/data/faiss_index.pkl",
                 embeddings_file: str = "agent/core/data/embeddings.pkl"):
        """
        Инициализация семантического поиска
        
        Args:
            data_file: Путь к файлу с данными задач
            index_file: Путь к файлу для сохранения FAISS индекса
            embeddings_file: Путь к файлу для сохранения embeddings
        """
        self.data_file = data_file
        self.index_file = index_file
        self.embeddings_file = embeddings_file
        
        # Используем модель для русского языка
        # LaBSE поддерживает русский и работает хорошо для семантического поиска
        model_name = "sentence-transformers/LaBSE"
        logger.info(f"Загружаю модель для embeddings: {model_name}", "SemanticSearch")
        
        try:
            self.model = SentenceTransformer(model_name)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"Модель загружена. Размерность embeddings: {self.embedding_dim}", "SemanticSearch")
        except Exception as e:
            logger.error(f"Ошибка загрузки модели: {e}", "SemanticSearch")
            raise
        
        # Инициализируем FAISS индекс
        self.index = None
        self.task_texts = []  # Тексты задач для поиска (название + описание)
        self.task_mappings = []  # Связь между индексами FAISS и task_id
        
        self._load_or_create_index()
    
    def _load_or_create_index(self):
        """Загрузить существующий индекс или создать новый"""
        try:
            if os.path.exists(self.index_file) and os.path.exists(self.embeddings_file):
                logger.info("Загружаю существующий индекс FAISS", "SemanticSearch")
                # Загружаем индекс
                self.index = faiss.read_index(self.index_file)
                
                # Загружаем mappings и тексты
                with open(self.embeddings_file, 'rb') as f:
                    data = pickle.load(f)
                    self.task_mappings = data.get('task_mappings', [])
                    self.task_texts = data.get('task_texts', [])
                
                logger.info(f"Индекс загружен. Задач в индексе: {len(self.task_mappings)}", "SemanticSearch")
            else:
                logger.info("Создаю новый индекс FAISS", "SemanticSearch")
                self._create_index()
        except Exception as e:
            logger.error(f"Ошибка загрузки индекса: {e}", "SemanticSearch")
            self._create_index()
    
    def _create_index(self):
        """Создать новый FAISS индекс"""
        # Создаем плоский индекс (Inner Product для косинусного расстояния)
        # Нормализуем векторы для косинусного поиска
        self.index = faiss.IndexFlatIP(self.embedding_dim)  # Inner Product для косинусного расстояния
        
        self.task_texts = []
        self.task_mappings = []
        self._rebuild_index()
    
    def _get_task_text(self, task: Dict) -> str:
        """Получить текст задачи для создания embedding (название + описание)"""
        task_name = task.get("task_name", "")
        task_description = task.get("task_description", "")
        return f"{task_name} {task_description}".strip()
    
    def _rebuild_index(self):
        """Перестроить индекс на основе всех задач из data.json"""
        import json
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Поддерживаем как старую, так и новую структуру данных
            if "users" in data:
                # Новая структура: массив пользователей
                users = data.get("users", [])
                tasks = []
                for user in users:
                    user_tasks = user.get("tasks", [])
                    # Убеждаемся, что каждая задача имеет user_id
                    for task in user_tasks:
                        if "user_id" not in task:
                            task["user_id"] = user.get("user_id")
                    tasks.extend(user_tasks)
            else:
                # Старая структура: один пользователь
                tasks = data.get("tasks", [])
                # Если в старой структуре есть user_id, добавляем его к задачам
                user_id = data.get("user_id")
                if user_id:
                    for task in tasks:
                        if "user_id" not in task:
                            task["user_id"] = user_id
            
            if not tasks:
                logger.info("Нет задач для индексации", "SemanticSearch")
                return
            
            logger.info(f"Индексирую {len(tasks)} задач", "SemanticSearch")
            
            # Подготовка текстов
            texts = []
            mappings = []
            
            for task in tasks:
                task_text = self._get_task_text(task)
                if task_text:  # Пропускаем пустые задачи
                    texts.append(task_text)
                    mappings.append({
                        "task_id": task.get("task_id"),
                        "task": task
                    })
            
            if not texts:
                logger.info("Нет текстов для индексации", "SemanticSearch")
                return
            
            # Создаем embeddings
            logger.info(f"Создаю embeddings для {len(texts)} задач", "SemanticSearch")
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            
            # Нормализуем векторы для косинусного поиска
            faiss.normalize_L2(embeddings)
            
            # Очищаем индекс и добавляем новые векторы
            self.index.reset()
            self.index.add(embeddings.astype('float32'))
            
            self.task_texts = texts
            self.task_mappings = mappings
            
            # Сохраняем индекс
            self._save_index()
            
            logger.info(f"Индекс перестроен. Задач в индексе: {len(self.task_mappings)}", "SemanticSearch")
            
        except Exception as e:
            logger.error(f"Ошибка перестройки индекса: {e}", "SemanticSearch")
    
    def _save_index(self):
        """Сохранить индекс и mappings на диск"""
        try:
            # Сохраняем FAISS индекс
            faiss.write_index(self.index, self.index_file)
            
            # Сохраняем mappings и тексты
            with open(self.embeddings_file, 'wb') as f:
                pickle.dump({
                    'task_mappings': self.task_mappings,
                    'task_texts': self.task_texts
                }, f)
            
            logger.info("Индекс сохранен на диск", "SemanticSearch")
        except Exception as e:
            logger.error(f"Ошибка сохранения индекса: {e}", "SemanticSearch")
    
    def search(self, query: str, top_k: int = 5, threshold: float = 0.3) -> List[Tuple[Dict, float]]:
        """
        Семантический поиск задач
        
        Args:
            query: Поисковый запрос
            top_k: Количество результатов для возврата
            threshold: Минимальный score для включения в результаты (0.0 - 1.0)
        
        Returns:
            Список кортежей (task, similarity_score) отсортированных по релевантности
        """
        if not query or not query.strip():
            return []
        
        if self.index is None or self.index.ntotal == 0:
            logger.warning("Индекс пуст, выполняется перестройка", "SemanticSearch")
            self._rebuild_index()
        
        if self.index.ntotal == 0:
            return []
        
        try:
            # Создаем embedding для запроса
            query_embedding = self.model.encode([query], convert_to_numpy=True)
            faiss.normalize_L2(query_embedding)  # Нормализуем для косинусного поиска
            query_embedding = query_embedding.astype('float32')
            
            # Поиск в FAISS
            k = min(top_k, self.index.ntotal)
            scores, indices = self.index.search(query_embedding, k)
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < len(self.task_mappings) and score >= threshold:
                    task_info = self.task_mappings[idx]
                    results.append((task_info["task"], float(score)))
            
            # Сортируем по score (от большего к меньшему)
            results.sort(key=lambda x: x[1], reverse=True)
            
            logger.info(f"Семантический поиск: запрос '{query}', найдено {len(results)} результатов", "SemanticSearch")
            
            return results
            
        except Exception as e:
            logger.error(f"Ошибка семантического поиска: {e}", "SemanticSearch")
            return []
    
    def update_index(self, task: Dict, operation: str = "add"):
        """
        Обновить индекс при изменении задачи
        
        Args:
            task: Задача для обновления
            operation: "add", "update", "delete"
        """
        # Для простоты перестраиваем весь индекс
        # В production можно оптимизировать для добавления/удаления отдельных векторов
        logger.info(f"Обновление индекса: операция {operation} для задачи {task.get('task_id')}", "SemanticSearch")
        self._rebuild_index()
    
    def rebuild_if_needed(self):
        """Перестроить индекс, если он пуст или устарел"""
        if self.index is None or self.index.ntotal == 0:
            self._rebuild_index()


