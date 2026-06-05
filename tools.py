import pyautogui
import subprocess
import os
import time
import pyperclip
import json
import sqlite3
from datetime import datetime

# --- Long-Term Memory Setup ---
DB_PATH = "bernard_memory.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()
# ------------------------------

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
    """Types text into the currently focused window, optionally presses enter. Handles unicode/emoji via clipboard."""
    print(f"[Tool] Typing text: {text}")
    try:
        # pyautogui.write() can only handle ASCII. For unicode, use clipboard paste.
        if all(ord(c) < 128 for c in text):
            pyautogui.write(text, interval=0.01)
        else:
            # Save current clipboard, paste our text, restore
            old_clipboard = pyperclip.paste()
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)
            pyperclip.copy(old_clipboard)
        if press_enter:
            pyautogui.press('enter')
        return {"status": "success", "message": f"Typed text (enter={press_enter})"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def search_web(query: str, max_results: int = 5):
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
            formatted += f"Result {i}:\nTitle: {r.get('title', '')}\nURL: {r.get('href', '')}\nSnippet: {r.get('body', '')}\n\n"
        return {"status": "success", "results": formatted.strip()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def read_file(file_path: str, start_line: int = 1, end_line: int = None):
    """Reads the contents of any local file. Supports start_line and end_line for large files."""
    print(f"[Tool] Reading file: {file_path} (Lines {start_line} to {end_line})")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        start_idx = max(0, start_line - 1)
        # If end_line is not provided, read up to 200 lines to prevent overflow
        end_idx = end_line if end_line is not None else min(start_idx + 200, len(lines))
        content = "".join(lines[start_idx:end_idx])
        return {"status": "success", "content": content, "total_lines": len(lines), "showing_lines": f"{start_line} to {end_idx}"}
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
        
        # Press Escape first to dismiss any existing overlays/menus
        pyautogui.press('escape')
        time.sleep(0.2)
        
        # Press the Windows key to open Start Menu
        pyautogui.press('win')
        time.sleep(0.7)
        
        # Type the app name into the Start Menu search
        pyautogui.write(app_name, interval=0.03)
        time.sleep(1.0)  # Wait for search results to populate
        
        # Press Enter to launch the top result
        pyautogui.press('enter')
        time.sleep(1.5)  # Wait for the app to start loading
        
        # Wait for a new window to appear (up to 10 seconds)
        start_time = time.time()
        while time.time() - start_time < 10:
            current_window = pyautogui.getActiveWindowTitle()
            if current_window and current_window != initial_window:
                print(f"[Tool] App launched! Window: '{current_window}'")
                return {"status": "success", "message": f"Opened {app_name} (Window: {current_window})"}
            time.sleep(0.3)
        
        return {"status": "warning", "message": f"Launched {app_name} via Start Menu, but couldn't verify the window. It may still be loading."}
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

def list_ui_elements(window_title: str = ""):
    """Lists all clickable UI elements in the active window, or a specific window if title is provided."""
    print(f"[Tool] Listing UI elements for: {window_title or 'active window'}...")
    try:
        import uiautomation as auto
        if window_title:
            window = auto.WindowControl(searchDepth=2, Name=window_title)
            if window.Exists(1.0):
                window.SetFocus()
                foreground = window_title
            else:
                return {"status": "error", "message": f"Window '{window_title}' not found."}
        else:
            foreground = pyautogui.getActiveWindowTitle()
            if not foreground:
                return {"status": "error", "message": "No active window found."}
            window = auto.WindowControl(searchDepth=2, Name=foreground)
            if not window.Exists(1.0):
                window = auto.GetRootControl()
            
        elements = []
        for control, depth in auto.WalkControl(window, includeTop=False, maxDepth=6):
            if control.Name and control.ControlType in [auto.ControlType.ButtonControl, auto.ControlType.ListItemControl, auto.ControlType.TabItemControl, auto.ControlType.EditControl]:
                elements.append(f"{control.ControlTypeName}: '{control.Name}'")
                
        unique_elements = list(dict.fromkeys(elements)) # Keep order but deduplicate
        if not unique_elements:
            return {"status": "warning", "message": f"No named interactive elements found in '{foreground}'."}
            
        return {"status": "success", "window": foreground, "elements": unique_elements[:50]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def click_ui_element(element_name: str, window_title: str = ""):
    """Clicks a UI element (like a button) by its exact name. Optionally searches in a specific window title."""
    print(f"[Tool] Clicking UI element: '{element_name}' in {window_title or 'active window'}")
    try:
        import uiautomation as auto
        if window_title:
            window = auto.WindowControl(searchDepth=2, Name=window_title)
            if window.Exists(1.0):
                window.SetFocus()
        
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

def save_memory(fact: str):
    """Saves a fact to long-term memory."""
    print(f"[Tool] Saving memory: {fact}")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO memories (fact, timestamp) VALUES (?, ?)", (fact, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return {"status": "success", "message": f"Successfully remembered: '{fact}'"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def search_memory(query: str):
    """Searches long-term memory for facts matching the query."""
    print(f"[Tool] Searching memory for: {query}")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, fact, timestamp FROM memories WHERE fact LIKE ?", (f'%{query}%',))
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return {"status": "success", "message": f"No memories found matching '{query}'."}
            
        memories = [{"id": row[0], "fact": row[1], "date": row[2]} for row in results]
        return {"status": "success", "memories": memories}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def delete_memory(memory_id: int):
    """Deletes a memory fact from the database by its ID."""
    print(f"[Tool] Deleting memory ID: {memory_id}")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        if cursor.rowcount == 0:
            conn.close()
            return {"status": "error", "message": f"No memory found with ID {memory_id}"}
        conn.commit()
        conn.close()
        return {"status": "success", "message": f"Deleted memory ID {memory_id}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_active_window():
    """Returns the title of the currently focused window."""
    print("[Tool] Getting active window...")
    try:
        window = pyautogui.getActiveWindowTitle()
        return {"status": "success", "active_window": window}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def set_system_volume(level: int):
    """Sets the system volume (0 to 100)."""
    print(f"[Tool] Setting volume to {level}%")
    try:
        from pycaw.pycaw import AudioUtilities
        devices = AudioUtilities.GetSpeakers()
        
        # Modern pycaw returns a wrapper with EndpointVolume already activated
        if hasattr(devices, 'EndpointVolume'):
            volume = devices.EndpointVolume
        else:
            # Fallback for older pycaw or raw COM access
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import IAudioEndpointVolume
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
        
        level = max(0, min(100, level))
        volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        return {"status": "success", "message": f"System volume set to {level}%"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_weather(city: str):
    """Fetches current weather for a specified location."""
    print(f"[Tool] Getting weather for: {city}")
    try:
        import urllib.request, urllib.parse
        # Use a plain-text format that avoids emoji encoding issues
        # curl user-agent forces text output from wttr.in
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=%l:+%C+%t+%h+%w"
        req = urllib.request.Request(url, headers={'User-Agent': 'curl/7.0'})
        with urllib.request.urlopen(req) as response:
            weather = response.read().decode('utf-8', errors='replace').strip()
        return {"status": "success", "weather": weather}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def extract_text_from_image(image_path: str):
    """Uses OCR to extract text from an image."""
    print(f"[Tool] Extracting text from image: {image_path}")
    try:
        import pytesseract
        from PIL import Image
        import os
        text = pytesseract.image_to_string(Image.open(os.path.abspath(image_path)))
        return {"status": "success", "text": text.strip()[:2000]}
    except Exception as e:
        return {"status": "error", "message": f"OCR failed: {e}"}

def get_system_stats():
    """Returns current CPU, RAM, and Disk usage."""
    print("[Tool] Getting system stats...")
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        stats = (
            f"CPU Usage: {cpu}%\n"
            f"RAM Usage: {ram.percent}% ({ram.used // (1024**3)}GB / {ram.total // (1024**3)}GB)\n"
            f"Disk Usage (C:): {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)"
        )
        return {"status": "success", "stats": stats}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_current_location():
    """Fetches the user's current geographical location based on their IP address."""
    print("[Tool] Getting current location...")
    try:
        import urllib.request
        import json
        url = "https://ipinfo.io/json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        if 'loc' in data:
            location = f"{data.get('city')}, {data.get('region')}, {data.get('country')}"
            lat_lon = data['loc'].split(',')
            return {"status": "success", "location": location, "lat": lat_lon[0], "lon": lat_lon[1]}
        else:
            return {"status": "error", "message": "Could not determine location."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# =============================================================================
# MEGA BATCH TOOLS (Phase 2)
# =============================================================================

def get_battery_status():
    """Checks if the laptop is charging and current battery %."""
    print("[Tool] Getting battery status...")
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery is None:
            return {"status": "error", "message": "No battery installed or found."}
        status = "Charging" if battery.power_plugged else "Discharging"
        return {"status": "success", "percentage": f"{battery.percent}%", "power": status}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def turn_off_screen():
    """Instantly put the Windows display to sleep."""
    print("[Tool] Turning off screen...")
    try:
        import ctypes
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
        return {"status": "success", "message": "Screen turned off."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def set_screen_brightness(level: int):
    """Control screen brightness from 0 to 100."""
    print(f"[Tool] Setting brightness to {level}...")
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(max(0, min(100, level)))
        return {"status": "success", "message": f"Brightness set to {level}%."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def toggle_windows_theme(mode: str):
    """Switch Windows between light and dark mode. Mode must be 'dark' or 'light'."""
    print(f"[Tool] Toggling Windows theme to {mode}...")
    try:
        import winreg
        val = 0 if mode.lower() == 'dark' else 1
        path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, val)
        winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, val)
        winreg.CloseKey(key)
        return {"status": "success", "message": f"Windows theme set to {mode} mode."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def media_controls(action: str):
    """Controls system media playback. Action must be 'playpause', 'next', 'previous', 'stop', or 'mute'."""
    print(f"[Tool] Executing media control: {action}...")
    try:
        import pyautogui
        valid_actions = {
            'playpause': 'playpause',
            'play': 'playpause',
            'pause': 'playpause',
            'next': 'nexttrack',
            'previous': 'prevtrack',
            'stop': 'stop',
            'mute': 'volumemute'
        }
        key = valid_actions.get(action.lower())
        if not key:
            return {"status": "error", "message": "Invalid action. Use playpause, next, previous, stop, or mute."}
        pyautogui.press(key)
        return {"status": "success", "message": f"Media action '{action}' executed."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def list_processes(app_name: str = ""):
    """Check what background processes/apps are running, optionally filtered by name."""
    print(f"[Tool] Listing processes (filter: {app_name})...")
    try:
        import psutil
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'memory_percent']):
            try:
                if not app_name or app_name.lower() in p.info['name'].lower():
                    procs.append(f"PID: {p.info['pid']} | {p.info['name']} | RAM: {p.info['memory_percent']:.1f}%")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if not procs:
            return {"status": "success", "message": "No matching processes found."}
        return {"status": "success", "processes": procs[:50]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def kill_process(name_or_pid):
    """Force-quit an app by its process name (e.g., notepad.exe) or PID."""
    print(f"[Tool] Killing process: {name_or_pid}...")
    try:
        import psutil
        killed = 0
        for p in psutil.process_iter(['pid', 'name']):
            try:
                if str(name_or_pid).lower() in p.info['name'].lower() or str(name_or_pid) == str(p.info['pid']):
                    p.kill()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if killed > 0:
            return {"status": "success", "message": f"Killed {killed} processes matching '{name_or_pid}'."}
        else:
            return {"status": "error", "message": f"No process found matching '{name_or_pid}'."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def take_webcam_photo():
    """Take a snapshot from the webcam to see the user or room."""
    print("[Tool] Taking webcam photo...")
    try:
        import cv2
        import os
        import time
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return {"status": "error", "message": "Webcam not found or inaccessible."}
        for _ in range(5):
            cap.read()
        ret, frame = cap.read()
        cap.release()
        if ret:
            os.makedirs("screenshots", exist_ok=True)
            filename = os.path.abspath(f"screenshots/webcam_{int(time.time())}.jpg")
            cv2.imwrite(filename, frame)
            return {"status": "success", "message": "Photo taken.", "image_path": filename}
        else:
            return {"status": "error", "message": "Failed to capture image from webcam."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def read_pdf(file_path: str):
    """Extract text from a .pdf document directly."""
    print(f"[Tool] Reading PDF: {file_path}...")
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        text = ""
        for i, page in enumerate(reader.pages):
            text += f"\n--- Page {i+1} ---\n{page.extract_text()}"
        return {"status": "success", "text": text[:10000]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def extract_zip(zip_path: str, extract_to: str = "."):
    """Unzip downloaded archives."""
    print(f"[Tool] Extracting ZIP: {zip_path} to {extract_to}...")
    try:
        import zipfile
        import os
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        return {"status": "success", "message": f"Extracted {zip_path} to {os.path.abspath(extract_to)}."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def search_files_local(query: str, directory: str = "."):
    """Deep-search the hard drive for a file by name."""
    print(f"[Tool] Searching files in {directory} for '{query}'...")
    try:
        import os
        results = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                if query.lower() in file.lower():
                    results.append(os.path.join(root, file))
                    if len(results) >= 50:
                        break
            if len(results) >= 50:
                break
        if results:
            return {"status": "success", "files": results}
        else:
            return {"status": "success", "message": "No matching files found."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def read_webpage(url: str):
    """Extract clean text from an entire webpage."""
    print(f"[Tool] Reading webpage: {url}...")
    try:
        import urllib.request
        from bs4 import BeautifulSoup
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            html = response.read()
        soup = BeautifulSoup(html, 'html.parser')
        for script in soup(["script", "style"]):
            script.extract()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        return {"status": "success", "content": text[:10000]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def download_file(url: str, save_path: str):
    """Download files directly from the internet."""
    print(f"[Tool] Downloading {url} to {save_path}...")
    try:
        import urllib.request
        import os
        abs_path = os.path.abspath(save_path)
        parent_dir = os.path.dirname(abs_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        urllib.request.urlretrieve(url, abs_path)
        return {"status": "success", "message": f"Downloaded to {abs_path}."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_crypto_price(coin: str):
    """Fetch real-time cryptocurrency prices."""
    print(f"[Tool] Fetching crypto price for: {coin}...")
    try:
        import urllib.request
        import json
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin.lower()}&vs_currencies=usd"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
        if coin.lower() in data:
            return {"status": "success", "price_usd": data[coin.lower()]['usd']}
        else:
            return {"status": "error", "message": f"Coin '{coin}' not found on CoinGecko."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_stock_price(ticker: str):
    """Fetch live stock market prices."""
    print(f"[Tool] Fetching stock price for: {ticker}...")
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")
        if data.empty:
            return {"status": "error", "message": f"No data found for ticker '{ticker}'."}
        current_price = data['Close'].iloc[-1]
        return {"status": "success", "ticker": ticker.upper(), "current_price_usd": round(current_price, 2)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def translate_text(text: str, target_lang: str):
    """Translate foreign text instantly."""
    print(f"[Tool] Translating text to {target_lang}...")
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(target=target_lang)
        translated = translator.translate(text)
        return {"status": "success", "translated_text": translated}
    except Exception as e:
        return {"status": "error", "message": str(e)}

EVENT_CALLBACK = None

def set_timer(minutes: float, reminder: str):
    """Spawns a background timer that will interrupt and speak the reminder."""
    print(f"[Tool] Setting {minutes} min timer for: {reminder}...")
    try:
        import threading
        import time
        def timer_thread():
            time.sleep(minutes * 60)
            if EVENT_CALLBACK:
                EVENT_CALLBACK(("system", f"TIMER COMPLETED: {reminder}. Please verbally alert the user right now."))
            else:
                import winsound
                winsound.Beep(1000, 1000)
                print(f"\n[TIMER ALERT] {reminder}")
                
        t = threading.Thread(target=timer_thread, daemon=True)
        t.start()
        return {"status": "success", "message": f"Timer set for {minutes} minutes."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def set_clipboard(text: str):
    """Write text directly to clipboard."""
    print(f"[Tool] Setting clipboard to: {text[:20]}...")
    try:
        import pyperclip
        pyperclip.copy(text)
        return {"status": "success", "message": "Text copied to clipboard."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def list_open_windows():
    """List the titles of all open, visible windows (equivalent to looking at Alt+Tab)."""
    print("[Tool] Listing open windows...")
    try:
        import pyautogui
        titles = [t for t in pyautogui.getAllTitles() if t and t != "Program Manager"]
        return {"status": "success", "windows": titles}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def switch_to(target: str):
    """Smart tool: Switches to an open Windows application, or cycles browser tabs to find a specific tab."""
    print(f"[Tool] Smart-switching to '{target}'...")
    try:
        import pyautogui
        import time
        import ctypes
        
        # 1. Try to find a matching Windows app first
        windows = pyautogui.getWindowsWithTitle(target)
        if windows:
            w = windows[0]
            if w.isMinimized:
                w.restore()
            try:
                w.activate()
            except Exception:
                ctypes.windll.user32.SetForegroundWindow(w._hWnd)
            return {"status": "success", "message": f"Switched to application window: '{w.title}'."}
            
        # 2. If no window matches, it might be a hidden browser tab. 
        # Let's find a browser window, activate it, and Ctrl+Tab through it.
        browser_keywords = ["chrome", "edge", "firefox", "brave", "opera", "browser"]
        browser_window = None
        for t in pyautogui.getAllTitles():
            if any(b in t.lower() for b in browser_keywords):
                browser_window = pyautogui.getWindowsWithTitle(t)[0]
                break
                
        if not browser_window:
            return {"status": "error", "message": f"Could not find window '{target}', and no web browser is open to search for tabs."}
            
        # Activate browser
        if browser_window.isMinimized:
            browser_window.restore()
        try:
            browser_window.activate()
        except Exception:
            ctypes.windll.user32.SetForegroundWindow(browser_window._hWnd)
            
        time.sleep(0.5)
        
        # Cycle tabs
        start_window = pyautogui.getActiveWindow()
        if not start_window:
             return {"status": "error", "message": "Failed to activate browser."}
        start_title = start_window.title
        
        for i in range(25):
            pyautogui.hotkey('ctrl', 'tab')
            time.sleep(0.3)
            current_window = pyautogui.getActiveWindow()
            if not current_window:
                continue
            current_title = current_window.title
            
            if target.lower() in current_title.lower():
                return {"status": "success", "message": f"Found and switched to browser tab: '{current_title}'"}
                
            if i > 0 and current_title == start_title:
                return {"status": "error", "message": f"Searched all windows and browser tabs. '{target}' not found."}
                
        return {"status": "error", "message": f"Searched windows and cycled 25 tabs, but didn't find '{target}'."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_music_status():
    """Gets the currently playing music/media status and info on Windows (like Spotify or YouTube)."""
    print("[Tool] Getting current music status...")
    try:
        import asyncio
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
        
        async def _get_media():
            manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
            session = manager.get_current_session()
            if not session:
                return {"status": "success", "message": "No media is currently playing or paused."}
                
            props = await session.try_get_media_properties_async()
            playback = session.get_playback_info()
            
            # Map playback status enum
            # 0: Closed, 1: Opened, 2: Changing, 3: Stopped, 4: Playing, 5: Paused
            status_map = {
                0: "Closed", 1: "Opened", 2: "Changing", 
                3: "Stopped", 4: "Playing", 5: "Paused"
            }
            status_code = getattr(playback, 'playback_status', 0)
            status_str = status_map.get(status_code, "Unknown")
            
            return {
                "status": "success",
                "title": props.title,
                "artist": props.artist,
                "playback_status": status_str
            }
            
        return asyncio.run(_get_media())
    except ImportError:
        return {"status": "error", "message": "Required modules not found. Please run: pip install winrt-Windows.Media.Control winrt-Windows.Foundation"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def set_humor_level(level: int):
    """Sets Bernard's humor level by saving it to config.json."""
    try:
        config = {}
        config_path = "config.json"
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                try:
                    config = json.load(f)
                except:
                    pass
        config["humor_level"] = int(level)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)
        return {"status": "success", "message": f"Humor level permanently set to {level}%"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# =============================================================================
# TOOL REGISTRY — Bernard picks what he needs from here
# =============================================================================
TOOL_REGISTRY = {
    "set_humor_level": set_humor_level,
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
    "image_to_ascii": image_to_ascii,
    "save_memory": save_memory,
    "search_memory": search_memory,
    "delete_memory": delete_memory,
    "get_active_window": get_active_window,
    "set_system_volume": set_system_volume,
    "get_weather": get_weather,
    "extract_text_from_image": extract_text_from_image,
    "get_system_stats": get_system_stats,
    "get_current_location": get_current_location,
    "get_battery_status": get_battery_status,
    "turn_off_screen": turn_off_screen,
    "set_screen_brightness": set_screen_brightness,
    "list_processes": list_processes,
    "kill_process": kill_process,
    "take_webcam_photo": take_webcam_photo,
    "read_pdf": read_pdf,
    "extract_zip": extract_zip,
    "search_files_local": search_files_local,
    "read_webpage": read_webpage,
    "download_file": download_file,
    "get_crypto_price": get_crypto_price,
    "get_stock_price": get_stock_price,
    "translate_text": translate_text,
    "set_timer": set_timer,
    "set_clipboard": set_clipboard,
    "list_open_windows": list_open_windows,
    "switch_to": switch_to,
    "get_music_status": get_music_status,
    "toggle_windows_theme": toggle_windows_theme,
    "media_controls": media_controls
}

