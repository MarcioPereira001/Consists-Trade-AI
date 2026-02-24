'use client';

import React, { useState, useEffect } from 'react';
import { X, Save, Loader2 } from 'lucide-react';
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
}

export default function SettingsPanel({ isOpen, onClose, userId }: SettingsPanelProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [config, setConfig] = useState<TradeConfig>({
    profile_id: userId,
    ativo: 'EURUSD',
    lote: 0.01,
    stop_loss: 100,
    take_profit: 200,
    estrategia_ativa: 'Smart Money Concepts (SMC)',
    modo_operacional: 'DEMO',
    ambiente: 'AO VIVO',
    horario_inicio: '09:00',
    horario_fim: '17:30',
    data_replay_inicio: new Date().toISOString().split('T')[0],
    data_replay_fim: new Date().toISOString().split('T')[0],
  });

  // Carregar configurações iniciais (se existirem)
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const { data, error } = await supabase
          .from('trade_configs')
          .select('*')
          .eq('profile_id', userId)
          .single();

        if (error && error.code !== 'PGRST116') { // PGRST116 é "nenhuma linha encontrada"
          console.error('Erro ao carregar configurações:', error);
        } else if (data) {
          setConfig(data);
        }
      } catch (error) {
        console.error('Erro inesperado:', error);
      }
    };

    if (isOpen && userId) {
      loadConfig();
    }
  }, [isOpen, userId]);

  const handleSave = async () => {
    setIsLoading(true);
    try {
      const configToSave = {
        ...config,
        updated_at: new Date().toISOString(),
      };

      let error;
      if (config.id) {
        const { error: updateError } = await supabase
          .from('trade_configs')
          .update(configToSave)
          .eq('id', config.id);
        error = updateError;
      } else {
        const { error: insertError } = await supabase
          .from('trade_configs')
          .insert([configToSave]);
        error = insertError;
      }

      if (error) {
        console.error('Erro ao salvar configurações:', error);
        alert('Erro ao salvar configurações. Verifique o console.');
      } else {
        alert('Configurações salvas com sucesso!');
        onClose();
      }
    } catch (error) {
      console.error('Erro inesperado ao salvar:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md h-full bg-[#141414] border-l border-[#27272a] shadow-2xl flex flex-col animate-in slide-in-from-right">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#27272a]">
          <h2 className="text-lg font-bold tracking-tight text-gray-100">Configurações do Motor</h2>
          <button 
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-100 hover:bg-[#27272a] rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Ambiente */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-300">Ambiente de Execução</label>
            <div className="flex bg-[#0a0a0a] border border-[#27272a] rounded-md p-1">
              <button
                onClick={() => setConfig({...config, ambiente: 'AO VIVO'})}
                className={`flex-1 py-1.5 text-sm font-bold rounded ${config.ambiente === 'AO VIVO' ? 'bg-emerald-500/20 text-emerald-500' : 'text-gray-500 hover:text-gray-300'}`}
              >
                AO VIVO
              </button>
              <button
                onClick={() => setConfig({...config, ambiente: 'REPLAY HISTÓRICO'})}
                className={`flex-1 py-1.5 text-sm font-bold rounded ${config.ambiente === 'REPLAY HISTÓRICO' ? 'bg-purple-500/20 text-purple-500' : 'text-gray-500 hover:text-gray-300'}`}
              >
                REPLAY
              </button>
            </div>
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
              <label className="text-sm font-medium text-gray-300">Stop Loss (pts)</label>
              <input 
                type="number" 
                value={Number.isNaN(config.stop_loss) ? '' : config.stop_loss}
                onChange={(e) => setConfig({...config, stop_loss: e.target.value === '' ? 0 : parseInt(e.target.value)})}
                className="w-full bg-[#0a0a0a] border border-[#27272a] rounded-md px-3 py-2 text-sm text-red-400 focus:outline-none focus:border-red-500 font-mono"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">Take Profit (pts)</label>
              <input 
                type="number" 
                value={Number.isNaN(config.take_profit) ? '' : config.take_profit}
                onChange={(e) => setConfig({...config, take_profit: e.target.value === '' ? 0 : parseInt(e.target.value)})}
                className="w-full bg-[#0a0a0a] border border-[#27272a] rounded-md px-3 py-2 text-sm text-emerald-400 focus:outline-none focus:border-emerald-500 font-mono"
              />
            </div>
          </div>

          {/* Horário de Operação */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">Horário Início</label>
              <input 
                type="time" 
                value={config.horario_inicio}
                onChange={(e) => setConfig({...config, horario_inicio: e.target.value})}
                className="w-full bg-[#0a0a0a] border border-[#27272a] rounded-md px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-300">Horário Fim</label>
              <input 
                type="time" 
                value={config.horario_fim}
                onChange={(e) => setConfig({...config, horario_fim: e.target.value})}
                className="w-full bg-[#0a0a0a] border border-[#27272a] rounded-md px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>
          </div>

          {/* Modo Operacional */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-300">Modo Operacional</label>
            <div className="flex bg-[#0a0a0a] border border-[#27272a] rounded-md p-1">
              <button
                onClick={() => setConfig({...config, modo_operacional: 'DEMO'})}
                className={`flex-1 py-1.5 text-sm font-bold rounded ${config.modo_operacional === 'DEMO' ? 'bg-blue-500/20 text-blue-500' : 'text-gray-500 hover:text-gray-300'}`}
              >
                DEMO
              </button>
              <button
                onClick={() => setConfig({...config, modo_operacional: 'REAL'})}
                className={`flex-1 py-1.5 text-sm font-bold rounded ${config.modo_operacional === 'REAL' ? 'bg-red-500/20 text-red-500' : 'text-gray-500 hover:text-gray-300'}`}
              >
                REAL
              </button>
            </div>
          </div>

          {/* Estratégia */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-300">Estratégia Base</label>
            <select 
              value={config.estrategia_ativa}
              onChange={(e) => setConfig({...config, estrategia_ativa: e.target.value})}
              className="w-full bg-[#0a0a0a] border border-[#27272a] rounded-md px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
            >
              <option value="Adaptável (Camaleão / Dinâmica)">Adaptável (Camaleão / Dinâmica)</option>
              <option value="Smart Money Concepts (SMC)">Smart Money Concepts (SMC)</option>
              <option value="Wyckoff">Wyckoff</option>
              <option value="Fractal Chaos">Fractal Chaos</option>
              <option value="Price Action Limpo">Price Action Limpo</option>
              <option value="Rompimento com Volume">Rompimento com Volume</option>
              <option value="Cruzamento de Médias">Cruzamento de Médias</option>
            </select>
          </div>
        </div>

        <div className="p-6 border-t border-[#27272a] bg-[#141414]">
          <button 
            onClick={handleSave}
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 px-4 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                <Save className="w-5 h-5" />
                Salvar Configurações
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
