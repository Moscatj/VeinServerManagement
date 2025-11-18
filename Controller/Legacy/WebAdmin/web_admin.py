from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    UserMixin,
    current_user,
)
import subprocess
import os
import json
import sys

from datetime import datetime

# === CONFIGURATION ===
SERVER_DIR = "G:\\Servers\\VeinServer"
TOOLS_DIR = os.path.join(SERVER_DIR, "Tools")
WEBADMIN_DIR = os.path.join(TOOLS_DIR, "WebAdmin")
USERS_FILE = os.path.join(WEBADMIN_DIR, "user_accounts.json")
STATE_FILE = os.path.join(WEBADMIN_DIR, "server_state.json")
BACKUP_ROOT = os.path.join(SERVER_DIR, "Vein", "Backups")
PORT = 5000

sys.path.append(TOOLS_DIR)
from Tools.process import is_server_running
from Tools.discord import send_discord_message
from Tools.backups_api import make_backup as backup_save_file

app = Flask(__name__, template_folder=os.path.join(WEBADMIN_DIR, "templates"))
app.secret_key = "REPLACE_WITH_STRONG_SECRET_KEY"
login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(UserMixin):
    def __init__(self, id, role):
        self.id = id
        self.role = role


def load_users():
    with open(USERS_FILE, "r") as f:
        return json.load(f)


@login_manager.user_loader
def load_user(user_id):
    users = load_users()
    if user_id in users:
        return User(user_id, users[user_id]["role"])
    return None


def read_state_file():
    if not os.path.exists(STATE_FILE):
        return {"players": [], "player_count": 0}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"players": [], "player_count": 0}


def get_backup_status(root: str) -> dict:
    status = {}
    root_path = Path(root)
    if not root_path.exists():
        return status
    for category in sorted(root_path.iterdir()):
        if not category.is_dir():
            continue
        archives = sorted(category.glob("*.zip"), reverse=True)
        status[category.name] = {
            "count": len(archives),
            "latest": archives[0].name if archives else None,
        }
    return status


@app.route("/")
@login_required
def index():
    server_running = is_server_running()
    state = read_state_file()
    backup_status = get_backup_status(BACKUP_ROOT)
    return render_template(
        "index.html",
        server_running=server_running,
        player_count=state.get("player_count", 0),
        players=state.get("players", []),
        backup_status=backup_status,
        user=current_user,
    )


@app.route("/start")
@login_required
def start_server():
    if current_user.role != "admin":
        flash("Permission Denied: Admins only.")
        return redirect(url_for("index"))

    subprocess.Popen(
        ["cmd", "/c", os.path.join(SERVER_DIR, "StartServer.bat")], shell=True
    )
    flash("Server start command issued.")
    send_discord_message(
        "🟢 Server start command issued via Web Admin.", channel="startup"
    )
    return redirect(url_for("index"))


@app.route("/stop")
@login_required
def stop_server():
    if current_user.role != "admin":
        flash("Permission Denied: Admins only.")
        return redirect(url_for("index"))

    subprocess.Popen(
        ["cmd", "/c", os.path.join(SERVER_DIR, "ShutdownServer.bat")], shell=True
    )
    flash("Server shutdown command issued.")
    send_discord_message(
        "🔴 Server shutdown command issued via Web Admin.", channel="shutdown"
    )
    return redirect(url_for("index"))


@app.route("/backup")
@login_required
def manual_backup():
    if current_user.role != "admin":
        flash("Permission Denied: Admins only.")
        return redirect(url_for("index"))

    backup_save_file(reason="ManualWebBackup")
    flash("Manual backup created successfully.")
    send_discord_message("💾 Manual backup triggered via Web Admin.", channel="backups")
    return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        users = load_users()

        if username in users and users[username]["password"] == password:
            user_obj = User(username, users[username]["role"])
            login_user(user_obj)
            return redirect(url_for("index"))
        else:
            flash("Invalid credentials")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
