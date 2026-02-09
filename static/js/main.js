const socket = io();
let currentChannel = null;
let username = document.body.dataset.username;

// Загружаем категории и каналы
async function loadCategories() {
    try {
        const response = await fetch('/api/categories');
        const data = await response.json();
        
        const sidebar = document.getElementById('sidebar');
        sidebar.innerHTML = ''; // Очищаем
        
        // Добавляем информацию о пользователе
        const userInfo = document.createElement('div');
        userInfo.className = 'user-info';
        userInfo.innerHTML = `
            👤 ${username}
            <a href="/logout">Выйти</a>
        `;
        sidebar.appendChild(userInfo);
        
        // Добавляем категории и каналы
        data.categories.forEach(category => {
            const categoryDiv = document.createElement('div');
            categoryDiv.className = 'category';
            categoryDiv.textContent = category.name;
            sidebar.appendChild(categoryDiv);
            
            category.channels.forEach(channel => {
                const channelDiv = document.createElement('div');
                channelDiv.className = 'channel';
                channelDiv.innerHTML = `<span>${channel.name}</span>`;
                channelDiv.dataset.channelId = channel.id;
                channelDiv.dataset.channelName = channel.name;
                
                channelDiv.onclick = () => selectChannel(channel.id, channel.name);
                sidebar.appendChild(channelDiv);
            });
        });
    } catch (error) {
        console.error('Ошибка загрузки категорий:', error);
        showError('Не удалось загрузить каналы');
    }
}

// Показать ошибку
function showError(message) {
    const container = document.getElementById('messagesContainer');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'message';
    errorDiv.style.color = '#ed4245';
    errorDiv.textContent = `❌ ${message}`;
    container.appendChild(errorDiv);
}