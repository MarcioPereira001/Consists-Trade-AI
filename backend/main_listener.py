import os
import time
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Variáveis para guardar os processos
api_process = None
bot_process = None

def update_status(status: str):
    try:
        supabase.table('bot_control').update({
            'status': status,
            'command': 'NONE',
            'last_updated': datetime.now().isoformat()
        }).eq('id', 1).execute()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Status da Nuvem atualizado para: {status}")
    except Exception as e:
        pass

def start_api():
    """Liga a API (main.py) silenciosamente no background"""
    global api_process
    print("🌐 Iniciando Servidor API (main.py) em background...")
    
    # Redireciona os logs chatos para um arquivo de texto, limpando a tela
    log_file = open('api_logs.txt', 'a')
    api_process = subprocess.Popen(["python", "main.py"], stdout=log_file, stderr=log_file)
    print("✅ Servidor API Online (Logs salvos em api_logs.txt)")

print("==================================================")
print("🛡️ GERENCIADOR CENTRAL AWS INICIADO")
print("==================================================")

# 1. Liga a API e a Comunicação com o Painel assim que abre
start_api()
update_status('OFFLINE')

print("📡 Aguardando ordens de ignição do Painel Web...")

# 2. Loop de vigilância para ligar/desligar o Motor
while True:
    try:
        # Lê a ordem do chefe no Supabase
        response = supabase.table('bot_control').select('*').eq('id', 1).execute()
        data = response.data[0]
        comando = data['command']
        status_atual = data['status']

        # ORDEM: LIGAR O MOTOR
        if comando == 'START' and status_atual == 'OFFLINE':
            print("\n🚀 ORDEM RECEBIDA DO FRONTEND: INICIANDO MOTOR IA...")
            # Abre o bot no mesmo terminal para você ver os logs de inteligência
            bot_process = subprocess.Popen(["python", "trading_bot.py"])
            update_status('ONLINE')

        # ORDEM: DESLIGAR O MOTOR
        elif comando == 'STOP' and status_atual == 'ONLINE':
            print("\n🛑 ORDEM RECEBIDA DO FRONTEND: PARANDO OPERAÇÕES...")
            if bot_process:
                bot_process.terminate() 
                bot_process.wait() 
                bot_process = None
            
            # Garante que nenhum processo do robô fique preso na memória
            os.system("taskkill /f /im python.exe /fi \"WINDOWTITLE ne main_listener.py*\" >nul 2>&1")
            
            update_status('OFFLINE')
            print("💤 Motor desligado. Aguardando novas ordens...")
            
            # Como matamos os processos python soltos, a API pode ter caido junto. Religa ela:
            if api_process.poll() is not None:
                start_api()

        # Checa se o robô "crashou" sozinho e avisa o painel
        if status_atual == 'ONLINE' and bot_process and bot_process.poll() is not None:
            print("\n⚠️ ATENÇÃO: O motor do robô parou inesperadamente.")
            bot_process = None
            update_status('OFFLINE')

    except Exception as e:
        pass # Ignora pequenas quedas de internet e continua rodando
        
    time.sleep(3)