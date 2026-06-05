import React, { useEffect, useRef, useState } from 'react';
import './Live2DAvatar.css';

export function Live2DAvatar({ state, amplitude }) {
  const [currentEmotion, setCurrentEmotion] = useState('Neutral');
  const [targetJawDrop, setTargetJawDrop] = useState(0);

  useEffect(() => {
    window.triggerExpression = (emotion) => {
      setCurrentEmotion(emotion);
    };
    return () => {
      window.triggerExpression = undefined;
    };
  }, []);

  // Calculate jaw drop
  const isSpeaking = state === 'speaking';
  const jawDrop = isSpeaking ? amplitude * 18 : 0; // max drop 18px

  // Subtle breathing animation on the top half
  const time = Date.now() / 1000;
  const breath = Math.sin(time * 2) * 2; // subtle bob
  
  let borderColor = 'rgba(255, 255, 255, 0.2)';
  let glowColor = 'transparent';

  const emo = currentEmotion.toLowerCase();
  if (emo.includes('angry')) {
    borderColor = '#ff4444';
    glowColor = `rgba(255, 68, 68, ${0.2 + amplitude * 0.5})`;
  } else if (emo.includes('joy') || emo.includes('happy')) {
    borderColor = '#ffdd44';
    glowColor = `rgba(255, 221, 68, ${0.2 + amplitude * 0.5})`;
  } else if (emo.includes('sad')) {
    borderColor = '#4488ff';
    glowColor = `rgba(68, 136, 255, ${0.2 + amplitude * 0.5})`;
  } else if (isSpeaking) {
    borderColor = '#00ff88';
    glowColor = `rgba(0, 255, 136, ${0.2 + amplitude * 0.5})`;
  } else if (state === 'listening') {
    borderColor = '#0088ff';
    glowColor = 'rgba(0, 136, 255, 0.4)';
  } else if (state === 'thinking') {
    borderColor = '#ff9900';
    glowColor = 'rgba(255, 153, 0, 0.4)';
  }

  return (
    <div className="live2d-avatar-container">
      <div 
        className="live2d-avatar-frame"
        style={{
          borderColor: borderColor,
          boxShadow: `0 0 30px ${glowColor}`
        }}
      >
        {/* Background / Inside of Mouth */}
        <div className="live2d-mouth-interior"></div>

        {/* Top Half of Head */}
        <div 
          className="live2d-part live2d-top"
          style={{
            transform: `translateY(${breath}px)`,
          }}
        >
          <img src="/avatar.png" alt="Bernard Top" />
        </div>

        {/* Bottom Half of Head (Jaw) */}
        <div 
          className="live2d-part live2d-jaw"
          style={{
            transform: `translateY(${jawDrop + breath}px)`,
            transition: 'transform 0.05s ease-out'
          }}
        >
          <img src="/avatar.png" alt="Bernard Jaw" />
        </div>
      </div>
      <div className="emotion-badge">{currentEmotion}</div>
    </div>
  );
}
