import os
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import List

# Carrega variáveis de ambiente
load_dotenv()

# Inicialização do FastAPI
app = FastAPI(
    title="Consists Trade AI - Motor Quantitativo",
    description="Backend de integração MT5, IA e WebSockets",
    version="1.0.0"
)

# --- GERENCIADOR DE CONEXÕES WEBSOCKET (ROBUSTO) ---
class ConnectionManager:
    def __init__(self):
        # Centralizamos as conexões aqui para evitar erros de 'undefined'
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """
        Envia mensagens para todos os clientes. 
        Usa send_json para garantir compatibilidade com o Frontend.
        """
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                # Se falhar, removemos a conexão morta
                print(f"Erro ao transmitir: {e}")
                self.active_connections.remove(connection)

manager = ConnectionManager()

# --- CONFIGURAÇÕES GLOBAIS DE CONTROLE ---
current_symbol = "EURUSD" # padrão inicial se no supabase não configurado outro
replay_speed = 1.0

# Configuração do CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicialização do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase client inicializado com sucesso.")
    except Exception as e:
        print(f"Erro ao inicializar Supabase: {e}")

# --- ENDPOINTS DE API ---

@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "current_asset": current_symbol,
        "replay_speed": replay_speed,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/select_asset")
async def select_asset(data: dict):
    global current_symbol
    new_asset = data.get("asset")
    if new_asset:
        current_symbol = new_asset
        print(f"--- COMANDO RECEBIDO: Trocando foco para {current_symbol} ---")
        return {"status": "success", "asset": current_symbol}
    return {"status": "error", "message": "Ativo não informado"}, 400

@app.post("/api/set_replay_speed")
async def set_speed(data: dict):
    global replay_speed
    try:
        replay_speed = float(data.get("speed", 1.0))
        print(f"--- VELOCIDADE REPLAY: {replay_speed}x ---")
        return {"status": "success", "speed": replay_speed}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400

@app.post("/api/broadcast_log")
async def broadcast_log(data: dict):
    """
    Este é o endpoint que o trading_bot.py chama.
    Agora ele usa o manager.broadcast corretamente.
    """
    await manager.broadcast(data)
    return {"status": "sent"}

# --- ENDPOINT WEBSOCKET ---

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await manager.connect(websocket)
    print(f"Novo cliente conectado. Total: {len(manager.active_connections)}")
    
    try:
        # Envia log inicial de boas-vindas
        await websocket.send_json({
            "id": "init-001",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "type": "info",
            "message": "Motor Consists Trade AI Iniciado. Conexão Estabelecida."
        })
        
        while True:
            # Mantém a conexão aberta recebendo pings ou apenas aguardando
            data = await websocket.receive_text()
            # Se o frontend mandar algo, podemos tratar aqui
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Cliente desconectado.")
    except Exception as e:
        manager.disconnect(websocket)
        print(f"Erro no WebSocket: {e}")

# --- EXECUÇÃO ---

if __name__ == "__main__":
    import uvicorn
    # reload=True é ótimo para desenvolvimento
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)