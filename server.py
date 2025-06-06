from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
import sqlite3
import os
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Database Setup ---
def get_db_connection():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

connected_users = {}  # sid -> username
user_rate_limits = {}  # username -> last message timestamp
CHAT_LOG_FILE = "chat_log.txt"

# --- Rate Limiting Decorator ---
def rate_limited(max_per_minute=30):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            data = request.get_json() if request.is_json else request.form
            username = data.get('username')
            
            if username in user_rate_limits:
                last_time = user_rate_limits[username]
                time_diff = (datetime.datetime.now() - last_time).total_seconds()
                if time_diff < 60/max_per_minute:
                    return jsonify({
                        "success": False,
                        "message": "Message rate limit exceeded. Please wait before sending another message."
                    }), 429
            
            user_rate_limits[username] = datetime.datetime.now()
            return f(*args, **kwargs)
        return wrapped
    return decorator

# --- HTTP Routes ---

@app.route("/")
def index():
    """Serve the HTML chat client"""
    return render_template('index.html')

@app.route("/register", methods=["POST"])
@rate_limited(max_per_minute=5)  # Limit registration attempts
def register():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not username or not password:
        return jsonify({"success": False, "message": "Missing username or password"}), 400
    
    if len(username) < 3 or len(username) > 20:
        return jsonify({"success": False, "message": "Username must be 3-20 characters"}), 400
    
    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Username already exists"}), 409

        hashed_password = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)", 
            (username, hashed_password)
        )
        conn.commit()
        return jsonify({"success": True, "message": "Registration successful"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

@app.route("/login", methods=["POST"])
@rate_limited(max_per_minute=5)  # Limit login attempts
def login():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not username or not password:
        return jsonify({"success": False, "message": "Missing username or password"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password'], password):
            return jsonify({
                "success": True, 
                "message": "Login successful",
                "username": username
            })
        else:
            return jsonify({"success": False, "message": "Invalid username or password"}), 401
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

@app.route("/history", methods=["GET"])
def get_history():
    """Get recent chat history"""
    limit = request.args.get('limit', default=50, type=int)
    if limit > 100:
        limit = 100
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT username, message, timestamp FROM messages "
            "ORDER BY timestamp DESC LIMIT ?", 
            (limit,)
        )
        messages = cursor.fetchall()
        return jsonify({
            "success": True,
            "messages": [
                {
                    "username": msg['username'],
                    "message": msg['message'],
                    "timestamp": msg['timestamp']
                } for msg in messages
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

# --- Socket.IO Events ---

@socketio.on("connect")
def on_connect():
    print(f"Client connected: {request.sid}")

@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    if sid in connected_users:
        username = connected_users[sid]
        print(f"{username} disconnected.")
        emit("user_left", {"username": username}, broadcast=True)
        del connected_users[sid]
        send_online_users()

@socketio.on("join")
def on_join(data):
    username = data.get("username", "").strip()
    if not username:
        return  # ignore if no username

    # Verify the user exists
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username=?", (username,))
    if not cursor.fetchone():
        emit("join_error", {"message": "User does not exist"})
        return
    conn.close()

    connected_users[request.sid] = username
    print(f"{username} joined.")
    emit("user_joined", {"username": username}, broadcast=True)
    send_online_users()

    # Send the user their recent messages
    emit("welcome", {
        "message": f"Welcome to the chat, {username}!",
        "timestamp": datetime.datetime.now().isoformat()
    })

@socketio.on("message")
def on_message(data):
    username = data.get("username", "").strip()
    message = data.get("message", "").strip()
    
    if not username or not message:
        return
    
    if username not in connected_users.values():
        emit("error", {"message": "You must join first"})
        return
    
    # Rate limiting
    if username in user_rate_limits:
        last_time = user_rate_limits[username]
        time_diff = (datetime.datetime.now() - last_time).total_seconds()
        if time_diff < 1:  # 1 second between messages
            emit("error", {"message": "Message rate limit exceeded"})
            return
    
    user_rate_limits[username] = datetime.datetime.now()
    
    # Store message in database
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO messages (username, message) VALUES (?, ?)",
            (username, message)
        )
        conn.commit()
    except Exception as e:
        print(f"Error saving message: {e}")
    finally:
        conn.close()
    
    # Broadcast message
    timestamp = datetime.datetime.now().isoformat()
    emit("message", {
        "username": username,
        "message": message,
        "timestamp": timestamp
    }, broadcast=True)
    
    # Log to file
    log_chat(username, message)

def send_online_users():
    user_list = list(connected_users.values())
    emit("online_users", {"users": user_list}, broadcast=True)

def log_chat(username, message):
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(CHAT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {username}: {message}\n")

# --- HTML Template ---
@app.route('/template')
def chat_template():
    """Endpoint to serve the HTML template for testing"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Chat App</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
            #chat { border: 1px solid #ccc; padding: 10px; height: 400px; overflow-y: scroll; }
            #users { border: 1px solid #ccc; padding: 10px; }
            .message { margin: 5px 0; padding: 5px; background: #f0f0f0; }
            .my-message { background: #d0e5ff; text-align: right; }
        </style>
    </head>
    <body>
        <h1>Chat App</h1>
        <div style="display: flex;">
            <div style="flex: 3;">
                <div id="chat"></div>
                <input id="message" placeholder="Type your message" style="width: 80%;">
                <button id="send">Send</button>
            </div>
            <div style="flex: 1;">
                <h3>Online Users</h3>
                <div id="users"></div>
            </div>
        </div>
        
        <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
        <script>
            const socket = io();
            let username = prompt("Enter your username:");
            
            // Join chat
            socket.emit('join', { username });
            
            // Handle messages
            socket.on('message', (data) => {
                const chat = document.getElementById('chat');
                const messageDiv = document.createElement('div');
                messageDiv.className = data.username === username ? 'message my-message' : 'message';
                messageDiv.innerHTML = `<strong>${data.username}:</strong> ${data.message}`;
                chat.appendChild(messageDiv);
                chat.scrollTop = chat.scrollHeight;
            });
            
            // Handle online users
            socket.on('online_users', (data) => {
                const usersDiv = document.getElementById('users');
                usersDiv.innerHTML = data.users.map(user => 
                    `<div>${user}</div>`
                ).join('');
            });
            
            // Handle user join/leave
            socket.on('user_joined', (data) => {
                const chat = document.getElementById('chat');
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message';
                messageDiv.innerHTML = `<em>${data.username} joined the chat</em>`;
                chat.appendChild(messageDiv);
            });
            
            socket.on('user_left', (data) => {
                const chat = document.getElementById('chat');
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message';
                messageDiv.innerHTML = `<em>${data.username} left the chat</em>`;
                chat.appendChild(messageDiv);
            });
            
            // Send message
            document.getElementById('send').addEventListener('click', () => {
                const message = document.getElementById('message').value;
                if (message) {
                    socket.emit('message', { username, message });
                    document.getElementById('message').value = '';
                }
            });
            
            // Send on Enter key
            document.getElementById('message').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    document.getElementById('send').click();
                }
            });
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
