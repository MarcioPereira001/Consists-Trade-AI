'use client';

import React, { useState, useEffect } from 'react';
import { 
  X, Save, Loader2, Target, Globe, Landmark, 
  TrendingUp, AlertTriangle, ShieldCheck, Zap, 
  ChevronRight, Calendar, Activity, Lock, 
  MousePointer2, RefreshCcw, BarChart3
} from 'lucide-react';
import { supabase } from '@/lib/supabase';

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  userId: string;
}

interface TradeConfig {
  id?: string;
  profile_id: string;
  ativo: string;
  lote: number;
  stop_loss: number;
  take_profit: number;
  estrategia_ativa: string;
  modo_operacional: 'DEMO' | 'REAL';
  ambiente: 'AO VIVO' | 'REPLAY HISTÓRICO';
  horario_inicio: string;
  horario_fim: string;
  data_replay_inicio?: string;
  data_replay_fim?: string;
  meta_diaria: number;
  limite_perda: number;
  trailing_stop_auto: boolean;
  auto_decisao_ia: boolean;
  agressividade: 'CONSERVADOR' | 'MODERADO' | 'SNIPER' | 'SCALPER';
}

// --- MOTOR GERADOR DE TICKERS B3 (AUTO-ATUALIZÁVEL) ---
const generateB3Symbols = () => {
  const now = new Date();
  let year = now.getFullYear() % 100;
  const month = now.getMonth() + 1; // 1-12
  const day = now.getDate();

  const letters = ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z'];
  
  // Dólar e BIT (Vence todo mês. O contrato negociado é sempre o do mês seguinte)
  const currentMonthIdx = month - 1;
  const activeWdoIdx = (currentMonthIdx + 1) % 12; 
  const nextWdoIdx = (currentMonthIdx + 2) % 12;
  
  const wdoYear = activeWdoIdx < currentMonthIdx ? year + 1 : year;
  const nextWdoYear = nextWdoIdx < activeWdoIdx ? year + 1 : year;

  // Índice (Vence meses pares. Acontece perto do dia 15)
  const winMap = ['G', 'G', 'J', 'J', 'M', 'M', 'Q', 'Q', 'V', 'V', 'Z', 'Z'];
  let activeWinLetter = winMap[month - 1];
  let winYear = year;
  
  if (month % 2 === 0 && day >= 15) {
      activeWinLetter = winMap[(month) % 12];
      if (month === 12) winYear += 1;
  }

  return {
    win: `WIN${activeWinLetter}${winYear}`,
    wdoAtual: `WDO${letters[activeWdoIdx]}${wdoYear}`,
    wdoProx: `WDO${letters[nextWdoIdx]}${nextWdoYear}`,
    bitAtual: `BIT${letters[activeWdoIdx]}${wdoYear}`,
    bitProx: `BIT${letters[nextWdoIdx]}${nextWdoYear}`,
  };
};

