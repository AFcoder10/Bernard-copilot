import os
os.environ["PATH"] += os.pathsep + r"C:\Program Files\MPV Player"
from RealtimeTTS import TextToAudioStream, KokoroEngine
engine = KokoroEngine(voice="af_bella", default_speed=1.0)
stream = TextToAudioStream(engine)
stream.add_pause("wake", 0.5)
stream.feed(["[wake] Hello there, is the start of this sentence clipped?"])
stream.play()
