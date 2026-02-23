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

# Gerenciador de Conexões WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                print(f"Erro ao enviar mensagem para cliente: {e}")

manager = ConnectionManager()

# Configuração do CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todas as origens (ajuste para produção)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicialização do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Fail-safe: Apenas inicializa se as chaves existirem
supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase client inicializado com sucesso.")
    except Exception as e:
        print(f"Erro ao inicializar Supabase: {e}")
else:
    print("Aviso: SUPABASE_URL ou SUPABASE_KEY não configurados.")

@app.get("/api/health")
async def health_check():
    """
    Endpoint de verificação de saúde do sistema.
    """
    return {
        "status": "online",
        "mt5": "pending",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/broadcast_log")
async def broadcast_log(request: Request):
    """
    Endpoint interno para o trading_bot.py enviar logs para os clientes conectados.
    """
    data = await request.json()
    await manager.broadcast(data)
    return {"status": "ok"}

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """
    Endpoint WebSocket para envio de logs em tempo real para o Frontend.
    """
    await manager.connect(websocket)
    print("Novo cliente conectado ao WebSocket de logs.")
    
    try:
        # Envia log inicial
        initial_log = {
            "id": "init-001",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "type": "info",
            "message": "Motor Consists Trade AI Iniciado. Aguardando conexão MT5..."
        }
        await websocket.send_text(json.dumps(initial_log))
        
        # Loop de manutenção da conexão (Keep-alive)
        while True:
            await asyncio.sleep(10) # Aguarda 10 segundos
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Cliente desconectado do WebSocket de logs.")
    except Exception as e:
        manager.disconnect(websocket)
        print(f"Erro no WebSocket: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
