from flask import Flask, Response
from flask_socketio import SocketIO, send, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

connected_users = {}

@app.route('/')
def index():
    return Response(get_html(), mimetype='text/html')

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

def get_html():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Chat App</title>
    <style>
        body { display: flex; font-family: sans-serif; }
        #chat-box { flex: 1; padding: 10px; position: relative; }
        #user-list { width: 200px; border-left: 1px solid #ccc; padding: 10px; background: #f5f5f5; }
        #messages { height: 400px; overflow-y: auto; border: 1px solid #ccc; padding: 5px; margin-bottom: 10px; }
        #status { font-weight: bold; margin-bottom: 10px; }
        .user { cursor: pointer; margin: 5px 0; padding: 5px; border-radius: 5px; }
        .user:hover { background: #e0e0e0; }
        #notif {
            background-color: #ffeb3b;
            padding: 10px;
            margin-bottom: 5px;
            font-weight: bold;
            display: none;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div id="chat-box">
        <div id="notif" onclick="switchToPublic()">📢 New message received (Click to view)</div>
        <div id="status">Status: Connecting...</div>
        <div id="messages"></div>
        <input id="message" placeholder="Type your message" />
        <button onclick="sendMessage()">Send</button>
    </div>
    <div id="user-list">
        <h4>Users</h4>
        <div id="users"></div>
    </div>

    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script>
        const socket = io();
        const username = prompt("Enter your username:");
        const password = prompt("Enter your password:");

        let currentRecipient = 'ALL';
        let publicMessages = [];
        let privateMessages = {};

        socket.on('connect', () => {
            document.getElementById("status").innerText = "✅ Connected";
            socket.emit('register', { username });
        });

        socket.on('disconnect', () => {
            document.getElementById("status").innerText = "❌ Disconnected";
        });

        socket.on('message', (msg) => {
            const isPrivate = msg.includes('[Private]') || msg.includes('[You ➜]');
            const isPublic = !isPrivate;

            if (isPrivate) {
                const match = msg.match(/(➜|Private\\] )(\\w+):?/);
                const otherUser = match ? match[2] : currentRecipient;

                if (!privateMessages[otherUser]) privateMessages[otherUser] = [];
                privateMessages[otherUser].push(msg);

                if (currentRecipient === otherUser) {
                    appendMessage(msg);
                } else {
                    showNotification(`🔔 New private message from ${otherUser}`, () => setRecipient(otherUser));
                }
            }

            if (isPublic) {
                publicMessages.push(msg);
                if (currentRecipient === 'ALL') {
                    appendMessage(msg);
                } else {
                    showNotification("📢 New public message", switchToPublic);
                }
            }
        });

        socket.on('user_list', (users) => {
            const userList = document.getElementById("users");
            userList.innerHTML = '';

            const allDiv = document.createElement('div');
            allDiv.textContent = '🌍 Public Chat';
            allDiv.className = 'user';
            allDiv.style.fontWeight = currentRecipient === 'ALL' ? 'bold' : '';
            allDiv.onclick = () => setRecipient('ALL');
            userList.appendChild(allDiv);

            users.forEach(user => {
                if (user !== username) {
                    const userDiv = document.createElement('div');
                    userDiv.textContent = user;
                    userDiv.className = 'user';
                    userDiv.style.fontWeight = currentRecipient === user ? 'bold' : '';
                    userDiv.onclick = () => setRecipient(user);
                    userList.appendChild(userDiv);
                }
            });
        });

        function sendMessage() {
            const msg = document.getElementById("message").value.trim();
            if (!msg) return;

            socket.emit('send_message', {
                username,
                password,
                recipient: currentRecipient,
                message: msg
            });

            if (currentRecipient !== 'ALL') {
                const formatted = `📤 [You ➜ ${currentRecipient}]: ${msg}`;
                if (!privateMessages[currentRecipient]) privateMessages[currentRecipient] = [];
                privateMessages[currentRecipient].push(formatted);
                appendMessage(formatted);
            }

            document.getElementById("message").value = '';
        }

        function setRecipient(user) {
            currentRecipient = user;
            document.getElementById("status").innerText =
                user === 'ALL' ? "🟢 Public chat" : `🔒 Private chat with ${user}`;
            clearMessages();
            hideNotification();

            if (user === 'ALL') {
                publicMessages.forEach(msg => appendMessage(msg));
            } else {
                (privateMessages[user] || []).forEach(msg => appendMessage(msg));
            }
        }

        function appendMessage(msg) {
            const div = document.createElement("div");
            div.textContent = msg;
            document.getElementById("messages").appendChild(div);
        }

        function clearMessages() {
            document.getElementById("messages").innerHTML = '';
        }

        function showNotification(text, onClick) {
            const notif = document.getElementById("notif");
            notif.innerText = text + " (Click to view)";
            notif.style.display = 'block';
            notif.onclick = onClick;
        }

        function hideNotification() {
            document.getElementById("notif").style.display = 'none';
        }

        function switchToPublic() {
            setRecipient('ALL');
        }
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    from flask import request  # Needed for 'request.sid'
    socketio.run(app, host='0.0.0.0', port=5000)
