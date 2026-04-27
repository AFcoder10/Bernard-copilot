import os
import time
import threading
import queue
import re
import sys
import logging
import ollama

# Suppress RealtimeTTS internal warnings about PCM streams
logging.getLogger().setLevel(logging.ERROR)

# Force UTF-8 encoding for standard output to prevent emoji/unicode crashes on Windows terminals
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
# Inject mpv into path automatically so Edge TTS works flawlessly
os.environ["PATH"] += os.pathsep + r"C:\Program Files\MPV Player"
from RealtimeTTS import TextToAudioStream, EdgeEngine, SystemEngine
from RealtimeSTT import AudioToTextRecorder

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from action_executor import execute_action
from llm_client import SYSTEM_PROMPT

import json

console = Console()

SESSION_FILE = "session.json"

# The Conversation Memory
conversation_history = [
    {'role': 'system', 'content': SYSTEM_PROMPT}
]

if os.path.exists(SESSION_FILE):
    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            saved_history = json.load(f)
            # Limit to last 20 messages
            conversation_history.extend(saved_history[-20:])
    except Exception:
        pass

def save_session():
    """Saves conversation history (excluding system prompt) to disk."""
    try:
        with open(SESSION_FILE, 'w', encoding='utf-8') as f:
            json.dump(conversation_history[1:], f, indent=2)
    except Exception:
        pass

# Shared input queue — used by both voice and keyboard threads, and also for barge-in
input_queue = queue.Queue()

# Link the tools module's event callback to our main input queue so background tools (like timers) can interrupt Bernard!
import tools
tools.EVENT_CALLBACK = input_queue.put

