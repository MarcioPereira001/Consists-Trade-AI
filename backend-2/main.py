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
    title="Consists Trade AI - Motor Micro-Scalping",
    description="Backend de integração MT5, IA e WebSockets (Alta Frequência)",
    version="2.0.0"
)

# --- GERENCIADOR DE CONEXÕES WEBSOCKET (ROBUSTO) ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """
        Envia mensagens para todos os clientes conectados. 
        """
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Erro ao transmitir: {e}")
                self.active_connections.remove(connection)

manager = ConnectionManager()

# --- CONFIGURAÇÕES GLOBAIS DE CONTROLE ---
current_symbol = "BITG26" # Padrão inicial focado no ativo mencionado
force_config_reload = True # Flag para otimização de cache do banco

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
        "mode": "micro-scalping",
        "current_asset": current_symbol,
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

@app.post("/api/reload_config")
async def reload_config():
    global force_config_reload
    force_config_reload = True
    print("--- COMANDO RECEBIDO: Recarregar Configurações do Supabase ---")
    return {"status": "success"}

@app.post("/api/broadcast_log")
async def broadcast_log(data: dict):
    """
    Endpoint interno chamado pelo trading_bot.py para enviar dados ao frontend via WebSocket.
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
            "message": "Motor Consists Trade AI (Micro-Scalping) Iniciado. Conexão Estabelecida."
        })
        
        while True:
            # Mantém a conexão aberta recebendo pings
            data = await websocket.receive_text()
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Cliente desconectado.")
    except Exception as e:
        manager.disconnect(websocket)
        print(f"Erro no WebSocket: {e}")

# --- EXECUÇÃO ---

if __name__ == "__main__":
    import uvicorn
    # reload=True para facilitar o desenvolvimento
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
