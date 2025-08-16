"""
Streamlit UI для мультиагентной системы управления задачами
"""

import streamlit as st
import sys
import os
from datetime import datetime

# Добавляем путь к модулю agent
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Загружаем переменные окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    st.warning("⚠️ python-dotenv не установлен. Установите: pip install python-dotenv")

from agent.agent import Agent
from agent.core.nodes import Graph
from agent.core.llm import YandexGPT

# Настройка страницы
st.set_page_config(
    page_title="🤖 Мультиагентная система",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS для красивого интерфейса
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 15px;
        margin: 0.5rem 0;
        display: flex;
        align-items: flex-start;
    }
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin-left: 20%;
    }
    .ai-message {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        margin-right: 20%;
    }
    .message-time {
        font-size: 0.8rem;
        opacity: 0.8;
        margin-top: 0.5rem;
    }
    .sidebar-section {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .status-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-online { background-color: #28a745; }
    .status-offline { background-color: #dc3545; }
</style>
""", unsafe_allow_html=True)

def initialize_agent():
    """Инициализация агента"""
    try:
        # Создаем YandexGPT
        yandex_gpt = None
        folder_id = os.getenv("YANDEX_FOLDER_ID", "your_folder_id")
        api_key = os.getenv("YANDEX_API_KEY", "your_api_key")
        model = os.getenv("YANDEX_MODEL", "yandexgpt-lite")
        version = os.getenv("YANDEX_VERSION", "rc")
        
        if folder_id != "your_folder_id" and api_key != "your_api_key":
            yandex_gpt = YandexGPT(folder_id=folder_id, api_key=api_key, model=model, version=version)
            st.session_state.yandex_status = "online"
        else:
            st.session_state.yandex_status = "offline"
        
        # Создаем граф и агента
        graph_instance = Graph(yandex_gpt)
        graph = graph_instance.get_graph()
        agent = Agent(graph)
        
        return agent, yandex_gpt is not None
        
    except Exception as e:
        st.error(f"Ошибка инициализации: {e}")
        return None, False

def display_chat_message(message, is_user=True):
    """Отображение сообщения в чате"""
    if is_user:
        st.markdown(f"""
        <div class="chat-message user-message">
            <div style="flex: 1;">
                <strong>👤 Вы:</strong><br>
                {message['content']}
                <div class="message-time">{message['timestamp']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="chat-message ai-message">
            <div style="flex: 1;">
                <strong>🤖 Агент:</strong><br>
                {message['content']}
                <div class="message-time">{message['timestamp']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

def main():
    # Заголовок
    st.markdown("""
    <div class="main-header">
        <h1>🤖 Мультиагентная система управления задачами</h1>
        <p>Умный помощник для работы с задачами и календарем</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Инициализация сессии
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'agent' not in st.session_state:
        st.session_state.agent = None
    if 'yandex_status' not in st.session_state:
        st.session_state.yandex_status = "offline"
    
    # Боковая панель
    with st.sidebar:
        st.markdown("## ⚙️ Настройки")
        
        # Статус YandexGPT
        status_color = "🟢" if st.session_state.yandex_status == "online" else "🔴"
        st.markdown(f"**YandexGPT:** {status_color} {st.session_state.yandex_status}")
        
        # Информация о системе
        st.markdown("""
        <div class="sidebar-section">
            <h4>📋 Возможности</h4>
            <ul>
                <li>Создание и управление задачами</li>
                <li>Планирование в календаре</li>
                <li>Умная маршрутизация запросов</li>
                <li>Fallback режим без LLM</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        # Примеры команд
        st.markdown("""
        <div class="sidebar-section">
            <h4>💡 Примеры команд</h4>
            <ul>
                <li>"привет"</li>
                <li>"что ты умеешь?"</li>
                <li>"помощь"</li>
                <li>"задача"</li>
                <li>"календарь"</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        # Кнопка очистки чата
        if st.button("🗑️ Очистить чат", type="secondary"):
            st.session_state.messages = []
            st.rerun()
    
    # Основная область
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Область чата
        st.markdown("### 💬 Чат с агентом")
        
        # Отображение истории сообщений
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.messages:
                display_chat_message(message, message['is_user'])
        
        # Поле ввода
        with st.form("chat_form", clear_on_submit=True):
            user_input = st.text_input(
                "Введите ваше сообщение:",
                placeholder="Например: привет, что ты умеешь?",
                key="user_input"
            )
            
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                submit_button = st.form_submit_button("🚀 Отправить", type="primary")
            with col2:
                if st.form_submit_button("🤖 Тест агента"):
                    user_input = "привет, что ты умеешь?"
                    submit_button = True
            with col3:
                if st.form_submit_button("📅 Тест календаря"):
                    user_input = "календарь"
                    submit_button = True
        
        # Обработка сообщения
        if submit_button and user_input.strip():
            # Инициализируем агента если нужно
            if st.session_state.agent is None:
                with st.spinner("Инициализация агента..."):
                    agent, yandex_available = initialize_agent()
                    if agent:
                        st.session_state.agent = agent
                        st.session_state.yandex_status = "online" if yandex_available else "offline"
                    else:
                        st.error("Не удалось инициализировать агента")
                        return
            
            # Добавляем сообщение пользователя
            user_message = {
                'content': user_input,
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'is_user': True
            }
            st.session_state.messages.append(user_message)
            
            # Получаем ответ от агента
            with st.spinner("🤖 Агент думает..."):
                try:
                    response = st.session_state.agent.process_message(user_input)
                    
                    # Добавляем ответ агента
                    ai_message = {
                        'content': response,
                        'timestamp': datetime.now().strftime("%H:%M:%S"),
                        'is_user': False
                    }
                    st.session_state.messages.append(ai_message)
                    
                    # Обновляем страницу
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Ошибка обработки: {e}")
    
    with col2:
        # Статистика
        st.markdown("### 📊 Статистика")
        st.metric("Сообщений", len(st.session_state.messages))
        st.metric("Пользователь", len([m for m in st.session_state.messages if m['is_user']]))
        st.metric("Агент", len([m for m in st.session_state.messages if not m['is_user']]))
        
        # Статус системы
        st.markdown("### 🔍 Статус системы")
        if st.session_state.agent:
            st.success("✅ Агент активен")
        else:
            st.warning("⚠️ Агент не инициализирован")
        
        # Информация о сессии
        if st.session_state.messages:
            last_message = st.session_state.messages[-1]
            st.markdown(f"**Последнее сообщение:** {last_message['timestamp']}")
    
    # Футер
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 1rem;">
        🤖 Мультиагентная система управления задачами | 
        Powered by LangGraph & YandexGPT
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
