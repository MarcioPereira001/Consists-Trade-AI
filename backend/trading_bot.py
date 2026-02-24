import os
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
import MetaTrader5 as mt5

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
        print(f"Erro ao salvar log: {e}")

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
        print(f"Erro ao salvar histórico: {e}")

async def trading_loop():
    """Loop principal de operação do robô."""
    print("Iniciando Trading Loop...")
    
    if not mt5_service.conectar():
        print("Encerrando bot por falha no MT5.")
        return

    while True:
        try:
            if not supabase:
                print("Supabase não configurado. Aguardando...")
                await asyncio.sleep(10)
                continue

            # 1. Buscar configurações ativas
            response = supabase.table('trade_configs').select('*').execute()
            configs = response.data
            
            if not configs:
                print("Nenhuma configuração encontrada.")
                await asyncio.sleep(10)
                continue

            for config in configs:
                profile_id = config.get('profile_id')
                ativo = config.get('ativo', 'EURUSD')
                lote = config.get('lote', 0.01)
                sl_pts = config.get('stop_loss', 100)
                tp_pts = config.get('take_profit', 200)
                estrategia = config.get('estrategia_ativa', 'Price Action Limpo')
                horario_inicio = config.get('horario_inicio', '09:00')
                horario_fim = config.get('horario_fim', '17:30')
                
                # 2. Verificar Filtro de Horário
                agora = datetime.now().time()
                try:
                    h_inicio = datetime.strptime(horario_inicio, '%H:%M').time()
                    h_fim = datetime.strptime(horario_fim, '%H:%M').time()
                    
                    if h_inicio <= h_fim:
                        dentro_horario = h_inicio <= agora <= h_fim
                    else: # Caso o horário passe da meia-noite (ex: 22:00 às 02:00)
                        dentro_horario = agora >= h_inicio or agora <= h_fim
                        
                except ValueError:
                    print(f"Formato de horário inválido para {profile_id}. Usando default.")
                    dentro_horario = True # Se der erro no parse, permite rodar por segurança

                if not dentro_horario:
                    # Log controlado para não floodar (apenas print, ou log no supabase a cada X tempo se necessário)
                    print(f"[{ativo}] Fora da janela de operação ({horario_inicio} - {horario_fim}). Aguardando...")
                    continue

                # Vamos assumir que se o modo for DEMO, podemos operar em conta demo.
                # Se houver uma flag de pausa no banco, checaríamos aqui.
                # is_paused = config.get('is_paused', False)
                # if is_paused: continue

                # 3. Puxar dados do MT5 (Fractal)
                # Macro: H1, Micro: M15 (exemplo)
                df_macro = mt5_service.obter_dados_mercado(ativo, mt5.TIMEFRAME_H1, 50)
                df_micro = mt5_service.obter_dados_mercado(ativo, mt5.TIMEFRAME_M15, 50)
                
                if df_micro is None or df_micro.empty:
                    continue

                # 4. Enviar para a IA
                print(f"Analisando mercado para {ativo} (Estratégia: {estrategia})...")
                analise = ai_trader.analisar_mercado(df_macro, df_micro, estrategia)
                
                decisao = analise.get('decisao', 'WAIT')
                motivo = analise.get('motivo', 'Sem motivo')
                regime_mercado = analise.get('regime_mercado', 'N/A')
                estrategia_escolhida = analise.get('estrategia_escolhida', estrategia)
                raciocinio_macro = analise.get('raciocinio_macro', '')
                raciocinio_micro = analise.get('raciocinio_micro', '')
                adaptabilidade = analise.get('adaptabilidade', '')
                estudos_visuais = analise.get('estudos_visuais', {})

                print(f"Decisão IA: {decisao} | Regime: {regime_mercado} | Motivo: {motivo}")
                
                # Log detalhado para o frontend
                log_msg = f"Ativo: {ativo} | Decisão: {decisao}\nRegime: {regime_mercado}\nEstratégia: {estrategia_escolhida}\nMacro: {raciocinio_macro}\nMicro: {raciocinio_micro}\nAdaptabilidade: {adaptabilidade}\nMotivo: {motivo}"
                await log_to_supabase(profile_id, "ai_analysis", log_msg)

                # 5. Executar ordem se BUY ou SELL
                if decisao in ['BUY', 'SELL']:
                    ambiente = config.get('ambiente', 'AO VIVO')
                    
                    if ambiente == 'REPLAY HISTÓRICO':
                        print(f"[MODO REPLAY] Simulando ordem {decisao} para {ativo} (Paper Trading)...")
                        # Pega o último preço do dataframe micro para simular
                        preco_atual = float(df_micro.iloc[-1]['close'])
                        resultado = mt5_service.simular_ordem_paper_trading(ativo, decisao, preco_atual, motivo)
                    else:
                        print(f"[MODO AO VIVO] Executando ordem REAL {decisao} para {ativo}...")
                        resultado = mt5_service.enviar_ordem(ativo, decisao, lote, sl_pts, tp_pts)
                    
                    if resultado:
                        tag = "[SIMULAÇÃO] " if ambiente == 'REPLAY HISTÓRICO' else ""
                        await log_to_supabase(profile_id, "trade", f"{tag}Ordem {decisao} executada com sucesso. Ticket: {resultado.order}")
                        await save_trade_history(profile_id, resultado.order, ativo, decisao, resultado.price, motivo)
                    else:
                        await log_to_supabase(profile_id, "error", f"Falha ao executar ordem {decisao} para {ativo}.")
                        
            # Aguarda o próximo ciclo (ex: 1 minuto)
            await asyncio.sleep(60)

        except Exception as e:
            print(f"Erro no loop principal: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(trading_loop())
    except KeyboardInterrupt:
        print("Bot encerrado pelo usuário.")
        mt5.shutdown()
