let socket;
const statusDot = document.getElementById('status');
const statusLabel = document.getElementById('status-label');
const chatLog = document.getElementById('chat-log');
const emptyState = document.getElementById('empty-state');
const input = document.getElementById('user-input');
const btn = document.getElementById('send-btn');

function addMessage(text, type = 'system') {
    if (emptyState) emptyState.remove();

    const wrapper = document.createElement('div');
    wrapper.className = `msg-wrapper ${type}`;

    const label = document.createElement('div');
    label.className = 'msg-label';
    const labels = { user: 'You', ai: 'AI', tool: 'Tool', system: 'System' };
    label.textContent = labels[type] || 'System';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    bubble.textContent = text;

    wrapper.appendChild(label);
    wrapper.appendChild(bubble);
    chatLog.appendChild(wrapper);
    chatLog.scrollTop = chatLog.scrollHeight;
}

function setButtonsState(running) {
    document.getElementById('send-btn').style.display = running ? 'none' : 'flex';
    document.getElementById('stop-btn').style.display = running ? 'flex' : 'none';
}

function connect() {
    socket = new WebSocket('ws://localhost:8000/ws');
    socket.onopen = () => {
        statusDot.className = "status-dot connected";
        statusLabel.textContent = "Live";
        addMessage("Engine Connected.");
    };
    socket.onclose = () => {
        statusDot.className = "status-dot";
        statusLabel.textContent = "Offline";
        setButtonsState(false);
        setTimeout(connect, 2000);
    };
    socket.onmessage = (event) => {
        const d = event.data;
        if (d.startsWith("AI:")) {
            addMessage(d, 'ai');
            setButtonsState(false);
        } else if (d.startsWith("✓") || d.startsWith("✗")) {
            addMessage(d, 'tool');
        } else if (d.startsWith("Thinking")) {
            addMessage(d, 'system');
        } else {
            addMessage(d, 'system');
            if (d.includes("stopped") || d.includes("Stopping") || d.includes("Error") || d.includes("max tool") || d.includes("System Error")) {
                setButtonsState(false);
            }
        }
    };
}

// Send command
btn.onclick = () => {
    const text = input.value.trim();
    if (text && socket.readyState === WebSocket.OPEN) {
        addMessage(text, 'user');
        setButtonsState(true);

        // Load all settings from storage
        chrome.storage.local.get({
            provider: 'ollama',
            model: 'qwen3.5:9b',
            apiKey: '',
            baseUrl: ''
        }, (data) => {
            const payload = {
                provider: data.provider,
                model: data.model,
                apiKey: data.apiKey,
                baseUrl: data.baseUrl,
                command: text
            };
            socket.send(JSON.stringify(payload));
        });

        input.value = '';
        input.style.height = 'auto';
    }
};

input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        btn.click();
    }
});

document.getElementById('stop-btn').onclick = () => {
    if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ command: "/stop" }));
        setButtonsState(false);
    }
};

// Auto-resize textarea
input.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});

// Settings gear opens the extension options page
document.getElementById('settings-btn').addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
});

connect();