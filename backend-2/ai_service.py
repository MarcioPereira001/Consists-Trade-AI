import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class AITrader:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            print("⚠️ AVISO: GEMINI_API_KEY não encontrada no .env")
            
        # Inicialização do novo SDK do Gemini
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-2.5-flash" # Usando o modelo rápido para alta frequência

    def analisar_mercado(self, dados_micro_df, estrategia, relevancia_anterior, dados_ontem, estado_anterior, image_path_m1=None, posicao_aberta=None):
        """
        Analisa o mercado focado em Micro-Scalping (M1).
        Busca reversões de RSI e picos de volume a favor da micro-tendência.
        """
        if dados_micro_df is None or dados_micro_df.empty:
            return {"decisao": "WAIT", "motivo": "Dados insuficientes."}

        # Pega os últimos 5 candles para o prompt de texto
        ultimos_candles = dados_micro_df.tail(5).to_dict('records')
        
        # Formata os dados para o prompt
        texto_dados = "Últimos 5 minutos (M1):\n"
        for c in ultimos_candles:
            texto_dados += f"Hora: {c['time']} | Abertura: {c['open']:.5f} | Máxima: {c['high']:.5f} | Mínima: {c['low']:.5f} | Fechamento: {c['close']:.5f} | Vol: {c['tick_volume']} | RSI: {c['rsi_14']:.2f} | VWAP: {c['vwap']:.5f}\n"

        preco_atual = ultimos_candles[-1]['close']
        rsi_atual = ultimos_candles[-1]['rsi_14']
        vol_atual = ultimos_candles[-1]['tick_volume']

        prompt = f"""
        Você é um robô Sniper de Micro-Scalping de Alta Frequência operando no gráfico de 1 Minuto (M1).
        Seu objetivo é capturar movimentos curtos (5 a 10 reais) a favor da micro-tendência, usando picos de volume e reversão de RSI.

        DADOS ATUAIS:
        Preço Atual: {preco_atual}
        RSI (14): {rsi_atual}
        Volume Atual: {vol_atual}
        
        {texto_dados}
        
        MEMÓRIA ANTERIOR:
        {estado_anterior}
        
        REGRAS DE MICRO-SCALPING (ALTA PRECISÃO):
        1. TENDÊNCIA INSTITUCIONAL (VWAP): O preço em relação à VWAP dita a direção suprema. Preço > VWAP = SÓ COMPRA. Preço < VWAP = SÓ VENDA.
        2. GATILHO DE COMPRA (BUY): Preço ACIMA da VWAP + Pullback (Preço caindo e RSI descansando na zona de 40 a 50 ou tocando a própria VWAP) + Vela de rejeição (pavio inferior) + Aumento de Volume.
        3. GATILHO DE VENDA (SELL): Preço ABAIXO da VWAP + Pullback (Preço subindo e RSI descansando na zona de 50 a 60 ou tocando a própria VWAP) + Vela de rejeição (pavio superior) + Aumento de Volume.
        4. FILTRO ANTI-RUÍDO: Se o preço estiver "costurando" a VWAP (cruzando para cima e para baixo sem direção clara) OU o volume estiver decrescente, você DEVE retornar WAIT.
        5. SEM "WAIT" SE HOUVER OPORTUNIDADE: Setup alinhado = atire (BUY ou SELL).
        6. GESTÃO: Se já houver posição aberta, retorne HOLD.
        
        RETORNE APENAS UM JSON VÁLIDO COM A SEGUINTE ESTRUTURA:
        {{
            "decisao": "BUY", "SELL", "WAIT" ou "HOLD",
            "motivo": "Explicação curta e direta do gatilho acionado (ex: RSI sobrevendido + Pico de volume no suporte).",
            "relevancia": 1 a 5 (5 para setups perfeitos),
            "estado_operacional": "Sua memória curta para o próximo ciclo de 15s."
        }}
        """

        contents = []
        
        # Adiciona a imagem se existir
        if image_path_m1 and os.path.exists(image_path_m1):
            try:
                # O novo SDK aceita o caminho do arquivo diretamente usando client.files.upload
                # Para simplificar e evitar problemas de upload em loop rápido, 
                # vamos ler o arquivo como bytes e enviar inline.
                with open(image_path_m1, "rb") as f:
                    image_bytes = f.read()
                
                contents.append(
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type="image/png"
                    )
                )
            except Exception as e:
                print(f"Erro ao carregar imagem M1: {e}")

        # Adiciona o texto
        contents.append(prompt)

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1 # Baixa temperatura para respostas consistentes
                )
            )
            
            resposta_texto = response.text.strip()
            
            # Limpa formatação markdown se houver
            if resposta_texto.startswith("```json"):
                resposta_texto = resposta_texto[7:-3].strip()
            elif resposta_texto.startswith("```"):
                resposta_texto = resposta_texto[3:-3].strip()
                
            return json.loads(resposta_texto)
            
        except Exception as e:
            print(f"Erro na API do Gemini: {e}")
            return {
                "decisao": "WAIT",
                "motivo": f"Erro na IA: {str(e)}",
                "relevancia": 1,
                "estado_operacional": estado_anterior
            }
