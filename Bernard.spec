# -*- mode: python ; coding: utf-8 -*-
# Bernard Copilot — PyInstaller Spec File
# This bundles the entire Bernard assistant into a standalone .exe with all dependencies,
# the Whisper STT model, and the TTS engine.

import os
import sys

block_cipher = None

# --- Paths ---
VENV_SITE = r'D:\PROJECTS\Bernard-copilot\.venv\Lib\site-packages'
WHISPER_MODEL_SNAPSHOT = r'C:\Users\Aditya Fere\.cache\huggingface\hub\models--Systran--faster-whisper-base\snapshots\ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66'

a = Analysis(
    ['ui.py'],
    pathex=[r'D:\PROJECTS\Bernard-copilot'],
    binaries=[
        # ctranslate2 native DLLs (required by faster-whisper)
        (os.path.join(VENV_SITE, 'ctranslate2', 'ctranslate2.dll'), 'ctranslate2'),
        (os.path.join(VENV_SITE, 'ctranslate2', 'libiomp5md.dll'), 'ctranslate2'),
        (os.path.join(VENV_SITE, 'ctranslate2', '_ext.cp312-win_amd64.pyd'), 'ctranslate2'),
    ],
    datas=[
        # React Web UI Assets
        (os.path.join(r'D:\PROJECTS\Bernard-copilot\ui\dist'), r'ui\dist'),
        # Whisper Base STT Model files
        (os.path.join(WHISPER_MODEL_SNAPSHOT, 'model.bin'), 'whisper_model'),
        (os.path.join(WHISPER_MODEL_SNAPSHOT, 'config.json'), 'whisper_model'),
        (os.path.join(WHISPER_MODEL_SNAPSHOT, 'tokenizer.json'), 'whisper_model'),
        (os.path.join(WHISPER_MODEL_SNAPSHOT, 'vocabulary.txt'), 'whisper_model'),
        # RealtimeTTS and RealtimeSTT package data
        (os.path.join(VENV_SITE, 'RealtimeTTS'), 'RealtimeTTS'),
        (os.path.join(VENV_SITE, 'RealtimeSTT'), 'RealtimeSTT'),
        # webrtcvad manual bundle (to bypass broken hook)
        (os.path.join(VENV_SITE, 'webrtcvad.py'), '.'),
        (os.path.join(VENV_SITE, '_webrtcvad.cp312-win_amd64.pyd'), '.'),
        # onnxruntime data (VAD model used by RealtimeSTT)
        (os.path.join(VENV_SITE, 'onnxruntime'), 'onnxruntime'),
        # language_tags data (required by Kokoro/misaki)
        (os.path.join(VENV_SITE, 'language_tags'), 'language_tags'),
    ],
    hiddenimports=[
        # Core project modules
        'tools',
        'action_executor',
        'llm_client',
        # RealtimeTTS / RealtimeSTT
        'RealtimeTTS',
        'RealtimeTTS.text_to_stream',
        'RealtimeTTS.stream_player',
        'RealtimeTTS.engines',
        'RealtimeTTS.engines.edge_engine',
        'RealtimeTTS.engines.system_engine',
        'RealtimeSTT',
        'RealtimeSTT.audio_recorder',
        # Whisper / CTranslate2
        'faster_whisper',
        'ctranslate2',
        'ctranslate2._ext',
        'huggingface_hub',
        'tokenizers',
        # webrtcvad is bundled as data to avoid broken hooks
        # Audio
        'pyaudio',
        'sounddevice',
        'soundfile',
        'edge_tts',
        'pycaw',
        'pycaw.pycaw',
        'comtypes',
        'comtypes.stream',
        # UI Automation
        'pyautogui',
        'pyperclip',
        'uiautomation',
        'pygetwindow',
        # Rich terminal
        'rich',
        'rich.console',
        'rich.panel',
        'rich.markdown',
        'rich.status',
        'rich.live',
        'rich.text',
        # System
        'psutil',
        'screen_brightness_control',
        # Web / Research
        'ddgs',
        'bs4',
        'urllib.request',
        'urllib.parse',
        # Media
        'cv2',
        'PIL',
        'PIL.Image',
        'pypdf',
        # Finance
        'yfinance',
        'pandas',
        'numpy',
        'curl_cffi',
        'frozendict',
        'peewee',
        'multitasking',
        # Translation
        'deep_translator',
        'deep_translator.google',
        # pywhatkit
        'pywhatkit',
        # Ollama
        'ollama',
        'httpx',
        # OCR
        'pytesseract',
        # Misc
        'sqlite3',
        'json',
        'queue',
        'threading',
        'logging',
        'winsound',
        'zipfile',
        'inspect',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'webrtcvad', # Excluded to avoid broken hook
        'tkinter',
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Bernard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # Opens a terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Bernard',
)
