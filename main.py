"""
Основной файл для запуска мультиагентной системы управления задачами
"""

import sys
import os

# Добавляем путь к модулю agent
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Загружаем переменные окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ python-dotenv не установлен. Установите: pip install python-dotenv")

from agent.agent import Agent
from agent.core.nodes import Graph
from agent.core.llm import YandexGPT

def main():
    """Основная функция с циклом общения"""
    print("🚀 Мультиагентная система управления задачами")
    print("Введите 'exit' для выхода")
    print("Введите 'помощь' для получения справки по командам")
    print("-" * 50)
    
    # Создаем YandexGPT (можно вынести в переменные окружения)
    yandex_gpt = None
    try:
        # Пытаемся получить из переменных окружения
        folder_id = os.getenv("YANDEX_FOLDER_ID", "your_folder_id")
        api_key = os.getenv("YANDEX_API_KEY", "your_api_key")
        model = os.getenv("YANDEX_MODEL", "yandexgpt-lite")
        version = os.getenv("YANDEX_VERSION", "rc")
        
        # Проверяем, что это не заглушки
        if folder_id != "your_folder_id" and api_key != "your_api_key":
            yandex_gpt = YandexGPT(folder_id=folder_id, api_key=api_key, model=model, version=version)
            print("✅ YandexGPT инициализирован")
        else:
            print("⚠️ Переменные окружения не настроены")
            print("Создайте файл .env с YANDEX_FOLDER_ID и YANDEX_API_KEY")
            print("Или используйте fallback режим без LLM")
    except Exception as e:
        print(f"⚠️ Ошибка инициализации YandexGPT: {e}")
        print("Используем fallback режим без LLM")
    
    # Создаем граф
    graph_instance = Graph(yandex_gpt)
    graph = graph_instance.get_graph()
    
    # Создаем агента
    agent = Agent(graph)
    
    # Основной цикл общения
    while True:
        try:
            # Получаем сообщение от пользователя
            user_input = input("\n👤 Вы: ").strip()
            
            # Проверяем команду выхода
            if user_input.lower() in ['exit', 'quit', 'выход', 'пока']:
                print("👋 До свидания! Спасибо за использование системы управления задачами!")
                break
            
            # Проверяем пустое сообщение
            if not user_input:
                print("⚠️ Пожалуйста, введите сообщение")
                continue
            
            # Обрабатываем сообщение через агента
            print("🤖 Агент обрабатывает...")
            response = agent.process_message(user_input)
            
            # Выводим ответ
            print(f"🤖 Агент: {response}")
            
        except KeyboardInterrupt:
            print("\n\n👋 Программа прервана пользователем. До свидания!")
            break
        except Exception as e:
            print(f"❌ Произошла ошибка: {e}")
            print("Попробуйте еще раз или введите 'помощь' для справки")

if __name__ == "__main__":
    main()
