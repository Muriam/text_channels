// Выбираем канал
async function selectChannel(channelId, channelName) {
    if (currentChannel) {
        socket.emit('leave', { channel_id: currentChannel });
    }
    
    currentChannel = channelId;
    document.getElementById('channelName').textContent = channelName;
    
    // Подсветка активного канала
    document.querySelectorAll('.channel').forEach(ch => {
        ch.classList.remove('active');
        if (ch.dataset.channelId == channelId) {
            ch.classList.add('active');
        }
    });
    
    // Включаем поле ввода
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    messageInput.disabled = false;
    sendButton.disabled = false;
    messageInput.focus();
    
    // Присоединяемся к комнате WebSocket
    socket.emit('join', {
        channel_id: channelId,
        username: username
    });
    
    // Загружаем сообщения
    await loadMessages(channelId);
}

// Загружаем сообщения
async function loadMessages(channelId) {
    try {
        const response = await fetch(`/api/channels/${channelId}/messages`);
        const data = await response.json();
        
        const container = document.getElementById('messagesContainer');
        container.innerHTML = '';
        
        if (data.messages.length === 0) {
            const emptyMsg = document.createElement('div');
            emptyMsg.className = 'status-message';
            emptyMsg.textContent = 'Пока нет сообщений. Будьте первым!';
            container.appendChild(emptyMsg);
        } else {
            data.messages.forEach(msg => {
                addMessage(msg.user, msg.content, msg.timestamp);
            });
        }
        
        container.scrollTop = container.scrollHeight;
    } catch (error) {
        console.error('Ошибка загрузки сообщений:', error);
        showError('Не удалось загрузить сообщения');
    }
}

// Добавляем сообщение в чат
function addMessage(user, content, timestamp) {
    const container = document.getElementById('messagesContainer');
    
    // Удаляем сообщение "Пока нет сообщений" если оно есть
    const emptyMsg = container.querySelector('.status-message');
    if (emptyMsg && emptyMsg.textContent.includes('Пока нет сообщений')) {
        emptyMsg.remove();
    }
    
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message';
    
    const avatarLetter = user.charAt(0).toUpperCase();
    const avatarColor = getAvatarColor(user);
    
    // Используем функцию для форматирования ссылок
    const formattedContent = formatMessageWithLinks(content);
    
    msgDiv.innerHTML = `
        <div class="message-header">
            <div class="avatar" style="background: ${avatarColor}">${avatarLetter}</div>
            <span class="username">${user}</span>
            <span class="timestamp">${timestamp}</span>
        </div>
        <div class="message-content">${formattedContent}</div>
    `;
    
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
    
    // Добавляем обработчики кликов для новых ссылок
    setTimeout(() => {
        const links = msgDiv.querySelectorAll('.message-link');
        links.forEach(link => {
            link.addEventListener('click', function(e) {
                e.stopPropagation();
                window.open(this.href, '_blank');
            });
        });
    }, 0);
}

// Генерация цвета для аватарки
function getAvatarColor(username) {
    const colors = [
        '#5865f2', '#3ba55c', '#ed4245', 
        '#faa61a', '#eb459e', '#5a65ea'
    ];
    let hash = 0;
    for (let i = 0; i < username.length; i++) {
        hash = username.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
}

// Экранирование HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Отправка сообщения
function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (message && currentChannel) {
        socket.emit('message', {
            channel_id: currentChannel,
            content: message
        });
        input.value = '';
        input.focus();
    }
}

// Функция для преобразования текста в HTML с ссылками
function formatMessageWithLinks(text) {
    // Регулярное выражение для поиска URL
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    
    // Заменяем URL на ссылки
    return escapeHtml(text).replace(urlRegex, function(url) {
        // Очищаем URL от возможных знаков препинания в конце
        let cleanUrl = url;
        const punctuation = /[.,;:!?)]+$/;
        const match = url.match(punctuation);
        let trailingPunctuation = '';
        
        if (match) {
            trailingPunctuation = match[0];
            cleanUrl = url.slice(0, -trailingPunctuation.length);
        }
        
        // Создаем безопасную ссылку
        return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer" class="message-link">${cleanUrl}</a>${trailingPunctuation}`;
    });
}

// Обработчики событий
document.addEventListener('DOMContentLoaded', function() {
    const sendButton = document.getElementById('sendButton');
    const messageInput = document.getElementById('messageInput');
    
    sendButton.onclick = sendMessage;
    
    messageInput.onkeypress = function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };
    
    // WebSocket события
    socket.on('new_message', function(data) {
        if (currentChannel) {
            addMessage(data.user, data.content, data.timestamp);
        }
    });
    
    socket.on('status', function(message) {
        const container = document.getElementById('messagesContainer');
        const statusDiv = document.createElement('div');
        statusDiv.className = 'status-message';
        statusDiv.textContent = `⚡ ${message}`;
        container.appendChild(statusDiv);
        container.scrollTop = container.scrollHeight;
    });
    
    // Инициализация
    loadCategories();
});