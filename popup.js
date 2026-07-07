const statusEl = document.getElementById("status");
const exportBtn = document.getElementById("export");

function setStatus(message) {
  statusEl.textContent = message;
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0];
}

exportBtn.addEventListener("click", async () => {
  try {
    const tab = await getActiveTab();
    if (!tab || !tab.url || !tab.url.includes("1688.com")) {
      setStatus("当前页面不是 1688。请先打开一个 1688 商品页。");
      return;
    }

    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content.js"]
    });

    if (!result || !result.ok) {
      setStatus(result?.error || "没有提取到商品信息。请刷新 1688 商品页，等页面加载完成后再试。");
      return;
    }

    const json = JSON.stringify(result.data, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const offerId = result.data.offer_id || "manual";
    await chrome.downloads.download({
      url,
      filename: `1688_product_${offerId}.json`,
      saveAs: true
    });
    setStatus("已生成 JSON。下载后回到 Streamlit 页面上传。");
  } catch (error) {
    setStatus(`导出失败：${error.message}`);
  }
});
