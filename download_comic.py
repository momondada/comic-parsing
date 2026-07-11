import argparse
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

JPG_EXTENSIONS = (".jpg", ".jpeg")


def get_filename_from_url(url: str) -> str:
    path = urlparse(url).path
    return path.rsplit("/", 1)[-1]


def is_jpg(url: str, content_type: str) -> bool:
    filename = get_filename_from_url(url).lower()
    if filename.endswith(JPG_EXTENSIONS):
        return True
    return content_type.split(";")[0].strip().lower() == "image/jpeg"


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
        description="開啟網頁、監控網路流量，下載頁面中的 jpg 圖片"
    )
    parser.add_argument("url", nargs="?", help="目標網址")
    parser.add_argument("-o", "--output", default="downloads", help="輸出資料夾")
    parser.add_argument("--show", action="store_true", help="顯示瀏覽器視窗（預設為背景執行）")
    parser.add_argument(
        "--url-contains",
        default=None,
        help="只下載網址中包含此字串的 jpg（例如 comic，可用來過濾掉留言區大頭貼等雜訊）",
    )
    args = parser.parse_args()

    url = args.url or input("請輸入網址: ").strip()
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.show)
        page = browser.new_page()

        def handle_response(response):
            if args.url_contains and args.url_contains not in response.url:
                return
            content_type = response.headers.get("content-type", "")
            if is_jpg(response.url, content_type):
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

    print(f"共擷取到 {len(captured)} 個 jpg 檔案，開始依時間排序並儲存...")
    captured.sort(key=lambda item: item["time"])

    for idx, item in enumerate(captured, start=1):
        filename = f"{idx:03d}.jpg"
        filepath = out_dir / filename
        filepath.write_bytes(item["body"])
        print(f"已儲存: {filepath} <- {item['url']}")

    print("全部完成。")


if __name__ == "__main__":
    main()
