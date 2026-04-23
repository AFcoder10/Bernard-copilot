# Bernard Copilot

Bernard is an autonomous, fully local AI assistant for your Windows PC, powered by Ollama. Instead of just answering questions, Bernard thinks agentically and uses over 20 built-in tools to take actions on your behalf.

## Features

* **Fully Local:** Runs privately using Ollama (`gemma4:e2b`).
* **Agentic Execution:** Autonomous tool-calling loop for complex tasks.
* **Real-time Voice:** Fast STT (Whisper) and TTS (Edge TTS) for fluid conversation.
* **Windows Native Control:** Interacts with desktop apps reliably using the Windows UIAutomation API.
* **Extensive Tools:** Automates web searches, YouTube playback, WhatsApp messaging (via PyWhatKit), file management, and more.

## Getting Started

1. Start Ollama with `ollama run gemma4:e2b`
2. Clone this repository and set up a virtual environment.
3. Install dependencies: `pip install -r requirements.txt`
4. Run the assistant: `python bernard_main.py`

## Usage

Speak naturally into your microphone or type in the terminal. Bernard will autonomously determine which tools to use to fulfill your request.

## License

MIT License.