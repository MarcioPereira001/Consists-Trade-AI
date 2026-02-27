'use client';

import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, ISeriesApi, CandlestickData, Time, LineStyle, SeriesMarker } from 'lightweight-charts';

export interface VisualStudies {
  linhas_tendencia?: { id: string; p1: { time: string; price: number }; p2: { time: string; price: number } }[];
  suporte_resistencia?: any[]; // Alterado para any para aceitar objetos da IA antes da sanitização
  fibo_proposals?: any[];      // Alterado para any para aceitar objetos da IA antes da sanitização
}

interface TradingChartProps {
  data: CandlestickData<Time>[];
  visualStudies?: VisualStudies;
  markers?: SeriesMarker<Time>[];
}

export default function TradingChart({ data, visualStudies, markers = [] }: TradingChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const chartRef = useRef<any>(null);
  const priceLinesRef = useRef<any[]>([]);

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

    // Se houver dados iniciais, carrega
    if (data && data.length > 0) {
      candlestickSeries.setData(data);
    }

    seriesRef.current = candlestickSeries;
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
  }, []); // Roda apenas uma vez no mount

  // 2. Efeito para Sincronização de Dados (Full Set ou New Candle)
  useEffect(() => {
    if (!seriesRef.current || !data) return;
    
    // Se a quantidade de dados mudou drasticamente (ex: troca de ativo), damos setData
    // Caso contrário, usamos o update para fluidez (Game Mode)
    const lastItem = data[data.length - 1];
    if (lastItem) {
      seriesRef.current.update(lastItem);
    }
  }, [data]);

  // 3. Efeito para as Setas de Compra/Venda (Markers)
  useEffect(() => {
    if (seriesRef.current) {
      seriesRef.current.setMarkers(markers);
    }
  }, [markers]);

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

  return (
    <div ref={chartContainerRef} className="w-full h-full absolute inset-0" />
  );
}