import os
import time
import threading
import queue
import re
import ollama

# Inject mpv into path automatically so Edge TTS works flawlessly
os.environ["PATH"] += os.pathsep + r"C:\Program Files\MPV Player"
from RealtimeTTS import TextToAudioStream, EdgeEngine, SystemEngine
from RealtimeSTT import AudioToTextRecorder

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from action_executor import execute_action
from llm_client import SYSTEM_PROMPT

console = Console()

# The Conversation Memory: Allows Bernard to remember past messages and tool outputs
conversation_history = [
    {'role': 'system', 'content': SYSTEM_PROMPT}
]

# Shared input queue — used by both voice and keyboard threads, and also for barge-in
input_queue = queue.Queue()

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
    if is_followup:
        # Follow-up after tool execution: just speak the result, no thinking needed
        use_thinking = False
        console.print("\n[bold cyan]━━━ Bernard is summarizing... ━━━[/bold cyan]")
    else:
        # Initial user query: always think (needed for tool routing)
        # Check for extra-deep thinking keywords
        last_user_msg = ""
        for msg in reversed(conversation_history):
            if msg['role'] == 'user':
                last_user_msg = msg['content'].lower()
                break
        
        think_keywords = ["think", "reason", "explain", "analyze", "debug", "solve", "calculate", "compare", "why"]
        is_complex = any(kw in last_user_msg for kw in think_keywords)
        use_thinking = True  # Always think on initial queries
        
        if is_complex:
            console.print("\n[bold cyan]━━━ Bernard is thinking deeply... 🧠 ━━━[/bold cyan]")
        else:
            console.print("\n[bold cyan]━━━ Bernard is thinking... ━━━[/bold cyan]")
    
    try:
        response_stream = ollama.chat(
            model='gemma4:e2b',
            messages=conversation_history,
            stream=True,
            think=use_thinking
        )

        first_chunk = True
        is_json_action = False
        json_buffer = ""
        spoken_text = ""

        # Internal generator to feed the TTS dynamically
        def tts_generator():
            nonlocal first_chunk, is_json_action, json_buffer, spoken_text
            for chunk in response_stream:
                content = chunk['message']['content']
                if not content:
                    continue
                
                # Check the very first character to decide if it's an action or speech
                if first_chunk:
                    first_chunk = False
                    if content.strip().startswith('{'):
                        is_json_action = True
                        console.print("[dim yellow]⚡ Action detected — routing to executor...[/dim yellow]")
                
                if is_json_action:
                    json_buffer += content
                    # Show JSON tokens streaming in
                    print(content, end="", flush=True)
                else:
                    spoken_text += content
                    # Show raw tokens in terminal (with markdown)
                    print(content, end="", flush=True)
                    # Feed cleaned text to TTS (no asterisks)
                    yield strip_markdown(content)

        # Feed text to TTS. If it's spoken text, audio streams immediately.
        tts_stream.feed(tts_generator())
        tts_stream.play_async()

        # Keep thread alive while TTS plays, but also check for barge-in
        # If the user speaks or types while Bernard is talking, the input_queue
        # will receive a message — we use that as the interrupt signal!
        interrupted_input = None
        while tts_stream.is_playing():
            if not input_queue.empty():
                interrupted_input = input_queue.get_nowait()
                tts_stream.stop()
                console.print("\n[bold red]⏸ Interrupted![/bold red]")
                break
            time.sleep(0.05)
        
        print()  # Newline after streaming tokens

        # Save what Bernard said to memory (even if interrupted)
        if spoken_text.strip() and not is_json_action:
            conversation_history.append({'role': 'assistant', 'content': spoken_text})
            # Render the final response as pretty markdown
            console.print(Panel(
                Markdown(spoken_text.strip()),
                title="[bold green]Bernard[/bold green]",
                border_style="green",
                padding=(1, 2)
            ))

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
        return "Good morning, sir. Bernard is online and ready to assist you."
    elif hour < 17:
        return "Good afternoon, sir. Bernard is online and ready to assist you."
    else:
        return "Good evening, sir. Bernard is online and ready to assist you."

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
    
    console.print("[dim]Loading Whisper Tiny STT Model...[/dim]")
    recorder = AudioToTextRecorder(
        model="tiny",                        # Whisper tiny (~39MB, fastest)
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
    console.print("[green]✓[/green] STT loaded (Whisper tiny • int8 • beam=1)")
    
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
    tts_stream.play_async()
    while tts_stream.is_playing():
        time.sleep(0.1)
    
    # Shared queue for both voice and keyboard input
    import queue
    input_queue = queue.Queue()
    
    # Thread 1: Voice input (STT)
    def voice_input_loop():
        try:
            while True:
                text = recorder.text()
                if text and text.strip():
                    input_queue.put(("voice", text.strip()))
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
    
    try:
        while True:
            # Block until either voice or keyboard gives us input
            source, user_text = input_queue.get()
            
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
                
            # Stream through the Brain (Agentic Loop)
            interrupted = process_agentic_loop(tts_stream)
            
            # If Bernard was interrupted, process the interrupting input immediately
            while interrupted:
                source, user_text = interrupted
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
                interrupted = process_agentic_loop(tts_stream)
 
             
    except KeyboardInterrupt:
        console.print("\n[bold red]Shutting down Bernard. Goodbye![/bold red]")
        try:
            recorder.shutdown()
        except:
            pass

if __name__ == '__main__':
    main()
