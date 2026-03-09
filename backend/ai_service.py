import os
import json
import numpy as np
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from PIL import Image # NOVO: Biblioteca de visão computacional
from google import genai
from google.genai import types

class NewsRadar:
    def __init__(self):
        # Gatilhos Reais: Brasil, USA e Crypto (Essencial para BITH11 e WIN/WDO)
        self.hard_triggers = [
            "Copom", "IPCA", "Payroll", "FOMC", "Taxa de Juros", 
            "PIB", "CPI", "Decisão FED", "SEC", 
            "Relatório Focus", "Caged", "Inflação", "PMI", "Non-Farm"
        ]
        self.eventos_cache = []
        self.ultimo_update = 0

    def capturar_calendario_real(self):
        """Busca notícias de alto impacto (USD) que afetam a B3 e o mundo."""
        agora_ts = time.time()
        # Atualiza o cache a cada 4 horas
        if self.eventos_cache and (agora_ts - self.ultimo_update < 14400):
            return self.eventos_cache

        eventos = []
        try:
            # Fonte pública gratuita e confiável para calendário econômico (Forex Factory)
            url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                dados = response.json()
                for item in dados:
                    # Filtra apenas notícias de ALTO IMPACTO para USD (afeta B3 em cheio) ou BRL (se disponível)
                    if item.get('impact') == 'High' and item.get('country') in ['USD', 'BRL']:
                        data_str = item.get('date', '')
                        if data_str:
                            try:
                                # O formato ISO vem com timezone (ex: 2026-03-02T10:00:00-05:00)
                                dt_evento = datetime.fromisoformat(data_str)
                                # Converte para o fuso horário local do servidor (onde o robô roda)
                                dt_evento_local = dt_evento.astimezone()
                                eventos.append({
                                    'evento': item.get('title'),
                                    'hora': dt_evento_local.strftime("%H:%M"),
                                    'data_completa': dt_evento_local,
                                    'moeda': item.get('country')
                                })
                            except Exception as e:
                                pass
                
                self.eventos_cache = eventos
                self.ultimo_update = agora_ts
                print(f"📡 Radar de Notícias Atualizado: {len(eventos)} eventos de ALTO IMPACTO encontrados para esta semana.")
        except Exception as e:
            print(f"⚠️ Erro ao capturar calendário econômico: {e}")
            
        return self.eventos_cache

    def verificar_bloqueio_operacional(self):
        """Implementa o Hiato Operacional de 30 minutos em torno de notícias fatais."""
        eventos = self.capturar_calendario_real()
        agora = datetime.now().astimezone() # Usa timezone aware para comparar corretamente
        
        for evento in eventos:
            try:
                dt_evento = evento['data_completa']
                
                # Verifica se o evento é HOJE
                if dt_evento.date() == agora.date():
                    # Janela de Proteção: 15min antes e 15min depois (Total 30 min)
                    inicio_janela = dt_evento - timedelta(minutes=15)
                    fim_janela = dt_evento + timedelta(minutes=15)
                    
                    if inicio_janela <= agora <= fim_janela:
                        return True, f"{evento['moeda']} - {evento['evento']}"
            except Exception as e:
                continue
                
        return False, None

