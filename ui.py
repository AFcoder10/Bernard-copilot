import threading
import os
import sys
import webview
import bernard_main

def start_ui():
    # Start Bernard's core logic in a background thread
    bernard_thread = threading.Thread(target=bernard_main.main, daemon=True)
    bernard_thread.start()

    # Determine the path to the React UI index.html
    if getattr(sys, 'frozen', False):
        ui_path = os.path.join(sys._MEIPASS, 'ui', 'dist', 'index.html')
    else:
        ui_path = os.path.join(os.path.dirname(__file__), 'ui', 'dist', 'index.html')

    # Start the webview on the main thread
    ui_window = webview.create_window(
        'Bernard Copilot', 
        url=ui_path,
        width=400, 
        height=650, 
        frameless=True, 
        transparent=True, 
        on_top=True
    )
    
    # Expose the webview window to bernard_main for callbacks
    bernard_main.ui_window = ui_window
    
    webview.start()

if __name__ == '__main__':
    start_ui()
