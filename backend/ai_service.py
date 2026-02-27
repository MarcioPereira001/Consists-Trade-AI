import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from PIL import Image # NOVO: Biblioteca de visão computacional
from google import genai
from google.genai import types

class NewsRadar:
    def __init__(self):
        # Gatilhos Reais: Brasil, USA e Crypto (Essencial para BITH11 e WIN/WDO)
        self.hard_triggers = [
            "Copom", "IPCA", "Payroll", "FOMC", "Taxa de Juros", 
            "PIB", "CPI USA", "Decisão FED", "SEC Crypto", 
            "Relatório Focus", "Caged", "Inflação"
        ]

    def capturar_calendario_real(self):
        """Interface para conexão com API de Calendário Econômico."""
        try:
            # Em produção, integrar com RapidAPI/Investing para dados reais
            return [] 
        except Exception as e:
            print(f"Erro ao capturar notícias: {e}")
            return []

    def verificar_bloqueio_operacional(self):
        """Implementa o Hiato Operacional de 30 minutos em torno de notícias fatais."""
        eventos = self.capturar_calendario_real()
        agora = datetime.now()
        for evento in eventos:
            try:
                # Valida se o evento está na lista de hard_triggers
                if any(trigger.lower() in evento['evento'].lower() for trigger in self.hard_triggers):
                    hora_evento = datetime.strptime(evento['hora'], "%H:%M").replace(
                        year=agora.year, month=agora.month, day=agora.day
                    )
                    # Janela de Proteção: 15min antes e 15min depois
                    if (agora >= hora_evento - timedelta(minutes=15)) and (agora <= hora_evento + timedelta(minutes=15)):
                        return True, evento['evento']
            except: continue
        return False, None

