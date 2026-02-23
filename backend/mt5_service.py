import os
import MetaTrader5 as mt5
import pandas as pd

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

    def obter_dados_mercado(self, ativo: str, timeframe: int = mt5.TIMEFRAME_M15, qtd_candles: int = 100):
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

    def enviar_ordem(self, ativo: str, tipo_ordem: str, lote: float, sl_pts: int, tp_pts: int):
        """
        Envia uma ordem a mercado (BUY ou SELL) com Stop Loss e Take Profit em pontos.
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
        volume_step = symbol_info.volume_step
        
        # Normaliza o lote para o volume_step do ativo
        lote_normalizado = round(float(lote) / volume_step) * volume_step
        
        # Obtém o preço atual (Ask para Compra, Bid para Venda)
        tick = mt5.symbol_info_tick(ativo)
        if tick is None:
            print(f"Falha ao obter tick para {ativo}.")
            return None
            
        price = tick.ask if tipo_ordem == 'BUY' else tick.bid
        
        # Calcula SL e TP
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

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": ativo,
            "volume": float(lote_normalizado),
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 123456,
            "comment": "Consists Trade AI",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None:
            print(f"Falha ao enviar ordem (Retorno None): {mt5.last_error()}")
            return None
            
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Falha ao enviar ordem: {result.retcode} - {mt5.last_error()}")
            return None
            
        print(f"Ordem executada com sucesso! Ticket: {result.order}")
        return result
