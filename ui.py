import threading
import os
import sys
import webview
import bernard_main
import ctypes
import ctypes.wintypes

def make_window_rounded():
    try:
        # Find the PyWebview window by its title
        hwnd = ctypes.windll.user32.FindWindowW(None, "Bernard Copilot")
        if hwnd:
            # 1. Use Windows 11 native DWM rounding for perfectly smooth antialiased corners
            value = ctypes.c_int(2) # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(value), ctypes.sizeof(value))
    except Exception as e:
        print("Could not round window:", e)

def start_ui():
    # Start Bernard's core logic in a background thread
    bernard_thread = threading.Thread(target=bernard_main.main, daemon=True)
    bernard_thread.start()

    # Determine the path to the React UI index.html
    if getattr(sys, 'frozen', False):
        ui_path = os.path.join(sys._MEIPASS, 'ui', 'dist', 'index.html')
    else:
        ui_path = os.path.join(os.path.dirname(__file__), 'ui', 'dist', 'index.html')

    class Api:
        def send_prompt(self, text):
            # This allows the user to type prompts directly into the React UI
            if hasattr(bernard_main, 'input_queue'):
                bernard_main.input_queue.put(("typed", text))

    api = Api()

    # Start the webview on the main thread
    ui_window = webview.create_window(
        'Bernard Copilot', 
        url=ui_path,
        width=400, 
        height=650, 
        frameless=True, 
        transparent=True, 
        on_top=True,
        js_api=api
    )
    
    # Expose the webview window to bernard_main for callbacks
    bernard_main.ui_window = ui_window
    
    def on_shown():
        # Apply the corner clipping once the window is visible
        make_window_rounded()
        
    ui_window.events.shown += on_shown
    
    # Use the default Edge WebView2 engine which is extremely fast and native
    webview.start()

if __name__ == '__main__':
    start_ui()
