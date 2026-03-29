import asyncio
import os
import json
import httpx
from fastapi import FastAPI, WebSocket
from playwright.async_api import async_playwright
from tools import AVAILABLE_TOOLS, TOOL_EXECUTORS
from starlette.websockets import WebSocketDisconnect
import uvicorn
from threading import Thread
from ollama import AsyncClient as OllamaAsyncClient

ollama_client = OllamaAsyncClient(host="http://127.0.0.1:11434")

app = FastAPI()

# Global state to keep track of the active browser page
browser_context = {"page": None, "context": None}

# ─── DOM Extraction Script (shared between initial load and read_dom tool) ───
DOM_EXTRACT_JS = """() => {
    const els = document.querySelectorAll('a, button, input, select, textarea, [role="button"], [role="link"], [role="tab"], [role="menuitem"], [onclick], label[for]');
    const results = [];
    let index = 0;
    for (const el of els) {
        if (results.length >= 80) break;
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        if (rect.bottom < 0 || rect.top > window.innerHeight) continue;
        const text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().substring(0, 50);
        const aiId = index.toString();
        el.setAttribute('ai-id', aiId);
        let info = { "ai-id": aiId, tag: el.tagName.toLowerCase() };
        if (text) info.text = text;
        if (el.id) info.id = el.id;
        const href = el.getAttribute('href');
        if (href && href !== '#' && href !== 'javascript:void(0)') info.href = href.substring(0, 80);
        if (el.name) info.name = el.name;
        if (el.type && (info.tag === 'input' || info.tag === 'button')) info.type = el.type;
        if (el.getAttribute('aria-label') && !text) info.aria = el.getAttribute('aria-label').substring(0, 40);
        if (info.text || info.id || info.name || info.href || info.aria) {
            results.push(info);
            index++;
        }
    }
    return { url: location.href, title: document.title, elements: results };
}"""

SYSTEM_PROMPT = (
    "You are an AI browser automation assistant. You control a real browser using tool calls.\n\n"
    "CURRENT PAGE INFO is provided in the DOM JSON, which includes the page URL, title, and interactive elements.\n\n"
    "RULES FOR USING TOOLS:\n"
    "- click_element: Takes a CSS selector. ALWAYS use [ai-id=\"N\"] from the DOM JSON (e.g. '[ai-id=\"4\"]'). This is the most reliable selector.\n"
    "- click_text: Click by visible text when ai-id is unavailable.\n"
    "- type_text: Type into an input field. Use [ai-id=\"N\"] as the selector.\n"
    "- goto_url: Navigate to a full URL.\n"
    "- scroll_page: Scroll 'up' or 'down' to reveal more content.\n"
    "- read_dom: Get a fresh DOM snapshot. ALWAYS call this after ANY interaction (click, type, navigate, scroll) because the page changes.\n"
    "- take_screenshot: Capture a visual screenshot if the DOM doesn't give enough context.\n"
    "- wait_for_page: Wait for the page to finish loading after navigation.\n\n"
    "STRATEGY:\n"
    "1. Analyze the DOM JSON to understand the page.\n"
    "2. Pick the right tool and execute.\n"
    "3. After EVERY interaction, call read_dom to get the updated page state.\n"
    "4. Repeat until the task is complete.\n\n"
    "OUTPUT RULES:\n"
    "- While working, output ONLY tool calls. No conversational text.\n"
    "- When the task is fully complete, output a brief summary of what you did."
)


async def call_ollama(model, messages, tools):
    """Call Ollama API with tool support."""
    response = await ollama_client.chat(
        model=model,
        messages=messages,
        tools=tools,
        options={"temperature": 0.0, "num_predict": 1024}
    )
    msg = response.get("message", {})
    return {
        "content": msg.get("content", ""),
        "tool_calls": msg.get("tool_calls", None),
        "thinking": msg.get("thinking", ""),
    }


