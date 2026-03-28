// Auto-open the side panel when the browser starts
chrome.runtime.onInstalled.addListener(() => {
    // This allows clicking the extension icon to automatically open the side panel
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

// Auto-open sidebar on every new tab
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.url) {
        try {
            await chrome.sidePanel.open({ tabId });
        } catch (e) {
            // Silently fail — panel may already be open
        }
    }
});

// Auto-open sidebar when switching tabs
chrome.tabs.onActivated.addListener(async (activeInfo) => {
    try {
        await chrome.sidePanel.open({ tabId: activeInfo.tabId });
    } catch (e) {
        // Silently fail
    }
});
