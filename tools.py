import base64
import json


async def click_element(state: dict, selector: str):
    """Click an element on the page using a CSS selector."""
    page = state["page"]
    if selector.startswith("http://") or selector.startswith("https://"):
        selector = f'a[href="{selector}"]'
    await page.click(selector, timeout=3000, force=True)
    return f"Clicked {selector}"


async def type_text(state: dict, selector: str, text: str):
    """Type text into an input field."""
    page = state["page"]
    if selector.startswith("http://") or selector.startswith("https://"):
        selector = f'input[name="{selector}"]'
    await page.fill(selector, text, timeout=3000, force=True)
    return f"Typed '{text}' into {selector}"


async def goto_url(state: dict, url: str):
    """Navigate to a URL."""
    page = state["page"]
    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
    return f"Navigated to {url}"


async def scroll_page(state: dict, direction: str = "down"):
    """Scroll the page up or down."""
    page = state["page"]
    if direction == "down":
        await page.evaluate("window.scrollBy(0, 800)")
    else:
        await page.evaluate("window.scrollBy(0, -800)")
    return f"Scrolled {direction}"


async def click_text(state: dict, text: str):
    """Click an element by its visible text content."""
    page = state["page"]
    await page.click(f"text={text}", timeout=3000, force=True)
    return f"Clicked element with text '{text}'"


async def wait_for_page(state: dict):
    """Wait for the page to finish loading."""
    page = state["page"]
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass
    return f"Page loaded: {page.url}"


async def read_dom(state: dict):
    """Returns a fresh snapshot of the current DOM."""
    page = state["page"]
    from main import DOM_EXTRACT_JS
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=3000)
    except Exception:
        pass
    try:
        dom_snapshot = await page.evaluate(DOM_EXTRACT_JS)
        return json.dumps(dom_snapshot)
    except Exception as e:
        return json.dumps({"url": "", "title": "", "elements": [], "error": str(e)})


async def take_screenshot(state: dict):
    """Take a screenshot of the current page."""
    page = state["page"]
    screenshot_bytes = await page.screenshot(type='jpeg', quality=50)
    b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
    return b64


# Map of tool name -> Python function
TOOL_EXECUTORS = {
    "click_element": click_element,
    "type_text": type_text,
    "goto_url": goto_url,
    "scroll_page": scroll_page,
    "click_text": click_text,
    "wait_for_page": wait_for_page,
    "read_dom": read_dom,
    "take_screenshot": take_screenshot,
}

# Tool schemas (Ollama / OpenAI compatible)
AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "click_element",
            "description": "Click an element on the page. ALWAYS use [ai-id=\"N\"] from the DOM JSON as the selector (e.g. '[ai-id=\"4\"]'). This is the most reliable method.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector. Prefer '[ai-id=\"N\"]'. Alternatives: '#id', 'a[href=\"/path\"]'"
                    }
                },
                "required": ["selector"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "click_text",
            "description": "Click an element by its visible text label. Use when ai-id is not available.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The visible text of the element (e.g. 'Sign In', 'Submit')"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text into an input field. Use [ai-id=\"N\"] as the selector.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector of the input (e.g. '[ai-id=\"10\"]')"
                    },
                    "text": {
                        "type": "string",
                        "description": "The text to type"
                    }
                },
                "required": ["selector", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "goto_url",
            "description": "Navigate the browser to a specific URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full URL (e.g. 'https://example.com')"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scroll_page",
            "description": "Scroll the page to reveal more content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "'up' or 'down'",
                        "enum": ["up", "down"]
                    }
                },
                "required": ["direction"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wait_for_page",
            "description": "Wait for the current page to finish loading. Use after navigation or form submission.",
            "parameters": {
                "type": "object",
                "properties": {},
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Capture a visual screenshot of the page. Use when the DOM isn't providing enough context.",
            "parameters": {
                "type": "object",
                "properties": {},
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_dom",
            "description": "Get a fresh DOM snapshot. ALWAYS call this after clicking, typing, navigating, or scrolling to see the updated page.",
            "parameters": {
                "type": "object",
                "properties": {},
            }
        }
    },
]
