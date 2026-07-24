import React, { useEffect, useRef, useState } from 'react';
import './LedMatrixFace.css';

const GRID_SIZE = 20;
const TOTAL_PIXELS = GRID_SIZE * GRID_SIZE;

export function LedMatrixFace({ state, amplitude }) {
  const containerRef = useRef(null);
  const pixelsRef = useRef([]);
  const [currentEmotion, setCurrentEmotion] = useState('Happy');
  const isMorphing = useRef(false);

  useEffect(() => {
    window.triggerExpression = (emotion) => {
      if (emotion === currentEmotion) return;
      setCurrentEmotion(emotion);
      
      isMorphing.current = true; // Start morphing
      setTimeout(() => {
        isMorphing.current = false; // End morphing, back to normal audio reactivity
      }, 400);
    };
    return () => {
      window.triggerExpression = undefined;
    };
  }, [currentEmotion]);

  // Update loop for 60fps responsiveness without React state overhead
  useEffect(() => {
    let animationFrameId;

    const renderFace = () => {
      if (!pixelsRef.current.length) return;

      const emo = currentEmotion.toLowerCase();
      const isSpeaking = state === 'speaking';
      const vol = (isSpeaking && !isMorphing.current) ? amplitude : 0; // Force 0 volume during morphs
      
      // Determine color
      let color = '#00ffff'; // Default cyan
      let glow = 'rgba(0, 255, 255, 0.6)';
      
      if (emo.includes('angry')) {
        color = '#ff1111';
        glow = 'rgba(255, 17, 17, 0.6)';
      } else if (emo.includes('joy') || emo.includes('happy') || emo.includes('excited') || emo.includes('laugh') || emo.includes('wink')) {
        color = '#ffcc00';
        glow = 'rgba(255, 204, 0, 0.6)';
      } else if (emo.includes('sad') || emo.includes('concerned')) {
        color = '#3366ff';
        glow = 'rgba(51, 102, 255, 0.6)';
      } else if (emo.includes('sleep') || emo.includes('bored')) {
        color = '#0044ff';
        glow = 'rgba(0, 68, 255, 0.6)';
      } else if (emo.includes('fear') || emo.includes('surprise') || emo.includes('confused') || emo.includes('think') || emo.includes('scared') || emo.includes('alarm')) {
        color = '#cc33ff';
        glow = 'rgba(204, 51, 255, 0.6)';
      } else if (emo.includes('annoyed') || emo.includes('disgust') || emo.includes('exasperated')) {
        color = '#ff8800';
        glow = 'rgba(255, 136, 0, 0.6)';
      }

      // Create a blank 2D grid
      const grid = Array(GRID_SIZE).fill(0).map(() => Array(GRID_SIZE).fill(false));

      // --- EYES & EYEBROWS ---
      const drawEyeAndBrow = (cx, cy, type, isRight) => {
        const browY = cy - 4;
        
        // 1. Draw Eye & Brow
        if (type === 'happy') {
          // Large arched happy eye
          grid[cy][cx] = true; // pupil
          grid[cy-1][cx-2] = true; grid[cy-1][cx+2] = true; // arch sides
          grid[cy-2][cx-1] = true; grid[cy-2][cx] = true; grid[cy-2][cx+1] = true; // arch top
        } else if (type === 'excited') {
          // Diamond/Star shaped eyes
          grid[cy-1][cx] = true;
          grid[cy][cx-1] = true; grid[cy][cx] = true; grid[cy][cx+1] = true;
          grid[cy+1][cx] = true;
          // raised brows
          grid[browY - 1][cx - 1] = true; grid[browY - 1][cx] = true; grid[browY - 1][cx + 1] = true;
        } else if (type === 'laugh') {
          // ^ ^ squinting eyes
          grid[cy][cx-1] = true; grid[cy-1][cx] = true; grid[cy][cx+1] = true;
          // No brows for laugh
        } else if (type === 'neutral' || type === 'calm') {
          // Eyes closed for calm/neutral
          grid[cy][cx-1] = true; grid[cy][cx] = true; grid[cy][cx+1] = true;
          // No brows when closed
        } else if (type === 'angry') {
          const dir = cx < 10 ? 1 : -1; 
          grid[cy-1][cx - dir] = true; grid[cy][cx] = true; grid[cy+1][cx + dir] = true;
          grid[cy-1][cx] = true; grid[cy][cx+dir] = true;
          
          // Slanted down towards nose
          const innerX = isRight ? cx - 1 : cx + 1;
          const outerX = isRight ? cx + 1 : cx - 1;
          grid[browY - 1][outerX] = true;
          grid[browY][cx] = true;
          grid[browY + 1][innerX] = true;
        } else if (type === 'sad') {
          const dir = cx < 10 ? -1 : 1; 
          grid[cy-1][cx - dir] = true; grid[cy][cx] = true; grid[cy+1][cx + dir] = true;
          grid[cy-1][cx] = true; grid[cy][cx+dir] = true;
          
          // Slanted up towards nose
          const innerX = isRight ? cx - 1 : cx + 1;
          const outerX = isRight ? cx + 1 : cx - 1;
          grid[browY + 1][outerX] = true;
          grid[browY][cx] = true;
          grid[browY - 1][innerX] = true;
        } else if (type === 'concerned') {
          // Wide eyes
          grid[cy-1][cx] = true; grid[cy+1][cx] = true;
          grid[cy][cx-1] = true; grid[cy][cx+1] = true;
          
          // Slanted up towards nose (like sad brows)
          const innerX = isRight ? cx - 1 : cx + 1;
          const outerX = isRight ? cx + 1 : cx - 1;
          grid[browY + 1][outerX] = true;
          grid[browY][cx] = true;
          grid[browY - 1][innerX] = true;
        } else if (type === 'surprise') {
          grid[cy-1][cx] = true; grid[cy+1][cx] = true;
          grid[cy][cx-1] = true; grid[cy][cx+1] = true;
          
          // Raised horizontal brow
          grid[browY - 1][cx - 1] = true;
          grid[browY - 1][cx] = true;
          grid[browY - 1][cx + 1] = true;
        } else if (type === 'think') {
          // Looking up and right
          grid[cy-1][cx+1] = true; grid[cy-1][cx] = true;
          
          // One raised brow, one lowered
          if (!isRight) {
             grid[browY+1][cx-1] = true; grid[browY][cx] = true; grid[browY][cx+1] = true;
          } else {
             grid[browY-1][cx-1] = true; grid[browY-1][cx] = true; grid[browY-1][cx+1] = true;
          }
        } else if (type === 'wink') {
          if (!isRight) {
            // happy eye
            grid[cy][cx] = true; 
            grid[cy-1][cx-2] = true; grid[cy-1][cx+2] = true;
            grid[cy-2][cx-1] = true; grid[cy-2][cx] = true; grid[cy-2][cx+1] = true;
          } else {
            // closed eye
            grid[cy][cx-1] = true; grid[cy][cx] = true; grid[cy][cx+1] = true;
          }
        } else if (type === 'sleep') {
          // Sleeping U shaped eyes or closed
          grid[cy][cx-1] = true; grid[cy][cx] = true; grid[cy][cx+1] = true;
        } else if (type === 'confused') {
          // Both eyes neutral
          grid[cy][cx-1] = true; grid[cy][cx] = true; grid[cy][cx+1] = true;
          
          if (!isRight) {
            // Raised brow
            grid[browY - 1][cx - 1] = true; grid[browY - 1][cx] = true; grid[browY - 1][cx + 1] = true;
          } else {
            // Lowered slanted brow
            grid[browY + 1][cx - 1] = true; grid[browY][cx] = true; grid[browY - 1][cx + 1] = true;
          }
        } else if (type === 'annoyed') {
          // Flat half-closed eyes
          grid[cy][cx-1] = true; grid[cy][cx] = true; grid[cy][cx+1] = true;
          // Lowered flat brow (just 1 pixel above the eye)
          grid[browY + 2][cx - 1] = true; grid[browY + 2][cx] = true; grid[browY + 2][cx + 1] = true;
        } else if (type === 'sigh') {
          // Eyes closed
          grid[cy][cx-1] = true; grid[cy][cx] = true; grid[cy][cx+1] = true;
          // Sad/exhausted slanted brows
          const innerX = isRight ? cx - 1 : cx + 1;
          const outerX = isRight ? cx + 1 : cx - 1;
          grid[browY + 1][outerX] = true;
          grid[browY][cx] = true;
          grid[browY - 1][innerX] = true;
        } else if (type === 'cringe') {
          // Single tiny dot eye, no eyebrows
          grid[cy][cx] = true;
        } else if (type === 'love') {
          const bob = Math.sin(Date.now() / 400) > 0.5 ? -1 : 0;
          const y = cy + bob;
          grid[y-1][cx-1] = true; grid[y-1][cx+1] = true;
          grid[y][cx-2] = true; grid[y][cx] = true; grid[y][cx+2] = true;
          grid[y+1][cx-1] = true; grid[y+1][cx+1] = true;
          grid[y+2][cx] = true;
        } else if (type === 'dead') {
          grid[cy-1][cx-1] = true; grid[cy-1][cx+1] = true;
          grid[cy][cx] = true;
          grid[cy+1][cx-1] = true; grid[cy+1][cx+1] = true;
        } else if (type === 'smug') {
          grid[cy][cx-1] = true; grid[cy][cx] = true; grid[cy][cx+1] = true;
          if (!isRight) {
             grid[browY+1][cx-1] = true; grid[browY+1][cx] = true; grid[browY+1][cx+1] = true;
          } else {
             grid[browY-1][cx-1] = true; grid[browY-1][cx] = true; grid[browY-1][cx+1] = true;
          }
        } else if (type === 'scared') {
          // Tall trembling eyes
          const xOff = Math.sin(Date.now() / 50) > 0.5 ? 1 : 0;
          grid[cy-1][cx+xOff] = true; grid[cy][cx+xOff] = true; grid[cy+1][cx+xOff] = true;
          // High concerned brows
          const innerX = isRight ? cx - 1 : cx + 1;
          const outerX = isRight ? cx + 1 : cx - 1;
          grid[browY+1][outerX+xOff] = true;
          grid[browY][cx+xOff] = true;
          grid[browY - 1][innerX+xOff] = true;
        } else if (type === 'bored') {
          // Half closed eyes
          grid[cy][cx-1] = true; grid[cy][cx] = true; grid[cy][cx+1] = true;
          // Flat low brows
          grid[browY + 1][cx - 1] = true; grid[browY + 1][cx] = true; grid[browY + 1][cx + 1] = true;
        } else if (type === 'disgust') {
          // Squinting eyes
          grid[cy][cx-1] = true; grid[cy][cx] = true; grid[cy][cx+1] = true;
          grid[cy-1][cx] = true;
          // Wrinkled nose brows
          const innerX = isRight ? cx - 1 : cx + 1;
          grid[browY + 1][cx] = true; grid[browY][innerX] = true; 
        } else if (type === 'exasperated') {
          // Flat eyes, no brows (like the fallback)
          grid[cy][cx-1] = true; grid[cy][cx] = true; grid[cy][cx+1] = true;
        } else if (type === 'alarmed') {
          // Wide open ring eyes
          grid[cy-1][cx-1] = true; grid[cy-1][cx] = true; grid[cy-1][cx+1] = true;
          grid[cy][cx-1] = true; grid[cy][cx+1] = true; // empty center
          grid[cy+1][cx-1] = true; grid[cy+1][cx] = true; grid[cy+1][cx+1] = true;
          
          // High arched brows
          grid[browY - 2][cx - 1] = true;
          grid[browY - 3][cx] = true;
          grid[browY - 2][cx + 1] = true;
        } else {
          // Fallback
          grid[cy][cx-1] = true; grid[cy][cx] = true; grid[cy][cx+1] = true;
        }
      };

      let eyeType = 'neutral';
      if (emo.includes('happy') || emo.includes('joy')) eyeType = 'happy';
      if (emo.includes('excited')) eyeType = 'excited';
      if (emo.includes('laugh')) eyeType = 'laugh';
      if (emo.includes('angry')) eyeType = 'angry';
      if (emo.includes('sad')) eyeType = 'sad';
      if (emo.includes('concerned')) eyeType = 'concerned';
      if (emo.includes('surprise')) eyeType = 'surprise';
      if (emo.includes('think')) eyeType = 'think';
      if (emo.includes('wink')) eyeType = 'wink';
      if (emo.includes('sleep')) eyeType = 'sleep';
      if (emo.includes('confused')) eyeType = 'confused';
      if (emo.includes('annoyed')) eyeType = 'annoyed';
      if (emo.includes('sigh')) eyeType = 'sigh';
      if (emo.includes('cringe')) eyeType = 'cringe';
      if (emo.includes('love')) eyeType = 'love';
      if (emo.includes('dead')) eyeType = 'dead';
      if (emo.includes('smug')) eyeType = 'smug';
      if (emo.includes('scared')) eyeType = 'scared';
      if (emo.includes('bored')) eyeType = 'bored';
      if (emo.includes('alarm')) eyeType = 'alarmed';
      if (emo.includes('bored')) eyeType = 'bored';
      if (emo.includes('disgust')) eyeType = 'disgust';
      if (emo.includes('exasperated')) eyeType = 'exasperated';

      drawEyeAndBrow(5, 5, eyeType, false); // Left
      drawEyeAndBrow(14, 5, eyeType, true);  // Right

      // --- MOUTH ---
      // Big smile base mouth shape
      const mouthWidth = 12;
      const startX = Math.floor((GRID_SIZE - mouthWidth) / 2); // 4
      const endX = startX + mouthWidth - 1; // 15
      const baseY = 14;

      // Audio reactive opening
      const mouthOpenAmount = Math.floor(vol * 5); // 0 to 4 pixels down

      for (let x = startX; x <= endX; x++) {
        let y = baseY;
        
        // Apply emotion curve to the mouth base
        if (eyeType === 'happy' || eyeType === 'excited' || eyeType === 'laugh' || eyeType === 'wink') {
          // Big smile! Curving up drastically at the edges
          if (x === startX || x === endX) y -= 2;
          else if (x === startX + 1 || x === endX - 1) y -= 1;
        } else if (eyeType === 'sad' || eyeType === 'angry' || eyeType === 'concerned') {
          if (x === startX || x === endX) y += 2;
          else if (x === startX + 1 || x === endX - 1) y += 1;
        } else if (eyeType === 'surprise' || eyeType === 'sleep') {
          if (x < startX + 3 || x > endX - 3) continue; // narrower mouth
          y += 1;
        } else if (eyeType === 'confused') {
          if (x < startX + 4) y += 1;
          else if (x > endX - 4) y -= 1;
        } else if (eyeType === 'think') {
          if (x < startX + 4 || x > endX - 4) continue; // Pursed lips
        } else if (eyeType === 'cringe') {
          if (x < startX + 2 || x > endX - 2) continue; // narrower teeth block
        } else if (eyeType === 'smug') {
          if (x > startX + 5) y -= 1; // smirk on one side
          if (x === endX) y -= 1;
        } else if (eyeType === 'scared') {
          const xOff = Math.sin(Date.now() / 50) > 0.5 ? 1 : 0;
          if (x < startX + 3 || x > endX - 3) continue;
          y += 1;
          // Don't modify the loop variable x! Just use a temporary variable for drawing
          let drawX = x + xOff;
          for (let dy = 0; dy <= height; dy++) {
            if (y + dy < GRID_SIZE && drawX < GRID_SIZE) {
              grid[y + dy][drawX] = true;
            }
          }
          continue; // Skip the default drawing loop below
        } else if (eyeType === 'bored') {
          if (x < startX + 3 || x > endX - 3) continue;
        } else if (eyeType === 'disgust') {
          if (x < startX + 2 || x > endX - 3) continue;
          if (x === startX + 2) y -= 1;
          if (x === endX - 3) y += 1;
        } else if (eyeType === 'annoyed') {
          // Completely deadpan flat line
        } else if (eyeType === 'sigh' || eyeType === 'dead') {
          // Slightly sad flat line
          if (x === startX || x === endX) y += 1;
        } else if (eyeType === 'exasperated') {
          // Flat line with edges curled UP (default fallback shape)
          if (x === startX || x === endX) y -= 1;
        } else {
          // Neutral/Calm: Slight polite smile instead of a flat serious line
          if (x === startX || x === endX) y -= 1;
        }

        // Draw the vertical column for this X to simulate opening mouth
        let height = mouthOpenAmount;
        if (eyeType === 'surprise') height += 3;
        if (eyeType === 'excited' || eyeType === 'love') height += 2; // Always slightly open with excitement
        if (eyeType === 'laugh') height += Math.max(1, mouthOpenAmount * 2); // Extremely wide laugh
        if (eyeType === 'sleep' || eyeType === 'dead' || eyeType === 'smug') height = 0; // Don't open mouth while sleeping
        if (eyeType === 'sigh') height = Math.max(1, mouthOpenAmount); // Always slightly open to let out the sigh
        if (eyeType === 'cringe') height = Math.max(3, mouthOpenAmount + 2);
        
        for (let dy = 0; dy <= height; dy++) {
          if (y + dy < GRID_SIZE) {
            if (eyeType === 'surprise') {
              // Draw 'O' shape outline
              const cxSurprise = startX + 3;
              const cxSurpriseEnd = endX - 3;
              if (dy === 0 || dy === height || x === cxSurprise || x === cxSurpriseEnd) {
                // remove corners for roundness
                if ((dy === 0 || dy === height) && (x === cxSurprise || x === cxSurpriseEnd)) continue;
                grid[y + dy][x] = true;
              }
            } else if (eyeType === 'sigh') {
              // Open mouth slightly, but hollow
              if (dy === 0 || dy === height) grid[y + dy][x] = true;
            } else if (eyeType === 'cringe') {
              // Clenched teeth grimace
              const cxCringe = startX + 2;
              const cxCringeEnd = endX - 2;
              if (dy === 0 || dy === height || x === cxCringe || x === cxCringeEnd) {
                // Box outline
                grid[y + dy][x] = true;
              } else if (dy === Math.floor(height / 2)) {
                // Middle teeth separation
                grid[y + dy][x] = true;
              }
            } else {
              grid[y + dy][x] = true;
            }
          }
        }
      }

      // Apply to DOM via refs for massive performance boost
      for (let y = 0; y < GRID_SIZE; y++) {
        for (let x = 0; x < GRID_SIZE; x++) {
          const idx = y * GRID_SIZE + x;
          const px = pixelsRef.current[idx];
          if (!px) continue;
          
          // Force a slower transition during morphs
          if (isMorphing.current) {
            px.style.transition = 'background-color 0.4s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.4s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.4s cubic-bezier(0.4, 0, 0.2, 1)';
          } else {
            px.style.transition = ''; // fallback to CSS classes
          }

          if (grid[y][x]) {
            px.style.backgroundColor = color;
            px.style.boxShadow = `0 0 8px ${glow}, 0 0 12px ${glow}`;
            px.style.opacity = '1';
          } else {
            px.style.backgroundColor = '#1a1d24'; // dark unlit pixel
            px.style.boxShadow = 'none';
            px.style.opacity = '0.3';
          }
        }
      }

      // --- BODY LANGUAGE (Head Bobbing & Tilting) ---
      // We apply this to the entire grid container for sub-pixel smoothness,
      // simulating a physical head moving while talking.
      if (!containerRef.current.headAnim) {
        containerRef.current.headAnim = { phase: 0, currentY: 0, currentRot: 0 };
      }
      const anim = containerRef.current.headAnim;
      
      if (isSpeaking) {
        // Phase moves faster when volume is higher
        anim.phase += 0.08 + (amplitude * 0.2);
        
        // Target positions (bob up/down by up to 8px, tilt by up to 3deg)
        const targetY = Math.sin(anim.phase) * (amplitude * 8);
        const targetRot = Math.cos(anim.phase * 0.6) * (amplitude * 3);
        
        // Smoothly interpolate towards the target
        anim.currentY += (targetY - anim.currentY) * 0.2;
        anim.currentRot += (targetRot - anim.currentRot) * 0.2;
      } else {
        // Smoothly return to dead center when not speaking
        anim.currentY += (0 - anim.currentY) * 0.1;
        anim.currentRot += (0 - anim.currentRot) * 0.1;
      }
      
      containerRef.current.style.transform = `translateY(${anim.currentY}px) rotate(${anim.currentRot}deg)`;

      animationFrameId = requestAnimationFrame(renderFace);
    };

    renderFace();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [state, amplitude, currentEmotion]);

  return (
    <div className="led-face-wrapper">
      <div className="led-face-grid" ref={containerRef}>
        {Array.from({ length: TOTAL_PIXELS }).map((_, i) => {
          const isMouthArea = Math.floor(i / GRID_SIZE) >= 12;
          return (
            <div 
              key={i} 
              className={`led-pixel ${isMouthArea ? 'mouth-pixel' : 'eye-pixel'}`} 
              ref={el => pixelsRef.current[i] = el}
            />
          );
        })}
      </div>
      <div className="emotion-badge">{currentEmotion}</div>
    </div>
  );
}
