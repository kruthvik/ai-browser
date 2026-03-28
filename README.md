# AI Browser Bridge

Agentic browser automation system that connects local Python backend w/ injected Chrome Extension Sidepanel, allowing users to autonomously script and navigate web pages using large language models.

* **Backend (`main.py`)**: A Python-based FastAPI server managing a persistent Chromium instance via Playwright, providing multimodal and tooling support to the AI.
* **Frontend Extension (`extension/`)**: A sleek Manifest V3 Chrome Extension Sidepanel UI built with Vanilla JS that interfaces dynamically with the backend via a WebSocket connection.

## Installation

### 1. Backend Setup

Ensure you have Python 3 installed. Then, install the required dependencies:

```bash
pip install -r requirements.txt
playwright install
```

### 2. Configure Extension
The browser is automatically launched with the extension folder pre-loaded by Playwright. To run the app, simply start the engine:

```bash
python main.py
```

## Usage

1. **Launch the Engine**: `python main.py` triggers a new Chromium browser session.
2. **Open the Side Panel**: Click the **"AI Bridge"** extension icon in your Chromium toolbar to open the Agent Sidepanel.
3. **Configure the AI**: Click the Gear Icon inside the sidepanel extension to select your preferred AI provider (`ollama`, `openai`, `anthropic`, etc.), model name, and API keys.
4. **Command the Agent**: Submit a prompt to start browser automation!

**APP COMPILE COMING SOON**
