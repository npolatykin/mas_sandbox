/**
 * Основное приложение UI Testing Agent Sandbox
 */

class AgentApp {
    constructor() {
        this.sessionId = this.generateSessionId();
        this.websocket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.loadInitialData();
        this.connectWebSocket();
        this.startPeriodicUpdates();
    }
    
    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    bindEvents() {
        // Форма чата
        const chatForm = document.getElementById('chatForm');
        const messageInput = document.getElementById('messageInput');
        
        chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });
        
        // Enter для отправки
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Кнопка очистки логов
        const clearLogsBtn = document.getElementById('clearLogsBtn');
        clearLogsBtn.addEventListener('click', () => {
            this.clearLogs();
        });
        
        // Фильтры логов
        const logLevelFilter = document.getElementById('logLevelFilter');
        const logLimitFilter = document.getElementById('logLimitFilter');
        
        logLevelFilter.addEventListener('change', () => {
            this.animateLogsPanel();
            this.loadLogs();
        });
        
        logLimitFilter.addEventListener('change', () => {
            this.animateLogsPanel();
            this.loadLogs();
        });
    }
    
    animateLogsPanel() {
        // Анимация убрана - логи обновляются мгновенно
    }
    
    async sendMessage() {
        const messageInput = document.getElementById('messageInput');
        const message = messageInput.value.trim();
        
        if (!message) return;
        
        // Показываем сообщение пользователя
        this.addChatMessage(message, true);
        messageInput.value = '';
        
        // Показываем индикатор загрузки
        this.showLoading(true);
        
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    message: message
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Показываем ответ агента
                this.addChatMessage(data.response, false);
                
                // Обновляем статистику
                this.loadStats();
                
                // Показываем уведомление
                this.showNotification('Сообщение отправлено успешно!', 'success');
            } else {
                throw new Error(data.detail || 'Ошибка отправки сообщения');
            }
            
        } catch (error) {
            console.error('Ошибка отправки сообщения:', error);
            this.showNotification(`Ошибка: ${error.message}`, 'error');
        } finally {
            this.showLoading(false);
        }
    }
    
    addChatMessage(content, isUser) {
        const chatContainer = document.getElementById('chatContainer');
        
        // Убираем приветственное сообщение
        const welcomeMessage = chatContainer.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${isUser ? 'user-message' : 'ai-message'}`;
        
        const timestamp = new Date().toLocaleTimeString('ru-RU', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        messageDiv.innerHTML = `
            <div class="message-content">
                <strong>${isUser ? '👤 Вы:' : '🤖 Агент:'}</strong><br>
                ${this.escapeHtml(content)}
            </div>
            <div class="message-time">${timestamp}</div>
        `;
        
        chatContainer.appendChild(messageDiv);
        
        // Прокручиваем к последнему сообщению
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    async loadLogs() {
        try {
            const levelFilter = document.getElementById('logLevelFilter').value;
            const limitFilter = document.getElementById('logLimitFilter').value;
            
            const response = await fetch(`/api/logs?level=${levelFilter}&limit=${limitFilter}`);
            const data = await response.json();
            
            if (data.success) {
                this.displayLogs(data.logs);
            }
        } catch (error) {
            console.error('Ошибка загрузки логов:', error);
        }
    }
    
    displayLogs(logs) {
        const logsContainer = document.getElementById('logsContainer');
        
        if (!logs || logs.length === 0) {
            logsContainer.innerHTML = '<div class="no-logs-message"><p>📝 Логи отсутствуют</p></div>';
            return;
        }
        
        logsContainer.innerHTML = '';
        
        // Показываем логи в обратном порядке (новые сверху)
        logs.reverse().forEach((log, index) => {
            const logDiv = document.createElement('div');
            logDiv.className = `log-entry log-${log.level.toLowerCase()}`;
            
            const timestamp = new Date(log.timestamp).toLocaleTimeString('ru-RU', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            
            let tokenInfo = '';
            if (log.source === 'LLM' && log.details && log.details.tokens) {
                const tokens = log.details.tokens;
                let costInfo = '';
                if (tokens.cost_rub && tokens.cost_rub > 0) {
                    costInfo = ` | 💰 Стоимость: ${tokens.cost_rub} ₽`;
                }
                tokenInfo = ` | 🎯 Токены: ${tokens.input_tokens || 0}→${tokens.completion_tokens || 0} (всего: ${tokens.total_tokens || 0})${costInfo}`;
            }
            
            logDiv.innerHTML = `
                <strong>[${timestamp}] ${log.level}</strong> <em>${log.source}</em><br>
                ${this.escapeHtml(log.message)}${tokenInfo}
            `;
            
            logsContainer.appendChild(logDiv);
        });
    }
    
    async loadStats() {
        try {
            const response = await fetch('/api/stats');
            const data = await response.json();
            
            if (data.success) {
                this.updateStats(data.stats);
            }
        } catch (error) {
            console.error('Ошибка загрузки статистики:', error);
        }
    }
    
    updateStats(stats) {
        document.getElementById('totalTokens').textContent = stats.total_tokens || 0;
        document.getElementById('inputTokens').textContent = stats.input_tokens || 0;
        document.getElementById('completionTokens').textContent = stats.completion_tokens || 0;
        document.getElementById('totalCost').textContent = `${stats.total_cost_rub || 0} ₽`;
    }
    
    async clearLogs() {
        try {
            const response = await fetch('/api/logs/clear', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showNotification('Логи очищены успешно!', 'success');
                this.loadLogs();
                this.loadStats();
            }
        } catch (error) {
            console.error('Ошибка очистки логов:', error);
            this.showNotification(`Ошибка очистки логов: ${error.message}`, 'error');
        }
    }
    
    async loadInitialData() {
        await Promise.all([
            this.loadLogs(),
            this.loadStats()
        ]);
    }
    
    connectWebSocket() {
        try {
            // Закрываем существующее соединение если есть
            if (this.websocket) {
                this.websocket.close();
            }
            
            this.websocket = new WebSocket(`ws://${window.location.host}/ws`);
            
            this.websocket.onopen = () => {
                console.log('✅ WebSocket соединение установлено');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.reconnectDelay = 1000;
                
                // Показываем уведомление о подключении
                this.showNotification('WebSocket соединение установлено', 'success');
            };
            
            this.websocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (error) {
                    console.error('Ошибка парсинга WebSocket сообщения:', error);
                }
            };
            
            this.websocket.onclose = (event) => {
                console.log('🔌 WebSocket соединение закрыто:', event.code, event.reason);
                this.isConnected = false;
                
                // Пытаемся переподключиться только если это не было намеренное закрытие
                if (event.code !== 1000) {
                    this.scheduleReconnect();
                }
            };
            
            this.websocket.onerror = (error) => {
                console.error('❌ WebSocket ошибка:', error);
                this.showNotification('Ошибка WebSocket соединения', 'error');
            };
            
        } catch (error) {
            console.error('Ошибка подключения WebSocket:', error);
            this.scheduleReconnect();
        }
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`🔄 Попытка переподключения ${this.reconnectAttempts}/${this.maxReconnectAttempts} через ${this.reconnectDelay}ms`);
            
            setTimeout(() => {
                this.connectWebSocket();
            }, this.reconnectDelay);
            
            // Увеличиваем задержку для следующей попытки
            this.reconnectDelay = Math.min(this.reconnectDelay * 2, 10000);
        } else {
            console.error('❌ Превышено максимальное количество попыток переподключения');
            this.showNotification('Не удалось установить WebSocket соединение', 'error');
        }
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'logs_update':
                // Обновляем логи в реальном времени
                this.loadLogs();
                break;
            case 'pong':
                // Ответ на ping
                break;
            default:
                console.log('Неизвестный тип WebSocket сообщения:', data.type);
        }
    }
    
    startPeriodicUpdates() {
        // Обновляем статистику каждые 30 секунд
        setInterval(() => {
            this.loadStats();
        }, 30000);
        
        // Отправляем ping каждые 30 секунд для поддержания WebSocket соединения
        setInterval(() => {
            if (this.isConnected && this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                try {
                    this.websocket.send(JSON.stringify({ type: 'ping' }));
                } catch (error) {
                    console.error('Ошибка отправки ping:', error);
                    this.isConnected = false;
                }
            }
        }, 30000);
    }
    
    showLoading(show) {
        const loadingIndicator = document.getElementById('loadingIndicator');
        if (show) {
            loadingIndicator.classList.remove('hidden');
        } else {
            loadingIndicator.classList.add('hidden');
        }
    }
    
    showNotification(message, type = 'info') {
        const notificationsContainer = document.getElementById('notifications');
        
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        notificationsContainer.appendChild(notification);
        
        // Автоматически убираем уведомление через 5 секунд
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }
}

// Инициализация приложения при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    new AgentApp();
});

// Обработка ошибок
window.addEventListener('error', (event) => {
    console.error('Глобальная ошибка:', event.error);
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('Необработанное отклонение промиса:', event.reason);
});
