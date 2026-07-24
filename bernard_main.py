import os
import sys

# Force Hugging Face to cache all models in the project folder BEFORE importing any libraries
os.environ["HF_HOME"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.environ["MODELSCOPE_CACHE"] = os.environ["HF_HOME"]

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

def resolve_env_vars(value):
    """Replace ${VAR_NAME} with environment variable value."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        return os.environ.get(env_var, "")
    return value

import time
import threading
import queue
import re
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

def add_chat_message(role, text, is_partial=False, widget=None):
    try:
        import webview
        import json
        windows = webview.windows
        if windows:
            escaped_text = text.replace('\\', '\\\\').replace('`', '\\`')
            is_p = 'true' if is_partial else 'false'
            widget_json = json.dumps(widget) if widget else "null"
            windows[0].evaluate_js(f"if(window.addChatMessage) window.addChatMessage('{role}', `{escaped_text}`, {is_p}, {widget_json})")
    except Exception:
        pass

def update_ui_thought(thought_text):
    try:
        import webview
        windows = webview.windows
        if windows:
            escaped_text = thought_text.replace('\\', '\\\\').replace('`', '\\`')
            windows[0].evaluate_js(f"if(window.updateBernardThought) window.updateBernardThought(`{escaped_text}`)")
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
from RealtimeTTS import TextToAudioStream, SystemEngine, KokoroEngine, FasterQwenEngine, FasterQwenVoice
from RealtimeTTS.engines.base_engine import BaseEngine
from RealtimeSTT import AudioToTextRecorder
import requests
import pyaudio

class ProperCartesiaEngine(BaseEngine):
    def __init__(self, api_key: str, model_id: str = "sonic-3.5", voice_id: str = "4bc3cb8c-adb9-4bb8-b5d5-cbbef950b991"):
        self.api_key = api_key
        self.model_id = model_id
        self.voice_id = voice_id
        self.sample_rate = 44100
        import queue
        self.queue = queue.Queue()

    def get_stream_info(self):
        return (pyaudio.paInt16, 1, self.sample_rate)

    def synthesize(self, text: str, *args, **kwargs) -> bool:
        url = "https://api.cartesia.ai/tts/bytes"
        headers = {
            "Cartesia-Version": "2024-03-01",
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        data = {
            "model_id": self.model_id,
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": self.voice_id
            },
            "output_format": {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": self.sample_rate
            }
        }
        try:
            with requests.post(url, headers=headers, json=data, stream=True) as r:
                r.raise_for_status()
                buffer = b""
                for chunk in r.iter_content(chunk_size=4096):
                    if getattr(self, "stop_synthesis_event", None) and self.stop_synthesis_event.is_set():
                        break
                    if chunk:
                        buffer += chunk
                        if len(buffer) >= 2:
                            send_len = len(buffer) - (len(buffer) % 2)
                            self.queue.put(buffer[:send_len])
                            buffer = buffer[send_len:]
            return True
        except Exception as e:
            print(f"[ProperCartesiaEngine] Error: {e}")
            return False


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

def compact_context():
    """
    Checks if conversation history exceeds ~8000 tokens.
    If so, compacts the oldest messages, saves to JSON, and removes them from active context.
    """
    try:
        # Exclude massive base64 image strings from length calculation
        text_only_history = []
        for msg in conversation_history:
            clean_msg = {k: v for k, v in msg.items() if k != 'images'}
            text_only_history.append(clean_msg)
            
        # Rough token estimate: 1 token ~= 4 characters
        history_str = json.dumps(text_only_history)
        if len(history_str) > 32000: # ~8000 tokens
            from rich.console import Console
            c = Console()
            c.print("\n[dim cyan]🗜️ Context limit reached. Compacting old memories...[/dim cyan]")
            
            # Keep system prompt (index 0) and the 10 most recent messages.
            # Compact everything between index 1 and len - 10
            messages_to_compact = conversation_history[1:-10]
            if not messages_to_compact: return
            
            summary_prompt = "Summarize the following conversation history into a dense, highly detailed block of context. Retain all factual information, user preferences, names, links, and tool outcomes. Do not speak to the user, output only the condensed facts.\n\n"
            summary_prompt += json.dumps(messages_to_compact)
            
            config = {}
            if os.path.exists("config.json"):
                try:
                    with open("config.json", "r") as f:
                        config = json.load(f)
                except: pass
            
            initial_provider = config.get("current_provider", "ollama")
            providers = config.get("providers", {})
            
            fallback_order = [initial_provider]
            for p in ["nvidia", "openrouter", "ollama"]:
                if p not in fallback_order:
                    fallback_order.append(p)
                    
            summary_text = ""
            for llm_provider in fallback_order:
                provider_config = providers.get(llm_provider, {})
                # Resolve environment variables in provider config
                resolved_config = {k: resolve_env_vars(v) for k, v in provider_config.items()}
                model_name = resolved_config.get("model", "gemma:2b")
                
                try:
                    if llm_provider == "ollama":
                        import ollama
                        summary_response = ollama.chat(
                            model=model_name,
                            messages=[{'role': 'user', 'content': summary_prompt}]
                        )
                        summary_text = summary_response['message']['content']
                    else:
                        from openai import OpenAI
                        client = OpenAI(
                            api_key=resolved_config.get("api_key", ""),
                            base_url=resolved_config.get("base_url", "https://api.openai.com/v1")
                        )
                        summary_response = client.chat.completions.create(
                            model=model_name,
                            messages=[{'role': 'user', 'content': summary_prompt}],
                            temperature=0.2
                        )
                        summary_text = summary_response.choices[0].message.content or ""
                    break
                except Exception as e:
                    c.print(f"[dim red]Summarizer failed with {llm_provider}: {e}[/dim red]")
                    continue
            
            if not summary_text:
                c.print("[bold red]Context summarization failed across all providers![/bold red]")
                return
            
            # Save to long term JSON memory
            long_term_file = "bernard_long_term_memory.json"
            long_term_data = []
            if os.path.exists(long_term_file):
                with open(long_term_file, "r", encoding="utf-8") as f:
                    try: long_term_data = json.load(f)
                    except: pass
            
            import datetime
            long_term_data.append({
                "timestamp": datetime.datetime.now().isoformat(),
                "summary": summary_text
            })
            
            with open(long_term_file, "w", encoding="utf-8") as f:
                json.dump(long_term_data, f, indent=2)
                
            # Delete the compacted messages from active history
            del conversation_history[1:-10]
            save_session()
            c.print("[dim cyan]✓ Old memories compacted and stored in JSON.[/dim cyan]\n")
    except Exception as e:
        print(f"Error during context compaction: {e}")

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

def process_agentic_loop(tts_stream, is_followup=False, depth=0, parent_tts_queue=None):
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
        from llm_client import resolve_env_vars
        config_path = "config.json"
        config = {}
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                try: config = json.load(f)
                except: pass
                
        initial_provider = config.get("current_provider", "ollama")
        providers = config.get("providers", {})
        
        # Strictly use the selected provider, no sneaky fallbacks to paid APIs
        llm_provider = initial_provider
        provider_config = providers.get(llm_provider, {})
        
        # Resolve environment variables in provider config
        resolved_config = {}
        for key, value in provider_config.items():
            resolved_config[key] = resolve_env_vars(value)
        
        model_name = resolved_config.get("model", "gemma:2b")
        ollama_options = resolved_config.get("options", {})
                
        success = False
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
        think_buffer = ""
        in_speak = False
        speak_buffer = ""
        potential_tag = ""

        import queue
        import sys
        tts_queue = parent_tts_queue if parent_tts_queue is not None else queue.Queue()
        
        if parent_tts_queue is None:
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
            
            def start_tts_when_ready():
                # If we are in a recursive tool loop, the previous TTS might still be playing "Let me check...".
                # play_async() ignores calls if it's already playing, so we wait for the old audio to finish first.
                if is_followup:
                    while tts_stream.is_playing():
                        time.sleep(0.05)
                tts_stream.play_async(
                    fast_sentence_fragment=False,
                    buffer_threshold_seconds=0.5,
                    minimum_sentence_length=20,
                    minimum_first_fragment_length=20,
                    sentence_silence_duration=0.4,
                    comma_silence_duration=0.15,
                    language="en",
                    on_audio_chunk=tts_audio_chunk
                )
                
            threading.Thread(target=start_tts_when_ready, daemon=True).start()
        
        def process_chunk(content):
            nonlocal decided, is_json_action, json_buffer, spoken_text, detection_buffer
            nonlocal expression_buffer, in_expression, in_think, think_buffer, in_speak, speak_buffer, potential_tag
            
            if not content:
                return None
                
            clean_output = ""
            speak_output = ""
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
                    elif potential_tag == '<speak>':
                        in_speak = True
                        potential_tag = ""
                        continue
                    elif potential_tag == '</speak>':
                        in_speak = False
                        potential_tag = ""
                        continue
                    elif not ('<think>'.startswith(potential_tag) or '</think>'.startswith(potential_tag) or '<speak>'.startswith(potential_tag) or '</speak>'.startswith(potential_tag)):
                        # False alarm, flush potential_tag
                        if in_speak:
                            if not speak_buffer:
                                console.print("\n[bold green]Bernard:[/bold green] ", end="")
                            from rich.markup import escape
                            speak_buffer += potential_tag
                            speak_output += potential_tag
                            console.print(escape(potential_tag), end="")
                            sys.stdout.flush()
                        elif not in_think:
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
                    think_buffer += char
                    continue
                    
                if in_speak:
                    if not speak_buffer:
                        console.print("\n[bold green]Bernard:[/bold green] ", end="")
                    from rich.markup import escape
                    speak_buffer += char
                    speak_output += char
                    console.print(escape(char), end="")
                    sys.stdout.flush()
                    continue

                # 2. Handle [exp:...] and <exp:...> tags and ignore [No tool call needed]
                if (char == '[' or char == '<') and not in_expression:
                    in_expression = True
                    expression_buffer = char
                elif in_expression:
                    expression_buffer += char
                    if char == ']' or char == '>':
                        in_expression = False
                        lower_expr = expression_buffer.lower()
                        if lower_expr.startswith("[exp:") or lower_expr.startswith("<exp:"):
                            exp_name = expression_buffer[5:-1]
                            expressions_queue.append({
                                'char_index': len(spoken_text + clean_output),
                                'exp': exp_name,
                                'triggered': False
                            })
                            console.print(f"\n[dim magenta]👉 Expression queued: {exp_name}[/dim magenta]")
                        elif not any(ignored in lower_expr for ignored in ["no tool call", "[end]", "[speak]", "<speak>", "</speak>", "[/speak]", "[think]", "<think>", "</think>", "[/think]"]):
                            clean_output += expression_buffer
                        expression_buffer = ""
                else:
                    clean_output += char
            result_tts = ""
            if speak_output:
                result_tts += strip_markdown(speak_output)
                
            content = clean_output
            if not content:
                return result_tts if result_tts else None
                
            if not decided:
                detection_buffer += content
                stripped = detection_buffer.strip()
                
                if '{' in stripped and ('action' in stripped or stripped.startswith('{') or stripped.startswith('```json')):
                    decided = True
                    is_json_action = True
                    json_buffer += detection_buffer
                    console.print("\n[dim yellow]⚡ Streaming Action...[/dim yellow]")
                    return result_tts if result_tts else None
                elif len(stripped) > 25 and '{' not in stripped:
                    from rich.markup import escape
                    decided = True
                    is_json_action = False
                    spoken_text += detection_buffer
                    console.print(f"\n[bold green]Bernard:[/bold green] {escape(detection_buffer)}", end="")
                    sys.stdout.flush()
                    add_chat_message('assistant', spoken_text, True)
                    result_tts += strip_markdown(detection_buffer)
                    return result_tts if result_tts else None
                else:
                    return result_tts if result_tts else None
                    
            if is_json_action:
                json_buffer += content
                return result_tts if result_tts else None
            else:
                from rich.markup import escape
                spoken_text += content
                console.print(escape(content), end="")
                sys.stdout.flush()
                add_chat_message('assistant', spoken_text, True)
                result_tts += strip_markdown(content)
                
            if think_buffer:
                update_ui_thought(think_buffer)
                
            return result_tts if result_tts else None

        try:
            with Status(f"{status_msg} [{llm_provider}]", spinner="dots", console=console):
                if llm_provider == "ollama":
                    response_stream = ollama.chat(
                        model=model_name,
                        messages=conversation_history,
                        stream=True,
                        options=ollama_options,
                        think=use_thinking
                    )
                    first_chunk_data = next(response_stream)
                    first_text = first_chunk_data['message']['content']
                else:
                    from openai import OpenAI
                    client = OpenAI(
                        api_key=resolved_config.get("api_key", ""),
                        base_url=resolved_config.get("base_url", "https://api.openai.com/v1"),
                        timeout=15.0
                    )
                    response_stream = client.chat.completions.create(
                        model=model_name,
                        messages=conversation_history,
                        stream=True,
                        temperature=0.8
                    )
                    first_chunk_data = next(response_stream)
                    
            success = True
        except Exception as e:
            console.print(f"[bold red]Failed connecting to {llm_provider}: {e}[/bold red]")
            return None

        try:
            # Inject a short silence to wake up the soundcard and avoid clipping the first word
            tts_queue.put("[wake] ")

            raw_llm_response = ""
            in_native_reasoning = False
            
            def token_generator():
                nonlocal in_native_reasoning
                chunks = [first_chunk_data]
                def get_next():
                    if chunks: return chunks.pop(0)
                    try: return next(response_stream)
                    except StopIteration: return None
                
                while True:
                    chunk = get_next()
                    if not chunk:
                        if in_native_reasoning:
                            yield "</think>\n"
                        break
                        
                    if llm_provider == "ollama":
                        msg = getattr(chunk, 'message', None)
                        if type(chunk) is dict:
                            msg = chunk.get('message', {})
                            yield msg.get('content', "") or ""
                        else:
                            yield msg.content if msg and hasattr(msg, 'content') else ""
                    else:
                        delta = chunk.choices[0].delta if chunk.choices else None
                        if not delta: continue
                        
                        content = getattr(delta, 'content', None) or ""
                        reasoning = getattr(delta, 'reasoning_content', None) or getattr(delta, 'reasoning', None) or ""
                        
                        if reasoning:
                            if not in_native_reasoning:
                                in_native_reasoning = True
                                yield "<think>\n" + reasoning
                            else:
                                yield reasoning
                        elif content:
                            if in_native_reasoning:
                                in_native_reasoning = False
                                yield "\n</think>\n" + content
                            else:
                                yield content

            # Stream the response in main thread
            for token in token_generator():
                raw_llm_response += token
                clean_text = process_chunk(token)
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
            pass # We no longer put None here! We wait until the entire recursion tree finishes.

        # Fallback JSON Extraction: Sometimes small local models ignore the <speak> tags
        # and embed the JSON tool call at the end of their conversational text.
        if not is_json_action and spoken_text.strip():
            import re
            json_match = re.search(r'(\{[\s\S]*"action"[\s\S]*\})', spoken_text)
            if json_match:
                try:
                    parsed_json = json.loads(json_match.group(1))
                    if "action" in parsed_json:
                        is_json_action = True
                        json_buffer = json_match.group(1)
                        spoken_text = spoken_text.replace(json_buffer, "").strip()
                        console.print("\n[dim yellow]⚡ Recovered Action from Speech Buffer[/dim yellow]")
                except Exception:
                    pass

        # Save what Bernard said to memory
        if is_json_action:
            # We MUST save the exact raw response so vLLM parser sees perfectly matching tool call blocks
            conversation_history.append({'role': 'assistant', 'content': raw_llm_response})
            save_session()
            if speak_buffer.strip():
                add_chat_message('assistant', speak_buffer, False)
        else:
            if spoken_text.strip():
                conversation_history.append({'role': 'assistant', 'content': raw_llm_response})
                save_session()
                add_chat_message('assistant', spoken_text, False)

        # If it was an action instead of speech, execute it!
        # Do this BEFORE waiting for TTS so that tasks execute in parallel with speech!
        result_dict = None
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
            update_ui_state('working')
            action_name = ""
            try:
                action_data = json.loads(json_buffer)
                action_name = action_data.get("action", "tool")
                try:
                    import webview
                    import webview
                    if webview.windows:
                        webview.windows[0].evaluate_js(f"if(window.updateBernardAction) window.updateBernardAction('{action_name}')")
                except Exception:
                    pass
            except Exception:
                pass
            
            tool_result = None
            tool_finished = False
            
            def run_tool():
                nonlocal tool_result, tool_finished
                tool_result = execute_action(json_buffer)
                tool_finished = True
                
            tool_thread = threading.Thread(target=run_tool)
            tool_thread.start()
            
            start_time = time.time()
            fillers = [
                "I'm still working on this, please bear with me.",
                "Just taking a bit longer than expected.",
                "Processing the results now.",
                "Almost there."
            ]
            filler_idx = 0
            
            while not tool_finished:
                elapsed = time.time() - start_time
                if elapsed > (2.5 + (filler_idx * 4.0)) and filler_idx < len(fillers):
                    tts_queue.put(fillers[filler_idx])
                    filler_idx += 1
                time.sleep(0.1)
                
            result_dict = tool_result
            update_ui_state('thinking')
            
            if action_name in ["clear_session", "clear_all_memory"]:
                del conversation_history[1:]
                save_session()
                try:
                    import webview
                    if webview.windows:
                        webview.windows[0].evaluate_js("window.clearChatHistory && window.clearChatHistory()")
                except Exception:
                    pass
                # Speak confirmation and abort recursion to prevent infinite loops on a blank context!
                tts_queue.put("Memory has been wiped clean, sir.")
                while not tts_queue.empty():
                    time.sleep(0.1)
                return None
            
            # Check if this tool should render a rich UI widget
            if action_name == "get_weather" and isinstance(result_dict, dict) and "weather" in result_dict:
                weather_str = result_dict["weather"].lower()
                condition = "Clear"
                if any(w in weather_str for w in ["rain", "drizzle", "shower"]): condition = "Rain"
                elif any(w in weather_str for w in ["snow", "ice"]): condition = "Snow"
                elif any(w in weather_str for w in ["cloud", "overcast", "fog", "mist"]): condition = "Clouds"
                
                widget_data = {
                    "text": result_dict["weather"],
                    "condition": condition
                }
                add_chat_message('assistant', "", False, widget={"type": "weather", "data": widget_data})
            
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
                try:
                    import base64
                    with open(image_path, "rb") as f:
                        img_b64 = base64.b64encode(f.read()).decode('utf-8')
                    console.print(f"[dim magenta]👁 Attaching image for vision: {image_path}[/dim magenta]")
                    tool_message['images'] = [img_b64]
                except Exception as e:
                    console.print(f"[dim red]Failed to encode image: {e}[/dim red]")
            
            # Remove massive base64 payloads from OLD messages to prevent Ollama context overflow
            for msg in conversation_history:
                if 'images' in msg and msg != tool_message:
                    del msg['images']
                    
            conversation_history.append(tool_message)
            save_session()
            
            # 5. RECURSION: Read tool output and speak or call another tool
            console.print("[dim cyan]↻ Feeding result back to Bernard...[/dim cyan]")
            # Return the interrupted input if the recursive call gets interrupted
            interrupted_input = process_agentic_loop(tts_stream, is_followup=True, depth=depth + 1, parent_tts_queue=tts_queue)

    except Exception as e:
        from rich.markup import escape
        console.print(f"[bold red]Error communicating with {initial_provider}: {escape(str(e))}[/bold red]")
        
    if parent_tts_queue is None:
        tts_queue.put(None)

    # Keep alive until TTS finishes playing
    if interrupted_input is None and parent_tts_queue is None:
        while tts_stream.is_playing():
            if not input_queue.empty():
                interrupted_input = input_queue.get_nowait()
                tts_stream.stop()
                console.print("\n[bold red]⏸ Interrupted![/bold red]")
                break
            time.sleep(0.05)
    
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
    
    # Initialize the STT model in a background thread to load in parallel with TTS
    stt_recorder = [None]
    def init_stt():
        console.print("[dim]Loading Whisper STT Model (Base)...[/dim]")
        def realtime_callback(text):
            if text.strip():
                sys.stdout.write(f"\r\033[K\033[90m🎤 {text}\033[0m")
                sys.stdout.flush()
                add_chat_message('user', text.strip(), True)

        stt_recorder[0] = AudioToTextRecorder(
            transcription_engine="faster_whisper",
            model="base.en",
            language="en",
            spinner=False,
            post_speech_silence_duration=0.8,
            min_length_of_recording=1.0,
            pre_recording_buffer_duration=0.5,
            webrtc_sensitivity=3,
            silero_sensitivity=0.5,
            initial_prompt="Bernard AI assistant conversation.",
            enable_realtime_transcription=True,
            use_main_model_for_realtime=True,
            on_realtime_transcription_update=realtime_callback,
            on_vad_detect_start=lambda: update_ui_state('listening'),
            on_vad_detect_stop=lambda: update_ui_state('idle'),
            compute_type="float16",
            device="cuda"
        )
        console.print("[green]✓[/green] STT loaded (Faster-Whisper Base • CUDA)")
        
    stt_thread = threading.Thread(target=init_stt, daemon=True)
    stt_thread.start()
    
    # Initialize the TTS stream player
    try:
        import json
        from llm_client import resolve_env_vars
        config_path = "config.json"
        current_engine = "kokoro"
        cartesia_key = os.environ.get("CARTESIA_API_KEY")
        cartesia_voice_id = "4bc3cb8c-adb9-4bb8-b5d5-cbbef950b991"
        kokoro_voice = "0.5*bm_lewis + 0.5*am_puck + 0.2*af_bella + 0.3*bm_george + 0.4*am_michael"
        tts_speed = 1.25
        
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                    tts_cfg = cfg.get("tts", {})
                    current_engine = tts_cfg.get("current_engine", "kokoro")
                    if "cartesia_api_key" in tts_cfg:
                        cartesia_key = resolve_env_vars(tts_cfg["cartesia_api_key"])
                    if "cartesia_voice_id" in tts_cfg:
                        cartesia_voice_id = tts_cfg["cartesia_voice_id"]
                    if "kokoro_voice" in tts_cfg:
                        kokoro_voice = tts_cfg["kokoro_voice"]
                    if "speed" in tts_cfg:
                        tts_speed = float(tts_cfg["speed"])
                    if "qwen_instruct" in tts_cfg:
                        qwen_instruct = tts_cfg["qwen_instruct"]
                    else:
                        qwen_instruct = "A sophisticated British AI assistant."
            except Exception:
                pass
                
        if current_engine == "qwen":
            console.print("[dim]Allocating VRAM and initializing local Qwen3-TTS Engine (Voice Design)...[/dim]")
            voice = FasterQwenVoice(
                name="Jarvis", 
                instruct=qwen_instruct,
                language="English",
                ref_audio="custom_voice.wav",
                ref_text="Unfortunately, the device that's keeping your life is also killing you."
            )
            engine = FasterQwenEngine(
                model_name="Qwen/Qwen3-TTS-12Hz-0.6B-Base",
                voice=voice,
                device="cuda"
            )
            console.print(f"[green]✓[/green] TTS Engine loaded (Qwen3-TTS 0.6B • Custom Voice Design)")
        elif current_engine == "cartesia":
            console.print("[dim]Initializing Cartesia Sonic 3.5 Engine (Realtime Seamless)...[/dim]")
            if not cartesia_key:
                console.print("[yellow]⚠[/yellow] CARTESIA_API_KEY not found in config.json or environment.")
                raise ValueError("Missing Cartesia API key")
                
            engine = ProperCartesiaEngine(
                api_key=cartesia_key,
                model_id="sonic-3.5",
                voice_id=cartesia_voice_id
            )
            console.print(f"[green]✓[/green] TTS Engine loaded (Cartesia Sonic 3.5 • {cartesia_voice_id})")
        else:
            console.print(f"[dim]Allocating VRAM and initializing local Kokoro Neural Engine ({kokoro_voice})...[/dim]")
            engine = KokoroEngine(
                voice=kokoro_voice,
                default_speed=tts_speed,
                trim_silence=True,
                extra_start_ms=0,
                fade_in_ms=10
            )
            console.print(f"[green]✓[/green] TTS Engine loaded (Kokoro • custom blend @ {tts_speed}x)")
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] TTS Engine failed, using system voice: {e}")
        engine = SystemEngine()
        
    tts_stream = TextToAudioStream(engine)
    tts_stream.add_pause("wake", 0.4) # Add 400ms silence tag to wake up Bluetooth headsets and PyAudio
    
    stt_thread.join()
    recorder = stt_recorder[0]
    
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
    
    tts_stream.feed([f"[wake] {greeting}"])
    tts_stream.play(
        sentence_silence_duration=0.4,
        comma_silence_duration=0.15
    )
        
    # Sync history to UI
    try:
        import webview
        if webview.windows:
            ui_history = []
            for i, msg in enumerate(conversation_history[1:]):
                ui_history.append({
                    'id': str(i) + "hist",
                    'role': 'assistant' if msg['role'] == 'assistant' else 'user',
                    'text': str(msg.get('content', '')),
                    'isPartial': False
                })
            js_code = f"if (window.setInitialChatHistory) {{ window.setInitialChatHistory({json.dumps(ui_history)}); }}"
            webview.windows[0].evaluate_js(js_code)
    except Exception as e:
        pass
    
    # Shared queue for both voice and keyboard input is defined globally
    # Thread 1: Voice input (STT)
    def voice_input_loop():
        try:
            while True:
                text = recorder.text()
                if text and text.strip():
                    try:
                        if tts_stream and tts_stream.is_playing():
                            continue
                    except NameError:
                        pass
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
            tts_stream.play_async(sentence_silence_duration=0.4, comma_silence_duration=0.0)
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
        update_ui_state('idle')
        while True:
            # Block until either voice or keyboard gives us input
            source, user_input = input_queue.get()
            
            if check_exit(str(user_input)):
                break
                
            if source == "media":
                file_path = user_input
                console.print(f"[bold cyan]📎 Media Uploaded:[/bold cyan] {file_path}")
                ext = file_path.lower().split('.')[-1]
                
                # Image
                if ext in ['png', 'jpg', 'jpeg']:
                    import base64
                    try:
                        with open(file_path, "rb") as f:
                            img_b64 = base64.b64encode(f.read()).decode('utf-8')
                        # Remove old images before appending the new one
                        for msg in conversation_history:
                            if 'images' in msg:
                                del msg['images']
                                
                        conversation_history.append({
                            'role': 'user', 
                            'content': f"User uploaded an image: {os.path.basename(file_path)}", 
                            'images': [img_b64]
                        })
                        add_chat_message('user', f"[Attached Image: {os.path.basename(file_path)}]", False)
                    except Exception as e:
                        conversation_history.append({'role': 'user', 'content': f"Failed to attach image: {e}"})
                
                # Audio
                elif ext in ['mp3', 'wav']:
                    console.print("[dim]Transcribing uploaded audio...[/dim]")
                    try:
                        from faster_whisper import WhisperModel
                        model = WhisperModel("tiny", device="cpu", compute_type="int8")
                        segments, _ = model.transcribe(file_path, beam_size=5)
                        transcription = " ".join([s.text for s in segments])
                        
                        prompt = f"User uploaded an audio file ({os.path.basename(file_path)}). Transcription: {transcription}"
                        conversation_history.append({'role': 'user', 'content': prompt})
                        add_chat_message('user', f"[Attached Audio: {os.path.basename(file_path)}]\n{transcription}", False)
                    except Exception as e:
                        conversation_history.append({'role': 'user', 'content': f"Failed to transcribe audio: {e}"})
                        
                # Video
                elif ext in ['mp4', 'mkv', 'avi']:
                    console.print("[dim]Processing video (audio transcription + frame extraction)...[/dim]")
                    try:
                        import cv2
                        from faster_whisper import WhisperModel
                        
                        # 1. Transcribe audio (Whisper handles video files directly!)
                        model = WhisperModel("tiny", device="cpu", compute_type="int8")
                        segments, _ = model.transcribe(file_path, beam_size=5)
                        transcription = " ".join([s.text for s in segments])
                        
                        # 2. Extract 3 frames
                        cap = cv2.VideoCapture(file_path)
                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        frames_b64 = []
                        if total_frames > 0:
                            for i in [1, total_frames // 2, total_frames - 2]:
                                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                                ret, frame = cap.read()
                                if ret:
                                    import base64
                                    _, buffer = cv2.imencode('.jpg', frame)
                                    frames_b64.append(base64.b64encode(buffer).decode('utf-8'))
                        cap.release()
                        
                        prompt = f"User uploaded a video ({os.path.basename(file_path)}). Transcription: {transcription}. Also 3 frames were attached."
                        conversation_history.append({
                            'role': 'user', 
                            'content': prompt,
                            'images': frames_b64
                        })
                        add_chat_message('user', f"[Attached Video: {os.path.basename(file_path)}]\n{transcription}", False)
                    except Exception as e:
                        conversation_history.append({'role': 'user', 'content': f"Failed to process video: {e}"})
                
                else:
                    conversation_history.append({'role': 'user', 'content': f"User uploaded an unsupported file: {file_path}"})
                    
                console.print(f"\n[bold cyan]📎 {os.path.basename(file_path)} attached. What would you like me to do with it?[/bold cyan]")
                add_chat_message('assistant', f"📎 Attached {os.path.basename(file_path)}. What would you like me to do with it?", False)
                
                # Wait for next input to attach to the media
                source2, text2 = input_queue.get()
                if check_exit(str(text2)): break
                
                if conversation_history[-1]['role'] == 'user':
                    conversation_history[-1]['content'] += f"\n\nUser's instructions regarding the file: {text2}"
                
                if source2 != "media":
                    console.print(f"[bold bright_blue]⌨️ You (Typed):[/bold bright_blue] {text2}")
                    add_chat_message('user', str(text2), False)
                
            else:
                user_text = user_input
                # Show user input nicely
                if source == "voice":
                    icon = "🎤"
                    label = "You (Voice)"
                    color = "bright_magenta"
                elif source == "keyboard":
                    icon = "⌨️"
                    label = "You (Typed)"
                    color = "bright_blue"
                else:
                    icon = "💬"
                    label = "You"
                    color = "white"
                
                console.print(Panel(
                    user_text,
                    title=f"[bold {color}]{icon} {label}[/bold {color}]",
                    border_style=color,
                    padding=(0, 2)
                ))
                
                # Append user input to memory
                conversation_history.append({'role': 'user', 'content': user_text})
                add_chat_message('user', user_text, False)
            
            save_session()
            compact_context()
                
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
                add_chat_message('user', user_text, False)
                save_session()
                compact_context()
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
