from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
import sqlite3
import json
from datetime import datetime

app = FastAPI(title="Realtime Chat Server")

# 🔌 Ulanishlarni boshqaruvchi
class ConnectionManager:
    def __init__(self):
        self.connections = {}  # {"room": [websocket, ...]}

    async def connect(self, ws: WebSocket, room: str):
        await ws.accept()
        self.connections.setdefault(room, []).append(ws)

    def disconnect(self, ws: WebSocket, room: str):
        if room in self.connections:
            self.connections[room].remove(ws)
            if not self.connections[room]:
                del self.connections[room]

    async def broadcast(self, msg: str, room: str):
        for ws in self.connections.get(room, []):
            await ws.send_text(msg)

manager = ConnectionManager()

# 🗄️ SQLite boshlang'ich sozlamalar
DB = sqlite3.connect("chat.db", check_same_thread=False)
DB.cursor().execute('''CREATE TABLE IF NOT EXISTS messages
    (id INTEGER PRIMARY KEY, room TEXT, user TEXT, text TEXT, ts TEXT)''')
DB.commit()

@app.websocket("/ws/{room}")
async def chat(ws: WebSocket, room: str):
    await manager.connect(ws, room)
    sys_msg = json.dumps({"type": "system", "text": f"👤 {ws.client.host} qo'shildi", "ts": datetime.now().isoformat()})
    await manager.broadcast(sys_msg, room)
    
    try:
        while True:
            data = json.loads(await ws.receive_text())
            user, text = data.get("user", "Guest"), data.get("text", "")
            ts = datetime.now().isoformat()
            
            # DB ga yozish
            DB.cursor().execute("INSERT INTO messages VALUES (NULL, ?, ?, ?, ?)", (room, user, text, ts))
            DB.commit()
            
            # Barchaga yuborish
            await manager.broadcast(json.dumps({"type": "msg", "user": user, "text": text, "ts": ts}), room)
    except WebSocketDisconnect:
        manager.disconnect(ws, room)
        await manager.broadcast(json.dumps({"type": "system", "text": f"👋 Foydalanuvchi chiqdi", "ts": datetime.now().isoformat()}), room)

@app.get("/history/{room}")
def get_history(room: str, limit: int = 30):
    rows = DB.cursor().execute(
        "SELECT user, text, ts FROM messages WHERE room=? ORDER BY id DESC LIMIT ?", (room, limit)
    ).fetchall()
    return [{"user": r[0], "text": r[1], "ts": r[2]} for r in reversed(rows)]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
