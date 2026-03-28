const providerSelect = document.getElementById('provider-select');
const modelInput = document.getElementById('model-input');
const apiKeyInput = document.getElementById('api-key-input');
const baseUrlInput = document.getElementById('base-url-input');
const apiKeyGroup = document.getElementById('api-key-group');
const baseUrlField = document.getElementById('base-url-field');
const modelPresets = document.getElementById('model-presets');
const saveBtn = document.getElementById('save-btn');
const statusMsg = document.getElementById('status-msg');

// Provider configurations
const PROVIDER_CONFIG = {
    ollama: {
        baseUrl: '',
        needsKey: false,
        needsBaseUrl: false,
        defaultModel: 'qwen3.5:9b',
        presets: ['qwen3.5:9b', 'gemma3:4b', 'llama3.2:latest', 'mistral:latest']
    },
    openai: {
        baseUrl: 'https://api.openai.com/v1',
        needsKey: true,
        needsBaseUrl: false,
        defaultModel: 'gpt-4o',
        presets: ['gpt-4o', 'gpt-4o-mini', 'gpt-4.1', 'o4-mini']
    },
    anthropic: {
        baseUrl: 'https://api.anthropic.com/v1',
        needsKey: true,
        needsBaseUrl: false,
        defaultModel: 'claude-sonnet-4-20250514',
        presets: ['claude-sonnet-4-20250514', 'claude-opus-4-20250514', 'claude-3-5-haiku-20241022']
    },
    google: {
        baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai',
        needsKey: true,
        needsBaseUrl: false,
        defaultModel: 'gemini-2.5-flash',
        presets: ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash']
    },
    openrouter: {
        baseUrl: 'https://openrouter.ai/api/v1',
        needsKey: true,
        needsBaseUrl: false,
        defaultModel: 'anthropic/claude-sonnet-4',
        presets: ['anthropic/claude-sonnet-4', 'openai/gpt-4o', 'google/gemini-2.5-flash', 'meta-llama/llama-4-maverick']
    },
    custom: {
        baseUrl: '',
        needsKey: true,
        needsBaseUrl: true,
        defaultModel: '',
        presets: []
    }
};

function updateUI(provider) {
    const config = PROVIDER_CONFIG[provider];
    if (!config) return;

    // Show/hide API key section
    if (config.needsKey) {
        apiKeyGroup.classList.add('visible');
    } else {
        apiKeyGroup.classList.remove('visible');
    }

    // Show/hide base URL field
    baseUrlField.style.display = config.needsBaseUrl ? 'block' : 'none';

    // Set base URL
    if (!config.needsBaseUrl && config.baseUrl) {
        baseUrlInput.value = config.baseUrl;
    }

    // Render presets
    modelPresets.innerHTML = '';
    config.presets.forEach(preset => {
        const chip = document.createElement('span');
        chip.className = 'preset-chip';
        chip.textContent = preset;
        chip.addEventListener('click', () => {
            modelInput.value = preset;
        });
        modelPresets.appendChild(chip);
    });
}

// Load saved settings
chrome.storage.local.get({
    provider: 'ollama',
    model: 'qwen3.5:9b',
    apiKey: '',
    baseUrl: ''
}, (data) => {
    providerSelect.value = data.provider;
    modelInput.value = data.model;
    apiKeyInput.value = data.apiKey;
    baseUrlInput.value = data.baseUrl || PROVIDER_CONFIG[data.provider]?.baseUrl || '';
    updateUI(data.provider);
});

// Update UI when provider changes
providerSelect.addEventListener('change', () => {
    const provider = providerSelect.value;
    const config = PROVIDER_CONFIG[provider];
    modelInput.value = config.defaultModel;
    if (!config.needsBaseUrl) {
        baseUrlInput.value = config.baseUrl;
    } else {
        baseUrlInput.value = '';
    }
    updateUI(provider);
});

// Save settings
saveBtn.addEventListener('click', () => {
    const provider = providerSelect.value;
    const config = PROVIDER_CONFIG[provider];

    const settings = {
        provider,
        model: modelInput.value.trim() || config.defaultModel,
        apiKey: apiKeyInput.value.trim(),
        baseUrl: baseUrlInput.value.trim() || config.baseUrl,
    };

    chrome.storage.local.set(settings, () => {
        statusMsg.style.opacity = '1';
        setTimeout(() => { statusMsg.style.opacity = '0'; }, 2000);
    });
});