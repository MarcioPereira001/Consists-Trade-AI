import os
import asyncio
import json
import httpx
import requests
import time as time_lib
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
import MetaTrader5 as mt5
import pandas as pd

from mt5_service import MT5Service
from ai_service import AITrader

load_dotenv()

def capturar_dados_triplos(symbol):
    # Aumentamos para 100 candles de M1 para ver micro-tendências e exaustão
    rates_m1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 100)
    rates_m2 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M2, 0, 50)
    rates_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 60) # Aumentado para 60 para a IA ter o histórico correto na foto
    rates_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 15)

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
    """Envia os dados em tempo real para o servidor WebSocket repassar ao Painel Web (Assíncrono)."""
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://127.0.0.1:8000/api/broadcast_log", json=message, timeout=2.0)
    except Exception:
        pass 

async def trading_loop():
    """Loop principal com FORÇA TOTAL na leitura do Banco de Dados."""
    print("Iniciando Trading Loop (Motor Executor Híbrido)...")
    
    if not mt5_service.conectar():
        print("❌ ERRO CRÍTICO: Verifique se o MT5 da Genial/Corretora está aberto e se o .env está correto.")
        return

    cached_configs = None
    last_config_time = 0
    ultimo_minuto_ia = -1 # Controle do ciclo de 60s

    while True:
        try:
            import main
            agora_ts = time_lib.time()
            
            # 1. Buscar configurações REAIS do Supabase (Otimizado com Cache)
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
                ativo_banco = config.get('ativo', 'BITG26')
                
                # --- A BALA DE PRATA: CRIA A VARIÁVEL QUE FALTAVA ---
                ativo = ativo_banco
                symbol = ativo_banco 
                
                # --- FORÇA A SINCRONIZAÇÃO COM O FRONTEND ---
                import main
                main.current_symbol = ativo 
                
                # VARIÁVEIS DE EXECUÇÃO ORIGINAIS
                lote = float(config.get('lote', 1.0))
                sl_pts = int(config.get('stop_loss', 100))
                tp_pts = int(config.get('take_profit', 200))
                estrategia = config.get('estrategia_ativa', 'Adaptável (Camaleão / Dinâmica)')
                horario_inicio = config.get('horario_inicio', '09:00')
                horario_fim = config.get('horario_fim', '17:30')
                ambiente = config.get('ambiente', 'AO VIVO')

                # --- NOVAS VARIÁVEIS DE INTELIGÊNCIA IA ---
                trailing_stop_auto = config.get('trailing_stop_auto', True)
                auto_decisao_ia = config.get('auto_decisao_ia', False)
                agressividade = config.get('agressividade', 'SCALPER')
                
                # --- TRAVA INQUEBRÁVEL DE GESTÃO DE RISCO ---
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

                # 3. Puxar dados do MT5 (Fractal M1, M5, M15 + Ontem)
                pacote_dados = capturar_dados_triplos(ativo)

                if pacote_dados["m1"] is None or pacote_dados["m1"].empty:
                    continue

                df_micro = pacote_dados["m1"]
                preco_atual_log = float(df_micro.iloc[-1]['close']) # Tick atual (Vivo)
                preco_fechamento_anterior = float(df_micro.iloc[-2]['close']) # Fechamento da última vela
                preco_abertura_anterior = float(df_micro.iloc[-2]['open']) # Abertura da última vela (Para saber a cor)
                preco_maxima_anterior = float(df_micro.iloc[-2]['high'])
                preco_minima_anterior = float(df_micro.iloc[-2]['low'])
                timestamp_atual = int(df_micro.iloc[-1]['time'].timestamp() if hasattr(df_micro.iloc[-1]['time'], 'timestamp') else df_micro.iloc[-1]['time'])
                
                atr_atual = df_micro['atr_14'].iloc[-1] if 'atr_14' in df_micro.columns else 0

                # --- CÁLCULO DE SL E TP DINÂMICOS (BASEADO NO ATR) ---
                symbol_info = mt5.symbol_info(ativo)
                point = symbol_info.point if symbol_info else 1.0
                
                if atr_atual > 0 and point > 0:
                    atr_pts = atr_atual / point
                    sl_dinamico_pts = int(atr_pts * 1.5)
                    tp_dinamico_pts = int(atr_pts * 2.0)
                else:
                    sl_dinamico_pts = sl_pts
                    tp_dinamico_pts = tp_pts

                # --- PROTEÇÃO DINÂMICA CONTRA ERRO 10016 ---
                # Usa o maior valor entre o SL fixo (banco) e o SL dinâmico (ATR) para garantir proteção
                sl_real = max(sl_pts, sl_dinamico_pts)
                tp_real = max(tp_pts, tp_dinamico_pts)
                
                if 'BIT' in ativo.upper():
                    sl_real = max(sl_real, 1500) 
                    tp_real = max(tp_real, 3000)

                # ======================================================================
                # MÓDULO EXECUTOR (LATÊNCIA ZERO): EXECUÇÃO DE ARMADILHA
                # ======================================================================
                armadilha = memoria_ordem_programada.get(profile_id, {"acao": "NONE"})
                
                if armadilha.get("acao") in ["BUY", "SELL"] and not mt5_service.tem_posicao_aberta(ativo):
                    # Checagem de Timeout (15 minutos de validade)
                    timestamp_armadilha = armadilha.get("timestamp", time_lib.time())
                    idade_armadilha = time_lib.time() - timestamp_armadilha
                    
                    if idade_armadilha > 900: # 900 segundos = 15 minutos
                        print(f"[{ativo}] ⏰ Armadilha de {armadilha['acao']} expirou (Timeout > 15m). Desarmando.")
                        memoria_ordem_programada[profile_id] = {"acao": "NONE"}
                    else:
                        acao_armada = armadilha["acao"]
                        gatilho = float(armadilha.get("preco_gatilho", 0))
                        
                        print(f"[{ativo}] Monitorando Armadilha {acao_armada} no gatilho {gatilho}. Fechamento Anterior: {preco_fechamento_anterior}")
                        
                        # Checa a Autenticação em 2 Fatores (Rompimento Confirmado)
                        ordem_disparada = False
                        
                        if acao_armada == "BUY":
                            # Lógica 1: Rompimento (Preço abriu abaixo/no gatilho e fechou acima com força)
                            rompimento_buy = (preco_abertura_anterior <= gatilho and preco_fechamento_anterior > gatilho)
                            # Lógica 2: Pullback (Preço tocou no suporte/gatilho e rejeitou formando vela verde)
                            pullback_buy = (preco_minima_anterior <= gatilho and preco_fechamento_anterior > preco_abertura_anterior)
                            
                            if rompimento_buy or pullback_buy:
                                print(f"🔥 ARMADILHA CONFIRMADA: Gatilho {gatilho} acionado (Rompimento: {rompimento_buy} | Pullback: {pullback_buy}). BUY!")
                                ordem_disparada = True
                                
                        elif acao_armada == "SELL":
                            # Lógica 1: Rompimento (Preço abriu acima/no gatilho e fechou abaixo com força)
                            rompimento_sell = (preco_abertura_anterior >= gatilho and preco_fechamento_anterior < gatilho)
                            # Lógica 2: Pullback (Preço tocou na resistência/gatilho e rejeitou formando vela vermelha)
                            pullback_sell = (preco_maxima_anterior >= gatilho and preco_fechamento_anterior < preco_abertura_anterior)
                            
                            if rompimento_sell or pullback_sell:
                                print(f"🔥 ARMADILHA CONFIRMADA: Gatilho {gatilho} acionado (Rompimento: {rompimento_sell} | Pullback: {pullback_sell}). SELL!")
                                ordem_disparada = True

                    if ordem_disparada:
                        if ambiente == 'REPLAY HISTÓRICO':
                            resultado = mt5_service.simular_ordem_paper_trading(ativo, acao_armada, preco_atual_log, armadilha.get("motivo_gatilho", "Rompimento"))
                        else:
                            resultado = mt5_service.enviar_ordem(ativo, acao_armada, lote, sl_real, tp_real)
                        
                        # Limpa a armadilha após atirar para não atirar duplicado
                        memoria_ordem_programada[profile_id] = {"acao": "NONE"}
                        
                        if resultado:
                            motivo_detalhado = armadilha.get("motivo_ia", "Motivo não registrado.")
                            msg_execucao = f"[{ativo}] 🎯 ARMADILHA {acao_armada} ACIONADA no preço {preco_atual_log}!\n🧠 Raciocínio da IA: {motivo_detalhado}"
                            
                            await broadcast_to_frontend({
                                "id": str(datetime.now().timestamp()),
                                "timestamp": datetime.now().strftime("%H:%M:%S"),
                                "type": "trade",
                                "message": msg_execucao
                            })
                            
                            await broadcast_to_frontend({
                                "type": "trade",
                                "marker": {
                                    "time": timestamp_atual,
                                    "position": 'belowBar' if acao_armada == 'BUY' else 'aboveBar',
                                    "color": '#10b981' if acao_armada == 'BUY' else '#ef4444',
                                    "shape": 'arrowUp' if acao_armada == 'BUY' else 'arrowDown',
                                    "text": f"{acao_armada} [ARMADILHA]"
                                }
                            })
                        continue # Pula o resto do loop para não sobrecarregar a IA após atirar

                # 2.5 Verificar se já estamos posicionados (Trava Sniper)
                if ambiente != 'REPLAY HISTÓRICO' and mt5_service.tem_posicao_aberta(ativo):
                    print(f"[{ativo}] Posicionado. Monitorando Trailing Stop...")
                    await asyncio.sleep(10)
                    continue

                # ======================================================================
                # MÓDULO ANALISTA (IA): LEITURA DE FOTOS A CADA 5 MINUTOS E TEXTO A CADA 1 MINUTO
                # ======================================================================
                minuto_atual = datetime.now().minute
                
                # CICLO DE 15 SEGUNDOS: Monitora Armadilhas e Fast-Exit (Scalper)
                if minuto_atual == ultimo_minuto_ia:
                    # --- LÓGICA DE FAST-EXIT (MODO SCALPER) ---
                    # Se estamos posicionados e a IA ativou o modo Scalper, monitoramos a exaustão
                    if ambiente != 'REPLAY HISTÓRICO' and mt5_service.tem_posicao_aberta(ativo):
                        estado_ia = memoria_estado_ia.get(profile_id, "")
                        if "SCALPER_MODE" in estado_ia:
                            # Pega o último RSI/Stoch do M1
                            rsi_atual = pacote_dados["m1"]['rsi_14'].iloc[-1]
                            stoch_k = pacote_dados["m1"]['stoch_k'].iloc[-1]
                            
                            # Verifica o tipo de posição aberta
                            posicoes = mt5.positions_get(symbol=ativo)
                            if posicoes:
                                pos = posicoes[0]
                                tipo_pos = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                                
                                # Regra de Saída Rápida: Reversão do Indicador
                                # Se comprou na sobrevenda (<30) e o RSI cruzou pra cima de 50 (ou Stoch > 80)
                                if tipo_pos == "BUY" and (rsi_atual > 60 or stoch_k > 80):
                                    print(f"⚡ FAST-EXIT SCALPER: Fechando COMPRA. RSI: {rsi_atual:.1f} | Stoch: {stoch_k:.1f}")
                                    # Envia ordem contrária para fechar
                                    mt5_service.enviar_ordem(ativo, "SELL", pos.volume, 0, 0)
                                    await broadcast_to_frontend({
                                        "id": str(datetime.now().timestamp()),
                                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                                        "type": "trade",
                                        "message": f"[{ativo}] ⚡ FAST-EXIT (Scalper): Posição de COMPRA encerrada por reversão de indicador (RSI: {rsi_atual:.1f})."
                                    })
                                
                                # Se vendeu na sobrecompra (>70) e o RSI cruzou pra baixo de 50 (ou Stoch < 20)
                                elif tipo_pos == "SELL" and (rsi_atual < 40 or stoch_k < 20):
                                    print(f"⚡ FAST-EXIT SCALPER: Fechando VENDA. RSI: {rsi_atual:.1f} | Stoch: {stoch_k:.1f}")
                                    # Envia ordem contrária para fechar
                                    mt5_service.enviar_ordem(ativo, "BUY", pos.volume, 0, 0)
                                    await broadcast_to_frontend({
                                        "id": str(datetime.now().timestamp()),
                                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                                        "type": "trade",
                                        "message": f"[{ativo}] ⚡ FAST-EXIT (Scalper): Posição de VENDA encerrada por reversão de indicador (RSI: {rsi_atual:.1f})."
                                    })

                    # Apenas avisa o frontend que está vivo e monitorando
                    await broadcast_to_frontend({
                        "id": str(datetime.now().timestamp()),
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "type": "info",
                        "message": f"[{ativo}] Monitorando armadilhas e trailing stops... (Aguardando fechamento do candle M1)"
                    })
                    await asyncio.sleep(15)
                    continue
                
                # CICLO DE 60 SEGUNDOS: Chama a IA
                ultimo_minuto_ia = minuto_atual
                
                dados_ontem = mt5_service.obter_ohlc_ontem(ativo) or {}
                relevancia_anterior = memoria_relevancia.get(profile_id, 1)
                estado_anterior_ia = memoria_estado_ia.get(profile_id, "Iniciando...")
                
                # Controle Inteligente de Visão Computacional (Economiza Latência)
                enviar_fotos = (minuto_atual % 5 == 0) # Gera foto nos minutos: 0, 5, 10, 15, 20...
                
                caminho_foto_m5, caminho_foto_m1 = None, None
                if enviar_fotos:
                    print(f"📸 Ciclo de 5 Minutos. Gerando imagens visuais para a IA...")
                    # Correção: Passando os argumentos posicionais corretamente
                    caminho_foto_m5 = mt5_service.capturar_imagem_grafico(pacote_dados["m5"], ativo, "chart_m5.png", "M5")
                    caminho_foto_m1 = mt5_service.capturar_imagem_grafico(pacote_dados["m1"], ativo, "chart_m1.png", "M1")
                else:
                    print(f"⚡ Ciclo Rápido. IA lendo apenas dados de texto...")

                # Medidor de Latência da IA
                start_time = time_lib.time()
                
                # Obtém o status da posição atual para passar para a IA
                posicao_aberta = None
                if ambiente != 'REPLAY HISTÓRICO':
                    posicoes = mt5.positions_get(symbol=ativo)
                    if posicoes:
                        pos = posicoes[0]
                        posicao_aberta = {
                            "type": "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL",
                            "price_open": pos.price_open,
                            "profit": pos.profit
                        }
                
                analise = ai_trader.analisar_mercado(
                    dados_macro_df=pacote_dados["m15"], 
                    dados_micro_df=pacote_dados,       
                    estrategia=estrategia, 
                    relevancia_anterior=relevancia_anterior,
                    dados_ontem=dados_ontem,
                    estado_anterior=estado_anterior_ia,
                    image_path_m1=caminho_foto_m1, 
                    image_path_m5=caminho_foto_m5,
                    posicao_aberta=posicao_aberta
                )
                
                tempo_ia = time_lib.time() - start_time
                
                nova_relevancia = analise.get('relevancia', 1)
                memoria_relevancia[profile_id] = nova_relevancia
                memoria_estado_ia[profile_id] = analise.get('estado_operacional', analise.get('motivo', ''))

                # Armazena nova armadilha que a IA definir
                nova_armadilha = analise.get('ordem_programada', {"acao": "NONE"})
                nova_armadilha["motivo_ia"] = analise.get('motivo', 'Motivo não especificado.')

                # Salva o Timestamp para o Timeout apenas se a armadilha for válida (Com Trava Anti-Alucinação)
                if nova_armadilha.get("acao") != "NONE":
                    gatilho_ia = float(nova_armadilha.get("preco_gatilho", 0))
                    acao_ia = nova_armadilha.get("acao")
                    
                    # Sanitização: O gatilho não pode estar a mais de 1.5% de distância do preço atual
                    distancia_percentual = abs(gatilho_ia - preco_atual_log) / preco_atual_log if preco_atual_log > 0 else 1
                    
                    # TRAVA DE AÇO MATEMÁTICA: BUY Stop deve ser > Preço Atual | SELL Stop deve ser < Preço Atual
                    direcao_invalida = (acao_ia == "BUY" and gatilho_ia <= preco_atual_log) or \
                                       (acao_ia == "SELL" and gatilho_ia >= preco_atual_log)
                    
                    if distancia_percentual > 0.015 or gatilho_ia <= 0 or direcao_invalida:
                        print(f"⚠️ [ANTI-ALUCINAÇÃO] Gatilho ignorado ({gatilho_ia} para {acao_ia}). Distância irreal ou direção inválida (Preço Atual: {preco_atual_log}).")
                        nova_armadilha = {"acao": "NONE"}
                    else:
                        nova_armadilha["timestamp"] = time_lib.time()
                        nova_armadilha["preco_gatilho"] = gatilho_ia # Garante que é float
                    
                memoria_ordem_programada[profile_id] = nova_armadilha

                decisao = analise.get('decisao', 'WAIT')
                motivo = analise.get('motivo', 'Sem motivo')
                estrategia_escolhida = analise.get('estrategia_escolhida', estrategia)

                # Log Silencioso para Notícias
                if "BLOQUEIO: Notícia" in motivo:
                    if minuto_atual % 5 == 0:
                        print(f"🛑 [PAUSA DE NOTÍCIA] {motivo}")
                else:
                    print(f"IA [{nova_relevancia}★] [Preço: {preco_atual_log}] [Delay: {tempo_ia:.2f}s]: {decisao} | {motivo}")
                    
                if nova_armadilha.get("acao") != "NONE":
                    print(f"   🎯 ARMADILHA CONFIGURADA: {nova_armadilha['acao']} no rompimento/fechamento de {nova_armadilha['preco_gatilho']}")
                else:
                    print(f"   ↳ Memória da IA: {estado_anterior_ia}")

                # 5. EXECUTAR ORDEM IMEDIATA SE A IA MANDAR A MERCADO
                if decisao in ['BUY', 'SELL']:

                    if agressividade == 'SNIPER' and nova_relevancia < 5:
                        print(f"Sinal {decisao} rejeitado (Filtro SNIPER).")
                    elif agressividade == 'SCALPER' and nova_relevancia < 4:
                        print(f"Sinal {decisao} rejeitado (Filtro SCALPER).")
                    else:
                        # Executa de fato
                        if ambiente == 'REPLAY HISTÓRICO':
                            print(f"[MODO REPLAY] Simulando ordem {decisao} para {ativo} (Paper Trading)...")
                            resultado = mt5_service.simular_ordem_paper_trading(ativo, decisao, preco_atual_log, motivo)
                        else:
                            print(f"[MODO AO VIVO] Executando ordem REAL {decisao} para {ativo}...")
                            resultado = mt5_service.enviar_ordem(ativo, decisao, lote, sl_real, tp_real)
                        
                        if resultado:
                            tag = "[SIMULAÇÃO] " if ambiente == 'REPLAY HISTÓRICO' else ""
                            await log_to_supabase(profile_id, "trade", f"{tag}Ordem {decisao} via {estrategia_escolhida}")
                            await save_trade_history(profile_id, resultado.order, ativo, decisao, resultado.price, motivo)
                            
                            msg_execucao_mercado = f"[{ativo}] ⚡ ORDEM A MERCADO {decisao} EXECUTADA!\n🧠 Raciocínio da IA: {motivo}"
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
                            
                elif decisao == 'BREAKEVEN' and posicao_aberta:
                    if ambiente != 'REPLAY HISTÓRICO':
                        # Lógica para mover o Stop Loss para o preço de entrada (Breakeven)
                        try:
                            posicoes = mt5.positions_get(symbol=ativo)
                            if posicoes:
                                pos = posicoes[0]
                                preco_entrada = pos.price_open
                                sl_atual = pos.sl
                                
                                # Só ajusta se o SL atual for diferente da entrada
                                if abs(sl_atual - preco_entrada) > 0.00001: 
                                    request = {
                                        "action": mt5.TRADE_ACTION_SLTP,
                                        "symbol": ativo,
                                        "sl": preco_entrada,
                                        "tp": pos.tp,
                                        "position": pos.ticket
                                    }
                                    result = mt5.order_send(request)
                                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                                        print(f"🛡️ BREAKEVEN ACIONADO: Stop Loss movido para a entrada ({preco_entrada}).")
                                        await broadcast_to_frontend({
                                            "id": str(datetime.now().timestamp()),
                                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                                            "type": "trade",
                                            "message": f"[{ativo}] 🛡️ BREAKEVEN ACIONADO: Stop Loss movido para o preço de entrada ({preco_entrada}). Risco zero."
                                        })
                                    else:
                                        print(f"⚠️ Falha ao mover para Breakeven: {result.comment}")
                        except Exception as e:
                            print(f"Erro ao aplicar Breakeven: {e}")
                            
                elif decisao == 'HOLD' and posicao_aberta:
                    print(f"[{ativo}] ⏳ HOLD: IA decidiu manter a posição atual aberta. Lucro atual: {posicao_aberta['profit']}")

                # Broadcast para painel
                log_msg = f"Relevância: {nova_relevancia}★ | Ativo: {ativo} | Decisão: {decisao}\nMotivo: {motivo}\nLatência: {tempo_ia:.2f}s"
                await broadcast_to_frontend({
                    "id": str(datetime.now().timestamp()),
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "type": "ai_analysis",
                    "message": log_msg,
                    "estudos_visuais": analise.get('estudos_visuais', {}),
                    "relevancia": nova_relevancia,
                    "armadilha": nova_armadilha
                })

            # Aguarda o próximo ciclo (15 segundos é ideal para micro-tendências)
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