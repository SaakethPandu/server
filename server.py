from flask import Flask, request
from flask_socketio import SocketIO, emit
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
socketio = SocketIO(app, cors_allowed_origins="*")

connected_users = {}  # sid -> username
chat_history = []     # store last 100 messages
MAX_HISTORY = 100

def add_message(username, message, private=False, to_user=None):
    timestamp = datetime.now().strftime("%H:%M")
    entry = {
        "username": username,
        "message": message,
        "timestamp": timestamp,
        "private": private,
        "to_user": to_user
    }
    chat_history.append(entry)
    if len(chat_history) > MAX_HISTORY:
        chat_history.pop(0)
    return entry

@app.route('/')
def home():
    return "Chat Server is running."

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('request_username')

@socketio.on('set_username')
def handle_set_username(data):
    username = data.get('username')
    if not username:
        return
    connected_users[request.sid] = username
    print(f"Username set: {username} (SID: {request.sid})")
    emit('chat_history', chat_history)
    emit('user_joined', {"username": username}, broadcast=True)
    emit('online_users', list(connected_users.values()), broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    username = connected_users.pop(sid, None)
    if username:
        print(f"User disconnected: {username} (SID: {sid})")
        emit('user_left', {"username": username}, broadcast=True)
        emit('online_users', list(connected_users.values()), broadcast=True)

@socketio.on('send_message')
def handle_message(data):
    username = connected_users.get(request.sid, "Anonymous")
    message = data.get("message", "")
    to_user = data.get("to_user")

    if to_user and to_user != username:
        # Private message
        recipient_sid = None
        for sid, user in connected_users.items():
            if user == to_user:
                recipient_sid = sid
                break
        if recipient_sid:
            msg_data = add_message(username, message, private=True, to_user=to_user)
            emit('receive_message', msg_data, room=recipient_sid)
            emit('receive_message', msg_data, room=request.sid)
    else:
        # Broadcast message
        msg_data = add_message(username, message)
        emit('receive_message', msg_data, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
