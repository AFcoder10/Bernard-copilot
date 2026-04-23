import pyautogui
import subprocess
import os
import time
import pyperclip
from datetime import datetime

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None

# =============================================================================
# GENERAL-PURPOSE PRIMITIVES
# Bernard figures out what to do with these on his own.
# =============================================================================

def run_command(command: str):
    """Runs ANY shell command. This is the Swiss Army knife — open apps, run scripts, manage files, anything."""
    print(f"[Tool] Running command: {command}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout.strip() if result.stdout.strip() else result.stderr.strip()
        return {"status": "success", "output": output[:800]}
    except subprocess.TimeoutExpired:
        return {"status": "warning", "message": f"Command timed out after 30s (it may still be running in background)."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def press_keys(*keys):
    """Presses any keyboard shortcut or key combination."""
    print(f"[Tool] Pressing keys: {keys}")
    try:
        pyautogui.hotkey(*keys)
        return {"status": "success", "message": f"Pressed {'+'.join(keys)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def type_text(text: str, press_enter: bool = False):
    """Types text into the currently focused window, optionally presses enter."""
    print(f"[Tool] Typing text: {text}")
    try:
        pyautogui.write(text, interval=0.01)
        if press_enter:
            pyautogui.press('enter')
        return {"status": "success", "message": f"Typed text (enter={press_enter})"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def search_web(query: str, max_results: int = 3):
    """Searches the web using DuckDuckGo and returns summaries."""
    print(f"[Tool] Searching web for: '{query}'")
    if not DDGS:
        return {"status": "error", "message": "ddgs is not installed."}
    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return {"status": "success", "results": "No results found."}
        
        formatted = ""
        for i, r in enumerate(results, 1):
            formatted += f"Result {i}:\nTitle: {r.get('title', '')}\nSnippet: {r.get('body', '')}\n\n"
        return {"status": "success", "results": formatted.strip()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def read_file(file_path: str):
    """Reads the contents of any local file."""
    print(f"[Tool] Reading file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"status": "success", "content": content[:2000]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def write_file(file_path: str, content: str):
    """Creates or overwrites a file with the given content."""
    print(f"[Tool] Writing to file: {file_path}")
    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"status": "success", "message": f"Successfully wrote to {file_path}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def list_files(directory: str = "."):
    """Lists all files and folders in a directory."""
    print(f"[Tool] Listing files in: {directory}")
    try:
        entries = os.listdir(directory)
        result = []
        for entry in sorted(entries):
            full_path = os.path.join(directory, entry)
            if os.path.isdir(full_path):
                result.append(f"[DIR]  {entry}")
            else:
                size = os.path.getsize(full_path)
                result.append(f"[FILE] {entry} ({size} bytes)")
        return {"status": "success", "files": "\n".join(result[:50])}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_clipboard():
    """Reads what's currently copied to the clipboard."""
    print("[Tool] Reading clipboard...")
    try:
        text = pyperclip.paste()
        return {"status": "success", "content": text[:1000]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def take_screenshot():
    """Captures the screen and returns the image path for vision analysis."""
    print("[Tool] Taking screenshot...")
    try:
        os.makedirs("screenshots", exist_ok=True)
        filename = os.path.abspath(f"screenshots/screenshot_{int(time.time())}.png")
        pyautogui.screenshot(filename)
        print(f"[Tool] Screenshot saved to {filename}")
        return {"status": "success", "message": f"Screenshot saved to {filename}", "image_path": filename}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_current_time():
    """Gets the current local date and time."""
    print("[Tool] Getting current time...")
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {"status": "success", "time": now}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def open_app(app_name: str):
    """Opens any application using the Windows Start Menu search.
    This works for ALL apps — traditional desktop apps, UWP/Store apps, and anything
    that appears in the Windows Start Menu search. It simulates what a human would do:
    press the Windows key, type the app name, and press Enter."""
    print(f"[Tool] Opening app via Start Menu: {app_name}")
    try:
        # Get the current window so we can detect when a new one appears
        initial_window = pyautogui.getActiveWindowTitle()
        
        # Press the Windows key to open Start Menu
        pyautogui.press('win')
        time.sleep(0.5)
        
        # Type the app name into the Start Menu search
        pyautogui.write(app_name, interval=0.03)
        time.sleep(0.8)  # Wait for search results to populate
        
        # Press Enter to launch the top result
        pyautogui.press('enter')
        time.sleep(1.0)  # Wait for the app to start loading
        
        # Wait for a new window to appear (up to 8 seconds)
        start_time = time.time()
        while time.time() - start_time < 8:
            current_window = pyautogui.getActiveWindowTitle()
            if current_window and current_window != initial_window:
                print(f"[Tool] App launched! Window: '{current_window}'")
                return {"status": "success", "message": f"Opened {app_name} (Window: {current_window})"}
            time.sleep(0.3)
        
        return {"status": "warning", "message": f"Launched {app_name} via Start Menu, but couldn't verify the window."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def click_coordinates(x: int, y: int, button: str = 'left', clicks: int = 1):
    """Clicks the mouse at specific x, y coordinates on the screen."""
    print(f"[Tool] Clicking {button} button at ({x}, {y}) {clicks} time(s)")
    try:
        pyautogui.click(x=x, y=y, button=button, clicks=clicks)
        return {"status": "success", "message": f"Clicked {button} at ({x}, {y})"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def move_mouse(x: int, y: int):
    """Moves the mouse to specific x, y coordinates."""
    print(f"[Tool] Moving mouse to ({x}, {y})")
    try:
        pyautogui.moveTo(x=x, y=y, duration=0.2)
        return {"status": "success", "message": f"Mouse moved to ({x}, {y})"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def list_ui_elements():
    """Lists all clickable UI elements in the currently active window using Windows UIAutomation."""
    print("[Tool] Listing UI elements...")
    try:
        import uiautomation as auto
        foreground = pyautogui.getActiveWindowTitle()
        if not foreground:
            return {"status": "error", "message": "No active window found."}
            
        window = auto.WindowControl(searchDepth=2, Name=foreground)
        if not window.Exists(1.0):
            # Fallback to desktop if window name hook fails
            window = auto.GetRootControl()
            
        elements = []
        for control, depth in auto.WalkTree(window, getChildrenFunc=lambda c: c.GetChildren(), includeTop=False, maxDepth=6):
            if control.Name and control.ControlType in [auto.ControlType.ButtonControl, auto.ControlType.ListItemControl, auto.ControlType.TabItemControl, auto.ControlType.EditControl]:
                elements.append(f"{control.ControlTypeName}: '{control.Name}'")
                
        unique_elements = list(dict.fromkeys(elements)) # Keep order but deduplicate
        if not unique_elements:
            return {"status": "warning", "message": f"No named interactive elements found in '{foreground}'."}
            
        return {"status": "success", "window": foreground, "elements": unique_elements[:50]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def click_ui_element(element_name: str):
    """Clicks a UI element (like a button) by its exact name using Windows UIAutomation."""
    print(f"[Tool] Clicking UI element: '{element_name}'")
    try:
        import uiautomation as auto
        foreground = pyautogui.getActiveWindowTitle()
        
        # 1st try: Search inside active window
        if foreground:
            window = auto.WindowControl(searchDepth=2, Name=foreground)
            if window.Exists(0.5):
                element = window.Control(searchDepth=6, Name=element_name)
                if element.Exists(0.5):
                    element.Click()
                    return {"status": "success", "message": f"Successfully clicked '{element_name}' in '{foreground}'"}
        
        # 2nd try: Global search across entire desktop
        element_global = auto.Control(Name=element_name)
        if element_global.Exists(1.5):
            element_global.Click()
            return {"status": "success", "message": f"Successfully clicked '{element_name}' (global search)"}
            
        return {"status": "error", "message": f"Could not find element named '{element_name}'."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def play_youtube(query: str):
    """Searches YouTube and automatically plays the first video matching the query."""
    print(f"[Tool] Playing YouTube video: '{query}'")
    try:
        import pywhatkit
        pywhatkit.playonyt(query)
        return {"status": "success", "message": f"Now playing '{query}' on YouTube."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def send_whatsapp_message(phone_no: str, message: str):
    """Sends a WhatsApp message instantly via WhatsApp Web."""
    print(f"[Tool] Sending WhatsApp to {phone_no}")
    try:
        import pywhatkit
        # phone_no must include country code, e.g., +1234567890
        pywhatkit.sendwhatmsg_instantly(phone_no, message, wait_time=15, tab_close=True, close_time=3)
        return {"status": "success", "message": f"WhatsApp message sent to {phone_no}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_wikipedia_info(topic: str):
    """Fetches a brief summary from Wikipedia."""
    print(f"[Tool] Getting Wikipedia info for: {topic}")
    try:
        import pywhatkit
        # return_value=True makes it return the string instead of just printing
        info = pywhatkit.info(topic, lines=4, return_value=True)
        return {"status": "success", "info": info}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def generate_handwriting(text: str, save_path: str = "handwriting.png"):
    """Converts text to a handwritten image."""
    print("[Tool] Generating handwriting...")
    try:
        import pywhatkit
        import os
        save_path = os.path.abspath(save_path)
        pywhatkit.text_to_handwriting(text, save_to=save_path)
        return {"status": "success", "message": f"Handwriting saved to {save_path}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def image_to_ascii(image_path: str, output_path: str = "ascii_art"):
    """Converts an image to ASCII art text file."""
    print(f"[Tool] Converting {image_path} to ASCII art...")
    try:
        import pywhatkit
        import os
        image_path = os.path.abspath(image_path)
        output_path = os.path.abspath(output_path)
        pywhatkit.image_to_ascii_art(image_path, output_path)
        return {"status": "success", "message": f"ASCII art saved to {output_path}.txt"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# =============================================================================
# TOOL REGISTRY — Bernard picks what he needs from here
# =============================================================================
TOOL_REGISTRY = {
    "run_command": run_command,
    "press_keys": press_keys,
    "type_text": type_text,
    "search_web": search_web,
    "read_file": read_file,
    "write_file": write_file,
    "list_files": list_files,
    "get_clipboard": get_clipboard,
    "take_screenshot": take_screenshot,
    "get_current_time": get_current_time,
    "open_app": open_app,
    "click_coordinates": click_coordinates,
    "move_mouse": move_mouse,
    "list_ui_elements": list_ui_elements,
    "click_ui_element": click_ui_element,
    "play_youtube": play_youtube,
    "send_whatsapp_message": send_whatsapp_message,
    "get_wikipedia_info": get_wikipedia_info,
    "generate_handwriting": generate_handwriting,
    "image_to_ascii": image_to_ascii
}

