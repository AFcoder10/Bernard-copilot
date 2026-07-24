import React, { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './WeatherBackground.css';

export const WeatherBackground = ({ condition }) => {
  // Normalize condition
  const normalizedCondition = (condition || '').toLowerCase();
  let theme = null;

  if (normalizedCondition.includes('rain') || normalizedCondition.includes('drizzle') || normalizedCondition.includes('thunderstorm') || normalizedCondition.includes('shower')) {
    theme = 'rain';
  } else if (normalizedCondition.includes('snow') || normalizedCondition.includes('ice') || normalizedCondition.includes('sleet') || normalizedCondition.includes('blizzard')) {
    theme = 'snow';
  } else if (normalizedCondition.includes('clear') || normalizedCondition.includes('sun')) {
    theme = 'clear';
  } else if (normalizedCondition.includes('cloud') || normalizedCondition.includes('overcast') || normalizedCondition.includes('mist') || normalizedCondition.includes('fog') || normalizedCondition.includes('haze')) {
    theme = 'clouds';
  }

  // Generate random particles for rain/snow to avoid performance-heavy React state loops
  const particles = useMemo(() => {
    if (theme === 'rain' || theme === 'snow') {
      return Array.from({ length: 100 }).map((_, i) => ({
        id: i,
        left: `${Math.random() * 100}vw`,
        animationDuration: `${Math.random() * 1 + 0.5}s`,
        animationDelay: `${Math.random() * 2}s`,
        opacity: Math.random() * 0.5 + 0.2
      }));
    }
    return [];
  }, [theme]);

  if (!theme) return null;

  return (
    <AnimatePresence mode="wait">
      <motion.div 
        key={theme}
        className={`weather-background ${theme}`}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 1.5, ease: "easeInOut" }}
      >
        {theme === 'rain' && (
          <div className="rain-container">
            {particles.map(p => (
              <div 
                key={p.id} 
                className="rain-drop" 
                style={{ 
                  left: p.left, 
                  animationDuration: p.animationDuration, 
                  animationDelay: p.animationDelay,
                  opacity: p.opacity 
                }} 
              />
            ))}
          </div>
        )}

        {theme === 'snow' && (
          <div className="snow-container">
            {particles.map(p => (
              <div 
                key={p.id} 
                className="snow-flake" 
                style={{ 
                  left: p.left, 
                  animationDuration: `${parseFloat(p.animationDuration) * 3 + 2}s`, 
                  animationDelay: p.animationDelay,
                  opacity: p.opacity,
                  width: `${Math.random() * 4 + 2}px`,
                  height: `${Math.random() * 4 + 2}px`
                }} 
              />
            ))}
          </div>
        )}

        {theme === 'clear' && (
          <div className="sun-container">
            <div className="sun-glow"></div>
            <div className="sun-rays"></div>
          </div>
        )}

        {theme === 'clouds' && (
          <div className="clouds-container">
            <div className="cloud cloud-1"></div>
            <div className="cloud cloud-2"></div>
            <div className="cloud cloud-3"></div>
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  );
};
