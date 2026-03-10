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
                
        print("Conectado ao MetaTrader 5 com sucesso. (Modo Micro-Scalping)")
        self.connected = True
        return True

    def obter_dados_mercado(self, ativo: str, timeframe: int = mt5.TIMEFRAME_M1, qtd_candles: int = 100):
        """
        Obtém os dados históricos (OHLCV) do ativo especificado.
        Focado em M1 para Micro-Scalping. Adiciona RSI e VWAP.
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
        
        # --- CÁLCULO DE INDICADORES NATIVOS (PANDAS) ---
        # 1. RSI (Relative Strength Index) - Período 14 (Reversão)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # 2. VWAP (Volume Weighted Average Price) Diária
        df['date'] = df['time'].dt.date
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['tp_vol'] = df['typical_price'] * df['tick_volume']
        df['cum_vol'] = df.groupby('date')['tick_volume'].cumsum()
        df['cum_tp_vol'] = df.groupby('date')['tp_vol'].cumsum()
        df['vwap'] = df['cum_tp_vol'] / df['cum_vol']
        
        # Preenche NaNs iniciais com 50 (neutro) para evitar quebra na IA
        df.fillna({'rsi_14': 50, 'vwap': df['close']}, inplace=True)
        
        return df[['time', 'open', 'high', 'low', 'close', 'tick_volume', 'rsi_14', 'vwap']]

    def capturar_imagem_grafico(self, df_dados, symbol, filename="chart_m1.png", titulo_grafico="M1 - Micro Scalping"):
        """Gera uma foto (plot) do gráfico M1 para a IA 'enxergar' o volume e RSI."""
        if df_dados is None or df_dados.empty: 
            return None
        
        try:
            import mplfinance as mpf
            import pandas as pd
            
            df_plot = df_dados.copy()
            
            if 'time' in df_plot.columns:
                if not pd.api.types.is_datetime64_any_dtype(df_plot['time']):
                    df_plot['time'] = pd.to_datetime(df_plot['time'], unit='s')
                df_plot.set_index('time', inplace=True)
                
            df_plot.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'tick_volume': 'Volume'}, inplace=True)
            
            # Pega os últimos 30 candles (Foco no curtíssimo prazo)
            df_plot = df_plot.tail(30) 
            
            mc = mpf.make_marketcolors(up='#10b981', down='#ef4444', edge='inherit', wick='inherit', volume='in', ohlc='i')
            
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
            
            mpf.plot(
                df_plot, 
                type='candle', 
                style=s, 
                volume=True,
                mav=(9, 21),
                mavcolors=('#FFFF00', '#00BFFF'),
                title=f"VISÃO IA - {symbol} {titulo_grafico}", 
                savefig=filename, 
                figsize=(10, 6)
            )
            
            return filename
            
        except ImportError:
            print("⚠️ AVISO: 'mplfinance' não instalado. Rode: pip install mplfinance pillow")
            return None
        except Exception as e:
            print(f"⚠️ Erro ao gerar foto do gráfico: {e}")
            return None

    def enviar_ordem(self, ativo: str, tipo_ordem: str, lote: float, sl_pts: int, tp_pts: int):
        """
        Envia uma ordem a mercado (BUY ou SELL) com SL e TP iniciais curtos.
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

        point = symbol_info.point
        digits = symbol_info.digits
        volume_step = symbol_info.volume_step
        
        lote_normalizado = round(float(lote) / volume_step) * volume_step
        
        tick = mt5.symbol_info_tick(ativo)
        if tick is None:
            print(f"Falha ao obter tick para {ativo}.")
            return None
            
        price = tick.ask if tipo_ordem == 'BUY' else tick.bid
        
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

        filling_mode = symbol_info.filling_mode
        if filling_mode == 1 or filling_mode == 3:
            type_filling_val = mt5.ORDER_FILLING_FOK
        elif filling_mode == 2:
            type_filling_val = mt5.ORDER_FILLING_IOC
        else:
            type_filling_val = mt5.ORDER_FILLING_RETURN
        
        # Slippage ajustado para scalping (mais apertado)
        if "WIN" in ativo.upper():
            deviation_pts = 50
        elif "WDO" in ativo.upper():
            deviation_pts = 5
        elif "BIT" in ativo.upper():
            deviation_pts = 200
        else:
            deviation_pts = 10
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": ativo,
            "volume": float(lote_normalizado),
            "type": order_type,
            "price": round(price, digits),
            "sl": round(sl, digits),
            "tp": round(tp, digits),
            "deviation": deviation_pts,
            "magic": 123456,
            "comment": "Consists Trade AI - Micro Scalper",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": type_filling_val
        }

        result = mt5.order_send(request)
        
        if result is None:
            print(f"Falha ao enviar ordem (Retorno None): {mt5.last_error()}")
            return None
            
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"ERRO DE EXECUÇÃO: {result.retcode} - Comentário: {result.comment}")
            return None
            
        print(f"Ordem executada com sucesso! Ticket: {result.order} | Ativo: {ativo}")
        return result

    def tem_posicao_aberta(self, ativo: str):
        if not self.connected:
            return False
        posicoes = mt5.positions_get(symbol=ativo)
        return posicoes is not None and len(posicoes) > 0

    def obter_posicao_aberta(self, ativo: str):
        if not self.connected:
            return None
        posicoes = mt5.positions_get(symbol=ativo)
        if posicoes is None or len(posicoes) == 0:
            return None
            
        pos = posicoes[0]
        return {
            "ticket": pos.ticket,
            "type": "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL",
            "price_open": pos.price_open,
            "price_current": pos.price_current,
            "sl_atual": pos.sl,
            "tp_atual": pos.tp,
            "profit": pos.profit,
            "volume": pos.volume
        }

    def gerenciar_trailing_stop_dinamico(self, ativo: str):
        """
        Lógica de Trailing Stop Móvel (Micro-Scalping) BLINDADA:
        - Calcula o Spread e StopLevel da corretora para evitar Erro 10016.
        - Breakeven Real: Cobre taxas e spread.
        """
        posicao = self.obter_posicao_aberta(ativo)
        if not posicao:
            return False
            
        symbol_info = mt5.symbol_info(ativo)
        if not symbol_info:
            return False
            
        point = symbol_info.point
        digits = symbol_info.digits
        
        # --- BLINDAGEM DE INFRAESTRUTURA MT5 ---
        stoplevel = symbol_info.trade_stops_level * point
        spread = symbol_info.spread * point
        custo_tick = spread + (1 * point) # Cobre o spread + 1 tick de lucro mínimo
        
        preco_entrada = posicao["price_open"]
        preco_atual = posicao["price_current"]
        sl_atual = posicao["sl_atual"]
        tipo = posicao["type"]
        
        if tipo == "BUY":
            pontos_ganhos = (preco_atual - preco_entrada) / point
        else:
            pontos_ganhos = (preco_entrada - preco_atual) / point
            
        novo_sl = sl_atual
        
        # Lógica de escadinha do Trailing Stop
        if pontos_ganhos >= 50:
            novo_sl = preco_entrada + (40 * point) if tipo == "BUY" else preco_entrada - (40 * point)
        elif pontos_ganhos >= 20:
            novo_sl = preco_entrada + (10 * point) if tipo == "BUY" else preco_entrada - (10 * point)
        elif pontos_ganhos >= 10:
            # BREAKEVEN REAL: Garante que sai com lucro mínimo para pagar a B3/Corretora
            novo_sl = preco_entrada + custo_tick if tipo == "BUY" else preco_entrada - custo_tick
            
        novo_sl = round(novo_sl, digits)
        
        # --- VALIDAÇÃO DE SEGURANÇA (ANTI ERRO 10016) ---
        modificar = False
        if tipo == "BUY":
            # Só sobe o stop se for maior que o atual E respeitar a distância mínima da corretora
            if novo_sl > sl_atual and (preco_atual - novo_sl) >= stoplevel:
                modificar = True
        elif tipo == "SELL":
            # Só desce o stop se for menor que o atual E respeitar a distância mínima da corretora
            if (novo_sl < sl_atual or sl_atual == 0) and (novo_sl - preco_atual) >= stoplevel:
                modificar = True
                
        if modificar:
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": ativo,
                "sl": novo_sl,
                "tp": posicao["tp_atual"],
                "position": posicao["ticket"]
            }
            result = mt5.order_send(request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                # Se der erro, printa o motivo exato para debug quantitativo
                erro_msg = mt5.last_error()
                print(f"⚠️ Falha ao mover Trailing Stop. RetCode: {result.retcode if result else 'None'} | Erro: {erro_msg}")
                return False
                
            print(f"🛡️ TRAILING STOP ACIONADO: Lucro atual {pontos_ganhos:.1f} pts. Stop movido para {novo_sl}.")
            return True
            
        return False

    def obter_resultado_diario(self):
        if not self.connected:
            return 0.0
        hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        timestamp_hoje = int(hoje.timestamp())
        historico = mt5.history_deals_get(timestamp_hoje, int(datetime.now().timestamp()))
        if historico is None or len(historico) == 0:
            return 0.0
        df_historico = pd.DataFrame(list(historico), columns=historico[0]._asdict().keys())
        lucro_total = df_historico[df_historico['entry'] == 1]['profit'].sum()
        comissao = df_historico['commission'].sum()
        swap = df_historico['swap'].sum()
        return float(lucro_total + comissao + swap)

    def obter_informacoes_conta(self):
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
