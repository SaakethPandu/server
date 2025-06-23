from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)

connected_users = {}
maintenance_mode = False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@socketio.on('connect')
def handle_connect():
    emit('maintenance_status', maintenance_mode)

@socketio.on('get_maintenance_status')
def send_maintenance_status():
    emit('maintenance_status', maintenance_mode)

@socketio.on('register')
def register_user(data):
    username = data.get('username')
    if username in connected_users.values():
        emit('registration_failed', 'Username already taken.')
        return

    connected_users[request.sid] = username
    emit('user_list', list(connected_users.values()), broadcast=True)
    print(f"✅ {username} connected. Total users: {len(connected_users)}")

@socketio.on('disconnect')
def handle_disconnect():
    user = connected_users.pop(request.sid, None)
    if user:
        print(f"❌ {user} disconnected.")
        emit('user_list', list(connected_users.values()), broadcast=True)

@socketio.on('chat_message')
def handle_chat_message(data):
    msg = data.get('message')
    to_user = data.get('to', 'ALL')
    from_user = connected_users.get(request.sid, 'Unknown')

    if to_user == 'ALL':
        emit('chat_message', {'from': from_user, 'message': msg}, broadcast=True)
    else:
        for sid, user in connected_users.items():
            if user == to_user or sid == request.sid:
                emit('chat_message', {'from': from_user, 'message': msg}, room=sid)

@socketio.on('admin_command')
def handle_admin_command(cmd):
    global maintenance_mode
    sid = request.sid
    cmd = cmd.strip().lower()

    if cmd == "keep it under maintenance":
        maintenance_mode = True
        emit("maintenance_updated", True, broadcast=True)
        emit("cmd_result", "✅ Server set to maintenance.", room=sid)

    elif cmd == "keep online":
        maintenance_mode = False
        emit("maintenance_updated", False, broadcast=True)
        emit("cmd_result", "✅ Server set to online.", room=sid)

    elif cmd == "show users":
        if connected_users:
            users = "\n".join([f"• {u}" for u in connected_users.values()])
            emit("cmd_result", f"👥 Online users:\n{users}", room=sid)
        else:
            emit("cmd_result", "👥 No users currently connected.", room=sid)

    elif cmd == "clear":
        emit("cmd_result", "🧹 Cleared client terminal.", room=sid)

    else:
        emit("cmd_result", f"⚠️ Unknown command: {cmd}", room=sid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
