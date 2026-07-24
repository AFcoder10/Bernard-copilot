
import React from 'react';
import { motion } from 'framer-motion';

export const WidgetRenderer = ({ widget }) => {
  if (!widget || !widget.type || !widget.data) return null;

  if (widget.type === 'weather') {
    // Attempt to parse wttr.in format: "City: Condition +Temp°C Hum% Wind"
    // e.g. "Navi Mumbai: Light Rain, Rain Shower +29°C 84% ↗30km/h"
    const rawData = String(widget.data);
    let city = "Unknown";
    let condition = "Unknown";
    let temp = "--°C";
    let hum = "--%";
    let wind = "--";
    
    try {
      const parts = rawData.split(':');
      if (parts.length >= 2) {
        city = parts[0].trim();
        const details = parts.slice(1).join(':').trim().split(' ');
        
        // Find specific tokens
        temp = details.find(d => d.includes('°C') || d.includes('°F')) || temp;
        hum = details.find(d => d.includes('%')) || hum;
        wind = details.find(d => d.includes('km/h') || d.includes('mph')) || wind;
        
        // Condition is whatever is left before the temp
        const tempIdx = details.findIndex(d => d === temp);
        if (tempIdx > 0) {
          condition = details.slice(0, tempIdx).join(' ');
        } else {
          condition = details[0]; // fallback
        }
      }
    } catch (e) {
      console.warn("Failed to parse weather widget data:", e);
    }

    // Determine icon based on condition string (simple heuristic)
    const getIcon = (cond) => {
      const lower = cond.toLowerCase();
      if (lower.includes('rain') || lower.includes('drizzle')) return '🌧️';
      if (lower.includes('cloud') || lower.includes('overcast')) return '☁️';
      if (lower.includes('clear') || lower.includes('sun')) return '☀️';
      if (lower.includes('snow')) return '❄️';
      if (lower.includes('storm') || lower.includes('thunder')) return '⛈️';
      if (lower.includes('fog') || lower.includes('mist')) return '🌫️';
      return '🌤️';
    };

    const icon = getIcon(condition);

    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.4, type: 'spring', bounce: 0.4 }}
        style={{
          background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.03) 100%)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.2)',
          borderRadius: '16px',
          padding: '20px',
          width: '280px',
          boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.3)',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          overflow: 'hidden',
          position: 'relative'
        }}
      >
        {/* Subtle decorative glow */}
        <div style={{
          position: 'absolute',
          top: '-20px',
          right: '-20px',
          width: '100px',
          height: '100px',
          background: 'radial-gradient(circle, rgba(135, 206, 235, 0.3) 0%, rgba(0,0,0,0) 70%)',
          borderRadius: '50%',
          filter: 'blur(20px)',
          zIndex: 0
        }} />

        <div style={{ position: 'relative', zIndex: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '600', color: '#fff', letterSpacing: '0.5px' }}>
              {city}
            </h3>
            <span style={{ fontSize: '13px', color: 'rgba(255,255,255,0.7)', textTransform: 'capitalize' }}>
              {condition}
            </span>
          </div>
          <div style={{ fontSize: '32px', filter: 'drop-shadow(0px 2px 4px rgba(0,0,0,0.2))' }}>
            {icon}
          </div>
        </div>

        <div style={{ position: 'relative', zIndex: 1, display: 'flex', alignItems: 'baseline', gap: '8px', margin: '10px 0' }}>
          <span style={{ fontSize: '36px', fontWeight: '700', color: '#fff', letterSpacing: '-1px' }}>
            {temp}
          </span>
        </div>

        <div style={{ position: 'relative', zIndex: 1, display: 'flex', justifyContent: 'space-between', paddingTop: '12px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase', letterSpacing: '1px' }}>Humidity</span>
            <span style={{ fontSize: '14px', color: '#fff', fontWeight: '500' }}>💧 {hum}</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', textAlign: 'right' }}>
            <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase', letterSpacing: '1px' }}>Wind</span>
            <span style={{ fontSize: '14px', color: '#fff', fontWeight: '500' }}>💨 {wind}</span>
          </div>
        </div>
      </motion.div>
    );
  }

  // Fallback for unknown widget types
  return (
    <div style={{ padding: '12px', background: 'rgba(255,0,0,0.1)', border: '1px solid rgba(255,0,0,0.2)', borderRadius: '8px', color: '#ff9999', fontSize: '12px' }}>
      Unsupported widget type: {widget.type}
    </div>
  );
};
