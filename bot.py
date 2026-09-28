import os
import json
import time
import sqlite3
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler


# ==============================
# CONFIG - ENVIRONMENT SE LEGA
# ==============================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_BASE_URL = "https://backemdhub.zone.id/api/osint/num"
API_KEY = os.environ.get("API_KEY")
ADMIN_ID = "5017811608"

DB_FILE = "bot_state.db"
PHONE_BUTTON = "📱 Phone Lookup"


# ==============================
# DATABASE
# ==============================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS offset_data (
            id INTEGER PRIMARY KEY,
            last_offset INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def get_offset():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT last_offset FROM offset_data LIMIT 1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def save_offset(offset):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM offset_data")
    c.execute("INSERT INTO offset_data (last_offset) VALUES (?)", (offset,))
    conn.commit()
    conn.close()


# ==============================
# WEB SERVER (RENDER)
# ==============================

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {"status": "ok", "bot": "running"}
            self.wfile.write(json.dumps(data).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass


def run_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"✅ Server running on port {port}")
    server.serve_forever()


# ==============================
# TELEGRAM FUNCTIONS
# ==============================

def send_msg(chat_id, text, buttons=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    if buttons:
        data["reply_markup"] = json.dumps(buttons)
    
    try:
        requests.post(url, data=data, timeout=15)
    except:
        pass


def get_updates(offset):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    try:
        response = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=35)
        return response.json()
    except:
        return None


# ==============================
# API CALL
# ==============================

def lookup_phone(number):
    try:
        url = f"{API_BASE_URL}?mobile={number}&key={API_KEY}"
        response = requests.get(url, timeout=15)
        return response.json()
    except Exception as e:
        return {"error": str(e)}


# ==============================
# BOT MAIN
# ==============================

def bot():
    if not BOT_TOKEN or not API_KEY:
        print("❌ Missing BOT_TOKEN or API_KEY")
        return
    
    init_db()
    
    keyboard = {
        "keyboard": [[{"text": PHONE_BUTTON}]],
        "resize_keyboard": True
    }
    
    offset = get_offset()
    print(f"✅ Bot started. Offset: {offset}")
    
    while True:
        try:
            updates = get_updates(offset)
            
            if not updates or not updates.get("ok"):
                time.sleep(2)
                continue
            
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                save_offset(offset)
                
                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                user_id = msg.get("from", {}).get("id")
                text = msg.get("text", "").strip()
                
                if not chat_id or not text:
                    continue
                
                # START
                if text == "/start":
                    send_msg(chat_id, "👋 Welcome!\n\nClick button to lookup.", keyboard)
                    continue
                
                # ADMIN
                if text == "/admin":
                    if str(user_id) == ADMIN_ID:
                        send_msg(chat_id, f"🔐 Admin\n\nID: {user_id}\n✅ Access Granted", keyboard)
                    else:
                        send_msg(chat_id, "❌ Not authorized", keyboard)
                    continue
                
                # PHONE BUTTON
                if text == PHONE_BUTTON:
                    send_msg(chat_id, "📱 Send 10-digit number:", keyboard)
                    continue
                
                # LOOKUP
                if text.isdigit() and len(text) == 10:
                    send_msg(chat_id, "⏳ Searching...", keyboard)
                    result = lookup_phone(text)
                    
                    if "error" in result:
                        send_msg(chat_id, f"❌ Error: {result['error']}", keyboard)
                    else:
                        formatted = json.dumps(result, indent=2, ensure_ascii=False)
                        send_msg(chat_id, f"<pre>{formatted}</pre>", keyboard)
                    continue
                
                # DEFAULT
                send_msg(chat_id, "❌ Invalid. Use button.", keyboard)
            
            time.sleep(1)
        
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(3)


# ==============================
# START
# ==============================

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    bot()
