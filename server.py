from flask import Flask, request
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
connected_users = {}  # key = socket id, value = username

@app.route("/")
def index():
    return "✅ Chat Server is Running!"

@socketio.on('connect')
def handle_connect():
    print("Client connected.")

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in connected_users:
        username = connected_users[sid]
        print(f"{username} disconnected.")
        emit('user_left', {'username': username}, broadcast=True)
        del connected_users[sid]
        send_online_users()

@socketio.on('join')
def handle_join(data):
    username = data['username']
    connected_users[request.sid] = username
    print(f"{username} joined.")
    emit('user_joined', {'username': username}, broadcast=True)
    send_online_users()

@socketio.on('message')
def handle_message(data):
    emit('message', data, broadcast=True)

def send_online_users():
    user_list = list(connected_users.values())
    emit('online_users', user_list, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # for Render or localhost
    socketio.run(app, host="0.0.0.0", port=port)
