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
from llm_client import get_system_prompt

import json
import asyncio
import sys
import os

console = Console()

SESSION_FILE = "session.json"

# The Conversation Memory
conversation_history = [
    {'role': 'system', 'content': get_system_prompt()}
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

def process_agentic_loop(tts_stream, is_followup=False, depth=0):
    """
    Streams the response from Ollama using the full conversation history.
    Shows live thinking tokens and final formatted markdown output.
    Supports barge-in and agentic tool recursion.
    """
    from rich.status import Status
    from rich.live import Live
    
    interrupted_input = None
    
    # Determine if thinking is needed based on query complexity
    use_thinking = False
    status_msg = "[bold cyan]Bernard is thinking...[/bold cyan]"
    
    last_user_msg = ""
    for msg in reversed(conversation_history):
        if msg['role'] == 'user':
            last_user_msg = msg['content'].lower()
            break
            
    think_keywords = ["think", "reason", "explain", "analyze", "debug", "solve", "calculate", "compare", "why"]
    is_complex = any(kw in last_user_msg for kw in think_keywords)
    
    if depth >= 5:
        use_thinking = False
        status_msg = "[bold red]Bernard is exhausted from trying...[/bold red]"
    elif is_followup:
        status_msg = f"[bold cyan]Bernard is analyzing results (Step {depth})...[/bold cyan]"
        use_thinking = True  # Tool outputs might need reasoning
    else:
        use_thinking = is_complex
        status_msg = "[bold cyan]Bernard is thinking deeply... 🧠[/bold cyan]" if is_complex else "[bold cyan]Bernard is thinking...[/bold cyan]"

    
    try:
        update_ui_state('thinking')
        # Show thinking spinner while waiting for first token
        system_prompt = get_system_prompt()
        if use_thinking:
            system_prompt += "\nCRITICAL: You must think step-by-step. Put your reasoning inside <think>...</think> tags BEFORE your final response."
        
        conversation_history[0]['content'] = system_prompt
        
        import json
        import os
        config_path = "config.json"
        config = {}
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                try: config = json.load(f)
                except: pass
                
        llm_provider = config.get("llm_provider", "ollama")
        
        with Status(status_msg, spinner="dots", console=console):
            if llm_provider == "ollama":
                response_stream = ollama.chat(
                    model=config.get("llm_model", "gemma4:e2b"),
                    messages=conversation_history,
                    stream=True,
                    think=use_thinking
                )
                try:
                    first_chunk_data = next(response_stream)
                    first_text = first_chunk_data['message']['content']
                except StopIteration:
                    return None
            else:
                from openai import OpenAI
                client = OpenAI(
                    api_key=config.get("llm_api_key", ""),
                    base_url=config.get("llm_base_url", "https://api.openai.com/v1")
                )
                response_stream = client.chat.completions.create(
                    model=config.get("llm_model", "gpt-4o"),
                    messages=conversation_history,
                    stream=True,
                    temperature=0.8
                )
                try:
                    first_chunk_data = next(response_stream)
                    first_text = first_chunk_data.choices[0].delta.content or ""
                except StopIteration:
                    return None

        first_chunk = True
        is_json_action = False
        json_buffer = ""
        spoken_text = ""
        
        detection_buffer = ""
        decided = False
        
        expression_buffer = ""
        in_expression = False
        expressions_queue = []
        
        in_think = False
        potential_tag = ""

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
        audio_played_seconds = 0.0
        CHARS_PER_SECOND = 18.0 # Estimated speech rate at 1.25x speed
        
        def tts_audio_chunk(chunk):
            nonlocal audio_played_seconds
            import numpy as np
            try:
                # RealtimeTTS passes 16-bit PCM chunks by default
                audio = np.frombuffer(chunk, dtype=np.int16)
                audio_played_seconds += len(audio) / 24000.0 # Kokoro sample rate
                
                current_char_estimate = audio_played_seconds * CHARS_PER_SECOND
                for expr in expressions_queue:
                    if not expr.get('triggered') and current_char_estimate >= expr['char_index']:
                        expr['triggered'] = True
                        try:
                            import webview
                            windows = webview.windows
                            if windows:
                                windows[0].evaluate_js(f"if(window.triggerExpression) window.triggerExpression('{expr['exp']}')")
                        except Exception:
                            pass
                
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
            nonlocal expression_buffer, in_expression, in_think, potential_tag
            
            if not content:
                return None
                
            clean_output = ""
            for char in content:
                # 1. Handle <think> tags (which can span chunks)
                if char == '<':
                    potential_tag += char
                    continue
                elif potential_tag.startswith('<'):
                    potential_tag += char
                    if potential_tag == '<think>':
                        in_think = True
                        potential_tag = ""
                        continue
                    elif potential_tag == '</think>':
                        in_think = False
                        potential_tag = ""
                        continue
                    elif not ('<think>'.startswith(potential_tag) or '</think>'.startswith(potential_tag)):
                        # False alarm, flush potential_tag
                        if not in_think:
                            # Re-process the flushed tag characters through the expression logic below
                            for c in potential_tag:
                                if c == '[' and not in_expression:
                                    in_expression = True
                                    expression_buffer = "["
                                elif in_expression:
                                    expression_buffer += c
                                    if c == ']':
                                        in_expression = False
                                        if expression_buffer.startswith("[exp:"):
                                            exp_name = expression_buffer[5:-1]
                                            expressions_queue.append({
                                                'char_index': len(spoken_text + clean_output),
                                                'exp': exp_name,
                                                'triggered': False
                                            })
                                        elif "No tool call" not in expression_buffer and "[END]" not in expression_buffer: # Ignore tool hallucination tags
                                            clean_output += expression_buffer
                                        expression_buffer = ""
                                else:
                                    clean_output += c
                        potential_tag = ""
                    continue
                    
                if in_think:
                    continue

                # 2. Handle [exp:...] tags and ignore [No tool call needed]
                if char == '[' and not in_expression:
                    in_expression = True
                    expression_buffer = "["
                elif in_expression:
                    expression_buffer += char
                    if char == ']':
                        in_expression = False
                        if expression_buffer.startswith("[exp:"):
                            exp_name = expression_buffer[5:-1]
                            expressions_queue.append({
                                'char_index': len(spoken_text + clean_output),
                                'exp': exp_name,
                                'triggered': False
                            })
                            console.print(f"\n[dim magenta]👉 Expression queued: {exp_name}[/dim magenta]")
                        elif "No tool call" not in expression_buffer and "[END]" not in expression_buffer:
                            clean_output += expression_buffer
                        expression_buffer = ""
                else:
                    clean_output += char
            
            content = clean_output
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
                    from rich.markup import escape
                    decided = True
                    is_json_action = False
                    spoken_text += detection_buffer
                    console.print(f"\n[bold green]Bernard:[/bold green] {escape(detection_buffer)}", end="")
                    sys.stdout.flush()
                    add_chat_message('assistant', spoken_text, True)
                    return strip_markdown(detection_buffer)
                else:
                    return None
                    
            if is_json_action:
                json_buffer += content
                return None
            else:
                from rich.markup import escape
                spoken_text += content
                console.print(escape(content), end="")
                sys.stdout.flush()
                add_chat_message('assistant', spoken_text, True)
                return strip_markdown(content)

        try:
            # Inject a short silence to wake up the soundcard and avoid clipping the first word
            tts_queue.put("[wake] ")

            # Process the first chunk
            clean_text = process_chunk(first_text)
            if clean_text: tts_queue.put(clean_text)
            
            # Stream the rest in main thread
            for chunk in response_stream:
                if llm_provider == "ollama":
                    content = chunk['message']['content']
                else:
                    content = chunk.choices[0].delta.content or ""
                    
                clean_text = process_chunk(content)
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
            
            # 5. RECURSION: Read tool output and speak or call another tool
            console.print("[dim cyan]↻ Feeding result back to Bernard...[/dim cyan]")
            process_agentic_loop(tts_stream, is_followup=True, depth=depth + 1)
            
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
            update_ui_state('expression', 'dead')
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
