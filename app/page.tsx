'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Activity, Wifi, WifiOff, BrainCircuit, Terminal, Server, Settings, AlertTriangle, PauseCircle, PlayCircle, LogOut, FastForward, Play, Square } from 'lucide-react';
import TradingChart, { VisualStudies } from '@/components/TradingChart';
import { CandlestickData, Time, SeriesMarker } from 'lightweight-charts';
import { useTradeStore } from '@/store/useTradeStore';
import { supabase } from '@/lib/supabase';
import { useRouter } from 'next/navigation';
import { Session } from '@supabase/supabase-js';
import SettingsPanel from '@/components/SettingsPanel';
import axios from 'axios';

type ConnectionStatus = 'connected' | 'disconnected' | 'connecting';
type TradeMode = 'DEMO' | 'REAL';

interface LogEntry {
  id: string;
  timestamp: string;
  message: string;
  type: 'info' | 'warning' | 'error' | 'trade' | 'ai_analysis' | 'market_data';
}

export default function CockpitPage() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  
  const [mt5Status, setMt5Status] = useState<ConnectionStatus>('disconnected');
  const [aiStatus, setAiStatus] = useState<ConnectionStatus>('disconnected');
  const [engineStatus, setEngineStatus] = useState<'ONLINE' | 'OFFLINE' | 'LOADING'>('OFFLINE');
  const [isCommanding, setIsCommanding] = useState(false);
  const [tradeMode, setTradeMode] = useState<TradeMode>('DEMO');
  const [isRobotPaused, setIsRobotPaused] = useState(false);
  
  const { balance, equity, openPositions, dailyMetrics } = useTradeStore();
  
  const [aiLogs, setAiLogs] = useState<LogEntry[]>([]);
  const [backendStatus, setBackendStatus] = useState<'offline' | 'online'>('offline');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Estados Dinâmicos do Gráfico Financeiro
  const [visualStudies, setVisualStudies] = useState<VisualStudies | undefined>(undefined);
  const [chartData, setChartData] = useState<CandlestickData<Time>[]>([]);
  const [chartMarkers, setChartMarkers] = useState<SeriesMarker<Time>[]>([]);
  const [currentAsset, setCurrentAsset] = useState<string>('CARREGANDO...');

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.push('/auth');
      } else {
        setSession(session);
        carregarAtivoInicial(session.user.id);
      }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) {
        router.push('/auth');
      } else {
        setSession(session);
        carregarAtivoInicial(session.user.id);
      }
    });

    return () => subscription.unsubscribe();
  }, [router]);

  // Sincronização do Status do Motor AWS
  useEffect(() => {
    const fetchEngineStatus = async () => {
      const { data } = await supabase.from('bot_control').select('status').eq('id', 1).single();
      if (data) setEngineStatus(data.status as any);
    };
    const interval = setInterval(fetchEngineStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const sendEngineCommand = async (cmd: 'START' | 'STOP') => {
    setIsCommanding(true);
    await supabase.from('bot_control').update({ 
      command: cmd, 
      last_updated: new Date().toISOString() 
    }).eq('id', 1);
    setTimeout(() => setIsCommanding(false), 2000);
  };

  // Busca o ativo configurado no Supabase para colocar no topo do gráfico
  const carregarAtivoInicial = async (userId: string) => {
    const { data } = await supabase.from('trade_configs').select('ativo').eq('profile_id', userId).single();
    if (data && data.ativo) {
      setCurrentAsset(data.ativo);
      // Sincroniza o backend com o ativo carregado
      syncAssetWithBackend(data.ativo);
    } else {
      setCurrentAsset('NENHUM ATIVO');
    }
  };

  // Função para sincronizar a troca de ativo com o Backend
  const syncAssetWithBackend = async (asset: string) => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
      await fetch(`${apiUrl}/api/select_asset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asset: asset }),
      });
      console.log("Backend sincronizado com o ativo:", asset);
    } catch (error) {
      console.error("Erro ao sincronizar ativo com o backend (Pode ser bloqueio HTTPS):", error);
    }
  };

  // Monitora mudanças no currentAsset para sincronizar (caso venha de outras partes do app)
  useEffect(() => {
    if (currentAsset !== 'CARREGANDO...' && currentAsset !== 'NENHUM ATIVO') {
      syncAssetWithBackend(currentAsset);
    }
  }, [currentAsset]);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [aiLogs]);

  // CONEXÃO WEBSOCKET (COM PROTEÇÃO ANTI-TELA PRETA)
  useEffect(() => {
    let ws: WebSocket | null = null;

    try {
      const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://127.0.0.1:8000/ws/logs';
      // Se o Chrome bloquear por segurança (HTTPS vs HTTP), ele cai no catch sem quebrar o site
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setBackendStatus('online');
        setAiStatus('connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // 1. Tratamento de Logs e Análises (Cérebro)
          if (data.type !== 'market_data') {
            setAiLogs((prev) => [...prev, data]);
            if (data.type === 'ai_analysis' && data.estudos_visuais) {
              setVisualStudies(data.estudos_visuais);
            }
          }
          
          // 2. Tratamento de Dados de Mercado (Olhos - Game Mode)
          if (data.type === 'market_data') {
            if (data.candles) {
              setChartData(data.candles);
            } 
            else if (data.tick) {
              setChartData((prev) => {
                const lastCandle = prev[prev.length - 1];
                if (lastCandle) {
                  const updatedCandle = {
                    ...lastCandle,
                    close: data.tick.price,
                    high: Math.max(lastCandle.high, data.tick.price),
                    low: Math.min(lastCandle.low, data.tick.price),
                  };
                  return [...prev.slice(0, -1), updatedCandle];
                }
                return prev;
              });
            }
            setMt5Status('connected');
          }

          if (data.type === 'trade' && data.marker) {
            setChartMarkers(prev => [...prev, data.marker]);
          }

        } catch (error) {
          console.error('Erro no processamento de dados em tempo real:', error);
        }
      };

      ws.onclose = () => {
        setBackendStatus('offline');
        setAiStatus('disconnected');
        setMt5Status('disconnected');
      };

      ws.onerror = () => {
        console.warn('WebSocket desconectado ou falha na conexão (Bloqueio de Mixed Content).');
        setBackendStatus('offline');
        setAiStatus('disconnected');
        setMt5Status('disconnected');
      };

    } catch (error) {
      console.error("Escudo ativado: O navegador bloqueou a conexão insegura, mas o painel continua vivo.", error);
      setBackendStatus('offline');
    }

    return () => {
      if (ws) ws.close();
    };
  }, []);

  return (
    <div className="flex flex-col h-screen bg-[#0a0a0a] text-gray-100 overflow-hidden font-sans">
      <header className="flex items-center justify-between px-4 py-3 bg-[#141414] border-b border-[#27272a] shrink-0">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-500" />
            <h1 className="text-lg font-bold tracking-tight">Consists Trade AI</h1>
          </div>
          
          <div className="flex items-center gap-4 text-sm font-medium">
            <div className="flex items-center gap-1.5">
              <Server className={`w-4 h-4 ${backendStatus === 'online' ? 'text-emerald-500' : 'text-red-500'}`} />
              <span className={backendStatus === 'online' ? 'text-emerald-500' : 'text-red-500'}>
                MOTOR: {backendStatus.toUpperCase()}
              </span>
            </div>

            <div className="flex items-center gap-1.5">
              {mt5Status === 'connected' ? (
                <Wifi className="w-4 h-4 text-emerald-500" />
              ) : (
                <WifiOff className="w-4 h-4 text-red-500" />
              )}
              <span className={mt5Status === 'connected' ? 'text-emerald-500' : 'text-red-500'}>
                MT5: {mt5Status.toUpperCase()}
              </span>
            </div>
            
            <div className="flex items-center gap-1.5">
              <BrainCircuit className={`w-4 h-4 ${aiStatus === 'connected' ? 'text-purple-500' : 'text-gray-500'}`} />
              <span className={aiStatus === 'connected' ? 'text-purple-500' : 'text-gray-500'}>
                IA: {aiStatus === 'connected' ? 'ONLINE' : 'AGUARDANDO'}
              </span>
            </div>
            
            <div className={`px-2 py-0.5 rounded text-xs font-bold ${tradeMode === 'REAL' ? 'bg-red-500/20 text-red-500' : 'bg-blue-500/20 text-blue-500'}`}>
              {tradeMode}
            </div>
            
            {session && (
              <div className="flex items-center gap-3 ml-4 pl-4 border-l border-[#27272a]">
                <span className="text-xs text-gray-400">{session.user.email}</span>
                <button 
                  onClick={() => supabase.auth.signOut()}
                  className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-red-400/10 rounded transition-colors"
                  title="Sair"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            )}
            
            <button 
              onClick={() => setIsSettingsOpen(true)}
              className="p-1.5 text-gray-400 hover:text-gray-100 hover:bg-[#27272a] rounded transition-colors ml-2"
              title="Configurações do Motor"
            >
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="flex items-center gap-4 mr-4 border-r border-[#27272a] pr-6">
            <div className="flex flex-col">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider font-bold">Lucro Líquido</span>
              <span className={`text-sm font-mono font-bold ${dailyMetrics.totalProfit >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                ${dailyMetrics.totalProfit.toFixed(2)}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider font-bold">Win Rate</span>
              <span className="text-sm font-mono font-bold text-blue-400">
                {dailyMetrics.winRate.toFixed(1)}%
              </span>
            </div>
            <div className="flex flex-col">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider font-bold">Drawdown</span>
              <span className="text-sm font-mono font-bold text-red-400">
                {dailyMetrics.maxDrawdown.toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="flex flex-col items-end">
            <span className="text-xs text-gray-400 uppercase tracking-wider">Saldo</span>
            <span className="text-sm font-mono font-bold">${balance.toFixed(2)}</span>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-xs text-gray-400 uppercase tracking-wider">Patrimônio</span>
            <span className="text-sm font-mono font-bold">${equity.toFixed(2)}</span>
          </div>
        </div>
      </header>

      <main className="flex flex-1 overflow-hidden">
        <section className="flex-1 flex flex-col border-r border-[#27272a] bg-[#0a0a0a]">
          <div className="flex items-center justify-between px-4 py-2 bg-[#141414] border-b border-[#27272a]">
            <div className="flex items-center gap-3">
              <span className="font-bold text-lg text-blue-400">{currentAsset}</span>
              <span className="text-xs px-1.5 py-0.5 bg-[#27272a] rounded text-gray-300">M15</span>
              
              {/* REPLAY SPEED CONTROLS */}
              <div className="flex items-center gap-2 ml-4 px-2 border-l border-[#27272a]">
                <span className="text-[10px] font-bold text-purple-400 flex items-center gap-1">
                  <FastForward className="w-3 h-3" /> SPEED:
                </span>
                {[1, 2, 4, 10].map((v) => (
                  <button 
                    key={v}
                    onClick={() => {
                      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
                      axios.post(`${apiUrl}/api/set_replay_speed`, { speed: v }).catch(console.error);
                    }}
                    className="px-2 py-0.5 text-[10px] bg-[#27272a] hover:bg-purple-500/40 hover:text-white rounded transition-all text-gray-400"
                  >
                    {v}x
                  </button>
                ))}
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <button 
                onClick={() => setIsRobotPaused(!isRobotPaused)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded transition-colors ${
                  isRobotPaused 
                    ? 'bg-yellow-500/20 text-yellow-500 hover:bg-yellow-500/30' 
                    : 'bg-[#27272a] text-gray-300 hover:bg-[#3f3f46]'
                }`}
              >
                {isRobotPaused ? <PlayCircle className="w-4 h-4" /> : <PauseCircle className="w-4 h-4" />}
                {isRobotPaused ? 'RETOMAR ROBÔ' : 'PAUSAR ROBÔ'}
              </button>
              
              <button 
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded bg-red-500/20 text-red-500 hover:bg-red-500/30 transition-colors"
                onClick={() => confirm('Tem certeza que deseja zerar todas as posições abertas?') && console.log('Zerar posições acionado')}
              >
                <AlertTriangle className="w-4 h-4" />
                ZERAR POSIÇÕES
              </button>
            </div>

            <div className="flex items-center gap-4 text-sm font-mono">
               {chartData.length > 0 ? (
                 <>
                   <span className="text-gray-400">O: <span className="text-gray-200">{(chartData[chartData.length - 1] as any).open.toFixed(5)}</span></span>
                   <span className="text-gray-400">H: <span className="text-gray-200">{(chartData[chartData.length - 1] as any).high.toFixed(5)}</span></span>
                   <span className="text-gray-400">L: <span className="text-gray-200">{(chartData[chartData.length - 1] as any).low.toFixed(5)}</span></span>
                   <span className="text-gray-400">C: <span className="text-emerald-400 font-bold">{(chartData[chartData.length - 1] as any).close.toFixed(5)}</span></span>
                 </>
               ) : (
                 <span className="text-gray-500 italic">Aguardando dados...</span>
               )}
            </div>
          </div>
          <div className="flex-1 relative">
            <TradingChart data={chartData} visualStudies={visualStudies} markers={chartMarkers} />
          </div>
        </section>

        <aside className="w-96 flex flex-col bg-[#0f0f0f]">
          <div className="flex items-center justify-between px-4 py-2.5 bg-[#141414] border-b border-[#27272a]">
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-gray-400" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-300">Terminal IA</h2>
            </div>
            
            <div className="flex gap-2">
              {engineStatus === 'ONLINE' ? (
                <button 
                  onClick={() => sendEngineCommand('STOP')}
                  disabled={isCommanding}
                  className="p-1 bg-red-500/20 hover:bg-red-500/40 text-red-500 rounded border border-red-500/50 transition-all disabled:opacity-30"
                  title="Parar Motor Central AWS"
                >
                  <PauseCircle className="w-4 h-4 fill-current" />
                </button>
              ) : (
                <button 
                  onClick={() => sendEngineCommand('START')}
                  disabled={isCommanding}
                  className="p-1 bg-emerald-500/20 hover:bg-emerald-500/40 text-emerald-500 rounded border border-emerald-500/50 transition-all disabled:opacity-30"
                  title="Ligar Motor Central AWS"
                >
                  <PlayCircle className="w-4 h-4 fill-current" />
                </button>
              )}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-3">
            {aiLogs.length === 0 ? (
              <div className="text-gray-600 italic">Aguardando inicialização do motor de inferência...</div>
            ) : (
              aiLogs.map((log, index) => {
                let isAnalysis = log.type === 'ai_analysis';
                let parts = log.message ? log.message.split('\n') : [];
                
                return (
                  <div key={log.id || index} className="flex flex-col gap-1 border-l-2 border-[#27272a] pl-2 pb-2 mb-2 border-b border-[#27272a]/50 last:border-b-0">
                    <div className="flex items-center gap-2">
                      <span className="text-gray-500">{log.timestamp}</span>
                      <span className={`font-bold uppercase ${
                        log.type === 'error' ? 'text-red-400' : 
                        log.type === 'trade' ? 'text-emerald-400' : 
                        log.type === 'ai_analysis' ? 'text-purple-400' :
                        'text-blue-400'
                      }`}>
                        {log.type}
                      </span>
                    </div>
                    
                    {isAnalysis && parts.length > 1 ? (
                      <div className="space-y-1 mt-1">
                        <div className="font-bold text-white">{parts[0]}</div>
                        {parts.slice(1).map((part: string, idx: number) => {
                          if (part.startsWith('Regime:')) return <div key={idx} className="text-pink-300"><span className="font-bold">Regime:</span> {part.replace('Regime: ', '')}</div>;
                          if (part.startsWith('Estratégia:')) return <div key={idx} className="text-cyan-300"><span className="font-bold">Estratégia:</span> {part.replace('Estratégia: ', '')}</div>;
                          if (part.startsWith('Macro:')) return <div key={idx} className="text-purple-300"><span className="font-bold">Macro:</span> {part.replace('Macro: ', '')}</div>;
                          if (part.startsWith('Micro:')) return <div key={idx} className="text-blue-300"><span className="font-bold">Micro:</span> {part.replace('Micro: ', '')}</div>;
                          if (part.startsWith('Adaptabilidade:')) return <div key={idx} className="text-amber-300"><span className="font-bold">Adaptabilidade:</span> {part.replace('Adaptabilidade: ', '')}</div>;
                          if (part.startsWith('Motivo:')) return <div key={idx} className="text-gray-400 italic mt-1">{part}</div>;
                          return <div key={idx} className="text-gray-300">{part}</div>;
                        })}
                      </div>
                    ) : (
                      <span className={`
                        ${log.type === 'error' ? 'text-red-400' : ''}
                        ${log.type === 'warning' ? 'text-yellow-400' : ''}
                        ${log.type === 'trade' ? 'text-emerald-400' : ''}
                        ${log.type === 'info' ? 'text-blue-300' : ''}
                        ${!['error', 'warning', 'trade', 'ai_analysis', 'info'].includes(log.type) ? 'text-gray-300' : ''}
                      `}>
                        {log.message}
                      </span>
                    )}
                  </div>
                );
              })
            )}
            <div ref={logsEndRef} />
          </div>
        </aside>
      </main>

      <footer className="h-64 flex flex-col bg-[#141414] border-t border-[#27272a] shrink-0">
        <div className="flex items-center gap-6 px-4 py-2 border-b border-[#27272a] text-sm">
          <button className="font-semibold text-blue-400 border-b-2 border-blue-400 pb-1 -mb-[9px]">
            Posições Abertas ({openPositions.length})
          </button>
          <button className="font-semibold text-gray-500 hover:text-gray-300 pb-1 -mb-[9px]">
            Histórico
          </button>
        </div>
        <div className="flex-1 overflow-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-gray-400 uppercase bg-[#1a1a1a] sticky top-0">
              <tr>
                <th className="px-4 py-2 font-medium">Ticket</th>
                <th className="px-4 py-2 font-medium">Ativo</th>
                <th className="px-4 py-2 font-medium">Tipo</th>
                <th className="px-4 py-2 font-medium text-right">Volume</th>
                <th className="px-4 py-2 font-medium text-right">P. Abertura</th>
                <th className="px-4 py-2 font-medium text-right">P. Atual</th>
                <th className="px-4 py-2 font-medium text-right">Lucro</th>
              </tr>
            </thead>
            <tbody className="font-mono text-xs">
              {openPositions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-500 italic">
                    Nenhuma posição aberta no momento.
                  </td>
                </tr>
              ) : (
                openPositions.map((pos) => (
                  <tr key={pos.ticket} className="border-b border-[#27272a] hover:bg-[#1f1f1f] transition-colors">
                    <td className="px-4 py-2">{pos.ticket}</td>
                    <td className="px-4 py-2 font-bold">{pos.symbol}</td>
                    <td className={`px-4 py-2 font-bold ${pos.type === 'BUY' ? 'text-emerald-500' : 'text-red-500'}`}>
                      {pos.type}
                    </td>
                    <td className="px-4 py-2 text-right">{pos.volume.toFixed(2)}</td>
                    <td className="px-4 py-2 text-right">{pos.openPrice.toFixed(5)}</td>
                    <td className="px-4 py-2 text-right">{pos.currentPrice.toFixed(5)}</td>
                    <td className={`px-4 py-2 text-right font-bold ${pos.profit >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                      ${pos.profit.toFixed(2)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </footer>
      
      {session && (
        <SettingsPanel 
          isOpen={isSettingsOpen} 
          onClose={() => setIsSettingsOpen(false)} 
          userId={session.user.id}
        />
      )}
    </div>
  );
}