class AITrader:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("ERRO CRÍTICO: GEMINI_API_KEY não configurada no .env.")
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash-lite"
        self.radar = NewsRadar()

    def _analise_estatistica_previa(self, df_m1, df_m5):
        """Calcula saúde macro, padrões e suportes REAIS do momento exato (INTEGRADO)."""
        if df_m1 is None or len(df_m1) < 20: return {}
        
        # Volatilidade Dinâmica (ATR 14)
        high_low = df_m1['high'] - df_m1['low']
        atr = high_low.rolling(window=14).mean().iloc[-1]
        
        # Regressão Linear M1
        y_m1 = df_m1['close'].tail(15).values
        x_m1 = np.arange(len(y_m1))
        slope, intercept = np.polyfit(x_m1, y_m1, 1)

        # Momentum de Curto Prazo (Últimos 5 candles M1 - Para o Camaleão)
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
            "direcao_slope": "ALTA (Bullish)" if slope > 0 else "BAIXA (Bearish)",
            "forca_tendencia": "ALTA (Institucional)" if abs(slope) > (atr * 0.4) else "BAIXA (Consolidação)",
            "intensidade_slope": round(slope, 6),
            "volume_status": esforco,
            "direcao_imediata": "COLAPSO / QUEDA FORTE" if slope_rapido < -atr else ("EXPLOSÃO / ALTA FORTE" if slope_rapido > atr else "CONSOLIDAÇÃO"),
            "aceleracao_slope": round(slope_rapido, 6),
            "max_recente_m5": max_recente,
            "min_recente_m5": min_recente
        }

    def analisar_mercado(self, dados_macro_df, dados_micro_df, estrategia: str, relevancia_anterior: int, dados_ontem: dict, estado_anterior: str = "", image_path_m1: str = None, image_path_m5: str = None) -> dict:
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
        
        # Zonas de Liquidez
        sup_m15 = df_m15['low'].min() if df_m15 is not None and not df_m15.empty else 0
        res_m15 = df_m15['high'].max() if df_m15 is not None and not df_m15.empty else 0
        
        contexto_ontem = f"MAX: {dados_ontem.get('maxima_ontem')} | MIN: {dados_ontem.get('minima_ontem')} | FECH: {dados_ontem.get('fechamento_ontem')}" if dados_ontem else "Sem dados de ontem."

        # 3. CONSTRUÇÃO DO CÉREBRO DA IA (ESTRUTURA HEDGE FUND)
        system_instruction = f"""
        Você é um Quant Trader Sênior Híbrido operando como 'Camaleão Dinâmico' Multimodal (Lê Texto, Números e IMAGENS).
        Sua missão é gerar lucro implacável, focar em PULLBACKS SAUDÁVEIS e evitar REVERSÕES.

        ESTRUTURA DE DADOS OBRIGATÓRIA (Siga o JSON estritamente):
        {{
            "relevancia": inteiro de 1 a 5,
            "decisao": "WAIT", "WAIT_TO_BUY", "WAIT_TO_SELL", "BUY" ou "SELL",
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
                "linhas_tendencia": [],
                "suporte_resistencia": [],
                "fibo_proposals": []
            }}
        }}

        --- 🚨 A LEI DO PULLBACK E O PERIGO DA REVERSÃO 🚨 ---
        REGRA DE OURO: Você é ESTRITAMENTE PROIBIDO de emitir "BUY" ou "SELL" no topo/fundo de um rompimento esticado.
        O SEU PROTOCOLO É O SEGUINTE:
        1. ALINHAMENTO MACRO: Opere a favor da tendência (rompimento da Máx/Mín do dia). Identificou o rompimento? Emita "WAIT_TO_BUY" ou "WAIT_TO_SELL" e não faça nada.
        2. ESPERE O PULLBACK: Aguarde o preço voltar para testar a linha rompida ou as médias móveis (Amarela/Azul).
        3. O USO DA ARMADILHA (ORDEM PROGRAMADA): Quando o preço estiver exatamente na zona de reteste (S/R), você DEVE usar o campo "ordem_programada" para armar a sua entrada (BUY/SELL) no gatilho que retoma a tendência. Assim não perdemos tempo de execução.
        4. ⚠️ ALERTA DE REVERSÃO (O FALSO PULLBACK): Analise o contexto! Se o preço voltar contra a tendência RASGANDO o S/R e a LTA/LTB com velas fortes (engolfos) e volume alto, CANCELE a ideia de pullback. O mercado exauriu e reverteu. Nesse caso, mantenha a armadilha em "NONE" e a decisão em "WAIT".
        5. O TIRO DE SNIPER: Só arme a armadilha ou emita a ordem a mercado se o pullback vier "secando" (volume caindo) e deixar REJEIÇÃO (pavio, doji, martelo) na zona de Suporte/Resistência.

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
        Status Quant: Tendência {stats.get('direcao_slope')} | Volume {stats.get('volume_status')}
        Direção Micro Imediata: {stats.get('direcao_imediata')} (Aceleração: {stats.get('aceleracao_slope')})
        
        ---> SUA MEMÓRIA DO CICLO ANTERIOR: 
        "{estado_anterior}"
        
        MAPA DE LIQUIDEZ:
        Níveis Ontem: {contexto_ontem}
        Micro (M5 Recente): S:{stats.get('min_recente_m5')} / R:{stats.get('max_recente_m5')}
        Macro (M15): S:{sup_m15} / R:{res_m15}
        
        HISTÓRICO FRACTAL (OHLCV RECENTE):
        M15 (Parede Institucional): 
        {df_m15.tail(3).to_string(index=False) if df_m15 is not None else 'N/A'}
        
        M5 (Coração do Fluxo): 
        {df_m5.tail(5).to_string(index=False) if df_m5 is not None else 'N/A'}
        
        M1 (Gatilho): 
        {df_m1.tail(5).to_string(index=False) if df_m1 is not None else 'N/A'}

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
            return {
                "relevancia": 1, "decisao": "WAIT", 
                "motivo": f"Erro IA Multimodal Dupla: {str(e)}",
                "estado_operacional": f"Aguardando estabilidade. Erro na leitura visual dupla.", 
                "ordem_programada": {"acao": "NONE", "preco_gatilho": 0.0, "motivo_gatilho": ""},
                "estudos_visuais": {"suporte_resistencia": []}
            }