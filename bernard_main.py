import os
import time
import threading
import queue
import re
import sys
import logging
import warnings
import ollama
import webview

ui_window = None

def update_ui_state(state, amplitude=0):
    try:
        import webview
        windows = webview.windows
        if windows:
            windows[0].evaluate_js(f"if(window.updateBernardState) window.updateBernardState('{state}', {amplitude})")
    except Exception:
        pass

def add_chat_message(role, text, is_partial=False):
    try:
        import webview
        windows = webview.windows
        if windows:
            escaped_text = text.replace('\\', '\\\\').replace('`', '\\`')
            is_p = 'true' if is_partial else 'false'
            windows[0].evaluate_js(f"if(window.addChatMessage) window.addChatMessage('{role}', `{escaped_text}`, {is_p})")
    except Exception:
        pass

# Suppress messy developer warnings from PyTorch and Hugging Face
warnings.filterwarnings("ignore")
logging.getLogger().setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

# Force UTF-8 encoding for standard output to prevent emoji/unicode crashes on Windows terminals
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
# Inject mpv into path automatically so Edge TTS works flawlessly
os.environ["PATH"] += os.pathsep + r"C:\Program Files\MPV Player"
from RealtimeTTS import TextToAudioStream, SystemEngine, KokoroEngine
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
    
    interrupted_input = None
    
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
        update_ui_state('thinking')
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
        def tts_audio_chunk(chunk):
            import numpy as np
            try:
                # RealtimeTTS passes 16-bit PCM chunks by default
                audio = np.frombuffer(chunk, dtype=np.int16)
                amp = min(1.0, float(np.sqrt(np.mean((audio / 32768.0)**2)) * 5))
                update_ui_state('speaking', amp)
            except Exception:
                pass

        tts_stream.feed(tts_generator())
        tts_stream.play_async(
            fast_sentence_fragment=False,
            buffer_threshold_seconds=0.5,
            minimum_sentence_length=15,
            minimum_first_fragment_length=15,
            sentence_silence_duration=0.8,
            comma_silence_duration=0.3,
            on_audio_chunk=tts_audio_chunk
        )
        
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
                    add_chat_message('assistant', spoken_text, True)
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
                add_chat_message('assistant', spoken_text, True)
                return strip_markdown(content)

        try:
            # Inject a short silence to wake up the soundcard and avoid clipping the first word
            tts_queue.put("[wake] ")

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
            add_chat_message('assistant', spoken_text, False)

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
    import time
    # Allow the WebView DOM a moment to mount before changing state
    time.sleep(1)
    update_ui_state('loading')
    
    console.print(Panel(
        "[bold white]BERNARD COPILOT[/bold white]\n[dim]Autonomous AI Assistant • Local • Private[/dim]",
        border_style="bright_cyan",
        padding=(1, 4)
    ))
    
    # Initialize the TTS stream player with Kokoro Neural Voice
    try:
        console.print("[dim]Allocating VRAM and initializing local Kokoro Neural Engine...[/dim]")
        engine = KokoroEngine(
            voice="0.5*bm_lewis + 0.5*am_puck + 0.2*af_bella + 0.3*bm_george + 0.4*am_michael",  # Custom 5-voice blend
            default_speed=1.25,
            trim_silence=True,
            extra_start_ms=0, # Prevent deleting the first consonant
            fade_in_ms=10     # Prevent a sharp 'pop' at the start of the audio
        )
        console.print("[green]✓[/green] TTS Engine loaded (Kokoro • custom_blend @ 1.25x)")
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] KokoroEngine failed, using system voice: {e}")
        engine = SystemEngine()
        
    tts_stream = TextToAudioStream(engine)
    tts_stream.add_pause("wake", 0.4) # Add 400ms silence tag to wake up Bluetooth headsets and PyAudio
    
    console.print("[dim]Loading Moonshine v2 Tiny STT Model...[/dim]")
    
    # When running as a PyInstaller bundle, handle bundled model path here if packaging Moonshine in the future
    
    def realtime_callback(text):
        if text.strip():
            # \r carriage return and \033[K clears the current line so it acts in-place
            sys.stdout.write(f"\r\033[K\033[90m🎤 {text}\033[0m")
            sys.stdout.flush()
            add_chat_message('user', text.strip(), True)

    recorder = AudioToTextRecorder(
        transcription_engine="moonshine",
        model="UsefulSensors/moonshine-streaming-tiny",
        language="en",
        spinner=False,
        post_speech_silence_duration=0.3,
        min_length_of_recording=0.3,
        pre_recording_buffer_duration=0.5,
        silero_sensitivity=0.4,
        initial_prompt="Bernard AI assistant conversation.",
        enable_realtime_transcription=True,
        use_main_model_for_realtime=True,
        on_realtime_transcription_update=realtime_callback,
        on_vad_detect_start=lambda: update_ui_state('listening'),
        on_vad_detect_stop=lambda: update_ui_state('idle'),
    )
    console.print("[green]✓[/green] STT loaded (Moonshine v2 Tiny • Streaming)")
    
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
    update_ui_state('idle')
    greeting = get_greeting()
    console.print(f"\n[bold green]Bernard:[/bold green] {greeting}")
    add_chat_message('assistant', greeting, False)
    tts_stream.feed(f"[wake] {greeting}")
    tts_stream.play_async(
        sentence_silence_duration=1.5,
        comma_silence_duration=0.3
    )
    while tts_stream.is_playing():
        time.sleep(0.1)
    
    # Shared queue for both voice and keyboard input is defined globally
    # Thread 1: Voice input (STT)
    def voice_input_loop():
        try:
            while True:
                text = recorder.text()
                if text and text.strip():
                    sys.stdout.write("\r\033[K")
                    sys.stdout.flush()
                    add_chat_message('user', text.strip(), False)
                    input_queue.put(("voice", text.strip()))
        except Exception:
            pass
    
    # Thread 2: Keyboard input
    def keyboard_input_loop():
        try:
            while True:
                text = input()
                if text and text.strip():
                    add_chat_message('user', text.strip(), False)
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
            tts_stream.feed(f"[wake] {goodbye_msg}")
            tts_stream.play_async(sentence_silence_duration=1.5, comma_silence_duration=0.3)
            while tts_stream.is_playing():
                time.sleep(0.1)
            
            # Forcefully exit the process to kill all stubborn background STT/TTS threads
            try:
                recorder.shutdown()
            except:
                pass
            os._exit(0)
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
