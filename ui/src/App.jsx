import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { LedMatrixFace } from './components/LedMatrixFace'
import { WidgetRenderer } from './components/WidgetRenderer'
import { WeatherBackground } from './components/WeatherBackground'
import './App.css'

function App() {
  const [state, setState] = useState('loading') // idle, listening, thinking, speaking, loading, working
  const [messages, setMessages] = useState([]) // { id, role: 'user' | 'assistant', text, isPartial }
  const [amplitude, setAmplitude] = useState(0)
  const [activeThought, setActiveThought] = useState('')
  const [activeAction, setActiveAction] = useState('')
  const [appTheme, setAppTheme] = useState(null)
  
  const [micAmplitude, setMicAmplitude] = useState(0)
  const audioContextRef = useRef(null)
  const analyserRef = useRef(null)
  const micStreamRef = useRef(null)
  const requestRef = useRef(null)
  const themeTimeoutRef = useRef(null)
  
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, state, activeThought, activeAction])

  useEffect(() => {
    window.updateBernardState = (newState, newAmplitude = 0) => {
      setState(newState)
      setAmplitude(newAmplitude)
      window.__currentAmplitude = newAmplitude
    }

    window.addChatMessage = (role, text, isPartial, widget = null) => {
      if (widget && widget.type === 'weather' && widget.data && widget.data.condition) {
        setAppTheme(widget.data.condition);
        if (themeTimeoutRef.current) clearTimeout(themeTimeoutRef.current);
        themeTimeoutRef.current = setTimeout(() => {
          setAppTheme(null);
        }, 10000);
      }

      setMessages(prev => {
        const lastMsg = prev[prev.length - 1]
        
        if (lastMsg && lastMsg.role === role && (lastMsg.isPartial || isPartial)) {
           const updated = [...prev]
           // If the incoming message has a widget, attach it to the existing text block
           const newWidget = widget || lastMsg.widget
           updated[updated.length - 1] = { ...lastMsg, text, isPartial, widget: newWidget }
           return updated
        }
        
        return [...prev, { id: Date.now().toString() + Math.random(), role, text, isPartial, widget }]
      })
    }
    window.clearChatHistory = () => {
      setMessages([])
    }
    
    window.setInitialChatHistory = (history) => {
        setMessages(history)
    }

    window.updateBernardThought = (text) => {
      setActiveThought(text)
    }

    window.updateBernardAction = (actionName) => {
      setActiveAction(actionName)
    }

    return () => {
      delete window.updateBernardState
      delete window.addChatMessage
      delete window.setInitialChatHistory
      delete window.updateBernardThought
      delete window.updateBernardAction
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

  const currentAmp = state === 'listening' ? micAmplitude : 0
  const [isWide, setIsWide] = useState(window.innerWidth >= 900)
  
  useEffect(() => {
    const handleResize = () => setIsWide(window.innerWidth >= 900)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const inputComponent = (
      <div className="input-container drag-area">
        <button 
            className="attach-btn no-drag"
            onClick={() => {
                if (window.pywebview && window.pywebview.api) {
                    window.pywebview.api.trigger_file_upload();
                }
            }}
            title="Attach file (Image, Audio, Video)"
        >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
            </svg>
        </button>
        <input 
          className="input-pill no-drag"
          type="text" 
          placeholder="Message Bernard..." 
          onKeyDown={(e) => {
            if (e.key === 'Enter' && e.target.value.trim()) {
              if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.send_prompt(e.target.value.trim());
                e.target.value = '';
              }
            }
          }}
        />
      </div>
  );

  return (
    <>
      <WeatherBackground condition={appTheme} />
      <div className="glass-window drag-area">
        <div className="app-container">
          <div className="left-pane drag-area">
            
          <div className="title-container drag-area">
              <div className="title">BERNARD</div>
              <div className="status-badge">
                  <div className="status-dot" style={{ 
                      backgroundColor: state === 'listening' ? '#00ff88' : 
                                       state === 'thinking' ? '#ff9900' : 
                                       state === 'working' ? '#00c6ff' : 
                                       state === 'speaking' ? '#a255ff' : '#666',
                      boxShadow: state !== 'idle' && state !== 'loading' ? `0 0 8px ${
                          state === 'listening' ? '#00ff88' : 
                          state === 'thinking' ? '#ff9900' : 
                          state === 'working' ? '#00c6ff' : 
                          state === 'speaking' ? '#a255ff' : '#666'
                      }` : 'none'
                  }} />
                  <div className="status-text">{state}</div>
              </div>
          </div>
          
          <div className="avatar-container" style={{ flex: 1, width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '150px' }}>
            <div style={{ transform: isWide ? 'scale(1.1)' : 'scale(0.9)', transition: 'transform 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)' }}>
              <LedMatrixFace state={state} amplitude={amplitude} />
            </div>
          </div>
          
          <div className="waveform-container drag-area">
            <Waveform state={state} amplitude={currentAmp} />
          </div>
          
          {!isWide && inputComponent}
        </div>

        {isWide && (
          <div className="right-pane">
            <div className="chat-history">
              {messages.length === 0 && (
                <motion.div 
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  style={{ color: 'rgba(255,255,255,0.3)', textAlign: 'center', marginTop: '40px', fontSize: '14px', fontFamily: 'Inter' }}
                >
                  No messages yet. Start speaking!
                </motion.div>
              )}
              
              <AnimatePresence>
              {messages.map(msg => (
                <motion.div 
                  initial={{ opacity: 0, y: 15, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.3, ease: "easeOut" }}
                  key={msg.id} 
                  className={`message-bubble ${msg.widget ? 'message-widget' : (msg.role === 'user' ? 'message-user' : 'message-assistant')}`}
                >
                  {msg.text && (
                    <div style={{
                      backgroundColor: msg.widget ? 'rgba(255, 255, 255, 0.05)' : 'transparent',
                      padding: msg.widget ? '14px 18px' : '0',
                      borderRadius: msg.widget ? '18px' : '0',
                      border: msg.widget ? '1px solid rgba(255,255,255,0.08)' : 'none',
                      backdropFilter: msg.widget ? 'blur(12px)' : 'none'
                    }}>
                      {msg.text}
                    </div>
                  )}
                  {msg.widget && <WidgetRenderer widget={msg.widget} />}
                </motion.div>
              ))}
              </AnimatePresence>
              
              <AnimatePresence>
                {state === 'thinking' && activeThought && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }} 
                    animate={{ opacity: 1, y: 0 }} 
                    exit={{ opacity: 0, height: 0, margin: 0, padding: 0 }}
                    transition={{ duration: 0.3 }}
                    style={{
                      alignSelf: 'flex-start',
                      backgroundColor: 'rgba(255, 153, 0, 0.05)',
                      border: '1px solid rgba(255, 153, 0, 0.2)',
                      padding: '12px 18px',
                      borderRadius: '16px',
                      maxWidth: '90%',
                      fontSize: '13px',
                      color: '#ffb347',
                      fontFamily: 'monospace',
                      whiteSpace: 'pre-wrap',
                      overflow: 'hidden',
                      backdropFilter: 'blur(8px)'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', fontWeight: 'bold' }}>
                      <span className="spinner" style={{ animation: 'spin 2s linear infinite', display: 'inline-block' }}>⚙️</span> 
                      Thinking...
                    </div>
                    <div style={{ opacity: 0.8, lineHeight: '1.5' }}>{activeThought}</div>
                  </motion.div>
                )}
                
                {state === 'working' && activeAction && (
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.95 }} 
                    animate={{ opacity: 1, scale: 1 }} 
                    exit={{ opacity: 0, scale: 0.95, height: 0, margin: 0 }}
                    style={{
                      alignSelf: 'center',
                      backgroundColor: 'rgba(0, 255, 136, 0.08)',
                      border: '1px solid rgba(0, 255, 136, 0.3)',
                      padding: '10px 20px',
                      borderRadius: '24px',
                      fontSize: '13px',
                      color: '#00ff88',
                      fontWeight: '600',
                      boxShadow: '0 0 15px rgba(0, 255, 136, 0.1)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      margin: '10px 0',
                      backdropFilter: 'blur(8px)'
                    }}
                  >
                    <span style={{ animation: 'pulse 1.5s ease-in-out infinite' }}>⚡</span>
                    Executing: {activeAction}
                  </motion.div>
                )}
              </AnimatePresence>
              
              <style>{`
                @keyframes spin { 100% { transform: rotate(360deg); } }
                @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
              `}</style>
              
              <div ref={messagesEndRef} />
            </div>
            
            {inputComponent}
          </div>
        )}
      </div>
    </div>
    </>
  )
}

function Waveform({ state, amplitude }) {
  const bars = 7
  
  return (
    <div className="waveform">
      {[...Array(bars)].map((_, i) => {
        let height = 6
        let color = 'rgba(255,255,255,0.3)'
        let anim = 'none'

        if (state === 'loading') {
          height = 14
          anim = `wave-pulse 0.8s ease-in-out infinite alternate ${i * 0.1}s`
          color = '#ffffff'
        } else if (state === 'thinking') {
          height = 14
          anim = `wave-sine 1s ease-in-out infinite alternate ${i * 0.15}s`
          color = '#ff9900'
        } else if (state === 'listening' || state === 'speaking') {
          const baseHeight = 6
          const dist = Math.abs(i - 3) // 0 to 3
          const multiplier = 1.5 - (dist * 0.3)
          height = baseHeight + (amplitude * 60 * multiplier)
          color = state === 'listening' ? '#00ff88' : '#a255ff'
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
