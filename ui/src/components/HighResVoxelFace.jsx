import { useRef, useState, useEffect, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

// We load the generated voxel data
import voxelData from '../../public/voxel_face.json';

const tempObject = new THREE.Object3D();
const tempColor = new THREE.Color();

export function HighResVoxelFace() {
  const meshRef = useRef();
  
  const [currentEmotion, setCurrentEmotion] = useState('Neutral');
  const amplitudeRef = useRef(0);

  // We need an array of colors for the instances
  const colorArray = useMemo(() => {
    const array = new Float32Array(voxelData.length * 3);
    voxelData.forEach((voxel, i) => {
      tempColor.set(voxel.color);
      tempColor.toArray(array, i * 3);
    });
    return array;
  }, []);

  useEffect(() => {
    window.triggerExpression = (emotion) => {
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

  useFrame((state) => {
    if (!meshRef.current) return;
    
    const volume = window.__currentAmplitude || amplitudeRef.current || 0;
    const emo = currentEmotion.toLowerCase();
    
    // Animate each voxel individually based on its role
    voxelData.forEach((voxel, i) => {
      let tz = voxel.z;
      let ty = voxel.y;
      
      // 1. Lip Sync (Move mouth voxels)
      if (voxel.isMouth) {
        // Move mouth down based on volume
        if (voxel.y < -7) {
          ty -= volume * 3.0; // Open jaw
        }
      }
      
      // 2. Expressions
      if (voxel.isEyebrowLeft || voxel.isEyebrowRight) {
        if (emo.includes('angry')) {
          const inner = voxel.x > -5 && voxel.x < 5;
          if (inner) ty -= 1.0;
          else ty += 0.5;
        } else if (emo.includes('sad')) {
          const inner = voxel.x > -5 && voxel.x < 5;
          if (inner) ty += 1.0;
          else ty -= 0.5;
        } else if (emo.includes('surprise')) {
          ty += 1.5;
        }
      }
      
      if (voxel.isEyeLeft || voxel.isEyeRight) {
        if (emo.includes('joy') || emo.includes('happy')) {
          if (voxel.y < 4) ty += 0.8; // Squint bottom up
        }
      }
      
      // Smoothly update positions
      tempObject.position.set(voxel.x * 0.1, ty * 0.1, tz * 0.1);
      
      // Idle bobbing for the whole head
      tempObject.position.y += Math.sin(state.clock.elapsedTime * 2 + voxel.x * 0.1) * 0.05;
      
      tempObject.updateMatrix();
      meshRef.current.setMatrixAt(i, tempObject.matrix);
    });
    
    meshRef.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <group position={[0, 0, 0]} rotation={[0, 0, 0]}>
      <instancedMesh ref={meshRef} args={[null, null, voxelData.length]}>
        {/* We use a tiny box for each pixel/voxel */}
        <boxGeometry args={[0.09, 0.09, 0.09]}>
          <instancedBufferAttribute attach="attributes-color" args={[colorArray, 3]} />
        </boxGeometry>
        <meshStandardMaterial vertexColors roughness={0.6} />
      </instancedMesh>
    </group>
  );
}
