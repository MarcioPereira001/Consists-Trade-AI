'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Activity, Wifi, WifiOff, BrainCircuit, Terminal, Server, Settings, AlertTriangle, PauseCircle, PlayCircle, LogOut } from 'lucide-react';
import TradingChart, { VisualStudies } from '@/components/TradingChart';
import SettingsPanel from '@/components/SettingsPanel';
import { CandlestickData, Time } from 'lightweight-charts';
import { useTradeStore } from '@/store/useTradeStore';
import { supabase } from '@/lib/supabase';
import { useRouter } from 'next/navigation';
import { Session } from '@supabase/supabase-js';

// Tipos base para os estados (preparando para o WebSocket)
type ConnectionStatus = 'connected' | 'disconnected' | 'connecting';
type TradeMode = 'DEMO' | 'REAL';

interface LogEntry {
  id: string;
  timestamp: string;
  message: string;
  type: 'info' | 'warning' | 'error' | 'trade' | 'ai_analysis';
}

export default function CockpitPage() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  
  // Estados Iniciais (Zero mocks, arrays vazios)
  const [mt5Status, setMt5Status] = useState<ConnectionStatus>('disconnected');
  const [aiStatus, setAiStatus] = useState<ConnectionStatus>('disconnected');
  const [tradeMode, setTradeMode] = useState<TradeMode>('DEMO');
  const [isRobotPaused, setIsRobotPaused] = useState(false);
  
  // Zustand Store
  const { balance, equity, openPositions, dailyMetrics } = useTradeStore();
  
  const [aiLogs, setAiLogs] = useState<LogEntry[]>([]);
  const [backendStatus, setBackendStatus] = useState<'offline' | 'online'>('offline');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Estudos Visuais Dinâmicos (Vindos da IA)
  const [visualStudies, setVisualStudies] = useState<VisualStudies | undefined>(undefined);

  useEffect(() => {
    // Verifica sessão inicial
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.push('/auth');
      } else {
        setSession(session);
      }
    });

    // Escuta mudanças de autenticação
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) {
        router.push('/auth');
      } else {
        setSession(session);
      }
    });

    return () => subscription.unsubscribe();
  }, [router]);

  useEffect(() => {
    // Auto-scroll para o final dos logs
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [aiLogs]);

  useEffect(() => {
    // Inicializa a conexão WebSocket com o backend
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/logs';
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setBackendStatus('online');
      setAiStatus('connected'); // Assumindo que o backend gerencia a IA
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setAiLogs((prev) => [...prev, data]);
        
        // Extrai estudos visuais se houver no log da IA
        if (data.type === 'ai_analysis' && data.estudos_visuais) {
          setVisualStudies(data.estudos_visuais);
        }
      } catch (error) {
        console.error('Erro ao fazer parse da mensagem do WebSocket:', error);
      }
    };

    ws.onclose = () => {
      setBackendStatus('offline');
      setAiStatus('disconnected');
    };

    ws.onerror = (error) => {
      // Evita poluir o console com erros de conexão quando o backend não está rodando localmente
      if (process.env.NODE_ENV === 'development') {
        console.warn('WebSocket desconectado ou falha na conexão.');
      }
      setBackendStatus('offline');
      setAiStatus('disconnected');
    };

    return () => {
      ws.close();
    };
  }, []);

  // Mock temporário apenas para validar a renderização visual do gráfico
  const initialChartData: CandlestickData<Time>[] = [
    { time: '2026-02-23' as Time, open: 1.0850, high: 1.0865, low: 1.0840, close: 1.0860 },
    { time: '2026-02-24' as Time, open: 1.0860, high: 1.0880, low: 1.0855, close: 1.0875 },
    { time: '2026-02-25' as Time, open: 1.0875, high: 1.0890, low: 1.0860, close: 1.0865 },
  ];

  return (
    <div className="flex flex-col h-screen bg-[#0a0a0a] text-gray-100 overflow-hidden font-sans">
      {/* HEADER */}
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
          {/* Métricas Rápidas */}
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

      {/* MAIN CONTENT */}
      <main className="flex flex-1 overflow-hidden">
        {/* CHART AREA */}
        <section className="flex-1 flex flex-col border-r border-[#27272a] bg-[#0a0a0a]">
          <div className="flex items-center justify-between px-4 py-2 bg-[#141414] border-b border-[#27272a]">
            <div className="flex items-center gap-3">
              <span className="font-bold text-lg">EURUSD</span>
              <span className="text-xs px-1.5 py-0.5 bg-[#27272a] rounded text-gray-300">M15</span>
            </div>
            
            {/* Controles Operacionais */}
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
              <span className="text-gray-400">O: <span className="text-gray-200">0.00000</span></span>
              <span className="text-gray-400">H: <span className="text-gray-200">0.00000</span></span>
              <span className="text-gray-400">L: <span className="text-gray-200">0.00000</span></span>
              <span className="text-gray-400">C: <span className="text-gray-200">0.00000</span></span>
            </div>
          </div>
          <div className="flex-1 relative">
            <TradingChart data={initialChartData} visualStudies={visualStudies} />
          </div>
        </section>

        {/* AI LOGS TERMINAL */}
        <aside className="w-96 flex flex-col bg-[#0f0f0f]">
          <div className="flex items-center gap-2 px-4 py-2.5 bg-[#141414] border-b border-[#27272a]">
            <Terminal className="w-4 h-4 text-gray-400" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-300">Terminal IA</h2>
          </div>
          <div className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-3">
            {aiLogs.length === 0 ? (
              <div className="text-gray-600 italic">Aguardando inicialização do motor de inferência...</div>
            ) : (
              aiLogs.map((log) => {
                let isAnalysis = log.type === 'ai_analysis';
                let parts = log.message.split('\n');
                
                return (
                  <div key={log.id} className="flex flex-col gap-1 border-l-2 border-[#27272a] pl-2 pb-2 mb-2 border-b border-[#27272a]/50 last:border-b-0">
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

      {/* FOOTER - POSITIONS & HISTORY */}
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
                <th className="px-4 py-2 font-medium">Volume</th>
                <th className="px-4 py-2 font-medium">Preço Abertura</th>
                <th className="px-4 py-2 font-medium">Preço Atual</th>
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
                  <tr key={pos.ticket} className="border-b border-[#27272a] hover:bg-[#1f1f1f]">
                    <td className="px-4 py-2">{pos.ticket}</td>
                    <td className="px-4 py-2 font-bold">{pos.symbol}</td>
                    <td className={`px-4 py-2 font-bold ${pos.type === 'BUY' ? 'text-emerald-500' : 'text-red-500'}`}>
                      {pos.type}
                    </td>
                    <td className="px-4 py-2">{pos.volume.toFixed(2)}</td>
                    <td className="px-4 py-2">{pos.openPrice.toFixed(5)}</td>
                    <td className="px-4 py-2">{pos.currentPrice.toFixed(5)}</td>
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
      
      {/* MODAL DE CONFIGURAÇÕES */}
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
