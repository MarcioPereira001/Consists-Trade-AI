import os
import json
from google import genai
from google.genai import types
import pandas as pd

class AITrader:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("Aviso: GEMINI_API_KEY não configurada no .env.")
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash-lite"

    def analisar_mercado(self, dados_macro_df: pd.DataFrame, dados_micro_df: pd.DataFrame, estrategia: str) -> dict:
        """
        Analisa os dados de mercado em múltiplos timeframes (Fractal) e retorna uma decisão de trade 
        estruturada em JSON, incluindo raciocínio e estudos visuais.
        """
        if dados_micro_df is None or dados_micro_df.empty:
            return {"decisao": "WAIT", "motivo": "Dados de mercado insuficientes."}

        # Formata os dados para a IA
        macro_data = dados_macro_df.tail(30).to_string(index=False) if dados_macro_df is not None and not dados_macro_df.empty else "N/A"
        micro_data = dados_micro_df.tail(30).to_string(index=False)
        
        system_instruction = """
        Você é um Quant Trader Institucional Sênior, operando em um Fundo de Alta Frequência.
        Sua especialidade é a Análise Fractal do mercado, combinando o contexto Macro (tendência maior, liquidez) 
        com o gatilho Micro (ChoCh, BOS, exaustão de volume).
        
        REGRAS ABSOLUTAS:
        1. Você DEVE retornar APENAS um JSON válido, sem markdown ou texto adicional.
        2. Analise a estrutura do mercado: identifique ChoCh (Change of Character) e BOS (Break of Structure).
        3. Identifique zonas de liquidez (Fair Value Gaps, Order Blocks).
        4. Recalcule a rota dinamicamente se o contexto macro divergir do micro.
        5. Forneça coordenadas para estudos visuais (Linhas de Tendência, Suporte/Resistência, Fibonacci) 
           baseados nos dados fornecidos.
        6. SE a estratégia for "Adaptável (Camaleão / Dinâmica)", você DEVE realizar uma Análise de Regime de Mercado 
           (Tendência de Alta, Baixa, Consolidação, Alta Volatilidade) e escolher a melhor sub-estratégia 
           (SMC, Price Action, Rompimento, etc) para o momento.
        
        O JSON DEVE seguir EXATAMENTE esta estrutura:
        {
          "regime_mercado": "Regime atual do mercado (ex: Tendência de Alta, Consolidação)...",
          "estrategia_escolhida": "Estratégia que você decidiu usar para este trade...",
          "raciocinio_macro": "Análise do contexto geral (H1/M15)...",
          "raciocinio_micro": "Análise do gatilho atual (M5/M1)...",
          "adaptabilidade": "Recálculo de rota/tendência atual...",
          "estudos_visuais": {
            "linhas_tendencia": [{"id": "lt_1", "p1": {"time": "YYYY-MM-DD HH:MM:SS", "price": 0.0}, "p2": {"time": "YYYY-MM-DD HH:MM:SS", "price": 0.0}}],
            "suporte_resistencia": [0.0, 0.0],
            "fibo_proposals": [{"level": "61.8", "price": 0.0}]
          },
          "decisao": "BUY" | "SELL" | "WAIT",
          "sl_recomendado": 0.0,
          "tp_recomendado": 0.0,
          "motivo": "Justificativa final curta e técnica."
        }
        """

        prompt = f"""
        Estratégia Operacional: {estrategia}
        
        Dados MACRO (Contexto Maior):
        {macro_data}
        
        Dados MICRO (Gatilho de Entrada):
        {micro_data}
        
        Execute a análise fractal e retorne o JSON estrito.
        """

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.1 # Muito baixa para consistência lógica e JSON estrito
                )
            )
            
            result = json.loads(response.text)
            return result
        except Exception as e:
            print(f"Erro na análise fractal da IA: {e}")
            return {
                "regime_mercado": "Desconhecido",
                "estrategia_escolhida": "N/A",
                "raciocinio_macro": "Erro na inferência.",
                "raciocinio_micro": "Erro na inferência.",
                "adaptabilidade": "Falha de sistema.",
                "estudos_visuais": {"linhas_tendencia": [], "suporte_resistencia": [], "fibo_proposals": []},
                "decisao": "WAIT",
                "sl_recomendado": 0,
                "tp_recomendado": 0,
                "motivo": f"Erro: {str(e)}"
            }