'use client';

import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, ISeriesApi, CandlestickData, Time, CandlestickSeries, IPriceLine, LineStyle } from 'lightweight-charts';

export interface VisualStudies {
  linhas_tendencia?: { id: string; p1: { time: string; price: number }; p2: { time: string; price: number } }[];
  suporte_resistencia?: number[];
  fibo_proposals?: { level: string; price: number }[];
}

interface TradingChartProps {
  data: CandlestickData<Time>[];
  visualStudies?: VisualStudies;
}

export default function TradingChart({ data, visualStudies }: TradingChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const handleResize = () => {
      if (chartContainerRef.current && chart) {
        chart.applyOptions({ 
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight
        });
      }
    };

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
        mode: 1, // Normal mode
        vertLine: {
          color: '#52525b',
          width: 1,
          style: 3, // Dashed
          labelBackgroundColor: '#1f1f1f',
        },
        horzLine: {
          color: '#52525b',
          width: 1,
          style: 3, // Dashed
          labelBackgroundColor: '#1f1f1f',
        },
      },
      timeScale: {
        borderColor: '#27272a',
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: '#27272a',
      },
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
    });

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10b981',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });

    seriesRef.current = candlestickSeries;
    candlestickSeries.setData(data);

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [data]);

  // Efeito secundário para renderizar os estudos visuais
  useEffect(() => {
    if (!seriesRef.current) return;

    const series = seriesRef.current;

    // Limpa linhas antigas
    priceLinesRef.current.forEach(line => series.removePriceLine(line));
    priceLinesRef.current = [];

    if (!visualStudies) return;

    // Renderiza Suportes e Resistências
    if (visualStudies.suporte_resistencia) {
      visualStudies.suporte_resistencia.forEach(price => {
        const line = series.createPriceLine({
          price: price,
          color: '#eab308', // Amarelo/Dourado
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: 'S/R',
        });
        priceLinesRef.current.push(line);
      });
    }

    // Renderiza Fibonacci Proposals
    if (visualStudies.fibo_proposals) {
      visualStudies.fibo_proposals.forEach(fibo => {
        const line = series.createPriceLine({
          price: fibo.price,
          color: '#8b5cf6', // Azul/Púrpura
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          axisLabelVisible: true,
          title: `Fibo ${fibo.level}%`,
        });
        priceLinesRef.current.push(line);
      });
    }
  }, [visualStudies]);

  return (
    <div
      ref={chartContainerRef}
      className="w-full h-full absolute inset-0"
    />
  );
}
