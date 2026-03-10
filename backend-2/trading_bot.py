import os
import asyncio
import json
import httpx
import time as time_lib
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
import MetaTrader5 as mt5
import pandas as pd

from mt5_service import MT5Service
from ai_service import AITrader

load_dotenv()

# Inicialização do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

mt5_service = MT5Service()
ai_trader = AITrader()

# --- VARIÁVEIS DE ESTADO EM MEMÓRIA ---
memoria_relevancia = {} 
memoria_estado_ia = {}

async def log_to_supabase(profile_id: str, log_type: str, message: str):
    """Salva logs de sistema no Supabase."""
    if not supabase: return
    try:
        supabase.table('system_logs').insert({
            "profile_id": profile_id,
            "type": log_type,
            "message": message,
            "created_at": datetime.now().isoformat()
        }).execute()
    except Exception as e:
        pass

async def save_trade_history(profile_id: str, ticket: int, ativo: str, tipo: str, preco: float, motivo: str):
    """Salva o histórico de trades no Supabase."""
    if not supabase: return
    try:
        supabase.table('trade_history').insert({
            "profile_id": profile_id,
            "ticket_mt5": ticket,
            "ativo": ativo,
            "tipo_ordem": tipo,
            "preco_entrada": preco,
            "motivo_ia": motivo,
            "created_at": datetime.now().isoformat()
        }).execute()
    except Exception as e:
        pass

async def broadcast_to_frontend(message: dict):
    """Envia os dados em tempo real para o servidor WebSocket repassar ao Painel Web."""
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://127.0.0.1:8000/api/broadcast_log", json=message, timeout=2.0)
    except Exception:
        pass 

