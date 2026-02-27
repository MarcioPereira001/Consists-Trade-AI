import os
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, time

class MT5Service:
    def __init__(self):
        self.login = int(os.getenv("MT5_LOGIN", 0))
        self.password = os.getenv("MT5_PASSWORD", "")
        self.server = os.getenv("MT5_SERVER", "")
        self.connected = False

    def conectar(self):
        """
        Inicializa a conexão com o terminal MetaTrader 5 usando as credenciais do .env.
        """
        if not mt5.initialize():
            print(f"Falha ao inicializar MT5: {mt5.last_error()}")
            return False
        
        if self.login > 0 and self.password and self.server:
            authorized = mt5.login(self.login, password=self.password, server=self.server)
            if not authorized:
                print(f"Falha ao conectar na conta MT5: {mt5.last_error()}")
                return False
                
        print("Conectado ao MetaTrader 5 com sucesso.")
        self.connected = True
        return True

    def obter_dados_mercado(self, ativo: str, timeframe: int = mt5.TIMEFRAME_M5, qtd_candles: int = 100):
        """
        Obtém os dados históricos (OHLCV) do ativo especificado.
        """
        if not self.connected:
            print("MT5 não está conectado. Tentando reconectar...")
            if not self.conectar():
                return None
            
        rates = mt5.copy_rates_from_pos(ativo, timeframe, 0, qtd_candles)
        if rates is None or len(rates) == 0:
            print(f"Falha ao obter dados para {ativo}: {mt5.last_error()}")
            return None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df[['time', 'open', 'high', 'low', 'close', 'tick_volume']]

    def obter_ohlc_ontem(self, ativo: str):
        """
        Busca especificamente a Máxima, Mínima e Fechamento do dia anterior.
        """
        if not self.connected: return None
        
        # Puxa o candle diário (D1). O índice 1 é o dia de ontem terminado.
        rates = mt5.copy_rates_from_pos(ativo, mt5.TIMEFRAME_D1, 1, 1)
        if rates is not None and len(rates) > 0:
            return {
                "maxima_ontem": float(rates[0]['high']),
                "minima_ontem": float(rates[0]['low']),
                "fechamento_ontem": float(rates[0]['close'])
            }
        return None

    def capturar_imagem_grafico(self, df_m5, symbol, filename="chart_m5.png"):
        """Gera uma foto (plot) do gráfico de M5 para a IA 'enxergar'."""
        if df_m5 is None or df_m5.empty: 
            return None
        
        try:
            import mplfinance as mpf
            df_plot = df_m5.copy()
            
            # Formata a data para a biblioteca de desenho entender
            if 'time' in df_plot.columns:
                df_plot['time'] = pd.to_datetime(df_plot['time'], unit='s')
                df_plot.set_index('time', inplace=True)
                
            # Renomeia as colunas para o padrão exigido
            df_plot.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'tick_volume': 'Volume'}, inplace=True)
            
            # Pega os últimos 45 candles (A "foto" ideal)
            df_plot = df_plot.tail(45) 
            
            # --- CORREÇÃO CIRÚRGICA: ESTILO DARK MODE ---
            mc = mpf.make_marketcolors(up='#10b981', down='#ef4444', edge='inherit', wick='inherit', volume='in', ohlc='i')
            
            # Parâmetros de texto repassados da forma correta para o matplotlib (rc)
            estilo_rc = {
                'text.color': 'white', 
                'axes.labelcolor': 'white', 
                'xtick.color': 'white', 
                'ytick.color': 'white'
            }
            
            s = mpf.make_mpf_style(
                marketcolors=mc, 
                gridstyle=':', 
                y_on_right=True, 
                facecolor='#111111', 
                figcolor='#111111', 
                gridcolor='#333333',
                rc=estilo_rc
            )
            
            # Gera e salva a imagem
            mpf.plot(df_plot, type='candle', style=s, volume=True, title=f"VISÃO IA - {symbol} M5", savefig=filename, figsize=(10, 6))
            
            return filename
            
        except ImportError:
            print("⚠️ AVISO: 'mplfinance' não instalado. Rode: pip install mplfinance pillow")
            return None
        except Exception as e:
            print(f"⚠️ Erro ao gerar foto do gráfico: {e}")
            return None

    def enviar_ordem(self, ativo: str, tipo_ordem: str, lote: float, sl_pts: int, tp_pts: int):
        """
        Envia uma ordem a mercado (BUY ou SELL) com precisão fractal e normalização de volume.
        Suporta ativos B3 (BITH11, WIN, WDO) e Forex.
        """
        if not self.connected:
            print("MT5 não está conectado.")
            return None
            
        symbol_info = mt5.symbol_info(ativo)
        if symbol_info is None:
            print(f"Ativo {ativo} não encontrado.")
            return None
            
        if not symbol_info.visible:
            if not mt5.symbol_select(ativo, True):
                print(f"Falha ao selecionar ativo {ativo}.")
                return None

        # --- FUNDAMENTOS DO ATIVO ---
        point = symbol_info.point
        digits = symbol_info.digits  # BITH11=2, WIN=0, EURUSD=5
        volume_step = symbol_info.volume_step
        
        # NORMALIZAÇÃO DO LOTE (Preservando sua lógica robusta)
        lote_normalizado = round(float(lote) / volume_step) * volume_step
        
        # Obtém o preço atual (Ask para Compra, Bid para Venda)
        tick = mt5.symbol_info_tick(ativo)
        if tick is None:
            print(f"Falha ao obter tick para {ativo}.")
            return None
            
        price = tick.ask if tipo_ordem == 'BUY' else tick.bid
        
        # --- CÁLCULO DE SL E TP COM ARREDONDAMENTO PRECISO ---
        if tipo_ordem == 'BUY':
            order_type = mt5.ORDER_TYPE_BUY
            sl = price - (sl_pts * point)
            tp = price + (tp_pts * point)
        elif tipo_ordem == 'SELL':
            order_type = mt5.ORDER_TYPE_SELL
            sl = price + (sl_pts * point)
            tp = price - (tp_pts * point)
        else:
            print("tipo_ordem deve ser 'BUY' ou 'SELL'")
            return None

        # REQUISIÇÃO ROBUSTA (CORRIGIDA A SINTAXE)
        type_filling_val = mt5.ORDER_FILLING_RETURN if "11" in ativo or symbol_info.exchange else mt5.ORDER_FILLING_FOK
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": ativo,
            "volume": float(lote_normalizado),
            "type": order_type,
            "price": round(price, digits),
            "sl": round(sl, digits),    # Arredondamento dinâmico para evitar rejeição
            "tp": round(tp, digits),    # Essencial para ETFs como BITH11
            "deviation": 20,
            "magic": 123456,
            "comment": "Consists Trade AI - Sniper V4",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": type_filling_val # Passado corretamente aqui
        }

        # ENVIO E VALIDAÇÃO
        result = mt5.order_send(request)
        
        if result is None:
            print(f"Falha ao enviar ordem (Retorno None): {mt5.last_error()}")
            return None
            
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"ERRO DE EXECUÇÃO: {result.retcode} - Comentário: {result.comment}")
            # Log de depuração para entender rejeições de preço
            print(f"DEBUG: Price: {round(price, digits)} | SL: {round(sl, digits)} | TP: {round(tp, digits)}")
            return None
            
        print(f"Ordem executada com sucesso! Ticket: {result.order} | Ativo: {ativo}")
        return result
        
    def simular_ordem_paper_trading(self, ativo: str, tipo_ordem: str, preco_simulado: float, motivo: str):
        """
        Simula a execução de uma ordem no banco de dados sem enviar para a corretora real.
        Evita o Erro 10027 (Mercado Fechado / Algo Trading disabled).
        """
        import time
        import random
        
        ticket_simulado = int(time.time()) + random.randint(100, 999)
        print(f"[PAPER TRADING] Ordem {tipo_ordem} simulada com sucesso para {ativo} a R${preco_simulado:.2f}. Ticket: {ticket_simulado}")
        
        # Simula o retorno do MT5
        class MockResult:
            def __init__(self, order, price):
                self.order = order
                self.price = price
                
        return MockResult(order=ticket_simulado, price=preco_simulado)

    def tem_posicao_aberta(self, ativo: str):
        """
        Verifica diretamente no MetaTrader 5 se já existe uma operação rodando para este ativo.
        """
        if not self.connected:
            return False
            
        posicoes = mt5.positions_get(symbol=ativo)
        
        if posicoes is None or len(posicoes) == 0:
            return False
            
        return True

    def obter_resultado_diario(self):
        """
        Calcula o lucro/perda total de todas as ordens fechadas hoje.
        Essencial para a trava de meta e limite de perda.
        """
        if not self.connected:
            return 0.0

        # Define o início do dia de hoje (00:00:00)
        hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        timestamp_hoje = int(hoje.timestamp())

        # Busca o histórico de ordens finalizadas
        historico = mt5.history_deals_get(timestamp_hoje, int(datetime.now().timestamp()))
        
        if historico is None or len(historico) == 0:
            return 0.0

        df_historico = pd.DataFrame(list(historico), columns=historico[0]._asdict().keys())
        
        # Filtra apenas o que é lucro/prejuízo de trade (ignora depósitos/ajustes)
        # Entry 1 é 'OUT' (fechamento de posição)
        lucro_total = df_historico[df_historico['entry'] == 1]['profit'].sum()
        comissao = df_historico['commission'].sum()
        swap = df_historico['swap'].sum()

        return float(lucro_total + comissao + swap)

    def obter_informacoes_conta(self):
        """
        Retorna dados financeiros da conta (Saldo, Patrimônio, Margem).
        """
        if not self.connected:
            return None
        
        conta = mt5.account_info()
        if conta is None:
            return None
            
        return {
            "balance": conta.balance,
            "equity": conta.equity,
            "margin": conta.margin,
            "profit": conta.profit
        }
