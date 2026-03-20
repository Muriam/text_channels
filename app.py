from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, join_room, emit
from flask_sqlalchemy import SQLAlchemy
import os
from flask import send_from_directory
from datetime import datetime
import requests
from bs4 import BeautifulSoup


app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")


# Модели
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    password = db.Column(db.String(80))
    
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    
class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Добавляем отношения
    user = db.relationship('User', backref='messages')
    channel = db.relationship('Channel', backref='messages')

# текстовые каналы
def create_names_channels():
    if not User.query.first():
        # Создаем только обычного пользователя
        admin = User(username='admin', password='admin')
        db.session.add(admin)
        
        categories = ['Backend', 'Frontend', 'Other']
        for cat_name in categories:
            category = Category(name=cat_name)
            db.session.add(category)
            db.session.flush()
            
            channels = []
            if cat_name == 'Backend':
                channels = ['Python', 'Flask', 'Django', 'Другие фреймворки', 'SQLite3', 'SQL', 'DataBase']
            elif cat_name == 'Frontend':
                channels = ['JavaScript', 'HTML', 'CSS', 'Другие фреймворки']
            else:
                channels = ['reference', 'web', 'C', 'непонятки', 'прочее']
                
            for chan_name in channels:
                channel = Channel(name=chan_name, category_id=category.id)
                db.session.add(channel)
        
        db.session.commit()


@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# Маршруты
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('index'))
        return "Неверные данные"
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if not User.query.filter_by(username=username).first():
            user = User(username=username, password=password)  # is_admin удален
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('login'))
        return "Имя уже занято"
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/api/categories')
def get_categories():
    categories = Category.query.all()
    result = []
    for cat in categories:
        channels = Channel.query.filter_by(category_id=cat.id).all()
        result.append({
            'id': cat.id,
            'name': cat.name,
            'channels': [{'id': c.id, 'name': c.name} for c in channels]  # description удален
        })
    return {'categories': result}


@app.route('/api/channels/<int:channel_id>/messages')
def get_messages(channel_id):
    messages = Message.query.filter_by(channel_id=channel_id)\
        .join(User)\
        .order_by(Message.timestamp)\
        .limit(100)\
        .all()
    return {'messages': [{
        'id': m.id,
        'content': m.content,
        'user': m.user.username,
        'timestamp': m.timestamp.strftime('%H:%M')
    } for m in messages]}

# WebSocket
@socketio.on('join')
def on_join(data):
    join_room(data['channel_id'])
    emit('status', f"{data['username']} присоединился", room=data['channel_id'])

@socketio.on('message')
def handle_message(data):
    message = Message(
        content=data['content'],
        user_id=session['user_id'],
        channel_id=data['channel_id']
    )
    db.session.add(message)
    db.session.commit()
    
    emit('new_message', {
        'content': data['content'],
        'user': session['username'],
        'timestamp': message.timestamp.strftime('%H:%M')
    }, room=data['channel_id'])


@app.route('/api/preview')
def get_link_preview():
    url = request.args.get('url')
    if not url:
        return {'error': 'No URL'}, 400
    

    from urllib.parse import unquote, urlparse
    import re
    
    # Декодируем URL если нужно
    url = unquote(url)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    try:
        # Увеличиваем таймаут до 5 секунд
        response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        response.raise_for_status()
        
        # Определяем кодировку
        if response.encoding is None:
            response.encoding = 'utf-8'
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Функция для безопасного получения атрибутов
        def get_meta_content(property_names, is_property=True):
            for name in property_names:
                if is_property:
                    tag = soup.find('meta', property=name)
                else:
                    tag = soup.find('meta', attrs={'name': name})
                if tag and tag.get('content'):
                    return tag['content']
            return ''
        
        # Пробуем разные варианты заголовков
        title = (
            get_meta_content(['og:title', 'twitter:title']) or
            get_meta_content(['title'], is_property=False) or
            (soup.find('title').string if soup.find('title') else '')
        )
        
        # Пробуем разные варианты описаний
        description = (
            get_meta_content(['og:description', 'twitter:description']) or
            get_meta_content(['description'], is_property=False)
        )
        
        # Пробуем разные варианты изображений
        image = (
            get_meta_content(['og:image', 'twitter:image']) or
            get_meta_content(['og:image:secure_url'])
        )
        
        # Для YouTube особенно
        if 'youtube.com' in url or 'youtu.be' in url:
            video_id = None
            if 'youtube.com/watch' in url:
                match = re.search(r'[?&]v=([^&]+)', url)
                if match:
                    video_id = match.group(1)
            elif 'youtu.be/' in url:
                video_id = url.split('youtu.be/')[-1].split('?')[0]
            
            if video_id:
                image = f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg'
                if not title:
                    title = 'YouTube Video'
        
        # Очищаем от лишних пробелов
        if title:
            title = ' '.join(title.split())
        if description:
            description = ' '.join(description.split())
        
        # Функция для получения домена
        def get_domain_name(url):
            try:
                domain = urlparse(url).netloc
                return domain.replace('www.', '')
            except:
                return 'Ссылка'
        
        preview = {
            'title': title[:200] if title else '',
            'description': description[:300] if description else '',
            'image': image if image and not image.startswith('/') else '',
            'url': url,
            'site_name': get_meta_content(['og:site_name']) or get_domain_name(url)
        }
        
        return preview  # ← Вот этот return
        
    except requests.exceptions.Timeout:
        return {'error': 'Timeout'}, 504
    except requests.exceptions.ConnectionError:
        return {'error': 'Connection error'}, 502
    except requests.exceptions.HTTPError as e:
        return {'error': f'HTTP {e.response.status_code}'}, e.response.status_code
    except Exception as e:
        print(f"Preview error for {url}: {str(e)}")
        return {'error': 'Failed to fetch'}, 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_names_channels()
    socketio.run(app, debug=True, port=5000)