export default function SettingsPanel({ isOpen, onClose, userId }: SettingsPanelProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [marketType, setMarketType] = useState<'B3' | 'FOREX_CRYPTO'>('B3');
  
  const [config, setConfig] = useState<TradeConfig>({
    profile_id: userId,
    ativo: 'BITG26', // MUDE DE 'EURUSD' PARA 'WINJ26' AQUI
    lote: 1.0,
    stop_loss: 100,
    take_profit: 200,
    estrategia_ativa: 'Adaptável (Camaleão / Dinâmica)',
    modo_operacional: 'DEMO',
    ambiente: 'AO VIVO',
    horario_inicio: '09:00',
    horario_fim: '17:30',
    data_replay_inicio: new Date().toISOString().split('T')[0],
    data_replay_fim: new Date().toISOString().split('T')[0],
    meta_diaria: 500,
    limite_perda: -250,
    trailing_stop_auto: true,
    auto_decisao_ia: false,
    agressividade: 'MODERADO'
  });

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const { data, error } = await supabase
          .from('trade_configs')
          .select('*')
          .eq('profile_id', userId)
          .single();

        if (error && error.code !== 'PGRST116') {
          console.error('Erro ao carregar configurações:', error);
        } else if (data) {
          setConfig(data);
          const b3Keywords = ['WIN', 'WDO', 'VALE', 'PETR', 'BITH', 'ITUB', 'BBDC', 'ABEV', 'BBAS', 'MGLU'];
          const isB3 = b3Keywords.some(keyword => data.ativo?.toUpperCase().includes(keyword));
          setMarketType(isB3 ? 'B3' : 'FOREX_CRYPTO');
        }
      } catch (err) {
        console.error('Erro inesperado no carregamento:', err);
      }
    };

    if (isOpen && userId) loadConfig();
  }, [isOpen, userId]);

  const handleSave = async () => {
    setIsLoading(true);
    
    try {
      // 1. Tenta salvar normalmente (Update)
      const { id, ...configSemId } = config;
      const { error } = await supabase
        .from('trade_configs')
        .upsert(
          { ...configSemId, profile_id: userId, updated_at: new Date().toISOString() }, 
          { onConflict: 'profile_id' }
        );

      if (error) throw error;
      
      alert('Sincronização com o Cérebro IA Concluída!');
      
      // Recarrega os dados fresquinhos do banco
      const { data: updatedData } = await supabase
        .from('trade_configs')
        .select('*')
        .eq('profile_id', userId)
        .single();
          
      if (updatedData) {
        setConfig(updatedData);
      }
      
      onClose();

    } catch (err) {
      // 2. Se der erro, tenta o plano B (Força o Upsert limpando o ID)
      console.warn('Tentativa primária falhou, tentando fallback (Upsert):', err);
      
      try {
        const { id, ...configSemId } = config;
        const configToSave = {
          ...configSemId,
          profile_id: userId,
          updated_at: new Date().toISOString(),
        };

        const { error: upsertError } = await supabase
          .from('trade_configs')
          .upsert(configToSave, { onConflict: 'profile_id' });

        if (upsertError) {
          console.error('Erro crítico ao salvar configurações:', upsertError);
          alert('Erro ao salvar configurações. Verifique o console.');
        } else {
          alert('Configurações salvas com sucesso no modo de segurança!');
          onClose();
        }
      } catch (fallbackError) {
        console.error('Erro inesperado no Fallback:', fallbackError);
      }
      
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/80 backdrop-blur-md">
      <div className="w-full max-w-xl h-full bg-[#0a0a0a] border-l border-zinc-800 shadow-2xl flex flex-col animate-in slide-in-from-right">
        
        {/* HEADER */}
        <div className="px-8 py-6 border-b border-zinc-800 bg-[#111] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ShieldCheck className="text-blue-500 w-6 h-6" />
            <h2 className="text-xl font-black text-white tracking-tighter uppercase">Configurações do Motor Sniper</h2>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-zinc-800 rounded-full transition-all text-zinc-500 hover:text-white">
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* CONTEÚDO EM FLUXO ÚNICO (ESTÁVEL) */}
        <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar pb-32">
          
          {/* SEÇÃO 1: MERCADO E ATIVOS */}
          <div className="space-y-6 border-b border-zinc-800 pb-8">
            <div className="flex items-center gap-2 text-blue-500 font-black text-[10px] uppercase tracking-widest">
              <Globe className="w-3 h-3" /> Domínio Operacional
            </div>
            <div className="grid grid-cols-2 gap-4">
              <button onClick={() => setMarketType('B3')} className={`py-4 rounded-xl border-2 font-black text-xs flex items-center justify-center gap-2 ${marketType === 'B3' ? 'border-yellow-500/50 bg-yellow-500/10 text-yellow-500' : 'border-zinc-800 text-zinc-600'}`}>
                <Landmark className="w-4 h-4" /> B3 BRASIL
              </button>
              <button onClick={() => setMarketType('FOREX_CRYPTO')} className={`py-4 rounded-xl border-2 font-black text-xs flex items-center justify-center gap-2 ${marketType === 'FOREX_CRYPTO' ? 'border-blue-500/50 bg-blue-500/10 text-blue-500' : 'border-zinc-800 text-zinc-600'}`}>
                <Globe className="w-4 h-4" /> FOREX / CRYPTO
              </button>
            </div>

          {/* Datas do Replay (Só aparece se for Replay) */}
          {config.ambiente === 'REPLAY HISTÓRICO' && (
            <div className="grid grid-cols-2 gap-4 p-3 bg-purple-500/10 border border-purple-500/20 rounded-md">
              <div className="space-y-2">
                <label className="text-sm font-medium text-purple-300">Data Início (Replay)</label>
                <input 
                  type="date" 
                  value={config.data_replay_inicio}
                  onChange={(e) => setConfig({...config, data_replay_inicio: e.target.value})}
                  className="w-full bg-[#0a0a0a] border border-[#27272a] rounded-md px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-purple-500"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-purple-300">Data Fim (Replay)</label>
                <input 
                  type="date" 
                  value={config.data_replay_fim}
                  onChange={(e) => setConfig({...config, data_replay_fim: e.target.value})}
                  className="w-full bg-[#0a0a0a] border border-[#27272a] rounded-md px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-purple-500"
                />
              </div>
            </div>
          )}

          {/* Ativo */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-300">Ativo Operacional</label>
            <select 
              value={config.ativo}
              onChange={(e) => setConfig({...config, ativo: e.target.value})}
              className="w-full bg-[#0a0a0a] border border-[#27272a] rounded-md px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
            >
              <optgroup label="Forex Majors">
                <option value="EURUSD">EURUSD</option>
                <option value="GBPUSD">GBPUSD</option>
                <option value="USDJPY">USDJPY</option>
                <option value="USDCHF">USDCHF</option>
                <option value="AUDUSD">AUDUSD</option>
                <option value="USDCAD">USDCAD</option>
              </optgroup>
              <optgroup label="Índices Globais">
                <option value="SP500">SP500 (S&P 500)</option>
                <option value="US30">US30 (Dow Jones)</option>
                <option value="NAS100">NAS100 (Nasdaq)</option>
                <option value="GER40">GER40 (DAX)</option>
              </optgroup>
              <optgroup label="Commodities">
                <option value="XAUUSD">XAUUSD (Ouro)</option>
                <option value="XAGUSD">XAGUSD (Prata)</option>
                <option value="USOIL">USOIL (Petróleo WTI)</option>
              </optgroup>
              <optgroup label="Criptomoedas">
                <option value="BTCUSD">BTCUSD (Bitcoin)</option>
                <option value="ETHUSD">ETHUSD (Ethereum)</option>
              </optgroup>
              <optgroup label="B3 (Brasil)">
                <option value="WINJ26">WINJ26 (Mini Índice)</option>
                <option value="WDOJ26">WDOJ26 (Mini Dólar)</option>
              </optgroup>
            </select>
          </div>

          {/* Lote */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-300">Tamanho do Lote</label>
            <input 
              type="number" 
              step="0.01"
              value={Number.isNaN(config.lote) ? '' : config.lote}
              onChange={(e) => setConfig({...config, lote: e.target.value === '' ? 0 : parseFloat(e.target.value)})}
              className="w-full bg-[#0a0a0a] border border-[#27272a] rounded-md px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500 font-mono"
            />
          </div>

          {/* Stop Loss & Take Profit */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-zinc-500 uppercase">Ativo para Análise</label>
              <select 
                value={config.ativo}
                onChange={(e) => setConfig({...config, ativo: e.target.value})}
                className="w-full bg-black border border-zinc-800 rounded-xl p-4 text-white font-bold appearance-none focus:border-blue-500"
              >
                {marketType === 'B3' ? (
                  (() => {
                    const b3 = generateB3Symbols();
                    return (
                      <>
                        <optgroup label="MINI CONTRATOS (AUTO-ATUALIZADOS)">
                          <option value={b3.win}>{b3.win} (Índice Atual)</option>
                          <option value={b3.wdoAtual}>{b3.wdoAtual} (Dólar Atual)</option>
                          <option value={b3.wdoProx}>{b3.wdoProx} (Dólar Próximo)</option>
                        </optgroup>
                        <optgroup label="CRIPTO FUTUROS B3 (AUTO-ATUALIZADOS)">
                          <option value={b3.bitAtual}>{b3.bitAtual} (Bitcoin Atual)</option>
                          <option value={b3.bitProx}>{b3.bitProx} (Bitcoin Próximo)</option>
                          <option value="BITH11">BITH11 (ETF Bitcoin)</option>
                          <option value="ETHE11">ETHE11 (ETF Ethereum)</option>
                        </optgroup>
                        <optgroup label="BLUE CHIPS">
                          <option value="PETR4">PETR4</option>
                          <option value="VALE3">VALE3</option>
                          <option value="ITUB4">ITUB4</option>
                          <option value="BBAS3">BBAS3</option>
                        </optgroup>
                      </>
                    );
                  })()
                ) : (
                  <>
                    <optgroup label="FOREX">
                      <option value="EURUSD">EURUSD</option>
                      <option value="GBPUSD">GBPUSD</option>
                      <option value="USDJPY">USDJPY</option>
                      <option value="XAUUSD">GOLD</option>
                    </optgroup>
                    <optgroup label="GLOBAL CRIPTO">
                      <option value="BTCUSD">BITCOIN</option>
                      <option value="ETHUSD">ETHEREUM</option>
                    </optgroup>
                  </>
                )}
              </select>
            </div>
          </div>

          {/* SEÇÃO 2: AMBIENTE E REPLAY */}
          <div className="space-y-6 border-b border-zinc-800 pb-8">
            <div className="grid grid-cols-2 gap-4">
              <button onClick={() => setConfig({...config, ambiente: 'AO VIVO'})} className={`py-4 rounded-xl border-2 font-bold text-xs flex items-center justify-center gap-2 ${config.ambiente === 'AO VIVO' ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-500' : 'border-zinc-800 text-zinc-600'}`}>
                <Activity className="w-4 h-4" /> AO VIVO
              </button>
              <button onClick={() => setConfig({...config, ambiente: 'REPLAY HISTÓRICO'})} className={`py-4 rounded-xl border-2 font-bold text-xs flex items-center justify-center gap-2 ${config.ambiente === 'REPLAY HISTÓRICO' ? 'border-purple-500/50 bg-purple-500/10 text-purple-500' : 'border-zinc-800 text-zinc-600'}`}>
                <Calendar className="w-4 h-4" /> REPLAY
              </button>
            </div>

            {config.ambiente === 'REPLAY HISTÓRICO' && (
              <div className="grid grid-cols-2 gap-4 p-4 bg-purple-500/5 border border-purple-500/10 rounded-xl">
                <div className="space-y-1">
                  <label className="text-[10px] font-black text-purple-400 uppercase">Data Início</label>
                  <input type="date" value={config.data_replay_inicio} onChange={(e) => setConfig({...config, data_replay_inicio: e.target.value})} className="w-full bg-black border border-zinc-800 rounded p-2 text-white text-xs font-mono" />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-black text-purple-400 uppercase">Data Fim</label>
                  <input type="date" value={config.data_replay_fim} onChange={(e) => setConfig({...config, data_replay_fim: e.target.value})} className="w-full bg-black border border-zinc-800 rounded p-2 text-white text-xs font-mono" />
                </div>
              </div>
            )}
          </div>

          {/* SEÇÃO 3: GESTÃO DE RISCO */}
          <div className="space-y-6 border-b border-zinc-800 pb-8">
            <div className="p-6 bg-blue-500/5 border border-blue-500/10 rounded-2xl space-y-4">
              <h3 className="text-xs font-black text-blue-500 uppercase tracking-widest flex items-center gap-2"><Target className="w-4 h-4" /> Gestão de Risco Inquebrável</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-zinc-500 uppercase">Meta Diária ($)</label>
                  <input type="number" value={config.meta_diaria} onChange={(e) => setConfig({...config, meta_diaria: parseFloat(e.target.value)})} className="w-full bg-black border border-zinc-800 rounded-lg p-3 text-emerald-400 font-mono font-bold" />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-zinc-500 uppercase">Stop Diário ($)</label>
                  <input type="number" value={config.limite_perda} onChange={(e) => setConfig({...config, limite_perda: parseFloat(e.target.value)})} className="w-full bg-black border border-zinc-800 rounded-lg p-3 text-red-500 font-mono font-bold" />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-bold text-zinc-500 uppercase">Lote</label>
                <input type="number" step="0.01" value={config.lote} onChange={(e) => setConfig({...config, lote: parseFloat(e.target.value)})} className="w-full bg-black border border-zinc-800 rounded-lg p-3 text-white font-mono" />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-bold text-zinc-500 uppercase">Horário Fim</label>
                <input type="time" value={config.horario_fim} onChange={(e) => setConfig({...config, horario_fim: e.target.value})} className="w-full bg-black border border-zinc-800 rounded-lg p-3 text-white font-mono" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-red-500/5 border border-red-500/10 rounded-xl">
                <label className="text-[10px] font-black text-red-400 uppercase block mb-1">Stop Loss (pts)</label>
                <input type="number" value={config.stop_loss} onChange={(e) => setConfig({...config, stop_loss: parseInt(e.target.value)})} className="w-full bg-transparent text-xl font-bold text-white outline-none" />
              </div>
              <div className="p-4 bg-emerald-500/5 border border-emerald-500/10 rounded-xl">
                <label className="text-[10px] font-black text-emerald-400 uppercase block mb-1">Take Profit (pts)</label>
                <input type="number" value={config.take_profit} onChange={(e) => setConfig({...config, take_profit: parseInt(e.target.value)})} className="w-full bg-transparent text-xl font-bold text-white outline-none" />
              </div>
            </div>
          </div>

          {/* SEÇÃO 4: ESTRATÉGIA IA E CAMALEÃO */}
          <div className="space-y-6">
            <div className="space-y-3">
              <label className="text-xs font-black text-zinc-500 uppercase tracking-widest flex items-center gap-2"><Zap className="w-4 h-4 text-purple-500" /> Estratégia Adaptável</label>
              <select 
                value={config.estrategia_ativa}
                onChange={(e) => setConfig({...config, estrategia_ativa: e.target.value})}
                className="w-full bg-black border border-zinc-800 rounded-xl p-5 text-blue-400 font-black text-lg focus:border-blue-500"
              >
                <option value="Adaptável (Camaleão / Dinâmica)">Adaptável (Camaleão / Dinâmica)</option>
                <option value="Smart Money Concepts (SMC)">Smart Money Concepts (SMC)</option>
                <option value="Wyckoff Institutional">Wyckoff Institutional</option>
                <option value="Fractal Chaos V5">Fractal Chaos V5</option>
                <option value="Volume Spread Analysis (VSA)">Volume Spread Analysis (VSA)</option>
                <option value="Price Action Limpo">Price Action Limpo</option>
              </select>
              <p className="text-[10px] text-zinc-600 px-2 italic">* O modo Camaleão alterna dinamicamente entre padrões de mercado e candle.</p>
            </div>

            {/* AUTOMAÇÃO SNIPER */}
            <div className="space-y-4">
              <h4 className="text-[10px] font-black text-zinc-500 uppercase tracking-widest flex items-center gap-2"><BarChart3 className="w-3 h-3 text-yellow-500" /> Automação de Decisão Sniper</h4>
              <div className="grid grid-cols-1 gap-4">
                {/* Trailing Stop */}
                <button 
                  onClick={() => setConfig({...config, trailing_stop_auto: !config.trailing_stop_auto})}
                  className={`flex items-center justify-between p-5 rounded-2xl border-2 transition-all ${config.trailing_stop_auto ? 'border-blue-500 bg-blue-500/5 text-white' : 'border-zinc-800 text-zinc-600'}`}
                >
                  <div className="text-left">
                    <p className="text-sm font-black">Trailing Stop Inteligente</p>
                    <p className="text-[9px] opacity-60 uppercase">Move o stop conforme o volume e o gain crescem.</p>
                  </div>
                  <div className={`w-10 h-5 rounded-full relative transition-all ${config.trailing_stop_auto ? 'bg-blue-500' : 'bg-zinc-800'}`}>
                    <div className={`absolute top-1 w-3 h-3 bg-white rounded-full transition-all ${config.trailing_stop_auto ? 'right-1' : 'left-1'}`} />
                  </div>
                </button>

                {/* Auto Decisão IA */}
                <button 
                  onClick={() => setConfig({...config, auto_decisao_ia: !config.auto_decisao_ia})}
                  className={`flex items-center justify-between p-5 rounded-2xl border-2 transition-all ${config.auto_decisao_ia ? 'border-orange-500 bg-orange-500/5 text-white' : 'border-zinc-800 text-zinc-600'}`}
                >
                  <div className="text-left">
                    <p className="text-sm font-black">Modo Auto-Gestão (Zero Humano)</p>
                    <p className="text-[9px] opacity-60 uppercase">IA fecha posição ao detectar exaustão ou mudança de fluxo.</p>
                  </div>
                  <div className={`w-10 h-5 rounded-full relative transition-all ${config.auto_decisao_ia ? 'bg-orange-500' : 'bg-zinc-800'}`}>
                    <div className={`absolute top-1 w-3 h-3 bg-white rounded-full transition-all ${config.auto_decisao_ia ? 'right-1' : 'left-1'}`} />
                  </div>
                </button>
              </div>
            </div>

            <div className="space-y-4">
              <label className="text-xs font-black text-zinc-500 uppercase tracking-widest">Rigor Operacional (Agressividade)</label>
              <div className="grid grid-cols-4 gap-2">
                {(['CONSERVADOR', 'MODERADO', 'SNIPER', 'SCALPER'] as const).map((n) => (
                  <button 
                    key={n}
                    onClick={() => setConfig({...config, agressividade: n})}
                    className={`py-2 text-[9px] font-black rounded-xl border-2 transition-all ${config.agressividade === n ? 'bg-white text-black border-white shadow-[0_0_15px_rgba(255,255,255,0.2)]' : 'bg-transparent text-zinc-600 border-zinc-800 hover:border-zinc-700 hover:text-white'}`}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex bg-black rounded-lg p-1 border border-zinc-800">
              <button onClick={() => setConfig({...config, modo_operacional: 'DEMO'})} className={`flex-1 py-3 text-[10px] font-black rounded-md ${config.modo_operacional === 'DEMO' ? 'bg-blue-600 text-white' : 'text-zinc-600'}`}>DEMO MODE</button>
              <button onClick={() => setConfig({...config, modo_operacional: 'REAL'})} className={`flex-1 py-3 text-[10px] font-black rounded-md ${config.modo_operacional === 'REAL' ? 'bg-red-600 text-white' : 'text-zinc-600'}`}>REAL ACCOUNT</button>
            </div>
          </div>
        </div>

        {/* FOOTER FIXO */}
        <div className="absolute bottom-0 left-0 right-0 p-8 bg-[#0a0a0a]/90 backdrop-blur-md border-t border-zinc-800">
          <button 
            onClick={handleSave} 
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-3 bg-blue-600 hover:bg-blue-500 text-white font-black py-5 rounded-2xl transition-all shadow-[0_10px_30px_-10px_rgba(37,99,235,0.5)] active:scale-[0.98] disabled:opacity-50"
          >
            {isLoading ? <Loader2 className="w-6 h-6 animate-spin" /> : <><Save className="w-6 h-6" /> SINCRONIZAR TERMINAL SNIPER</>}
          </button>
        </div>
      </div>
    </div>
  );
}