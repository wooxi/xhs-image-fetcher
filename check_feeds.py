"""等待搜索结果加载并获取图片"""

import json
import time
import requests
import websockets.sync.client as ws_client

CDP_HOST = "127.0.0.1"
CDP_PORT = 9222

url = f"http://{CDP_HOST}:{CDP_PORT}/json"
resp = requests.get(url, timeout=5)
data = resp.json()

pages = [p for p in data if p.get("type") == "page" and "xiaohongshu.com" in p.get("url", "")]
ws_url = pages[0].get("webSocketDebuggerUrl", "")
print(f"连接: {ws_url}")

ws = ws_client.connect(ws_url)

def send_cmd(method, params=None, msg_id=1):
    msg = {"id": msg_id, "method": method}
    if params:
        msg["params"] = params
    ws.send(json.dumps(msg))
    while True:
        raw = ws.recv(timeout=30)
        data = json.loads(raw)
        if data.get("id") == msg_id:
            return data.get("result", {})

# 导航搜索
print("导航搜索页...")
send_cmd("Page.navigate", {"url": "https://www.xiaohongshu.com/search_result?keyword=大海&source=web_explore_feed"})

# 等待更长时间
print("等待 15 秒...")
time.sleep(15)

# 多次检查 feeds
for i in range(10):
    result = send_cmd("Runtime.evaluate", {
        "expression": """
            (() => {
                const state = window.__INITIAL_STATE__;
                if (!state?.search?.feeds) return {feeds: 0, imgs: 0};
                
                // Vue ref 取值
                const feeds = state.search.feeds._value || state.search.feeds._rawValue || state.search.feeds.value || [];
                
                // DOM 图片
                const imgs = document.querySelectorAll('img[src*="xhscdn"]');
                const contentImgs = [];
                imgs.forEach(img => {
                    const src = img.getAttribute('src') || '';
                    if (src && !src.includes('avatar') && !src.includes('icon')) {
                        contentImgs.push(src);
                    }
                });
                
                return {
                    feeds: feeds.length,
                    imgs: contentImgs.length,
                    urls: contentImgs.slice(0, 3)
                };
            })()
        """,
        "returnByValue": True
    }, msg_id=i+1)
    
    value = result.get("result", {}).get("result", {}).get("value", {})
    feeds_count = value.get("feeds", 0)
    imgs_count = value.get("imgs", 0)
    
    print(f"检查 {i+1}: feeds={feeds_count}, imgs={imgs_count}")
    
    if feeds_count > 0 or imgs_count > 0:
        print("\n找到数据!")
        print(json.dumps(value, indent=2, ensure_ascii=False))
        break
    
    time.sleep(1)

ws.close()