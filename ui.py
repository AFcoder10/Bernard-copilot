import threading
import os
import sys
import webview
import ctypes
import ctypes.wintypes

def make_window_rounded():
    try:
        # Find the PyWebview window by its title
        hwnd = ctypes.windll.user32.FindWindowW(None, "Bernard Copilot")
        if hwnd:
            # 1. Use Windows 11 native DWM rounding
            value = ctypes.c_int(2) # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(value), ctypes.sizeof(value))
            
            # 2. Make it non-resizable but maximizable
            GWL_STYLE = -16
            WS_THICKFRAME = 0x00040000
            WS_MAXIMIZEBOX = 0x00010000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            style = (style & ~WS_THICKFRAME) | WS_MAXIMIZEBOX
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style)
    except Exception as e:
        print("Could not adjust window:", e)

def start_ui():
    def run_bernard():
        import bernard_main
        bernard_main.main()

    # Start Bernard's core logic in a background thread
    bernard_thread = threading.Thread(target=run_bernard, daemon=True)
    bernard_thread.start()

    # Determine the path to the React UI index.html
    if getattr(sys, 'frozen', False):
        ui_path = os.path.join(sys._MEIPASS, 'ui', 'dist', 'index.html')
    else:
        ui_path = os.path.join(os.path.dirname(__file__), 'ui', 'dist', 'index.html')

    class Api:
        def send_prompt(self, text):
            # This allows the user to type prompts directly into the React UI
            import sys
            print(f"DEBUG UI: Received prompt: {text}")
            if 'bernard_main' in sys.modules:
                import bernard_main
                if hasattr(bernard_main, 'input_queue'):
                    bernard_main.input_queue.put(("typed", text))
                else:
                    print("DEBUG UI: input_queue not found on bernard_main")
            else:
                print("DEBUG UI: bernard_main not in sys.modules")
                    
        def trigger_file_upload(self):
            import sys
            file_types = ('Media Files (*.jpg;*.jpeg;*.png;*.mp3;*.wav;*.mp4)', 'All files (*.*)')
            try:
                if webview.windows:
                    window = webview.windows[0]
                    result = window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types)
                    if result and len(result) > 0:
                        file_path = result[0]
                        if 'bernard_main' in sys.modules:
                            import bernard_main
                            if hasattr(bernard_main, 'input_queue'):
                                bernard_main.input_queue.put(("media", file_path))
            except Exception as e:
                print(f"Error opening file dialog: {e}")

        def minimize_window(self):
            if webview.windows:
                webview.windows[0].minimize()

        def maximize_window(self):
            if webview.windows:
                webview.windows[0].toggle_fullscreen()

        def close_window(self):
            if webview.windows:
                webview.windows[0].destroy()
                
        def toggle_pin(self, is_pinned):
            if webview.windows:
                webview.windows[0].on_top = is_pinned

    api = Api()

    ui_window = webview.create_window(
        'Bernard Copilot', 
        url=ui_path,
        width=400, 
        height=600,
        min_size=(380, 550),
        frameless=False, 
        transparent=False, 
        on_top=True,
        resizable=True,
        js_api=api
    )
    
    # Expose the webview window to bernard_main for callbacks
    try:
        if 'bernard_main' in sys.modules:
            import bernard_main
            bernard_main.ui_window = ui_window
    except Exception as e:
        print(f"Failed to expose ui_window: {e}")
        
    def on_shown():
        pass
        
    ui_window.events.shown += on_shown
    
    # Use the default Edge WebView2 engine which is extremely fast and native
    webview.start()

def select_provider():
    import json
    import os
    try:
        if sys.stdout.encoding.lower() != 'utf-8':
            sys.stdout.reconfigure(encoding='utf-8')
        from rich.console import Console
        from rich.prompt import Prompt
        console = Console()
        
        config_path = "config.json"
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
            
            providers = list(config.get("providers", {}).keys())
            if not providers: return
            
            console.print("\n[bold cyan]🧠 Select LLM Provider for Bernard:[/bold cyan]")
            for i, p in enumerate(providers, 1):
                model = config["providers"][p].get("model", "Unknown Model")
                current_mark = "[bold green](Current)[/bold green]" if config.get("current_provider") == p else ""
                console.print(f"  [bold yellow]{i}.[/bold yellow] [bold white]{p}[/bold white] [dim]({model})[/dim] {current_mark}")
                
            current_provider = config.get("current_provider")
            default_index = "1"
            if current_provider in providers:
                default_index = str(providers.index(current_provider) + 1)
                
            choice = Prompt.ask("\n[bold cyan]Enter number[/bold cyan]", choices=[str(i) for i in range(1, len(providers) + 1)], default=default_index)
            
            selected_provider = providers[int(choice) - 1]
            config["current_provider"] = selected_provider
            
            with open(config_path, "w") as f:
                json.dump(config, f, indent=4)
                
            console.print(f"[bold green]✓ Set provider to {selected_provider}[/bold green]\n")
    except Exception as e:
        print(f"Error selecting provider: {e}")

if __name__ == '__main__':
    select_provider()
    start_ui()