class AITrader:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("ERRO CRÍTICO: GEMINI_API_KEY não configurada no .env.")
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash-lite"
        self.fallback_model_name = "gemini-2.5-flash"
        self.radar = NewsRadar()

    def _analise_estatistica_previa(self, df_m1, df_m5):
        """Calcula saúde macro, padrões e suportes REAIS do momento exato (INTEGRADO)."""
        if df_m1 is None or len(df_m1) < 20: return {}
        
        # Volatilidade Dinâmica (ATR 14)
        if 'atr_14' in df_m1.columns and not pd.isna(df_m1['atr_14'].iloc[-1]):
            atr = df_m1['atr_14'].iloc[-1]
        else:
            high_low = df_m1['high'] - df_m1['low']
            atr = high_low.rolling(window=14).mean().iloc[-1]
        
        # Regressão Linear M5 (Tendência Principal - 3 Horas / 36 candles)
        if df_m5 is not None and len(df_m5) >= 12:
            num_candles = min(len(df_m5), 36)
            y_m5 = df_m5['close'].tail(num_candles).values
            x_m5 = np.arange(len(y_m5))
            slope_m5, _ = np.polyfit(x_m5, y_m5, 1)
        else:
            slope_m5 = 0

        # Momentum de Curto Prazo (Últimos 5 candles M1 - Para o Camaleão / Gatilho)
        y_m1_fast = df_m1['close'].tail(5).values
        x_m1_fast = np.arange(len(y_m1_fast))
        slope_rapido, _ = np.polyfit(x_m1_fast, y_m1_fast, 1)

        # VSA (Volume Spread Analysis)
        vol_medio = df_m1['tick_volume'].tail(30).mean()
        vol_atual = df_m1['tick_volume'].iloc[-1]
        
        if vol_atual > vol_medio * 2.5:
            esforco = "IGNIÇÃO INSTITUCIONAL (Anomalia de Volume)"
        elif vol_atual > vol_medio * 1.5:
            esforco = "ESFORÇO ELEVADO (Absorção)"
        else:
            esforco = "VOLUME VAREJO (Normal)"

        # Captura Estrutura M5 Fresca
        max_recente = df_m5['high'].tail(5).max() if df_m5 is not None else 0
        min_recente = df_m5['low'].tail(5).min() if df_m5 is not None else 0

        return {
            "atr": round(atr, 5),
            "direcao_slope_m5": "ALTA (Bullish)" if slope_m5 > 0 else "BAIXA (Bearish)",
            "forca_tendencia_m5": "ALTA (Institucional)" if abs(slope_m5) > (atr * 0.1) else "BAIXA (Consolidação)",
            "intensidade_slope_m5": round(slope_m5, 6),
            "volume_status": esforco,
            "direcao_imediata_m1": "COLAPSO / QUEDA FORTE" if slope_rapido < -atr else ("EXPLOSÃO / ALTA FORTE" if slope_rapido > atr else "CONSOLIDAÇÃO"),
            "aceleracao_slope_m1": round(slope_rapido, 6),
            "max_recente_m5": max_recente,
            "min_recente_m5": min_recente
        }

    def _formatar_candles_raio_x(self, df, num_candles):
        """Formata os candles fechados com cálculo exato de pavios e indicadores para a IA."""
        if df is None or df.empty or len(df) < 2: return "N/A"
        # Remove o candle atual (aberto) e pega os últimos 'num_candles'
        df_closed = df.iloc[:-1].tail(num_candles)
        linhas = []
        for _, row in df_closed.iterrows():
            if isinstance(row['time'], (int, float, np.integer, np.floating)):
                tempo = pd.to_datetime(row['time'], unit='s').strftime('%H:%M')
            else:
                tempo = pd.to_datetime(row['time']).strftime('%H:%M')
            o, h, l, c = row['open'], row['high'], row['low'], row['close']
            pavio_sup = h - max(o, c)
            pavio_inf = min(o, c) - l
            
            # Adiciona RSI e Estocástico se existirem no DataFrame
            rsi = f" | RSI: {row['rsi_14']:.1f}" if 'rsi_14' in row else ""
            stoch = f" | StochK: {row['stoch_k']:.1f}" if 'stoch_k' in row else ""
            vwap = f" | VWAP: {row['vwap']:.5f}" if 'vwap' in row else ""
            
            linhas.append(f"[Tempo: {tempo} | Abertura: {o:.5f} | Max: {h:.5f} | Min: {l:.5f} | Fechamento: {c:.5f} | Pavio Sup: {pavio_sup:.5f} | Pavio Inf: {pavio_inf:.5f}{rsi}{stoch}{vwap}]")
        return "\n".join(linhas)

    def _encontrar_pivots(self, df, num_pivots=3):
        """Encontra os últimos topos e fundos confirmados (Pivot Points) com proteção anti-ruído."""
        if df is None or len(df) < 10: return "N/A"
        
        # Proteção: Se o DataFrame não tiver dados suficientes para a janela, reduz a exigência
        janela = 2 if len(df) > 20 else 1
        
        highs = df['high'].values
        lows = df['low'].values
        times = df['time'].values
        
        topos = []
        fundos = []
        
        try:
            for i in range(janela, len(df) - janela):
                # Verifica se é o maior valor na janela local (Topo)
                is_topo = True
                for j in range(1, janela + 1):
                    if highs[i] <= highs[i-j] or highs[i] <= highs[i+j]:
                        is_topo = False
                        break
                
                if is_topo:
                    t = times[i]
                    if isinstance(t, (int, float, np.integer, np.floating)):
                        t_str = pd.to_datetime(t, unit='s').strftime('%H:%M')
                    else:
                        t_str = pd.to_datetime(t).strftime('%H:%M')
                    topos.append(f"{highs[i]:.5f} ({t_str})")
                
                # Verifica se é o menor valor na janela local (Fundo)
                is_fundo = True
                for j in range(1, janela + 1):
                    if lows[i] >= lows[i-j] or lows[i] >= lows[i+j]:
                        is_fundo = False
                        break
                        
                if is_fundo:
                    t = times[i]
                    if isinstance(t, (int, float, np.integer, np.floating)):
                        t_str = pd.to_datetime(t, unit='s').strftime('%H:%M')
                    else:
                        t_str = pd.to_datetime(t).strftime('%H:%M')
                    fundos.append(f"{lows[i]:.5f} ({t_str})")
        except Exception as e:
            print(f"Aviso: Erro ao calcular pivôs: {e}")
            pass
                
        topos_str = ", ".join(topos[-num_pivots:]) if topos else "Nenhum topo claro"
        fundos_str = ", ".join(fundos[-num_pivots:]) if fundos else "Nenhum fundo claro"
        
        # Define a estrutura Macro (Tendência vs Lateralização)
        estrutura = "INDEFINIDA"
        if len(topos) >= 2 and len(fundos) >= 2:
            ultimo_topo = float(topos[-1].split(" ")[0])
            penultimo_topo = float(topos[-2].split(" ")[0])
            ultimo_fundo = float(fundos[-1].split(" ")[0])
            penultimo_fundo = float(fundos[-2].split(" ")[0])
            
            # Tolerância para lateralização (0.05% do preço)
            tolerancia = ultimo_topo * 0.0005
            
            if (ultimo_topo > penultimo_topo + tolerancia) and (ultimo_fundo > penultimo_fundo + tolerancia):
                estrutura = "TENDÊNCIA DE ALTA (HH/HL)"
            elif (ultimo_topo < penultimo_topo - tolerancia) and (ultimo_fundo < penultimo_fundo - tolerancia):
                estrutura = "TENDÊNCIA DE BAIXA (LH/LL)"
            else:
                estrutura = "LATERALIZAÇÃO (Consolidação)"
        
        return f"Estrutura: {estrutura} | Topos: {topos_str} | Fundos: {fundos_str}"

    def analisar_mercado(self, dados_macro_df, dados_micro_df, estrategia: str, relevancia_anterior: int, dados_ontem: dict, estado_anterior: str = "", image_path_m1: str = None, image_path_m5: str = None, posicao_aberta: dict = None) -> dict:
        """
        BRAIN V8.0 - HEDGE FUND MODE (Fotos a cada 5m + Ordens Programadas)
        """
        df_m1 = dados_micro_df.get("m1")
        df_m5 = dados_micro_df.get("m5")
        df_m15 = dados_macro_df if dados_macro_df is not None else dados_micro_df.get("m15")

        if df_m1 is None or df_m1.empty:
            return {"relevancia": 1, "decisao": "WAIT", "motivo": "Aguardando fluxo de dados..."}

        # 1. ESCUDO FUNDAMENTALISTA (NEWS)
        noticia_ativa, nome_evento = self.radar.verificar_bloqueio_operacional()
        if noticia_ativa:
            return {
                "relevancia": 5, "decisao": "WAIT",
                "motivo": f"BLOQUEIO: Notícia de Alto Impacto ({nome_evento}) detectada. Protegendo capital.",
                "regime_mercado": "Alta Volatilidade / Manipulação de News",
                "estado_operacional": "Aguardando",
                "ordem_programada": {"acao": "NONE", "preco_gatilho": 0.0, "motivo_gatilho": ""},
                "estudos_visuais": {"linhas_tendencia": [], "suporte_resistencia": [], "fibo_proposals": []}
            }

        # 2. INTELIGÊNCIA MATEMÁTICA E MÉTRICAS
        stats = self._analise_estatistica_previa(df_m1, df_m5)
        preco_atual = df_m1['close'].iloc[-1]
        vwap_atual = df_m1['vwap'].iloc[-1] if 'vwap' in df_m1.columns else preco_atual
        atr_atual = stats.get('atr', 0)
        
        # --- ANÁLISE DE GAP E SESSÃO ---
        gap_info = "Sem dados de gap."
        sessao_info = "Sessão em andamento."
        
        if dados_ontem and df_m1 is not None and not df_m1.empty:
            fechamento_ontem = dados_ontem.get('fechamento_ontem')
            
            # Tenta pegar a data do último candle para saber qual é o "hoje" do gráfico
            ultimo_tempo = df_m1['time'].iloc[-1]
            if isinstance(ultimo_tempo, (int, float, np.integer, np.floating)):
                data_atual_grafico = pd.to_datetime(ultimo_tempo, unit='s').date()
            else:
                data_atual_grafico = pd.to_datetime(ultimo_tempo).date()
            
            # Garante que a coluna time seja datetime para a comparação
            if not pd.api.types.is_datetime64_any_dtype(df_m1['time']):
                if pd.api.types.is_numeric_dtype(df_m1['time']):
                    df_m1_temp_time = pd.to_datetime(df_m1['time'], unit='s')
                else:
                    df_m1_temp_time = pd.to_datetime(df_m1['time'])
                df_hoje = df_m1[df_m1_temp_time.dt.date == data_atual_grafico]
            else:
                df_hoje = df_m1[df_m1['time'].dt.date == data_atual_grafico]
            
            if not df_hoje.empty:
                abertura_hoje = df_hoje['open'].iloc[0]
                
                if fechamento_ontem and fechamento_ontem > 0:
                    gap_pct = ((abertura_hoje - fechamento_ontem) / fechamento_ontem) * 100
                    if abs(gap_pct) > 0.05: # Gap relevante
                        direcao_gap = "ALTA" if gap_pct > 0 else "BAIXA"
                        gap_info = f"GAP DE {direcao_gap} ({gap_pct:.2f}%). Fechamento Ontem: {fechamento_ontem} -> Abertura Hoje: {abertura_hoje}"
                    else:
                        gap_info = f"Sem Gap relevante ({gap_pct:.2f}%)."
                
                t1 = df_hoje['time'].iloc[0]
                t2 = df_m1['time'].iloc[-1]
                
                if isinstance(t1, (int, float, np.integer, np.floating)):
                    tempo_primeiro_candle = pd.to_datetime(t1, unit='s')
                else:
                    tempo_primeiro_candle = pd.to_datetime(t1)
                    
                if isinstance(t2, (int, float, np.integer, np.floating)):
                    tempo_ultimo_candle = pd.to_datetime(t2, unit='s')
                else:
                    tempo_ultimo_candle = pd.to_datetime(t2)
                    
                minutos_desde_abertura = (tempo_ultimo_candle - tempo_primeiro_candle).total_seconds() / 60
                
                if minutos_desde_abertura <= 60:
                    sessao_info = f"INÍCIO DE PREGÃO (Aberto há {int(minutos_desde_abertura)} min). ATENÇÃO: Alta volatilidade, falsos rompimentos e formação de nova tendência."
                else:
                    sessao_info = f"PREGÃO EM ANDAMENTO (Aberto há {int(minutos_desde_abertura/60)}h {int(minutos_desde_abertura%60)}m)."
        
        # Zonas de Liquidez
        sup_m15 = df_m15['low'].min() if df_m15 is not None and not df_m15.empty else 0
        res_m15 = df_m15['high'].max() if df_m15 is not None and not df_m15.empty else 0
        
        contexto_ontem = f"MÁXIMA: {dados_ontem.get('maxima_ontem')} | MÍNIMA: {dados_ontem.get('minima_ontem')} | FECHAMENTO: {dados_ontem.get('fechamento_ontem')}" if dados_ontem else "Sem dados de ontem."

        # RAIO-X FRACTAL (Pré-Processamento para a IA)
        raio_x_m1 = self._formatar_candles_raio_x(df_m1, 30)
        raio_x_m5 = self._formatar_candles_raio_x(df_m5, 36)
        pivots_m1 = self._encontrar_pivots(df_m1, 3)
        pivots_m5 = self._encontrar_pivots(df_m5, 3)

        # 3. CONSTRUÇÃO DO CÉREBRO DA IA (ESTRUTURA HEDGE FUND)
        system_instruction = f"""
        Você é um Quant Trader Sênior Híbrido operando como 'Camaleão Dinâmico' Multimodal (Lê Texto, Números e IMAGENS).
        Sua missão é gerar lucro implacável, focar em PULLBACKS SAUDÁVEIS e evitar REVERSÕES.

        ESTRUTURA DE DADOS OBRIGATÓRIA (Siga o JSON estritamente):
        {{
            "relevancia": inteiro de 1 a 5,
            "decisao": "WAIT", "WAIT_TO_BUY", "WAIT_TO_SELL", "BUY", "SELL", "HOLD", ou "BREAKEVEN",
            "motivo": "Explicação do momento.",
            "regime_mercado": "Ex: Colapso M1 / Consolidação M15",
            "estrategia_escolhida": "Nome do sub-modo ativado",
            "raciocinio_macro": "Leitura rápida M15",
            "raciocinio_micro": "Leitura rápida M1 e M5",
            "adaptabilidade": "Justificativa curta de mudança",
            "probabilidade_acerto": "Ex: '85%'",
            "estado_operacional": "SUA MEMÓRIA. OBRIGATÓRIO INICIAR COM O PREÇO. Ex: '[Preço {preco_atual}] Aguardando pullback no suporte.'",
            "ordem_programada": {{
                "acao": "BUY", "SELL" ou "NONE",
                "preco_gatilho": 0.0,
                "motivo_gatilho": "Breve motivo da armadilha"
            }},
            "estudos_visuais": {{
                "suporte": 0.0,
                "resistencia": 0.0,
                "tendencia_direcao": "UP", "DOWN" ou "SIDEWAYS",
                "tendencia_preco": 0.0,
                "linhas_tendencia": [],
                "fibo_proposals": []
            }}
        }}
        
        --- INSTRUÇÕES BÁSICAS DE OPERACIONAL DO MERCADO ---
        0. REGRA DE TENDÊNCIA (CRÍTICA): A TENDÊNCIA (Direção de Compra ou Venda) DEVE SER DEFINIDA EXCLUSIVAMENTE PELO GRÁFICO M5. Analise os topos e fundos maiores/menores das últimas 3 horas (últimos 36 candles do M5). O Gráfico M1 serve APENAS para confirmar rompimentos e refinar o timing de entrada (gatilho), NUNCA para definir a tendência. Se o M5 diz ALTA, você só procura COMPRA no M1. Se o M5 diz BAIXA, você só procura VENDA no M1.
        1. A LEI DA VWAP (VOLUME WEIGHTED AVERAGE PRICE): Institucionais operam pela VWAP. 
           - NUNCA compre se o preço estiver ABAIXO da VWAP.
           - NUNCA venda se o preço estiver ACIMA da VWAP.
           - A VWAP atua como um ímã (Mean Reversion) e como suporte/resistência dinâmico.
        2. VOLATILIDADE E STOP LOSS (ATR): O ATR (Average True Range) mede a volatilidade real.
           - Use o ATR atual ({atr_atual:.5f}) para definir o Stop Loss. Exemplo: Stop Loss = 1.5x ATR.
           - Se o ATR estiver muito alto, exija confirmações mais fortes antes de entrar.
        3. ZONAS DE LIQUIDEZ (D-1): As Máximas e Mínimas do dia anterior são piscinas de liquidez.
           - Comprar exatamente em cima da Máxima de ontem é suicídio (armadilha de liquidez).
           - Vender exatamente em cima da Mínima de ontem é suicídio.
           - Espere o rompimento claro ou a rejeição nessas zonas.
        4. SUPORTE E RESISTÊNCIA (S/R): 
         * Suporte (S): É sempre a base (parte de baixo) do movimento que forma topos e fundos.
         * Resistência (R): É sempre o teto (parte de cima) do movimento que forma topos e fundos.
        5. PullBack: Estratégia de operar a favor da tendência buscando maior margem quando acontece uma correção (recuo) tocando S/R e entrando a favor da tendência.
        6. LINHAS DE TENDÊNCIA:
         * LTA (Linha de Tendência de Alta): Linha base dos candles de fundos cada vez mais altos/baixos (sempre na tendência atual), ela forma entre o último Suporte após romper, e o último Suporte atual.
         * LTB (Linha de Tendência de Baixa): Linha teto dos candles de topos cada vez mais baixos/altos (sempre na tendência atual), ela forma entre a última Resistência após romper, e a última resistência atual.
         * Conceito de LTA + LTB: Quando o mercado está perdendo a força entre tendência ou lateralização, usa-se as 2 linhas para identificar onde o mercado vai se romper LTA ou LTB.

        --- 🚨 A LEI DO TIMING E O PULLBACK OBRIGATÓRIO 🚨 ---
        REGRA DE OURO: É TOTALMENTE PROIBIDO ENTRAR NO ROMPIMENTO. O rompimento é apenas um aviso, NÃO É O GATILHO DE ENTRADA.
        Imponha este protocolo de 4 passos:
        1. Confirmação 1 (Macro): A tendência principal vista no M5 (1 hora) deve apoiar a direção.
        2. Confirmação 2 e 3 (Rompimento e Volume): Houve um rompimento de estrutura com volume alto? O rompimento é APENAS um aviso. Emita "WAIT".
        3. O PULLBACK OBRIGATÓRIO: O robô DEVE ESPERAR o preço recuar e tocar no Suporte/Resistência recém rompido (ou na LTA/LTB).
        4. Gatilho de Entrada (A Fraqueza): A ordem (BUY/SELL) só pode ser disparada quando o preço bater nesse nível de Pullback E o candle demonstrar fraqueza/rejeição (pavio contra o pullback, ex: doji, martelo), indicando que a tendência das confirmações vai ser retomada. Pegue todo o movimento a favor sem entrar no topo/fundo esticado!
        
        Outras Regras de Proteção:
        5. ⚠️ ALERTA DE REVERSÃO: Se o preço voltar contra a tendência RASGANDO o S/R e a LTA/LTB com velas fortes (engolfos) e volume alto, CANCELE a ideia de pullback. O mercado exauriu e reverteu.
        6. ⚠️ DUPLO ROMPIMENTO (REVERSÃO DE TENDÊNCIA): Você SÓ PODE operar contra a tendência anterior SE houver um "Duplo Rompimento" claro.
        7. TRAILLING STOP ÁGIL: Perceba as mudanças que podem dar loss e coloque o gain para 0 a 0 para se voltar o movimento dá tempo de reverter a perda, usando "decisao": "HOLD" ou "BREAKEVEN".

        --- ⚖️ MODO SCALPER (LATERALIZAÇÃO) ⚖️ ---
        Se a estrutura do mercado for "LATERALIZAÇÃO (Consolidação)":
        1. ESQUEÇA ROMPIMENTOS: Em consolidação, rompimentos são armadilhas (Breakout Traps) em 80% das vezes.
        2. OPERE AS EXTREMIDADES: Use o RSI e o Estocástico. 
           - Se o preço tocar a Resistência E o RSI/Stoch estiverem sobrecomprados (>70/>80), arme VENDA.
           - Se o preço tocar o Suporte E o RSI/Stoch estiverem sobrevendidos (<30/<20), arme COMPRA.
        3. FAST-EXIT (SAÍDA RÁPIDA): No campo "estrategia_escolhida", escreva "SCALPER_MODE". Isso avisará o robô para fechar a operação rapidamente assim que o indicador reverter, sem esperar o Take Profit fixo.
        4. ROMPIMENTO DE CAIXOTE: Se o preço romper a consolidação com FORÇA (Volume Anômalo + Vela de Força), a lateralização acabou. Mude para o modo Tendência e arme a ordem a favor do rompimento no primeiro pullback.

        --- FILTROS DE VERBOSIDADE E ECONOMIA DE TOKENS ---
        1. SE A DECISÃO FOR 'WAIT' E A ARMADILHA FOR 'NONE': O campo 'motivo' DEVE ser EXATAMENTE "[Preço {preco_atual}] Status mantido. Aguardando confirmação.". NÃO escreva mais nada.
        2. A PRIMEIRA ANÁLISE: SE e SOMENTE SE a sua memória (estado_anterior) for "Iniciando...", você tem permissão para fazer textão.
        3. TEXTO LONGO APENAS EM GATILHOS: Só justifique detalhadamente se a Relevância for 4★ ou 5★.

        --- ANÁLISE MULTIMODAL (FOTOS A CADA 5 MINUTOS) ---
        Se receber as FOTOS do M1 e M5, saiba ler o gráfico:
        1. MÉDIAS MÓVEIS (CRUCIAL): A linha AMARELA brilhante é a Média Móvel Rápida (9). A linha AZUL CLARO é a Média Móvel Lenta (21). Use elas como zonas de Pullback dinâmico. Se o preço cruzar e fechar do outro lado da linha Azul com força, suspeite de Reversão!
        2. DIAGONAIS PRIMEIRO: Procure linhas de tendência de alta (LTA) ou baixa (LTB) visuais para confirmar se a estrutura macro ainda está intacta durante o pullback.

        --- O MANIFESTO DO CAMALEÃO (ANÁLISE DE CONTEXTO PROFUNDO) ---
        1. CONTEXTO É REI: Antes de decidir atirar a mercado ou armar tocaia, você OBRIGATORIAMENTE deve cruzar 4 fatores: 
           A) Estrutura (Rompeu LTA/LTB recente? Fez reteste? O Preço está acima ou abaixo das linhas Amarela e Azul?)
           B) Volume (A anomalia de volume apoia o lado do rompimento? O volume secou durante o pullback?)
           C) Zonas de S/R (O preço está na beira do abismo ou no meio do ruído?)
           D) Padrões de Candle (Há engolfo, martelo, doji ou estrela cadente rejeitando a zona de reteste?)
        2. REGRA DO DOUBLE CHECK (PRIMEIRO PASSO): Se você identificar um setup de alta probabilidade, NÃO envie BUY/SELL direto. Emita "WAIT_TO_BUY" ou "WAIT_TO_SELL" e grave na memória o motivo.
        3. O TIRO DE CONFIRMAÇÃO (SEGUNDO PASSO): No ciclo de 15s seguinte, leia sua memória. Se a força se manteve e o candle confirmou o padrão a seu favor (ex: rejeitou o suporte no pullback), emita a decisão final "BUY" ou "SELL" para atirar a mercado.
        4. O USO DA PACIÊNCIA: Se a foto mostrar topos descendentes (micro LTB) indo contra uma LTA macro, priorize a força micro do M1. O mercado presente dita a regra.
        5. PACIÊNCIA SNIPER (MEAN REVERSION): Se a foto mostrar o preço esticado longe das médias, NUNCA entre a favor do movimento. Aguarde a regressão à média (o preço retornar para perto da linha Amarela/Azul).
        """

        prompt = f"""
        ANÁLISE HÍBRIDA (DADOS + IMAGEM) EM TEMPO REAL.
        Estratégia: {estrategia} | Preço Atual: {preco_atual}
        STATUS DA POSIÇÃO: {f"ABERTA -> {posicao_aberta['type']} no preço {posicao_aberta['price_open']} (Lucro: {posicao_aberta['profit']})" if posicao_aberta else "NENHUMA (Aguardando nova entrada)"}
        
        Status Quant: Tendência M5 {stats.get('direcao_slope_m5')} | Volume {stats.get('volume_status')}
        Direção Micro Imediata M1: {stats.get('direcao_imediata_m1')} (Aceleração: {stats.get('aceleracao_slope_m1')})
        VWAP Atual: {vwap_atual:.5f} | ATR Atual: {atr_atual:.5f}
        
        CONTEXTO DE SESSÃO E GAP:
        Sessão: {sessao_info}
        Gap Hoje: {gap_info}
        
        ---> SUA MEMÓRIA DO CICLO ANTERIOR: 
        "{estado_anterior}"
        
        MAPA DE LIQUIDEZ E PIVOTS:
        Níveis Ontem: {contexto_ontem}
        Pivots M5: {pivots_m5}
        Pivots M1: {pivots_m1}
        Macro (M15): S:{sup_m15} / R:{res_m15}
        
        RAIO-X FRACTAL (CANDLES FECHADOS COM PAVIOS):
        M5 (Últimos 36 candles - Coração do Fluxo): 
        {raio_x_m5}
        
        M1 (Últimos 30 candles - Gatilho): 
        {raio_x_m1}

        LEIA OS DADOS E OLHE A IMAGEM DO GRÁFICO (Se anexada). Defina uma Armadilha de Rompimento ("ordem_programada") ou execute a mercado se o gatilho já estourou. Gere o JSON estrito.
        """

        # 4. PREPARANDO O PAYLOAD MULTIMODAL (DUPLA VISÃO)
        contents_payload = [prompt]
        
        # Anexa a foto do M5 primeiro (Contexto)
        if image_path_m5 and os.path.exists(image_path_m5):
            try:
                img_m5 = Image.open(image_path_m5)
                contents_payload.append("IMAGEM 1: GRÁFICO M5 (Use para ver a tendência e Suportes/Resistências Maiores)")
                contents_payload.append(img_m5)
            except Exception as e:
                pass

        # Anexa a foto do M1 logo em seguida (Gatilho)
        if image_path_m1 and os.path.exists(image_path_m1):
            try:
                img_m1 = Image.open(image_path_m1)
                contents_payload.append("IMAGEM 2: GRÁFICO M1 (Use para procurar quebras de LTA/LTB e programar armadilhas de rompimento)")
                contents_payload.append(img_m1)
            except Exception as e:
                pass

        try:
            # Chamada unificada enviando texto e AS DUAS imagens
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents_payload, 
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )
            return json.loads(response.text)
            
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                print(f"⚠️ Modelo {self.model_name} indisponível (503). Tentando fallback para {self.fallback_model_name}...")
                try:
                    response = self.client.models.generate_content(
                        model=self.fallback_model_name,
                        contents=contents_payload, 
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            response_mime_type="application/json",
                            temperature=0.2
                        )
                    )
                    return json.loads(response.text)
                except Exception as fallback_e:
                    print(f"❌ Erro no fallback: {fallback_e}")
                    return {
                        "relevancia": 1, "decisao": "WAIT", 
                        "motivo": f"Erro IA Multimodal (Fallback): {str(fallback_e)}",
                        "estado_operacional": f"Aguardando estabilidade. Erro na leitura visual dupla.", 
                        "ordem_programada": {"acao": "NONE", "preco_gatilho": 0.0, "motivo_gatilho": ""},
                        "estudos_visuais": {"suporte_resistencia": []}
                    }
            else:
                return {
                    "relevancia": 1, "decisao": "WAIT", 
                    "motivo": f"Erro IA Multimodal Dupla: {str(e)}",
                    "estado_operacional": f"Aguardando estabilidade. Erro na leitura visual dupla.", 
                    "ordem_programada": {"acao": "NONE", "preco_gatilho": 0.0, "motivo_gatilho": ""},
                    "estudos_visuais": {"suporte_resistencia": []}
                }