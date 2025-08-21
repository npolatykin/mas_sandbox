"""
FastAPI сервер для мультиагентной системы управления задачами
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import asyncio
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# Добавляем путь к модулю agent
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent.agent import Agent
from agent.core.nodes import Graph
from agent.core.llm import YandexGPT
from agent.core.logger import logger, LogLevel

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan контекст для управления фоновыми задачами"""
    # Запускаем фоновую задачу
    task = asyncio.create_task(broadcast_logs())
    yield
    # Останавливаем задачу при завершении
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="UI Testing Agent API", version="1.0.0", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальные переменные
agents: Dict[str, Agent] = {}
websocket_connections: List[WebSocket] = []

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint для real-time обновлений"""
    await websocket.accept()
    websocket_connections.append(websocket)
    print(f"Новое WebSocket соединение. Всего активных: {len(websocket_connections)}")
    
    try:
        while True:
            # Ждем сообщения от клиента
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Обрабатываем сообщения от клиента
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                
    except WebSocketDisconnect:
        websocket_connections.remove(websocket)
        print(f"WebSocket соединение закрыто. Всего активных: {len(websocket_connections)}")
    except Exception as e:
        print(f"Ошибка WebSocket: {e}")
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)
            print(f"WebSocket соединение удалено из-за ошибки. Всего активных: {len(websocket_connections)}")

def initialize_agent(session_id: str) -> Agent:
    """Инициализация агента для сессии"""
    try:
        # Создаем YandexGPT
        yandex_gpt = None
        folder_id = os.getenv("YANDEX_FOLDER_ID", "your_folder_id")
        api_key = os.getenv("YANDEX_API_KEY", "your_api_key")
        model = os.getenv("YANDEX_MODEL", "yandexgpt-lite")
        version = os.getenv("YANDEX_VERSION", "rc")
        
        if folder_id != "your_folder_id" and api_key != "your_api_key":
            yandex_gpt = YandexGPT(folder_id=folder_id, api_key=api_key, model=model, version=version)
        
        # Создаем граф и агента
        graph_instance = Graph(yandex_gpt)
        graph = graph_instance.get_graph()
        agent = Agent(graph)
        
        return agent
        
    except Exception as e:
        logger.error(f"Ошибка инициализации агента: {e}", "System")
        raise HTTPException(status_code=500, detail=f"Ошибка инициализации агента: {e}")

async def broadcast_logs():
    """Отправка логов всем подключенным клиентам"""
    while True:
        try:
            # Получаем последние логи
            logs = logger.get_logs(limit=10)
            
            # Создаем копию списка соединений для безопасной итерации
            connections_to_remove = []
            
            # Отправляем всем подключенным клиентам
            for connection in websocket_connections:
                try:
                    if connection.client_state.value == 1:  # Проверяем что соединение активно
                        await connection.send_text(json.dumps({
                            "type": "logs_update",
                            "data": logs
                        }))
                    else:
                        connections_to_remove.append(connection)
                except Exception as e:
                    print(f"Ошибка отправки в WebSocket: {e}")
                    connections_to_remove.append(connection)
            
            # Удаляем отключенные соединения
            for connection in connections_to_remove:
                if connection in websocket_connections:
                    websocket_connections.remove(connection)
                    print(f"Удалено отключенное WebSocket соединение. Всего активных: {len(websocket_connections)}")
            
            await asyncio.sleep(2)  # Обновляем каждые 2 секунды
            
        except Exception as e:
            print(f"Ошибка broadcast_logs: {e}")
            await asyncio.sleep(5)

@app.post("/api/chat")
async def chat_endpoint(request: Dict[str, Any]):
    """API endpoint для чата"""
    try:
        session_id = request.get("session_id", "default")
        message = request.get("message", "")
        
        if not message.strip():
            raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
        
        # Инициализируем агента если нужно
        if session_id not in agents:
            agents[session_id] = initialize_agent(session_id)
        
        agent = agents[session_id]
        
        # Обрабатываем сообщение
        response = agent.process_message(message)
        
        return {
            "success": True,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка обработки чата: {e}", "API")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs")
async def get_logs_endpoint(
    level: str = "Все",
    limit: int = 100
):
    """API endpoint для получения логов"""
    try:
        level_filter = None
        if level != "Все":
            level_filter = LogLevel(level)
        
        logs = logger.get_logs(level=level_filter, limit=limit)
        return {
            "success": True,
            "logs": logs
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения логов: {e}", "API")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats_endpoint():
    """API endpoint для получения статистики токенов"""
    try:
        stats = logger.get_token_statistics()
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}", "API")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/logs/clear")
async def clear_logs_endpoint():
    """API endpoint для очистки логов"""
    try:
        logger.clear_logs()
        return {
            "success": True,
            "message": "Логи очищены"
        }
        
    except Exception as e:
        logger.error(f"Ошибка очистки логов: {e}", "API")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Главная страница"""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# Статические файлы - монтируем по пути /static/
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    
    # Загружаем переменные окружения
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("⚠️ python-dotenv не установлен. Установите: pip install python-dotenv")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
