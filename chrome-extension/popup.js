const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const prefixInput = document.getElementById("prefix");
const statusDiv = document.getElementById("status");

function refreshStatus() {
  chrome.runtime.sendMessage({ type: "STATUS" }, (res) => {
    if (!res) return;
    statusDiv.textContent = res.isMonitoring
      ? `監控中... 已擷取 ${res.count} 個檔案`
      : `尚未開始（上次擷取 ${res.count} 個檔案）`;
  });
}

startBtn.addEventListener("click", () => {
  chrome.runtime.sendMessage(
    { type: "START", prefix: prefixInput.value.trim() },
    () => refreshStatus()
  );
});

stopBtn.addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "STOP" }, (res) => {
    statusDiv.textContent = `已結束，共下載 ${res.total} 個檔案`;
  });
});

refreshStatus();
setInterval(refreshStatus, 1000);
