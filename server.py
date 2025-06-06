from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all origins

# SQLite setup
DB_PATH = "users.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Create users table if not exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)
""")
conn.commit()

def update_users_file():
    cursor.execute("SELECT username FROM users")
    users = [row[0] for row in cursor.fetchall()]
    with open("registered_users.txt", "w") as f:
        for user in users:
            f.write(user + "\n")
    print(f"Updated registered_users.txt with {len(users)} users.")

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"success": False, "message": "Username and password required."}), 400

    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        return jsonify({"success": False, "message": "Username already exists."}), 400

    cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
    conn.commit()

    update_users_file()

    return jsonify({"success": True, "message": "User registered successfully."})

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"success": False, "message": "Username and password required."}), 400

    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if row and row[0] == password:
        return jsonify({"success": True, "message": "Login successful."})
    else:
        return jsonify({"success": False, "message": "Invalid username or password."}), 401

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print("Creating new database file...")
    app.run(host="0.0.0.0", port=5000, debug=True)
