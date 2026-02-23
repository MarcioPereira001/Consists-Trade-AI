import { create } from 'zustand';

export interface Position {
  ticket: number;
  symbol: string;
  type: 'BUY' | 'SELL';
  volume: number;
  openPrice: number;
  currentPrice: number;
  profit: number;
}

export interface TradeHistoryEntry {
  id: string;
  ticket_mt5: number;
  ativo: string;
  tipo_ordem: 'BUY' | 'SELL';
  preco_entrada: number;
  preco_saida: number;
  lucro_prejuizo: number;
  motivo_ia: string;
}

export interface DailyMetrics {
  winRate: number;
  totalProfit: number;
  maxDrawdown: number;
}

interface TradeStoreState {
  balance: number;
  equity: number;
  openPositions: Position[];
  tradeHistory: TradeHistoryEntry[];
  dailyMetrics: DailyMetrics;
  
  // Actions
  setBalance: (balance: number) => void;
  setEquity: (equity: number) => void;
  setOpenPositions: (positions: Position[]) => void;
  addTradeToHistory: (trade: TradeHistoryEntry) => void;
  setTradeHistory: (history: TradeHistoryEntry[]) => void;
  updateDailyMetrics: (metrics: Partial<DailyMetrics>) => void;
}

export const useTradeStore = create<TradeStoreState>((set) => ({
  balance: 0,
  equity: 0,
  openPositions: [],
  tradeHistory: [],
  dailyMetrics: {
    winRate: 0,
    totalProfit: 0,
    maxDrawdown: 0,
  },

  setBalance: (balance) => set({ balance }),
  setEquity: (equity) => set({ equity }),
  setOpenPositions: (positions) => set({ openPositions: positions }),
  addTradeToHistory: (trade) => set((state) => ({ tradeHistory: [trade, ...state.tradeHistory] })),
  setTradeHistory: (history) => set({ tradeHistory: history }),
  updateDailyMetrics: (metrics) => set((state) => ({ 
    dailyMetrics: { ...state.dailyMetrics, ...metrics } 
  })),
}));
