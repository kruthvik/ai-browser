let socket;
const statusDot = document.getElementById('status');
const statusLabel = document.getElementById('status-label');
const chatLog = document.getElementById('chat-log');
const input = document.getElementById('user-input');
const btn = document.getElementById('send-btn');

// History UI Elements
const historyBtn = document.getElementById('history-btn');
const historyBackdrop = document.getElementById('history-backdrop');
const historyPanel = document.getElementById('history-panel');
const historyList = document.getElementById('history-list');
const newChatBtn = document.getElementById('new-chat-btn');

// State
let currentSessionId = null;
let sessions = []; // [{ id, title, date, messages: [{text, type}] }]

// ─── History Logic ───

function toggleHistory() {
    const isOpen = historyPanel.classList.contains('open');
    if (isOpen) {
        historyPanel.classList.remove('open');
        historyBackdrop.classList.remove('open');
    } else {
        historyPanel.classList.add('open');
        historyBackdrop.classList.add('open');
    }
}

historyBtn.addEventListener('click', toggleHistory);
historyBackdrop.addEventListener('click', toggleHistory);

function loadSessions(callback) {
    chrome.storage.local.get({ sessions: [] }, (data) => {
        sessions = data.sessions;
        renderHistoryList();
        if (callback) callback();
    });
}

function saveSessions() {
    chrome.storage.local.set({ sessions });
    renderHistoryList();
}

function renderHistoryList() {
    historyList.innerHTML = '';
    
    // Sort descending by ID (timestamp)
    const sorted = [...sessions].sort((a, b) => b.id - a.id);
    
    sorted.forEach(session => {
        const item = document.createElement('div');
        item.className = `history-item ${session.id === currentSessionId ? 'active' : ''}`;
        
        const title = document.createElement('span');
        title.className = 'history-item-title';
        title.textContent = session.title || 'New Chat';
        
        const date = document.createElement('span');
        date.className = 'history-item-date';
        date.textContent = new Date(session.id).toLocaleString(undefined, {
            month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
        });
        
        item.appendChild(title);
        item.appendChild(date);
        
        item.onclick = () => loadSessionIntoView(session.id);
        historyList.appendChild(item);
    });
}

function startNewChat() {
    currentSessionId = null;
    chatLog.innerHTML = `
        <div class="empty-state" id="empty-state">
            <div class="empty-state-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M13 10V3L4 14h7v7l9-11h-7z"/>
                </svg>
            </div>
            <p>Waiting for Python Engine…</p>
        </div>
    `;
    renderHistoryList();
    toggleHistory();
}

newChatBtn.addEventListener('click', startNewChat);

function loadSessionIntoView(id) {
    const session = sessions.find(s => s.id === id);
    if (!session) return;
    
    currentSessionId = id;
    chatLog.innerHTML = '';
    
    session.messages.forEach(m => {
        renderMessageDOM(m.text, m.type);
    });
    
    renderHistoryList();
    toggleHistory();
}

function appendMessageToMemory(text, type) {
    // Only save semantic messages. Exclude transient connecting messages.
    if (text === "Engine Connected.") return;
    
    if (!currentSessionId) {
        // Create new session
        currentSessionId = Date.now();
        const title = type === 'user' ? text.substring(0, 40) + (text.length > 40 ? '...' : '') : 'New Chat';
        sessions.push({
            id: currentSessionId,
            title: title,
            messages: []
        });
    }
    
    const session = sessions.find(s => s.id === currentSessionId);
    if (session) {
        session.messages.push({ text, type });
        // Update title if it was an empty chat that was resumed
        if (session.messages.length === 1 && type === 'user') {
             session.title = text.substring(0, 40) + (text.length > 40 ? '...' : '');
        }
        saveSessions();
    }
}

// ─── Chat DOM Logic ───

function renderMessageDOM(text, type = 'system') {
    const emptyState = document.getElementById('empty-state');
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

function addMessage(text, type = 'system') {
    renderMessageDOM(text, type);
    appendMessageToMemory(text, type);
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
        renderMessageDOM("Engine Connected.", "system");
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

// ─── Input Logic ───

btn.onclick = () => {
    const text = input.value.trim();
    if (text && socket.readyState === WebSocket.OPEN) {
        // Find existing context or keep blank
        let existingContext = null;
        if (currentSessionId) {
            const session = sessions.find(s => s.id === currentSessionId);
            if (session) existingContext = session.messages;
        }

        addMessage(text, 'user');
        setButtonsState(true);

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
                command: text,
                history: existingContext // Pass context to backend so it remembers past inputs in this session
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

// Settings button
document.getElementById('settings-btn').addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
});

// Init
loadSessions(() => {
    // If there is a most recent session, load it automatically? 
    // Or just start a new chat. Keeping it a new chat is standard.
});
connect();