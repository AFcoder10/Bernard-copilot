import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import './App.css'

function App() {
  const [state, setState] = useState('idle') // idle, listening, thinking, speaking, loading
  const [messages, setMessages] = useState([]) // { id, role: 'user' | 'assistant', text, isPartial }
  const [amplitude, setAmplitude] = useState(0)
  
  const [micAmplitude, setMicAmplitude] = useState(0)
  const audioContextRef = useRef(null)
  const analyserRef = useRef(null)
  const micStreamRef = useRef(null)
  const requestRef = useRef(null)
  
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    window.updateBernardState = (newState, newAmplitude = 0) => {
      setState(newState)
      setAmplitude(newAmplitude)
    }

    window.addChatMessage = (role, text, isPartial) => {
      setMessages(prev => {
        const lastMsg = prev[prev.length - 1]
        
        if (lastMsg && lastMsg.role === role && (lastMsg.isPartial || isPartial)) {
           const updated = [...prev]
           updated[updated.length - 1] = { ...lastMsg, text, isPartial }
           return updated
        }
        
        return [...prev, { id: Date.now().toString() + Math.random(), role, text, isPartial }]
      })
    }

    return () => {
      delete window.updateBernardState
      delete window.addChatMessage
    }
  }, [])

  useEffect(() => {
    if (state === 'listening') {
      const startMic = async () => {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
          micStreamRef.current = stream
          const audioCtx = new (window.AudioContext || window.webkitAudioContext)()
          audioContextRef.current = audioCtx
          const analyser = audioCtx.createAnalyser()
          analyser.fftSize = 256
          analyserRef.current = analyser
          const source = audioCtx.createMediaStreamSource(stream)
          source.connect(analyser)

          const dataArray = new Uint8Array(analyser.frequencyBinCount)

          const updateMic = () => {
            analyser.getByteFrequencyData(dataArray)
            let sum = 0
            for (let i = 0; i < dataArray.length; i++) sum += dataArray[i]
            const avg = sum / dataArray.length
            setMicAmplitude(Math.min(1, (avg / 128.0) * 2.5))
            requestRef.current = requestAnimationFrame(updateMic)
          }
          updateMic()
        } catch (e) {
          console.error("Microphone access denied", e)
        }
      }
      startMic()
    } else {
      if (requestRef.current) cancelAnimationFrame(requestRef.current)
      if (micStreamRef.current) micStreamRef.current.getTracks().forEach(track => track.stop())
      if (audioContextRef.current) audioContextRef.current.close()
      setMicAmplitude(0)
    }
    
    return () => {
      if (requestRef.current) cancelAnimationFrame(requestRef.current)
    }
  }, [state])

  const currentAmp = state === 'listening' ? micAmplitude : state === 'speaking' ? amplitude : 0

  return (
    <div className="glass-window drag-area">
      <div className="header drag-area">
        <div className="title">BERNARD</div>
        <div className="status">{state.toUpperCase()}</div>
      </div>
      
      <div className="chat-container drag-area">
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div 
              key={msg.id}
              initial={{ opacity: 0, y: 15, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.2 }}
              className={`message-wrapper ${msg.role}`}
            >
              <div className={`message-bubble ${msg.isPartial ? 'partial' : ''}`}>
                {msg.text}
                {msg.isPartial && <span className="blinking-cursor">|</span>}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={messagesEndRef} style={{ height: '10px' }} />
      </div>

      <div className="waveform-container drag-area">
        <Waveform state={state} amplitude={currentAmp} />
      </div>
    </div>
  )
}

function Waveform({ state, amplitude }) {
  const bars = 7
  
  return (
    <div className="waveform">
      {[...Array(bars)].map((_, i) => {
        let height = 6
        let color = 'rgba(255,255,255,0.4)'
        let anim = 'none'

        if (state === 'loading') {
          height = 12
          anim = `wave-pulse 0.8s ease-in-out infinite alternate ${i * 0.1}s`
          color = '#ffffff'
        } else if (state === 'thinking') {
          height = 12
          anim = `wave-sine 1s ease-in-out infinite alternate ${i * 0.15}s`
          color = '#ff9900'
        } else if (state === 'listening' || state === 'speaking') {
          const baseHeight = 6
          // Bell curve multiplier so middle bars are tallest
          const dist = Math.abs(i - 3) // 0 to 3
          const multiplier = 1.5 - (dist * 0.3)
          height = baseHeight + (amplitude * 60 * multiplier)
          color = state === 'listening' ? '#00ff88' : '#0088ff'
        }

        return (
          <div 
            key={i} 
            className="bar" 
            style={{ 
              height: `${height}px`,
              backgroundColor: color,
              animation: anim,
              boxShadow: `0 0 12px ${color}`,
              transition: (state === 'listening' || state === 'speaking') ? 'height 0.05s ease' : 'height 0.3s ease, background-color 0.3s ease'
            }} 
          />
        )
      })}
    </div>
  )
}

export default App