async def trading_loop():
    """Loop principal de Alta Frequência (Micro-Scalping)."""
    print("Iniciando Trading Loop (Motor Micro-Scalper - 15s)...")
    
    if not mt5_service.conectar():
        print("❌ ERRO CRÍTICO: Verifique se o MT5 está aberto e se o .env está correto.")
        return

    cached_configs = None
    last_config_time = 0
    ultimo_ts_ia = 0 # Controle do ciclo da IA (15 segundos)
    
    # Variáveis de Cooldown e Controle de Estado
    em_posicao_anterior = False
    tempo_ultimo_trade_fechado = 0

    while True:
        try:
            import main
            agora_ts = time_lib.time()
            
            # 1. Buscar configurações do Supabase (Cache de 5 minutos)
            if cached_configs is None or main.force_config_reload or (agora_ts - last_config_time > 300):
                response = supabase.table('trade_configs').select('*').execute()
                cached_configs = response.data
                last_config_time = agora_ts
                main.force_config_reload = False
                print("🔄 Configurações recarregadas do banco de dados (Cache Atualizado).")
            
            configs = cached_configs
            
            if not configs:
                await asyncio.sleep(10)
                continue

            for config in configs:
                profile_id = config.get('profile_id')
                ativo = config.get('ativo', 'BITG26')
                
                # Sincroniza com o frontend
                main.current_symbol = ativo 
                
                # Variáveis de Execução (Micro-Scalping)
                lote = float(config.get('lote', 1.0))
                # Stop Loss e Take Profit curtos para Scalping (Ex: SL 100, TP 200)
                sl_pts = int(config.get('stop_loss', 100))
                tp_pts = int(config.get('take_profit', 200))
                estrategia = "Micro-Scalping (Alta Frequência)"
                horario_inicio = config.get('horario_inicio', '09:00')
                horario_fim = config.get('horario_fim', '17:30')
                ambiente = config.get('ambiente', 'AO VIVO')
                
                # Trava de Risco
                meta_diaria = float(config.get('meta_diaria', 500.0))
                limite_perda = float(config.get('limite_perda', -250.0))
                
                resultado_atual = mt5_service.obter_resultado_diario()
                
                if resultado_atual >= meta_diaria:
                    print(f"[{ativo}] META ALCANÇADA: R$ {resultado_atual:.2f}. Hibernando.")
                    continue
                
                if resultado_atual <= limite_perda:
                    print(f"[{ativo}] LIMITE DE PERDA ATINGIDO: R$ {resultado_atual:.2f}. Travado.")
                    continue

                # 2. Verificar Filtro de Horário
                agora = datetime.now().time()
                try:
                    h_inicio = datetime.strptime(horario_inicio, '%H:%M').time()
                    h_fim = datetime.strptime(horario_fim, '%H:%M').time()
                    if h_inicio <= h_fim:
                        dentro_horario = h_inicio <= agora <= h_fim
                    else:
                        dentro_horario = agora >= h_inicio or agora <= h_fim
                except ValueError:
                    dentro_horario = True

                if not dentro_horario:
                    print(f"[{ativo}] Fora da janela operacional ({horario_inicio} às {horario_fim}).")
                    continue

                # ======================================================================
                # GESTÃO TICK-A-TICK (TRAILING STOP DINÂMICO)
                # ======================================================================
                esta_posicionado = (ambiente != 'REPLAY HISTÓRICO' and mt5_service.tem_posicao_aberta(ativo))
                
                # Controle de Cooldown (Resfriamento pós-trade)
                if not esta_posicionado and em_posicao_anterior:
                    # O trade acabou de ser fechado (Gain ou Loss)
                    tempo_ultimo_trade_fechado = agora_ts
                    print(f"[{ativo}] 🛑 Operação fechada. Iniciando Cooldown de 60 segundos para evitar overtrading.")
                    
                em_posicao_anterior = esta_posicionado
                
                if esta_posicionado:
                    # Roda o Trailing Stop Dinâmico (Escadinha)
                    mt5_service.gerenciar_trailing_stop_dinamico(ativo)
                    
                    # Se estiver posicionado, a IA não precisa analisar o mercado para entrar
                    # Apenas avisa que está gerindo a posição
                    if (agora_ts - ultimo_ts_ia) > 60:
                        ultimo_ts_ia = agora_ts
                        print(f"[{ativo}] 🛡️ Gerenciando posição aberta com Trailing Stop Dinâmico...")
                        await broadcast_to_frontend({
                            "id": str(datetime.now().timestamp()),
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "type": "info",
                            "message": f"[{ativo}] 🛡️ Gerenciando posição aberta com Trailing Stop Dinâmico..."
                        })
                    await asyncio.sleep(1) # Roda a cada 1 segundo para gerir o stop rapidamente
                    continue

                # ======================================================================
                # MÓDULO ANALISTA (IA): ALTA FREQUÊNCIA (15 SEGUNDOS)
                # ======================================================================
                
                # Verifica se está em Cooldown
                if (agora_ts - tempo_ultimo_trade_fechado) < 60:
                    # Ainda em período de resfriamento
                    await asyncio.sleep(1)
                    continue
                    
                agora_ts_loop = time_lib.time()
                
                # CICLO DA IA: A cada 15 segundos
                if (agora_ts_loop - ultimo_ts_ia) < 15:
                    await asyncio.sleep(1) # Espera 1 segundo e checa de novo
                    continue
                
                ultimo_ts_ia = agora_ts_loop
                
                # Puxa dados M1 (Apenas 30 candles)
                df_micro = mt5_service.obter_dados_mercado(ativo, mt5.TIMEFRAME_M1, 30)

                if df_micro is None or df_micro.empty:
                    continue

                preco_atual_log = float(df_micro.iloc[-1]['close'])
                timestamp_atual = int(df_micro.iloc[-1]['time'].timestamp() if hasattr(df_micro.iloc[-1]['time'], 'timestamp') else pd.to_datetime(df_micro.iloc[-1]['time']).timestamp())
                
                dados_ontem = mt5_service.obter_ohlc_ontem(ativo) or {}
                relevancia_anterior = memoria_relevancia.get(profile_id, 1)
                estado_anterior_ia = memoria_estado_ia.get(profile_id, "Iniciando...")
                
                # Gera imagem M1 a cada 15 segundos para a IA ver o RSI e Volume
                caminho_foto_m1 = mt5_service.capturar_imagem_grafico(df_micro, ativo, "chart_m1.png", "M1 - Micro Scalping")

                # Medidor de Latência da IA
                start_time = time_lib.time()
                
                print(f"⚡ [{ativo}] Analisando Micro-Tendência (M1)...")
                analise = ai_trader.analisar_mercado(
                    dados_micro_df=df_micro,       
                    estrategia=estrategia, 
                    relevancia_anterior=relevancia_anterior,
                    dados_ontem=dados_ontem,
                    estado_anterior=estado_anterior_ia,
                    image_path_m1=caminho_foto_m1, 
                    posicao_aberta=None
                )
                
                tempo_ia = time_lib.time() - start_time
                
                nova_relevancia = analise.get('relevancia', 1)
                memoria_relevancia[profile_id] = nova_relevancia
                memoria_estado_ia[profile_id] = analise.get('estado_operacional', analise.get('motivo', ''))

                decisao = analise.get('decisao', 'WAIT')
                motivo = analise.get('motivo', 'Sem motivo')
                
                # --- TRAVA HARD-CODED INSTITUCIONAL (VWAP) ---
                vwap_atual = float(df_micro.iloc[-1]['vwap'])
                if decisao == 'BUY' and preco_atual_log < vwap_atual:
                    print(f"[{ativo}] ⚠️ BLOQUEIO DE SEGURANÇA: IA tentou COMPRAR abaixo da VWAP. Sinal anulado.")
                    decisao = 'WAIT'
                    motivo = "Bloqueado pelo Motor: Compra abaixo da VWAP."
                elif decisao == 'SELL' and preco_atual_log > vwap_atual:
                    print(f"[{ativo}] ⚠️ BLOQUEIO DE SEGURANÇA: IA tentou VENDER acima da VWAP. Sinal anulado.")
                    decisao = 'WAIT'
                    motivo = "Bloqueado pelo Motor: Venda acima da VWAP."

                print(f"IA [{nova_relevancia}★] [Preço: {preco_atual_log}] [Delay: {tempo_ia:.2f}s]: {decisao} | {motivo}")

                # 5. EXECUTAR ORDEM IMEDIATA SE A IA MANDAR A MERCADO
                if decisao in ['BUY', 'SELL']:
                    # Filtro de Relevância: Só entra se a IA der nota 4 ou 5 (Setup Claro)
                    if nova_relevancia < 4:
                        print(f"Sinal {decisao} rejeitado (Relevância {nova_relevancia} < 4). Aguardando melhor oportunidade.")
                    else:
                        if ambiente == 'REPLAY HISTÓRICO':
                            print(f"[MODO REPLAY] Simulando ordem {decisao} para {ativo} (Paper Trading)...")
                            resultado = mt5_service.simular_ordem_paper_trading(ativo, decisao, preco_atual_log, motivo)
                        else:
                            print(f"[MODO AO VIVO] Executando ordem REAL {decisao} para {ativo}...")
                            resultado = mt5_service.enviar_ordem(ativo, decisao, lote, sl_pts, tp_pts)
                        
                        if resultado:
                            tag = "[SIMULAÇÃO] " if ambiente == 'REPLAY HISTÓRICO' else ""
                            await log_to_supabase(profile_id, "trade", f"{tag}Ordem {decisao} via {estrategia}")
                            await save_trade_history(profile_id, resultado.order, ativo, decisao, resultado.price, motivo)
                            
                            msg_execucao_mercado = f"[{ativo}] ⚡ MICRO-SCALPING: ORDEM {decisao} EXECUTADA!\n🧠 Raciocínio da IA: {motivo}"
                            await broadcast_to_frontend({
                                "id": str(datetime.now().timestamp()),
                                "timestamp": datetime.now().strftime("%H:%M:%S"),
                                "type": "trade",
                                "message": msg_execucao_mercado
                            })
                            
                            await broadcast_to_frontend({
                                "type": "trade",
                                "marker": {
                                    "time": timestamp_atual,
                                    "position": 'belowBar' if decisao == 'BUY' else 'aboveBar',
                                    "color": '#10b981' if decisao == 'BUY' else '#ef4444',
                                    "shape": 'arrowUp' if decisao == 'BUY' else 'arrowDown',
                                    "text": f"{decisao} {nova_relevancia}★"
                                }
                            })
                        else:
                            await log_to_supabase(profile_id, "error", f"Falha ao executar ordem {decisao} para {ativo}.")

                # Broadcast para painel
                log_msg = f"Relevância: {nova_relevancia}★ | Ativo: {ativo} | Decisão: {decisao}\nMotivo: {motivo}\nLatência: {tempo_ia:.2f}s"
                await broadcast_to_frontend({
                    "id": str(datetime.now().timestamp()),
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "type": "ai_analysis",
                    "message": log_msg,
                    "relevancia": nova_relevancia
                })

            # Aguarda 1 segundo antes de iterar o loop (Para não travar a CPU)
            await asyncio.sleep(1)

        except Exception as e:
            print(f"Erro no loop principal: {e}")
            await asyncio.sleep(5)

