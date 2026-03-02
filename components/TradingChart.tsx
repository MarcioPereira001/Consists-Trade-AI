'use client';

import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, ISeriesApi, CandlestickData, Time, LineStyle, SeriesMarker } from 'lightweight-charts';

export interface VisualStudies {
  linhas_tendencia?: any[];
  suporte_resistencia?: any[];
  fibo_proposals?: any[];
  suporte?: number;
  resistencia?: number;
  tendencia_direcao?: 'UP' | 'DOWN' | 'SIDEWAYS';
  tendencia_preco?: number;
}

interface TradingChartProps {
  data: CandlestickData<Time>[];
  visualStudies?: VisualStudies;
  markers?: SeriesMarker<Time>[];
  armadilha?: { acao: string; preco_gatilho: number };
}

export default function TradingChart({ data, visualStudies, markers = [], armadilha }: TradingChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const ema9SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ema21SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const chartRef = useRef<any>(null);
  const priceLinesRef = useRef<any[]>([]);
  const lastDataLengthRef = useRef<number>(0);

  // Função para calcular EMA
  const calculateEMA = (data: CandlestickData<Time>[], period: number) => {
    if (!data || data.length === 0) return [];
    const emaData: { time: Time; value: number }[] = [];
    const k = 2 / (period + 1);
    let ema = data[0].close;
    
    for (let i = 0; i < data.length; i++) {
      if (i === 0) {
        emaData.push({ time: data[i].time, value: ema });
      } else {
        ema = (data[i].close - ema) * k + ema;
        emaData.push({ time: data[i].time, value: ema });
      }
    }
    return emaData;
  };

  // 1. Efeito de Inicialização do Gráfico
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#0a0a0a' },
        textColor: '#a1a1aa',
      },
      grid: {
        vertLines: { color: '#27272a', style: 1 },
        horzLines: { color: '#27272a', style: 1 },
      },
      crosshair: {
        mode: 1, 
        vertLine: { color: '#52525b', width: 1, style: 3, labelBackgroundColor: '#1f1f1f' },
        horzLine: { color: '#52525b', width: 1, style: 3, labelBackgroundColor: '#1f1f1f' },
      },
      timeScale: {
        borderColor: '#27272a',
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: { borderColor: '#27272a' },
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
    });

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });

    const ema9Series = chart.addLineSeries({
      color: '#eab308', // Amarelo
      lineWidth: 2,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    const ema21Series = chart.addLineSeries({
      color: '#38bdf8', // Azul Claro
      lineWidth: 2,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    // Se houver dados iniciais, carrega
    if (data && data.length > 0) {
      candlestickSeries.setData(data);
      ema9Series.setData(calculateEMA(data, 9));
      ema21Series.setData(calculateEMA(data, 21));
    }

    seriesRef.current = candlestickSeries;
    ema9SeriesRef.current = ema9Series;
    ema21SeriesRef.current = ema21Series;
    chartRef.current = chart;

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ 
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Roda apenas uma vez no mount

  // 2. Efeito para Sincronização de Dados (Full Set ou New Candle)
  useEffect(() => {
    if (!seriesRef.current || !data || data.length === 0) return;
    
    const currentDataLength = data.length;
    const previousDataLength = lastDataLengthRef.current;

    if (Math.abs(currentDataLength - previousDataLength) > 1 || previousDataLength === 0) {
      seriesRef.current.setData(data);
      if (ema9SeriesRef.current && ema21SeriesRef.current) {
        ema9SeriesRef.current.setData(calculateEMA(data, 9));
        ema21SeriesRef.current.setData(calculateEMA(data, 21));
      }
    } else {
      const lastItem = data[data.length - 1];
      if (lastItem) {
        seriesRef.current.update(lastItem);
        
        // Atualiza as EMAs
        if (ema9SeriesRef.current && ema21SeriesRef.current) {
          const ema9Data = calculateEMA(data, 9);
          const ema21Data = calculateEMA(data, 21);
          if (ema9Data.length > 0) ema9SeriesRef.current.update(ema9Data[ema9Data.length - 1]);
          if (ema21Data.length > 0) ema21SeriesRef.current.update(ema21Data[ema21Data.length - 1]);
        }
      }
    }
    
    lastDataLengthRef.current = currentDataLength;
  }, [data]);

  // 3. Efeito para as Setas de Compra/Venda (Markers) e Tendência da IA
  useEffect(() => {
    if (!seriesRef.current) return;
    
    let combinedMarkers = [...markers];
    
    // Adiciona o marcador de tendência da IA (LTA/LTB)
    if (visualStudies?.tendencia_direcao && data.length > 0) {
      const lastTime = data[data.length - 1].time;
      if (visualStudies.tendencia_direcao === 'UP') {
        combinedMarkers.push({
          time: lastTime,
          position: 'belowBar',
          color: '#10b981',
          shape: 'arrowUp',
          text: 'LTA (IA)',
          size: 2,
        });
      } else if (visualStudies.tendencia_direcao === 'DOWN') {
        combinedMarkers.push({
          time: lastTime,
          position: 'aboveBar',
          color: '#ef4444',
          shape: 'arrowDown',
          text: 'LTB (IA)',
          size: 2,
        });
      }
    }
    
    // Ordena marcadores por tempo para evitar erros do Lightweight Charts
    combinedMarkers.sort((a, b) => {
      const timeA = typeof a.time === 'string' ? new Date(a.time).getTime() : a.time as number;
      const timeB = typeof b.time === 'string' ? new Date(b.time).getTime() : b.time as number;
      return timeA - timeB;
    });
    
    seriesRef.current.setMarkers(combinedMarkers);
  }, [markers, visualStudies, data]);

  // 4. Efeito para Linhas da IA (Suporte, Resistência e Fibo) com Sanitização
  useEffect(() => {
    if (!seriesRef.current) return;
    const series = seriesRef.current;

    // Limpa linhas antigas
    priceLinesRef.current.forEach(line => series.removePriceLine(line));
    priceLinesRef.current = [];

    if (!visualStudies) return;

    // Desenha Suporte e Resistência (Protegido contra objetos)
    if (visualStudies.suporte_resistencia && Array.isArray(visualStudies.suporte_resistencia)) {
      visualStudies.suporte_resistencia.forEach(item => {
        const priceValue = typeof item === 'object' ? item.price : parseFloat(item);
        if (!isNaN(priceValue) && priceValue > 0) {
          const line = series.createPriceLine({
            price: priceValue,
            color: '#eab308', 
            lineWidth: 2,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: 'S/R IA',
          });
          priceLinesRef.current.push(line);
        }
      });
    }

    // Desenha Suporte Específico
    if (visualStudies.suporte && visualStudies.suporte > 0) {
      const line = series.createPriceLine({
        price: visualStudies.suporte,
        color: '#10b981', 
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        axisLabelVisible: true,
        title: 'SUPORTE (IA)',
      });
      priceLinesRef.current.push(line);
    }

    // Desenha Resistência Específica
    if (visualStudies.resistencia && visualStudies.resistencia > 0) {
      const line = series.createPriceLine({
        price: visualStudies.resistencia,
        color: '#ef4444', 
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        axisLabelVisible: true,
        title: 'RESISTÊNCIA (IA)',
      });
      priceLinesRef.current.push(line);
    }

    // Desenha Fibonacci (Protegido contra objetos)
    if (visualStudies.fibo_proposals && Array.isArray(visualStudies.fibo_proposals)) {
      visualStudies.fibo_proposals.forEach(fibo => {
        const fiboPrice = typeof fibo === 'object' ? parseFloat(fibo.price) : parseFloat(fibo);
        const fiboLevel = typeof fibo === 'object' ? fibo.level : 'Nível';
        if (!isNaN(fiboPrice) && fiboPrice > 0) {
          const line = series.createPriceLine({
            price: fiboPrice,
            color: '#8b5cf6', 
            lineWidth: 1,
            lineStyle: LineStyle.Dotted,
            axisLabelVisible: true,
            title: `Fibo ${fiboLevel}%`,
          });
          priceLinesRef.current.push(line);
        }
      });
    }
  }, [visualStudies]);

  // 5. Efeito para a Linha de Armadilha (Gatilho da IA)
  useEffect(() => {
    if (!seriesRef.current) return;
    const series = seriesRef.current;

    // Remove a linha de armadilha anterior se existir
    const existingTrapLine = priceLinesRef.current.find(l => l.options().title?.includes('GATILHO'));
    if (existingTrapLine) {
      series.removePriceLine(existingTrapLine);
      priceLinesRef.current = priceLinesRef.current.filter(l => l !== existingTrapLine);
    }

    if (armadilha && armadilha.acao !== 'NONE' && armadilha.preco_gatilho > 0) {
      const line = series.createPriceLine({
        price: armadilha.preco_gatilho,
        color: armadilha.acao === 'BUY' ? '#10b981' : '#ef4444', 
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: `🎯 GATILHO ${armadilha.acao}`,
      });
      priceLinesRef.current.push(line);
    }
  }, [armadilha]);

  return (
    <div ref={chartContainerRef} className="w-full h-full absolute inset-0" />
  );
}