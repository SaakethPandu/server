import sys
import threading
import requests
import socketio
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QListWidget,
    QMessageBox
)
from PyQt5.QtCore import Qt

SERVER_URL = "http://localhost:5000"  # Change to your server URL
SOCKET_IO_URL = SERVER_URL

sio = socketio.Client()


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chat Login / Register")

        self.layout = QVBoxLayout()

        self.username_label = QLabel("Username:")
        self.username_edit = QLineEdit()

        self.password_label = QLabel("Password:")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)

        self.login_btn = QPushButton("Login")
        self.register_btn = QPushButton("Register")

        self.layout.addWidget(self.username_label)
        self.layout.addWidget(self.username_edit)
        self.layout.addWidget(self.password_label)
        self.layout.addWidget(self.password_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.login_btn)
        btn_layout.addWidget(self.register_btn)
        self.layout.addLayout(btn_layout)

        self.setLayout(self.layout)

        self.login_btn.clicked.connect(self.login)
        self.register_btn.clicked.connect(self.register)

    def login(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter username and password")
            return
        try:
            resp = requests.post(f"{SERVER_URL}/login", json={"username": username, "password": password})
            if resp.status_code == 200 and resp.json().get("success"):
                self.open_chat(username)
            else:
                QMessageBox.warning(self, "Login Failed", resp.json().get("message", "Unknown error"))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not connect to server: {e}")

    def register(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter username and password")
            return
        try:
            resp = requests.post(f"{SERVER_URL}/register", json={"username": username, "password": password})
            if resp.status_code == 200 and resp.json().get("success"):
                QMessageBox.information(self, "Success", "Registration successful! You can now login.")
            else:
                QMessageBox.warning(self, "Register Failed", resp.json().get("message", "Unknown error"))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not connect to server: {e}")

    def open_chat(self, username):
        self.chat_window = ChatWindow(username)
        self.chat_window.show()
        self.close()


class ChatWindow(QWidget):
    def __init__(self, username):
        super().__init__()
        self.setWindowTitle(f"Chat - {username}")
        self.username = username

        self.resize(600, 400)
        layout = QVBoxLayout()

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)

        self.online_users_label = QLabel("Online Users:")
        self.online_users_list = QListWidget()
        self.online_users_list.setMaximumWidth(150)

        self.message_edit = QLineEdit()
        self.message_edit.setPlaceholderText("Type your message here...")
        self.send_btn = QPushButton("Send")

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.message_edit)
        bottom_layout.addWidget(self.send_btn)

        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        left_layout.addWidget(self.chat_display)
        left_layout.addLayout(bottom_layout)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.online_users_label)
        right_layout.addWidget(self.online_users_list)

        main_layout.addLayout(left_layout, stretch=4)
        main_layout.addLayout(right_layout, stretch=1)

        layout.addLayout(main_layout)
        self.setLayout(layout)

        self.send_btn.clicked.connect(self.send_message)
        self.message_edit.returnPressed.connect(self.send_message)

        self.setup_socket()

    def setup_socket(self):
        # Connect socketio in a background thread
        threading.Thread(target=self.connect_socket).start()

    def connect_socket(self):
        try:
            sio.connect(SOCKET_IO_URL)
            sio.emit("join", {"username": self.username})
        except Exception as e:
            self.append_chat(f"Error connecting to chat server: {e}")

        @sio.event
        def connect():
            self.append_chat("Connected to chat server.")

        @sio.event
        def disconnect():
            self.append_chat("Disconnected from chat server.")

        @sio.on("message")
        def on_message(data):
            username = data.get("username")
            message = data.get("message")
            self.append_chat(f"<b>{username}:</b> {message}")

        @sio.on("user_joined")
        def on_user_joined(data):
            username = data.get("username")
            self.append_chat(f"<i>{username} joined the chat.</i>")

        @sio.on("user_left")
        def on_user_left(data):
            username = data.get("username")
            self.append_chat(f"<i>{username} left the chat.</i>")

        @sio.on("online_users")
        def on_online_users(data):
            self.online_users_list.clear()
            for user in data:
                self.online_users_list.addItem(user)

    def append_chat(self, text):
        self.chat_display.append(text)

    def send_message(self):
        message = self.message_edit.text().strip()
        if message:
            sio.emit("message", {"username": self.username, "message": message})
            self.message_edit.clear()


def main():
    app = QApplication(sys.argv)
    login = LoginWindow()
    login.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
