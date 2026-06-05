import React, { useEffect, useRef, useState } from 'react';
import './FlatAvatar.css';

export function FlatAvatar({ state, amplitude }) {
  const imageRef = useRef();
  const [currentEmotion, setCurrentEmotion] = useState('Neutral');

  useEffect(() => {
    window.triggerExpression = (emotion) => {
      setCurrentEmotion(emotion);
    };
    return () => {
      window.triggerExpression = undefined;
    };
  }, []);

  // Compute styles based on audio and emotion
  // When speaking, we want a slight pulse in size or glow
  const isSpeaking = state === 'speaking';
  const scale = 1 + (isSpeaking ? amplitude * 0.15 : 0);
  
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
    <div className="flat-avatar-container">
      <div 
        className="flat-avatar-image"
        style={{
          transform: `scale(${scale})`,
          borderColor: borderColor,
          boxShadow: `0 0 30px ${glowColor}`,
          transition: isSpeaking ? 'transform 0.05s ease-out, box-shadow 0.05s ease-out' : 'all 0.5s ease-in-out'
        }}
      >
        <img src="/avatar.png" alt="Bernard" />
      </div>
      <div className="emotion-badge">{currentEmotion}</div>
    </div>
  );
}
