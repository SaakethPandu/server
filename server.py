from flask import Flask, render_template, request
from flask_socketio import SocketIO, send, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

connected_users = {}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print("Client connected.")

@socketio.on('register')
def handle_register(data):
    username = data.get('username')
    if username:
        connected_users[username] = request.sid
        emit('user_list', list(connected_users.keys()), broadcast=True)
        send(f"{username}: joined the chat", broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    for user, sid in list(connected_users.items()):
        if sid == request.sid:
            del connected_users[user]
            send(f"{user}: left the chat", broadcast=True)
            break
    emit('user_list', list(connected_users.keys()), broadcast=True)

@socketio.on('send_message')
def handle_send_message(data):
    sender = data.get('username')
    recipient = data.get('recipient')
    message = data.get('message')

    if recipient == 'ALL':
        send(f"{sender}: {message}", broadcast=True)
    else:
        recipient_sid = connected_users.get(recipient)
        if recipient_sid:
            emit('message', f"📤 [You ➜ {recipient}]: {message}", to=request.sid)
            emit('message', f"📩 [Private] {sender}: {message}", to=recipient_sid)
        else:
            emit('message', f"⚠️ {recipient} not available", to=request.sid)

if __name__ == '__main__':
    socketio.run(app, debug=True)
