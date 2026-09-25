/**
 * NEXORA RANGE SCANNER — Interactive Range Chart Visualization
 * Conceptual replica of Auto Range Detector [QuantAlgo] on TradingView.
 * Renders Candlesticks, Shaded Range Box, Midline, Quartiles, Breakout Markers, SL & TP1-3.
 */

class RangeChart {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
  }

  render(candles, rangeData, signalData) {
    if (!candles || candles.length === 0) {
      this.container.innerHTML = '<div style="display:flex;height:100%;align-items:center;justify-content:center;color:#64748b;">No candle data available</div>';
      return;
    }

    const times = candles.map(c => new Date(c.timestamp));
    const opens = candles.map(c => c.open);
    const highs = candles.map(c => c.high);
    const lows = candles.map(c => c.low);
    const closes = candles.map(c => c.close);

    const traces = [];
    const shapes = [];
    const annotations = [];

    // 1. Candlestick Trace
    traces.push({
      x: times,
      open: opens,
      high: highs,
      low: lows,
      close: closes,
      type: 'candlestick',
      name: 'OHLC',
      increasing: { line: { color: '#10b981', width: 1 }, fillcolor: '#10b981' },
      decreasing: { line: { color: '#f43f5e', width: 1 }, fillcolor: '#f43f5e' },
      showlegend: false
    });

    // 2. Range Structure Visualization
    if (rangeData) {
      const startTime = new Date(rangeData.start_time);
      const endTime = new Date(rangeData.end_time);

      // Shaded Consolidation Range Box
      shapes.push({
        type: 'rect',
        xref: 'x',
        yref: 'y',
        x0: startTime,
        x1: endTime,
        y0: rangeData.lower,
        y1: rangeData.upper,
        fillcolor: 'rgba(0, 242, 254, 0.08)',
        line: { color: 'rgba(0, 242, 254, 0.5)', width: 1.5, dash: 'solid' },
      });

      // Midline (50%)
      shapes.push({
        type: 'line',
        xref: 'x',
        yref: 'y',
        x0: startTime,
        x1: endTime,
        y0: rangeData.midline,
        y1: rangeData.midline,
        line: { color: 'rgba(255, 255, 255, 0.4)', width: 1, dash: 'dash' },
      });

      // Upper Quartile (75%)
      if (rangeData.quartile_high) {
        shapes.push({
          type: 'line',
          xref: 'x',
          yref: 'y',
          x0: startTime,
          x1: endTime,
          y0: rangeData.quartile_high,
          y1: rangeData.quartile_high,
          line: { color: 'rgba(0, 242, 254, 0.25)', width: 1, dash: 'dot' },
        });
      }

      // Lower Quartile (25%)
      if (rangeData.quartile_low) {
        shapes.push({
          type: 'line',
          xref: 'x',
          yref: 'y',
          x0: startTime,
          x1: endTime,
          y0: rangeData.quartile_low,
          y1: rangeData.quartile_low,
          line: { color: 'rgba(0, 242, 254, 0.25)', width: 1, dash: 'dot' },
        });
      }

      // Breakout Marker
      if (rangeData.breakout_price) {
        annotations.push({
          x: endTime,
          y: rangeData.breakout_price,
          xref: 'x',
          yref: 'y',
          text: '⚡ BREAKOUT',
          showarrow: true,
          arrowhead: 2,
          arrowcolor: rangeData.breakout_price > rangeData.midline ? '#10b981' : '#f43f5e',
          bgcolor: 'rgba(15, 23, 42, 0.9)',
          bordercolor: rangeData.breakout_price > rangeData.midline ? '#10b981' : '#f43f5e',
          font: { color: '#ffffff', size: 10, family: 'Inter' }
        });
      }

      // Deviation / Fakeout Marker
      if (rangeData.deviation_price) {
        annotations.push({
          x: endTime,
          y: rangeData.deviation_price,
          xref: 'x',
          yref: 'y',
          text: '🔄 DEVIATION',
          showarrow: true,
          arrowhead: 2,
          arrowcolor: '#c084fc',
          bgcolor: 'rgba(15, 23, 42, 0.9)',
          bordercolor: '#c084fc',
          font: { color: '#ffffff', size: 10, family: 'Inter' }
        });
      }
    }

    // 3. Trade Entry, SL, TP1, TP2, TP3 Lines
    if (signalData) {
      const sigTime = new Date(signalData.timestamp);
      const lastTime = times[times.length - 1];

      const levels = [
        { name: 'ENTRY', val: signalData.entry_price, color: '#38bdf8' },
        { name: 'STOP', val: signalData.stop_loss, color: '#f43f5e' },
        { name: 'TP1', val: signalData.tp1, color: '#10b981' },
        { name: 'TP2', val: signalData.tp2, color: '#10b981' },
        { name: 'TP3', val: signalData.tp3, color: '#10b981' },
      ];

      levels.forEach(lvl => {
        shapes.push({
          type: 'line',
          xref: 'x',
          yref: 'y',
          x0: sigTime,
          x1: lastTime,
          y0: lvl.val,
          y1: lvl.val,
          line: { color: lvl.color, width: 1.5, dash: 'dashdot' },
        });

        annotations.push({
          x: lastTime,
          y: lvl.val,
          xref: 'x',
          yref: 'y',
          text: `${lvl.name}: ${lvl.val.toFixed(2)}`,
          showarrow: false,
          xanchor: 'left',
          font: { color: lvl.color, size: 10, family: 'JetBrains Mono' }
        });
      });
    }

    const layout = {
      dragmode: 'pan',
      margin: { r: 60, t: 30, b: 40, l: 60 },
      showlegend: false,
      xaxis: {
        autorange: true,
        rangeslider: { visible: false },
        gridcolor: 'rgba(255, 255, 255, 0.05)',
        linecolor: 'rgba(255, 255, 255, 0.1)',
        tickfont: { color: '#94a3b8', size: 10 }
      },
      yaxis: {
        autorange: true,
        gridcolor: 'rgba(255, 255, 255, 0.05)',
        linecolor: 'rgba(255, 255, 255, 0.1)',
        tickfont: { color: '#94a3b8', size: 10 },
        side: 'right'
      },
      plot_bgcolor: '#0a0d14',
      paper_bgcolor: '#0a0d14',
      shapes: shapes,
      annotations: annotations
    };

    const config = {
      responsive: true,
      scrollZoom: true,
      displayModeBar: false
    };

    Plotly.newPlot(this.container, traces, layout, config);
  }
}
