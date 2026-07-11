let isMonitoring = false;
let capturedFiles = [];
let currentPrefix = "bEqPbYfoPT0GmxXlAl";

const EXT_BY_MIME = {
  "image/jpeg": ".jpg",
  "image/png": ".png",
  "image/webp": ".webp",
  "image/gif": ".gif",
  "image/avif": ".avif",
  "image/bmp": ".bmp",
  "image/svg+xml": ".svg",
};

function getFilenameFromUrl(url) {
  try {
    const parts = new URL(url).pathname.split("/");
    return parts[parts.length - 1] || "";
  } catch (e) {
    return "";
  }
}

function guessExtension(url, contentType) {
  const filename = getFilenameFromUrl(url);
  const dotIndex = filename.lastIndexOf(".");
  if (dotIndex !== -1 && filename.length - dotIndex <= 6) {
    return filename.slice(dotIndex);
  }
  if (contentType) {
    const mime = contentType.split(";")[0].trim().toLowerCase();
    if (EXT_BY_MIME[mime]) return EXT_BY_MIME[mime];
  }
  return "";
}

chrome.webRequest.onCompleted.addListener(
  (details) => {
    if (!isMonitoring) return;
    const filename = getFilenameFromUrl(details.url);
    if (!filename.startsWith(currentPrefix)) return;

    let contentType = "";
    if (details.responseHeaders) {
      const header = details.responseHeaders.find(
        (h) => h.name.toLowerCase() === "content-type"
      );
      if (header) contentType = header.value;
    }

    capturedFiles.push({
      url: details.url,
      time: details.timeStamp,
      contentType,
    });
  },
  { urls: ["<all_urls>"] },
  ["responseHeaders"]
);

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "START") {
    isMonitoring = true;
    capturedFiles = [];
    currentPrefix = message.prefix || currentPrefix;
    sendResponse({ ok: true });
  } else if (message.type === "STOP") {
    isMonitoring = false;

    capturedFiles.sort((a, b) => a.time - b.time);
    const total = capturedFiles.length;
    capturedFiles.forEach((item, idx) => {
      const ext = guessExtension(item.url, item.contentType);
      const paddedIndex = String(idx + 1).padStart(3, "0");
      chrome.downloads.download({
        url: item.url,
        filename: `network-capture/${paddedIndex}${ext}`,
        conflictAction: "uniquify",
      });
    });

    sendResponse({ ok: true, total });
  } else if (message.type === "STATUS") {
    sendResponse({ isMonitoring, count: capturedFiles.length });
  }
  return true;
});
