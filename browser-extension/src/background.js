/* Lintel Browser Extension — Background Service Worker */

// Relay messages between content script and popup
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "ELEMENT_SELECTED") {
    // Forward to popup (if open)
    chrome.runtime.sendMessage(msg).catch(() => {
      // Popup may not be open — ignore
    });
  }
  return false;
});
