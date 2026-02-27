import os
import asyncio
import json
import requests
import time as time_lib
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
import MetaTrader5 as mt5

from mt5_service import MT5Service
from ai_service import AITrader

load_dotenv()

def capturar_dados_triplos(symbol):
    # Aumentamos para 100 candles de M1 para ver micro-tendências e exaustão
    rates_m1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 100)
    rates_m2 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M2, 0, 50)
    rates_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 20)
    rates_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 15)

    import pandas as pd
    return {
        "m1": pd.DataFrame(rates_m1) if rates_m1 is not None else None,
        "m2": pd.DataFrame(rates_m2) if rates_m2 is not None else None,
        "m5": pd.DataFrame(rates_m5) if rates_m5 is not None else None,
        "m15": pd.DataFrame(rates_m15) if rates_m15 is not None else None
    }

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
# NOVO: Memória de Armadilhas (Ordens Programadas pela IA)
memoria_ordem_programada = {}

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
        requests.post("http://127.0.0.1:8000/api/broadcast_log", json=message, timeout=2)
    except Exception:
        pass 

async def trading_loop():
    """Loop principal com FORÇA TOTAL na leitura do Banco de Dados."""
    print("Iniciando Trading Loop (Motor Executor Híbrido)...")
    
    if not mt5_service.conectar():
        print("❌ ERRO CRÍTICO: Verifique se o MT5 da Genial está aberto e se o .env está correto.")
        return

    while True:
        try:
            # 1. Buscar configurações REAIS do Supabase
            response = supabase.table('trade_configs').select('*').execute()
            configs = response.data
            
            if not configs:
                await asyncio.sleep(10)
                continue

            for config in configs:
                profile_id = config.get('profile_id')
                ativo_banco = config.get('ativo', 'BITG26')
                
                # --- FORÇA A SINCRONIZAÇÃO COM O FRONTEND ---
                import main
                main.current_symbol = ativo_banco 
                
                # VARIÁVEIS DE EXECUÇÃO ORIGINAIS
                lote = float(config.get('lote', 1.0))
                sl_pts = int(config.get('stop_loss', 100))
                tp_pts = int(config.get('take_profit', 200))
                estrategia = config.get('estrategia_ativa', 'Adaptável (Camaleão / Dinâmica)')
                horario_inicio = config.get('horario_inicio', '09:00')
                horario_fim = config.get('horario_fim', '17:30')

                # --- NOVAS VARIÁVEIS DE INTELIGÊNCIA IA ---
                trailing_stop_auto = config.get('trailing_stop_auto', True)
                auto_decisao_ia = config.get('auto_decisao_ia', False)
                agressividade = config.get('agressividade', 'SCALPER')
                
                # --- TRAVA INQUEBRÁVEL DE GESTÃO DE RISCO ---
                meta_diaria = float(config.get('meta_diaria', 500.0))
                limite_perda = float(config.get('limite_perda', -250.0))
                
                resultado_atual = mt5_service.obter_resultado_diario()
                
                if resultado_atual >= meta_diaria:
                    print(f"[{ativo_banco}] META ALCANÇADA: R$ {resultado_atual:.2f}. Hibernando.")
                    continue
                
                if resultado_atual <= limite_perda:
                    print(f"[{ativo_banco}] LIMITE DE PERDA ATINGIDO: R$ {resultado_atual:.2f}. Travado.")
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
                    print(f"[{ativo_banco}] Fora da janela operacional ({horario_inicio} às {horario_fim}).")
                    continue

                # 3. Puxar dados do MT5 (Fractal M1, M5, M15 + Ontem)
                pacote_dados = capturar_dados_triplos(ativo_banco)

                if pacote_dados["m1"] is None or pacote_dados["m1"].empty:
                    continue

                df_micro = pacote_dados["m1"]
                preco_atual_log = float(df_micro.iloc[-1]['close']) # Tick atual (Vivo)
                preco_fechamento_anterior = float(df_micro.iloc[-2]['close']) # Fechamento da última vela
                preco_abertura_anterior = float(df_micro.iloc[-2]['open']) # Abertura da última vela (Para saber a cor)

                # --- PROTEÇÃO DINÂMICA CONTRA ERRO 10016 (MOVIDO PARA CIMA) ---
                sl_real = sl_pts
                tp_real = tp_pts
                if 'BIT' in ativo_banco.upper():
                    sl_real = max(sl_pts, 1500) 
                    tp_real = max(tp_pts, 3000)

                # ======================================================================
                # MÓDULO EXECUTOR (LATÊNCIA ZERO): EXECUÇÃO DE ARMADILHA
                # ======================================================================
                armadilha = memoria_ordem_programada.get(profile_id, {"acao": "NONE"})
                ambiente = config.get('ambiente', 'AO VIVO')
                
                if armadilha.get("acao") in ["BUY", "SELL"] and not mt5_service.tem_posicao_aberta(ativo_banco):
                    # Checagem de Timeout (15 minutos de validade)
                    timestamp_armadilha = armadilha.get("timestamp", time_lib.time())
                    idade_armadilha = time_lib.time() - timestamp_armadilha
                    
                    if idade_armadilha > 900: # 900 segundos = 15 minutos
                        print(f"[{ativo_banco}] ⏰ Armadilha de {armadilha['acao']} expirou (Timeout > 15m). Desarmando.")
                        memoria_ordem_programada[profile_id] = {"acao": "NONE"}
                    else:
                        acao_armada = armadilha["acao"]
                        gatilho = float(armadilha.get("preco_gatilho", 0))
                        
                        print(f"[{ativo_banco}] Monitorando Armadilha {acao_armada} no gatilho {gatilho}. Fechamento Anterior: {preco_fechamento_anterior}")
                        
                        # Checa a Autenticação em 2 Fatores (Rompimento Confirmado)
                        ordem_disparada = False
                        
                        if acao_armada == "BUY":
                            # 1. Fechou acima do gatilho? | 2. Vela de força (Verde: Fechamento > Abertura)?
                            if (preco_fechamento_anterior > gatilho and 
                                preco_fechamento_anterior > preco_abertura_anterior):
                                print(f"🔥 ARMADILHA CONFIRMADA: Rompimento real de {gatilho} com força compradora sustentada. BUY!")
                                ordem_disparada = True
                                
                        elif acao_armada == "SELL":
                            # 1. Fechou abaixo do gatilho? | 2. Vela de força (Vermelha: Fechamento < Abertura)?
                            if (preco_fechamento_anterior < gatilho and 
                                preco_fechamento_anterior < preco_abertura_anterior):
                                print(f"🔥 ARMADILHA CONFIRMADA: Rompimento real de {gatilho} com força vendedora sustentada. SELL!")
                                ordem_disparada = True

                    if ordem_disparada:
                        if ambiente == 'REPLAY HISTÓRICO':
                            resultado = mt5_service.simular_ordem_paper_trading(ativo_banco, acao_armada, preco_atual_log, armadilha.get("motivo_gatilho", "Rompimento"))
                        else:
                            resultado = mt5_service.enviar_ordem(ativo_banco, acao_armada, lote, sl_real, tp_real)
                        
                        # Limpa a armadilha após atirar para não atirar duplicado
                        memoria_ordem_programada[profile_id] = {"acao": "NONE"}
                        
                        if resultado:
                            await broadcast_to_frontend({
                                "type": "trade",
                                "marker": {
                                    "time": int(df_micro.iloc[-1]['time']),
                                    "position": 'belowBar' if acao_armada == 'BUY' else 'aboveBar',
                                    "color": '#10b981' if acao_armada == 'BUY' else '#ef4444',
                                    "shape": 'arrowUp' if acao_armada == 'BUY' else 'arrowDown',
                                    "text": f"{acao_armada} [ARMADILHA]"
                                }
                            })
                        continue # Pula o resto do loop para não sobrecarregar a IA após atirar

                # 2.5 Verificar se já estamos posicionados (Trava Sniper)
                if ambiente != 'REPLAY HISTÓRICO' and mt5_service.tem_posicao_aberta(ativo_banco):
                    print(f"[{ativo_banco}] Posicionado. Monitorando Trailing Stop...")
                    await asyncio.sleep(10)
                    continue

                # ======================================================================
                # MÓDULO ANALISTA (IA): LEITURA DE FOTOS A CADA 5 MINUTOS
                # ======================================================================
                dados_ontem = mt5_service.obter_ohlc_ontem(ativo_banco) or {}
                relevancia_anterior = memoria_relevancia.get(profile_id, 1)
                estado_anterior_ia = memoria_estado_ia.get(profile_id, "Iniciando...")
                
                # Controle Inteligente de Visão Computacional (Economiza Latência)
                minuto_atual = datetime.now().minute
                enviar_fotos = (minuto_atual % 5 == 0) # Gera foto nos minutos: 0, 5, 10, 15, 20...
                
                caminho_foto_m5, caminho_foto_m1 = None, None
                if enviar_fotos:
                    print(f"📸 Ciclo de 5 Minutos. Gerando imagens visuais para a IA...")
                    caminho_foto_m5 = mt5_service.capturar_imagem_grafico(df_m5=pacote_dados["m5"], symbol=ativo_banco, filename="chart_m5.png")
                    caminho_foto_m1 = mt5_service.capturar_imagem_grafico(df_m5=pacote_dados["m1"], symbol=ativo_banco, filename="chart_m1.png")
                else:
                    print(f"⚡ Ciclo Rápido. IA lendo apenas dados de texto...")

                # Medidor de Latência da IA
                start_time = time_lib.time()
                
                analise = ai_trader.analisar_mercado(
                    dados_macro_df=pacote_dados["m15"], 
                    dados_micro_df=pacote_dados,       
                    estrategia=estrategia, 
                    relevancia_anterior=relevancia_anterior,
                    dados_ontem=dados_ontem,
                    estado_anterior=estado_anterior_ia,
                    image_path_m1=caminho_foto_m1, 
                    image_path_m5=caminho_foto_m5  
                )
                
                tempo_ia = time_lib.time() - start_time
                
                nova_relevancia = analise.get('relevancia', 1)
                memoria_relevancia[profile_id] = nova_relevancia
                memoria_estado_ia[profile_id] = analise.get('estado_operacional', analise.get('motivo', ''))

                # Armazena nova armadilha que a IA definir
                nova_armadilha = analise.get('ordem_programada', {"acao": "NONE"})
                
                # --- TRAVA ANTI-ALUCINAÇÃO (GATILHO INVERTIDO) ---
                if nova_armadilha.get("acao") == "BUY" and float(nova_armadilha.get("preco_gatilho", 0)) <= preco_atual_log:
                    print(f"⚠️ Alucinação da IA Bloqueada: Tentou armar BUY em {nova_armadilha.get('preco_gatilho')} com o preço já acima em {preco_atual_log}.")
                    nova_armadilha = {"acao": "NONE"}
                elif nova_armadilha.get("acao") == "SELL" and float(nova_armadilha.get("preco_gatilho", 0)) >= preco_atual_log:
                    print(f"⚠️ Alucinação da IA Bloqueada: Tentou armar SELL em {nova_armadilha.get('preco_gatilho')} com o preço já abaixo em {preco_atual_log}.")
                    nova_armadilha = {"acao": "NONE"}

                # Salva o Timestamp para o Timeout apenas se a armadilha for válida
                if nova_armadilha.get("acao") != "NONE":
                    nova_armadilha["timestamp"] = time_lib.time()
                    
                memoria_ordem_programada[profile_id] = nova_armadilha

                decisao = analise.get('decisao', 'WAIT')
                motivo = analise.get('motivo', 'Sem motivo')
                estrategia_escolhida = analise.get('estrategia_escolhida', estrategia) # <-- LINHA NOVA

                print(f"IA [{nova_relevancia}★] [Preço: {preco_atual_log}] [Delay: {tempo_ia:.2f}s]: {decisao} | {motivo}")
                if nova_armadilha.get("acao") != "NONE":
                    print(f"   🎯 ARMADILHA CONFIGURADA: {nova_armadilha['acao']} no rompimento/fechamento de {nova_armadilha['preco_gatilho']}")
                else:
                    print(f"   ↳ Memória da IA: {estado_anterior_ia}")

                # 5. EXECUTAR ORDEM IMEDIATA SE A IA MANDAR A MERCADO
                if decisao in ['BUY', 'SELL']:
                    if agressividade == 'SNIPER' and nova_relevancia < 5:
                        print(f"Sinal {decisao} rejeitado (Filtro SNIPER).")
                        continue
                    elif agressividade == 'SCALPER' and nova_relevancia < 4:
                        print(f"Sinal {decisao} rejeitado (Filtro SCALPER).")
                        continue

                    if ambiente == 'REPLAY HISTÓRICO':
                        resultado = mt5_service.simular_ordem_paper_trading(ativo_banco, decisao, preco_atual_log, motivo)
                    else:
                        resultado = mt5_service.enviar_ordem(ativo_banco, decisao, lote, sl_real, tp_real)
                    
                    if resultado:
                        tag = "[SIMULAÇÃO] " if ambiente == 'REPLAY HISTÓRICO' else ""
                        await log_to_supabase(profile_id, "trade", f"{tag}Ordem {decisao} via {estrategia_escolhida}")
                        await save_trade_history(profile_id, resultado.order, ativo_banco, decisao, resultado.price, motivo)
                        
                        await broadcast_to_frontend({
                            "type": "trade",
                            "marker": {
                                "time": int(df_micro.iloc[-1]['time']),
                                "position": 'belowBar' if decisao == 'BUY' else 'aboveBar',
                                "color": '#10b981' if decisao == 'BUY' else '#ef4444',
                                "shape": 'arrowUp' if decisao == 'BUY' else 'arrowDown',
                                "text": f"{decisao} {nova_relevancia}★"
                            }
                        })

                # Broadcast para painel
                log_msg = f"Relevância: {nova_relevancia}★ | Ativo: {ativo_banco} | Decisão: {decisao}\nMotivo: {motivo}\nLatência: {tempo_ia:.2f}s"
                await broadcast_to_frontend({
                    "id": str(datetime.now().timestamp()),
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "type": "ai_analysis",
                    "message": log_msg,
                    "estudos_visuais": analise.get('estudos_visuais', {}),
                    "relevancia": nova_relevancia
                })

            # Loop a cada 15 segundos para pegar o fechamento com precisão
            await asyncio.sleep(15)

        except Exception as e:
            print(f"Erro no loop principal: {e}")
            await asyncio.sleep(10)

async def atualizar_grafico_full():
    """Tarefa que envia o histórico de candles completo (Foco em M5)."""
    while True:
        try:
            from main import current_symbol
            df_micro = mt5_service.obter_dados_mercado(current_symbol, mt5.TIMEFRAME_M5, 100)
            if df_micro is not None and not df_micro.empty:
                candles_list = []
                for _, row in df_micro.iterrows():
                    candles_list.append({
                        "time": int(row['time'].timestamp()),
                        "open": float(row['open']), "high": float(row['high']),
                        "low": float(row['low']), "close": float(row['close'])
                    })
                await broadcast_to_frontend({"type": "market_data", "candles": candles_list})
            await asyncio.sleep(30)
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
        print(f"--- SISTEMA INICIADO: MODO MULTI-TASKING ROBUSTO ---")
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