async def call_openai_compatible(base_url, api_key, model, messages, tools):
    """Call OpenAI-compatible APIs (OpenAI, Gemini, Claude via OpenRouter, etc.)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Convert tool schemas to OpenAI format
    openai_tools = []
    for t in tools:
        openai_tools.append({
            "type": "function",
            "function": t["function"]
        })

    # Filter out image messages for non-vision compatible format
    # and convert ollama-style messages to OpenAI format
    openai_messages = []
    for m in messages:
        role = m.get("role", "user")
        if role == "tool":
            openai_messages.append({
                "role": "tool",
                "content": m.get("content", ""),
                "tool_call_id": m.get("tool_call_id", "call_0"),
            })
        elif "images" in m:
            # Vision message with base64 image
            openai_messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": m.get("content", "Here is a screenshot.")},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{m['images'][0]}"}}
                ]
            })
        else:
            openai_messages.append({"role": role, "content": m.get("content", "")})

    body = {
        "model": model,
        "messages": openai_messages,
        "tools": openai_tools,
        "temperature": 0.0,
        "max_tokens": 2048,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    choice = data.get("choices", [{}])[0]
    msg = choice.get("message", {})

    # Convert OpenAI tool_calls to our internal format
    tool_calls = None
    if msg.get("tool_calls"):
        tool_calls = []
        for tc in msg["tool_calls"]:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append({
                "function": {
                    "name": fn.get("name", ""),
                    "arguments": args,
                },
                "id": tc.get("id", "call_0"),
            })

    return {
        "content": msg.get("content", ""),
        "tool_calls": tool_calls,
        "thinking": "",
        "raw_tool_calls": msg.get("tool_calls"),  # Keep for message history
    }


async def run_agent_workflow(data, websocket):
    try:
        user_model = data.get("model", "qwen3.5:9b")
        user_command = data.get("command")
        provider = data.get("provider", "ollama")
        api_key = data.get("apiKey", "")
        base_url = data.get("baseUrl", "")

        # Dynamically find an active (non-closed) page
        p_ctx = browser_context.get("context")
        if not p_ctx or not p_ctx.pages:
            await websocket.send_text("Error: Browser tab not found.")
            return

        active_page = None
        for p in reversed(p_ctx.pages):
            if not p.is_closed():
                active_page = p
                break

        if not active_page:
            await websocket.send_text("Error: All browser tabs are closed.")
            return

        browser_context["page"] = active_page

        await websocket.send_text(f"Analyzing page with {provider}/{user_model}...")

        # Wait for the page to be in a stable state before extracting DOM
        try:
            await active_page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass  # Page may already be loaded

        # Extract DOM snapshot
        try:
            dom_snapshot = await browser_context["page"].evaluate(DOM_EXTRACT_JS)
        except Exception as dom_err:
            # Page might be navigating or in a bad state; retry once
            await asyncio.sleep(1)
            try:
                await active_page.wait_for_load_state("domcontentloaded", timeout=5000)
                dom_snapshot = await browser_context["page"].evaluate(DOM_EXTRACT_JS)
            except Exception:
                dom_snapshot = {"url": "", "title": "", "elements": []}
                await websocket.send_text(f"Warning: Could not read DOM ({dom_err}). Proceeding with empty state.")

        history_data = data.get("history", [])
        chat_history_str = ""
        if history_data:
            chat_history_str = "--- Past Conversation Context ---\n"
            for m in history_data:
                role = {"user": "User", "ai": "Assistant", "tool": "Tool", "system": "System"}.get(m.get("type", ""), "Unknown")
                chat_history_str += f"[{role}]: {m.get('text', '')}\n"
            chat_history_str += "--------------------------------\n\n"

        # Build messages
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{chat_history_str}Current Task: {user_command}\n\nDOM JSON:\n{json.dumps(dom_snapshot)}"},
        ]

        MAX_TOOL_ROUNDS = 200

        for round_num in range(MAX_TOOL_ROUNDS):
            # Route to the correct provider
            if provider == "ollama":
                result = await call_ollama(user_model, messages, AVAILABLE_TOOLS)
            else:
                result = await call_openai_compatible(base_url, api_key, user_model, messages, AVAILABLE_TOOLS)

            thinking = result.get("thinking", "")
            if thinking:
                short_thinking = thinking[:300] + "..." if len(thinking) > 300 else thinking
                await websocket.send_text(f"Thinking...\n{short_thinking}")

            tool_calls = result.get("tool_calls")

            # No tool calls = AI is done
            if not tool_calls:
                ai_reply = result.get("content", "").strip() or "Done."
                await websocket.send_text(f"AI: {ai_reply}")
                break

            # Add assistant message to history
            if provider == "ollama":
                messages.append({
                    "role": "assistant",
                    "content": result.get("content", ""),
                    "tool_calls": tool_calls,
                })
            else:
                # OpenAI format needs the raw tool_calls
                messages.append({
                    "role": "assistant",
                    "content": result.get("content", ""),
                    "tool_calls": result.get("raw_tool_calls", tool_calls),
                })

            # Execute each tool call
            for tc in tool_calls:
                func_info = tc.get("function", tc)
                tool_name = func_info.get("name", "")
                tool_args = func_info.get("arguments", func_info.get("args", {}))
                tool_call_id = tc.get("id", "call_0")

                if tool_name in TOOL_EXECUTORS:
                    try:
                        tool_func = TOOL_EXECUTORS[tool_name]
                        tool_result = await tool_func(browser_context, **tool_args)
                        if tool_name == "take_screenshot":
                            await websocket.send_text(f"✓ {tool_name}: Screenshot captured.")
                        elif tool_name == "read_dom":
                            await websocket.send_text(f"✓ {tool_name}: DOM refreshed.")
                        else:
                            await websocket.send_text(f"✓ {tool_name}: {tool_result}")
                    except Exception as tool_err:
                        tool_result = f"Error: {str(tool_err)}"
                        await websocket.send_text(f"✗ {tool_name}: {tool_result}")
                else:
                    tool_result = f"Unknown tool: {tool_name}"
                    await websocket.send_text(f"✗ {tool_result}")

                # Feed result back to model
                if tool_name == "take_screenshot" and not str(tool_result).startswith("Error"):
                    if provider == "ollama":
                        messages.append({"role": "tool", "content": "Screenshot captured."})
                        messages.append({"role": "user", "content": "Here is the screenshot.", "images": [tool_result]})
                    else:
                        messages.append({"role": "tool", "content": "Screenshot captured.", "tool_call_id": tool_call_id})
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Here is the screenshot."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{tool_result}"}}
                            ]
                        })
                else:
                    tool_msg = {"role": "tool", "content": str(tool_result)}
                    if provider != "ollama":
                        tool_msg["tool_call_id"] = tool_call_id
                    messages.append(tool_msg)
        else:
            await websocket.send_text("Reached max tool rounds. Stopping.")

    except asyncio.CancelledError:
        try:
            await websocket.send_text("System: Agent stopped by user.")
        except Exception:
            pass
        raise
    except Exception as e:
        try:
            await websocket.send_text(f"System Error: {str(e)}")
        except Exception:
            pass


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("System: Sidebar connected to Python Engine.")

    agent_task = None

    while True:
        try:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
        except WebSocketDisconnect:
            print("Sidebar disconnected.")
            if agent_task and not agent_task.done():
                agent_task.cancel()
            break
        except Exception:
            break

        command = data.get("command", "")

        if command == "/stop":
            if agent_task and not agent_task.done():
                agent_task.cancel()
                agent_task = None
            continue

        # Cancel previous task
        if agent_task and not agent_task.done():
            agent_task.cancel()

        agent_task = asyncio.create_task(run_agent_workflow(data, websocket))


def start_api():
    """Runs the FastAPI server."""
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")


async def run_agent():
    """Launches the Chromium browser with your extension."""
    Thread(target=start_api, daemon=True).start()

    async with async_playwright() as p:
        ext_path = os.path.abspath("./extension")

        context = await p.chromium.launch_persistent_context(
            user_data_dir="./chromium_profile",
            headless=False,
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            ignore_default_args=["--enable-automation"],
            args=[
                f"--disable-extensions-except={ext_path}",
                f"--load-extension={ext_path}",
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        browser_context["context"] = context
        browser_context["page"] = context.pages[0]

        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        await browser_context["page"].goto("https://www.google.com")

        print("--- AI Browser Bridge Active ---")
        print("Open the Side Panel in Chromium to begin.")

        while True:
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        print("\nExiting...")
