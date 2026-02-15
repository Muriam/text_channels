from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, join_room, emit
from flask_sqlalchemy import SQLAlchemy
import os
from flask import send_from_directory
from datetime import datetime


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
                channels = ['Python', 'Flask', 'Django', 'SQLite3']
            elif cat_name == 'Frontend':
                channels = ['JavaScript', 'HTML', 'CSS']
            else:
                channels = ['reference', 'web', 'C']
                
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


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_names_channels()
    socketio.run(app, debug=True, port=5000)