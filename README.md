# AI Browser Bridge

A high-performance, agentic browser automation system that bridges a local Python backend with an injected Chrome Extension Sidepanel, allowing users to autonomously script and navigate web pages using large language models.

## Features

- **Multi-Provider AI Support**: Configure the agent to run locally with `ollama`, or hook it up to OpenAI, Anthropic, Google, OpenRouter, or Custom endpoints directly via the extension settings.
- **Robust DOM Pruning Framework**: The system surgically extracts and minifies interactive elements off a web page and tracks them using self-generated `ai-id` data attributes. This allows smaller models (like `qwen3.5:9b`) to parse and navigate dense DOM pages seamlessly without guessing complex CSS selectors.
- **Interruptible Agentic Loop**: Built on FastAPI WebSockets, allowing you to instantly pause or override the AI task mid-execution.
- **Stealth Automation**: Pre-configured Playwright capabilities scrub default webdriver fingerprints to bypass bot security checks (like Cloudflare or Google ReCaptcha).

## Architecture

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
