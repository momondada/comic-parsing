import argparse
import mimetypes
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

TARGET_PREFIX = "bEqPbYfoPT0GmxXlAl"


def get_filename_from_url(url: str) -> str:
    path = urlparse(url).path
    return path.rsplit("/", 1)[-1]


def guess_extension(url: str, content_type: str) -> str:
    filename = get_filename_from_url(url)
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1]
        if len(ext) <= 6:
            return ext
    ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) if content_type else None
    return ext or ""


def scroll_to_bottom(page, pause_ms=1000, max_stable_rounds=3):
    stable_rounds = 0
    last_height = page.evaluate("document.body.scrollHeight")
    while stable_rounds < max_stable_rounds:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pause_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            stable_rounds += 1
        else:
            stable_rounds = 0
            last_height = new_height


def main():
    parser = argparse.ArgumentParser(
        description="開啟網頁、監控網路流量，下載檔名以指定前綴開頭的檔案"
    )
    parser.add_argument("url", nargs="?", help="目標網址")
    parser.add_argument("-o", "--output", default="downloads", help="輸出資料夾")
    parser.add_argument("--show", action="store_true", help="顯示瀏覽器視窗（預設為背景執行）")
    args = parser.parse_args()

    url = args.url or input("請輸入網址: ").strip()
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.show)
        page = browser.new_page()

        def handle_response(response):
            filename = get_filename_from_url(response.url)
            if filename.startswith(TARGET_PREFIX):
                try:
                    body = response.body()
                except Exception as e:
                    print(f"[警告] 無法讀取回應內容: {response.url} ({e})")
                    return
                captured.append(
                    {
                        "time": time.time(),
                        "url": response.url,
                        "body": body,
                        "content_type": response.headers.get("content-type", ""),
                    }
                )
                print(f"[抓到] {response.url}")

        page.on("response", handle_response)

        print(f"正在開啟網頁: {url}")
        page.goto(url, wait_until="load")

        print("開始滾動網頁到最底端...")
        scroll_to_bottom(page)
        print("已到達網頁最底端。")

        # 讓最後觸發的請求有機會完成
        page.wait_for_timeout(1500)

        page.remove_listener("response", handle_response)
        browser.close()

    print(f"共擷取到 {len(captured)} 個符合條件的檔案，開始依時間排序並儲存...")
    captured.sort(key=lambda item: item["time"])

    for idx, item in enumerate(captured, start=1):
        ext = guess_extension(item["url"], item["content_type"])
        filename = f"{idx:03d}{ext}"
        filepath = out_dir / filename
        filepath.write_bytes(item["body"])
        print(f"已儲存: {filepath} <- {item['url']}")

    print("全部完成。")


if __name__ == "__main__":
    main()
