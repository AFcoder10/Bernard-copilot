import { useRef, useState, useEffect, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { Sphere, MeshDistortMaterial } from '@react-three/drei';
import * as THREE from 'three';

export function SentientOrb() {
  const orbRef = useRef();
  const materialRef = useRef();
  
  const [currentEmotion, setCurrentEmotion] = useState('Neutral');
  const amplitudeRef = useRef(0);

  useEffect(() => {
    window.triggerExpression = (emotion) => {
      console.log("Orb expression triggered:", emotion);
      setCurrentEmotion(emotion);
    };

    const originalUpdate = window.updateBernardState;
    window.updateBernardState = (state, amplitude = 0) => {
      if (state === 'speaking') {
        amplitudeRef.current = amplitude;
      } else {
        amplitudeRef.current = 0;
      }
      if (originalUpdate) originalUpdate(state, amplitude);
    };

    return () => {
      window.triggerExpression = undefined;
      window.updateBernardState = originalUpdate;
    };
  }, []);

  // Pre-define target colors for emotions
  const colors = useMemo(() => ({
    cyan: new THREE.Color("#00ffff"),
    red: new THREE.Color("#ff1111"),
    yellow: new THREE.Color("#ffee00"),
    green: new THREE.Color("#44ff00"),
    blue: new THREE.Color("#0044ff"),
    purple: new THREE.Color("#9900ff"),
    white: new THREE.Color("#ffffff"),
  }), []);

  useFrame((state) => {
    if (!materialRef.current || !orbRef.current) return;

    // Default physical properties
    let targetDistort = 0.2;
    let targetSpeed = 1.5;
    let targetColor = colors.cyan;
    let targetScale = 1.0;

    const emo = currentEmotion.toLowerCase();

    // Emotion physics mapping
    if (emo.includes('joy') || emo.includes('happy') || emo.includes('excited')) {
      targetColor = colors.yellow;
      targetDistort = 0.4;
      targetSpeed = 4.0;
      targetScale = 1.1;
    } else if (emo.includes('angry')) {
      targetColor = colors.red;
      targetDistort = 0.8; // Highly spiked
      targetSpeed = 6.0;
      targetScale = 1.2;
    } else if (emo.includes('sad')) {
      targetColor = colors.blue;
      targetDistort = 0.1; // Smooth
      targetSpeed = 0.5; // Very slow
      targetScale = 0.9;
    } else if (emo.includes('fear') || emo.includes('scared')) {
      targetColor = colors.purple;
      targetDistort = 0.6;
      targetSpeed = 8.0; // Fast shaking
      targetScale = 0.8;
    } else if (emo.includes('disgust')) {
      targetColor = colors.green;
      targetDistort = 0.5;
      targetSpeed = 2.0;
    } else if (emo.includes('confused') || emo.includes('suspicious')) {
      targetColor = colors.cyan;
      targetDistort = 0.3;
      targetSpeed = 1.0;
    } else if (emo.includes('bored') || emo.includes('tired')) {
      targetColor = colors.white;
      targetDistort = 0.05;
      targetSpeed = 0.2;
      targetScale = 0.9;
    }

    // Real-Time Audio Reactivity overrides
    const volume = window.__currentAmplitude || amplitudeRef.current || 0;
    
    // When speaking, increase distortion, speed, and size based on volume
    if (volume > 0.01) {
      targetDistort += volume * 0.8;
      targetSpeed += volume * 5.0;
      targetScale += volume * 0.4;
    }

    // Smooth organic interpolation
    const smoothing = 0.08;
    materialRef.current.distort = THREE.MathUtils.lerp(materialRef.current.distort, targetDistort, smoothing);
    materialRef.current.speed = THREE.MathUtils.lerp(materialRef.current.speed, targetSpeed, smoothing);
    materialRef.current.color.lerp(targetColor, smoothing);
    
    orbRef.current.scale.setScalar(THREE.MathUtils.lerp(orbRef.current.scale.x, targetScale, smoothing));
    
    // Ambient slow rotation
    orbRef.current.rotation.y += 0.005;
    orbRef.current.rotation.x += 0.002;
  });

  return (
    <group position={[0, -0.2, 0]}>
      <Sphere ref={orbRef} args={[1.2, 128, 128]}>
        <MeshDistortMaterial
          ref={materialRef}
          roughness={0.1}
          metalness={0.8}
          clearcoat={1.0}
          clearcoatRoughness={0.1}
        />
      </Sphere>
      
      {/* Inner glowing core so it looks magical */}
      <Sphere args={[0.9, 32, 32]}>
        <meshBasicMaterial color="#ffffff" transparent opacity={0.2} />
      </Sphere>
    </group>
  );
}
