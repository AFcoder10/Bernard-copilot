import os
# Force add MPV to the system PATH inside Python so we don't need to restart VS Code
os.environ["PATH"] += os.pathsep + r"C:\Program Files\MPV Player"

from RealtimeTTS import TextToAudioStream, SystemEngine, EdgeEngine
import time

def dummy_llm_stream():
    """Simulates an LLM generating text token by token."""
    text = "Hello! I am Bernard. I am now speaking to you in real-time, instantly streaming audio as the words are generated. This completely eliminates the awkward silence."
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.1) # Simulate the generation delay of a local LLM

def main():
    print("Initializing TTS Engine...")
    try:
        # EdgeEngine is fast, free, and sounds incredible, but requires internet.
        # It streams audio chunks immediately as Azure generates them.
        engine = EdgeEngine() 
        print("Using Edge TTS Engine.")
    except Exception as e:
        # Fallback to local Windows system voice if offline
        print(f"EdgeEngine failed, falling back to local SystemEngine: {e}")
        engine = SystemEngine()

    # Create the real-time stream wrapper
    stream = TextToAudioStream(engine)
    
    print("\nSimulating LLM generation...")
    # By feeding it a Python generator, it plays audio immediately as sentences form!
    stream.feed(dummy_llm_stream())
    
    print("Playing stream asynchronously...")
    stream.play_async()
    
    # Keep main thread alive while async audio plays in the background
    while stream.is_playing():
        time.sleep(0.1)
    
    print("\nDone streaming.")

if __name__ == '__main__':
    main()