def strip_markdown(text):
    """Removes markdown formatting so TTS doesn't say 'asterisk asterisk'."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'\*(.+?)\*', r'\1', text)        # *italic*
    text = re.sub(r'`(.+?)`', r'\1', text)           # `code`
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)  # # headers
    text = re.sub(r'\*\*', '', text)   # stray **
    text = re.sub(r'\*', '', text)     # stray *
    text = text.replace('`', '')       # stray backticks
    return text

def process_agentic_loop(tts_stream, is_followup=False):
    """
    Streams the response from Ollama using the full conversation history.
    Shows live thinking tokens and final formatted markdown output.
    Supports barge-in and agentic tool recursion.
    
    Thinking mode:
    - ALWAYS ON for initial user queries (tool selection needs reasoning)
    - OFF for follow-up calls (just reading tool results and speaking)
    - Also triggered by keywords like 'think', 'explain', 'why', etc.
    """
    from rich.status import Status
    from rich.live import Live
    
    if is_followup:
        status_msg = "[bold cyan]Bernard is summarizing...[/bold cyan]"
        use_thinking = False
    else:
        last_user_msg = ""
        for msg in reversed(conversation_history):
            if msg['role'] == 'user':
                last_user_msg = msg['content'].lower()
                break
        
        think_keywords = ["think", "reason", "explain", "analyze", "debug", "solve", "calculate", "compare", "why"]
        is_complex = any(kw in last_user_msg for kw in think_keywords)
        use_thinking = True
        status_msg = "[bold cyan]Bernard is thinking deeply... 🧠[/bold cyan]" if is_complex else "[bold cyan]Bernard is thinking...[/bold cyan]"
    
    try:
        # Show thinking spinner while waiting for first token
        with Status(status_msg, spinner="dots", console=console):
            response_stream = ollama.chat(
                model='gemma4:e2b',
                messages=conversation_history,
                stream=True,
                think=use_thinking
            )
            
            # Fetch the first chunk to break out of the spinner
            try:
                first_chunk_data = next(response_stream)
            except StopIteration:
                return None

        first_chunk = True
        is_json_action = False
        json_buffer = ""
        spoken_text = ""
        
        detection_buffer = ""
        decided = False

        # Decouple LLM streaming from TTS audio playing using a queue
        import queue
        import sys
        tts_queue = queue.Queue()
        
        def tts_generator():
            while True:
                chunk = tts_queue.get()
                if chunk is None:
                    break
                yield chunk

        # Start TTS playing in background
        tts_stream.feed(tts_generator())
        tts_stream.play_async()
        
        def process_chunk(content):
            nonlocal decided, is_json_action, json_buffer, spoken_text, detection_buffer
            if not content:
                return None
                
            if not decided:
                detection_buffer += content
                stripped = detection_buffer.strip()
                
                if '{' in stripped and ('action' in stripped or stripped.startswith('{') or stripped.startswith('```json')):
                    decided = True
                    is_json_action = True
                    json_buffer += detection_buffer
                    console.print("\n[dim yellow]⚡ Streaming Action...[/dim yellow]")
                    return None
                elif len(stripped) > 25 and '{' not in stripped:
                    decided = True
                    is_json_action = False
                    spoken_text += detection_buffer
                    console.print(f"\n[bold green]Bernard:[/bold green] {detection_buffer}", end="")
                    sys.stdout.flush()
                    return strip_markdown(detection_buffer)
                else:
                    return None
                    
            if is_json_action:
                json_buffer += content
                return None
            else:
                spoken_text += content
                console.print(content, end="")
                sys.stdout.flush()
                return strip_markdown(content)

        try:
            # Process the first chunk
            clean_text = process_chunk(first_chunk_data['message']['content'])
            if clean_text: tts_queue.put(clean_text)
            
            # Stream the rest in main thread
            for chunk in response_stream:
                clean_text = process_chunk(chunk['message']['content'])
                if clean_text: tts_queue.put(clean_text)
                
                # Check for barge-in DURING generation
                if not input_queue.empty():
                    break
            
            # Flush the detection buffer if it was extremely short
            if not decided and detection_buffer.strip():
                is_json_action = False
                spoken_text += detection_buffer
                console.print(f"\n[bold green]Bernard:[/bold green] {detection_buffer}", end="")
                sys.stdout.flush()
                tts_queue.put(strip_markdown(detection_buffer))
                
            if not is_json_action:
                console.print()
                
        finally:
            tts_queue.put(None) # Signal TTS generator to stop

        # Keep alive until TTS finishes playing
            interrupted_input = None
            while tts_stream.is_playing():
                if not input_queue.empty():
                    interrupted_input = input_queue.get_nowait()
                    tts_stream.stop()
                    console.print("\n[bold red]⏸ Interrupted![/bold red]")
                    break
                time.sleep(0.05)

        # Save what Bernard said to memory
        if spoken_text.strip() and not is_json_action:
            conversation_history.append({'role': 'assistant', 'content': spoken_text})
            save_session()

        # If it was an action instead of speech, execute it!
        if is_json_action:
            console.print(Panel(
                json_buffer.strip(),
                title="[bold yellow]⚡ Tool Call[/bold yellow]",
                border_style="yellow",
                padding=(0, 2)
            ))
            
            # 1. Save the LLM's action request to memory
            conversation_history.append({'role': 'assistant', 'content': json_buffer})
            save_session()
            
            # 2. Execute the tool
            result_dict = execute_action(json_buffer)
            
            # 3. Show the result in terminal
            console.print(Panel(
                str(result_dict),
                title="[bold blue]📋 Tool Result[/bold blue]",
                border_style="blue",
                padding=(0, 2)
            ))
            
            # 4. Save the tool's output to memory
            tool_output = f"TOOL EXECUTION RESULT:\n{result_dict}"
            tool_message = {'role': 'user', 'content': tool_output}
            
            if isinstance(result_dict, dict) and 'image_path' in result_dict:
                image_path = result_dict['image_path']
                console.print(f"[dim magenta]👁 Attaching image for vision: {image_path}[/dim magenta]")
                tool_message['images'] = [image_path]
            
            conversation_history.append(tool_message)
            save_session()
            
            # 5. RECURSION: Read tool output and speak — no thinking needed here
            console.print("[dim cyan]↻ Feeding result back to Bernard...[/dim cyan]")
            process_agentic_loop(tts_stream, is_followup=True)
            
    except Exception as e:
        console.print(f"[bold red]Error communicating with Ollama: {e}[/bold red]")
    
    return interrupted_input

def get_greeting():
    """Returns a time-appropriate greeting."""
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning sir. Bernard is online and ready to assist you."
    elif hour < 17:
        return "Good afternoon sir. Bernard is online and ready to assist you."
    else:
        return "Good evening sir. Bernard is online and ready to assist you."

def main():
    console.print(Panel(
        "[bold white]BERNARD COPILOT[/bold white]\n[dim]Autonomous AI Assistant • Local • Private[/dim]",
        border_style="bright_cyan",
        padding=(1, 4)
    ))
    
    # Initialize the TTS stream player with UK Male Voice
    try:
        engine = EdgeEngine(rate=25)
        engine.set_voice("en-GB-RyanNeural")
        console.print("[green]✓[/green] TTS Engine loaded (en-GB-RyanNeural @ 1.25x)")
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] EdgeEngine failed, using system voice: {e}")
        engine = SystemEngine()
        
    tts_stream = TextToAudioStream(engine)
    
    console.print("[dim]Loading Whisper Base STT Model...[/dim]")
    
    # When running as a PyInstaller bundle, use the bundled model instead of downloading
    whisper_model = "base"
    if getattr(sys, 'frozen', False):
        bundled_model_path = os.path.join(sys._MEIPASS, 'whisper_model')
        if os.path.exists(bundled_model_path):
            whisper_model = bundled_model_path
            console.print(f"[dim]Using bundled model from: {bundled_model_path}[/dim]")
    
    recorder = AudioToTextRecorder(
        model=whisper_model,                 # Whisper base (~74MB)
        language="en",                       # Skip language detection = faster
        compute_type="int8",                 # Quantized = faster inference
        spinner=False,                       # No terminal spinner clutter
        post_speech_silence_duration=0.3,    # React 0.3s after you stop talking (default: 0.6)
        min_length_of_recording=0.3,         # Accept very short commands
        pre_recording_buffer_duration=0.5,   # Keep 0.5s buffer before speech
        silero_sensitivity=0.4,              # VAD sensitivity (0=off, 1=max)
        beam_size=1,                         # Greedy decoding = fastest (default: 5)
        initial_prompt="Bernard AI assistant conversation.",  # Whisper context hint
    )
    console.print("[green]✓[/green] STT loaded (Whisper base • int8 • beam=1)")
    
    console.print()
    console.print(Panel(
        "[bold]🎤 Speak naturally into your microphone, OR\n"
        "⌨️  Type a message and press Enter.\n"
        "You can interrupt Bernard by speaking over him.\n"
        "Press Ctrl+C to exit.[/bold]",
        title="[bold bright_cyan]Ready[/bold bright_cyan]",
        border_style="bright_cyan",
        padding=(1, 2)
    ))
    
    # Startup Greeting — Bernard introduces himself
    greeting = get_greeting()
    console.print(f"\n[bold green]Bernard:[/bold green] {greeting}")
    tts_stream.feed(greeting)
    tts_stream.play_async(
        sentence_silence_duration=1.5,
        comma_silence_duration=0.3
    )
    while tts_stream.is_playing():
        time.sleep(0.1)
    
    # Shared queue for both voice and keyboard input
    import queue
    input_queue = queue.Queue()
    
    # Thread 1: Voice input (STT)
    def voice_input_loop():
        wake_words = ["bernard", "hey bernard", "ok bernard", "okay bernard", "hi bernard"]
        last_awake_time = 0
        AWAKE_DURATION = 15.0  # seconds Bernard stays awake after last interaction
        
        try:
            while True:
                text = recorder.text()
                if text and text.strip():
                    clean_text = text.lower().strip('.!?,\n ')
                    
                    # 1. Check if the transcript contains any wake word
                    is_wake_word_detected = False
                    for ww in wake_words:
                        if ww in clean_text:
                            is_wake_word_detected = True
                            
                            # Strip the wake word from the beginning if it starts with it
                            if clean_text.startswith(ww):
                                lower_orig = text.lower()
                                idx = lower_orig.find(ww)
                                if idx != -1:
                                    text = text[idx + len(ww):].strip('.!?,\n ')
                            break
                            
                    # 2. Check if Bernard is currently "awake" from a previous interaction
                    is_currently_awake = (time.time() - last_awake_time) < AWAKE_DURATION
                            
                    if is_wake_word_detected or is_currently_awake:
                        # Reset the awake timer because we had an interaction
                        last_awake_time = time.time()
                        
                        # If they just said "Bernard" and nothing else
                        if not text.strip():
                            text = "Yes, I am here."
                        
                        # Only print the "awake" status if we didn't use the wake word this time
                        if not is_wake_word_detected:
                            console.print("[dim italic](Processed because Bernard is awake)[/dim italic]")
                            
                        input_queue.put(("voice", text.strip()))
                    else:
                        # Ignored background speech (no wake word and not currently awake)
                        console.print(f"[dim]Ignored (asleep): {text}[/dim]")
        except Exception:
            pass
    
    # Thread 2: Keyboard input
    def keyboard_input_loop():
        try:
            while True:
                text = input()
                if text and text.strip():
                    input_queue.put(("keyboard", text.strip()))
        except (EOFError, KeyboardInterrupt):
            pass
    
    # Start both input threads
    voice_thread = threading.Thread(target=voice_input_loop, daemon=True)
    keyboard_thread = threading.Thread(target=keyboard_input_loop, daemon=True)
    voice_thread.start()
    keyboard_thread.start()
    
    console.print("[dim]Listening for voice or keyboard input...[/dim]\n")
    
    def check_exit(text):
        clean_text = text.lower().strip().strip('.').strip('!')
        if clean_text in ["quit", "exit", "stop", "goodbye", "bye"]:
            console.print("\n[bold red]Shutting down Bernard...[/bold red]")
            goodbye_msg = "Goodbye sir. Shutting down."
            console.print(f"[bold green]Bernard:[/bold green] {goodbye_msg}")
            tts_stream.feed(goodbye_msg)
            tts_stream.play_async(sentence_silence_duration=1.5, comma_silence_duration=0.3)
            while tts_stream.is_playing():
                time.sleep(0.1)
            return True
        return False
    
    try:
        while True:
            # Block until either voice or keyboard gives us input
            source, user_text = input_queue.get()
            
            if check_exit(user_text):
                break
            
            # Show user input nicely
            if source == "voice":
                icon = "🎤"
                label = "You (Voice)"
                color = "bright_magenta"
            else:
                icon = "⌨️"
                label = "You (Typed)"
                color = "bright_blue"
            
            console.print(Panel(
                user_text,
                title=f"[bold {color}]{icon} {label}[/bold {color}]",
                border_style=color,
                padding=(0, 2)
            ))
            
            # Append user input to memory
            conversation_history.append({'role': 'user', 'content': user_text})
            save_session()
                
            # Stream through the Brain (Agentic Loop)
            interrupted = process_agentic_loop(tts_stream)
            
            # If Bernard was interrupted, process the interrupting input immediately
            while interrupted:
                source, user_text = interrupted
                
                if check_exit(user_text):
                    break
                    
                if source == "voice":
                    icon, label, color = "🎤", "You (Voice)", "bright_magenta"
                else:
                    icon, label, color = "⌨️", "You (Typed)", "bright_blue"
                
                console.print(Panel(
                    user_text,
                    title=f"[bold {color}]{icon} {label}[/bold {color}]",
                    border_style=color,
                    padding=(0, 2)
                ))
                conversation_history.append({'role': 'user', 'content': user_text})
                save_session()
                interrupted = process_agentic_loop(tts_stream)
 
             
    except KeyboardInterrupt:
        console.print("\n[bold red]Force shutting down... Goodbye![/bold red]")
        
    # Cleanup on exit
    try:
        recorder.shutdown()
    except:
        pass

if __name__ == '__main__':
    main()