async def atualizar_grafico_full():
    """Tarefa que envia o histórico de candles completo (Foco em M1)."""
    while True:
        try:
            from main import current_symbol
            df_micro = mt5_service.obter_dados_mercado(current_symbol, mt5.TIMEFRAME_M1, 100)
            if df_micro is not None and not df_micro.empty:
                candles_list = []
                for _, row in df_micro.iterrows():
                    candles_list.append({
                        "time": int(row['time'].timestamp() if hasattr(row['time'], 'timestamp') else pd.to_datetime(row['time']).timestamp()),
                        "open": float(row['open']), "high": float(row['high']),
                        "low": float(row['low']), "close": float(row['close'])
                    })
                await broadcast_to_frontend({"type": "market_data", "candles": candles_list})
            await asyncio.sleep(15) # Atualiza o gráfico a cada 15s
        except Exception as e:
            await asyncio.sleep(5)

async def monitor_tick_data():
    """Tarefa GAME MODE: Envia apenas a variação do preço a cada 0.5s dinamicamente."""
    while True:
        try:
            from main import current_symbol
            tick = mt5.symbol_info_tick(current_symbol)
            if tick:
                preco_atual = tick.last if tick.last != 0 else tick.bid
                await broadcast_to_frontend({
                    "type": "market_data",
                    "tick": {"price": float(preco_atual)}
                })
            await asyncio.sleep(0.5)
        except Exception as e:
            await asyncio.sleep(1)

if __name__ == "__main__":
    async def main():
        from main import current_symbol
        print(f"--- SISTEMA INICIADO: MODO MICRO-SCALPING (15s) ---")
        print(f"Ativo de Foco Inicial: {current_symbol}")
        await asyncio.gather(
            trading_loop(),
            atualizar_grafico_full(), 
            monitor_tick_data()        
        )

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Saindo e encerrando MT5...")
        mt5.shutdown()
