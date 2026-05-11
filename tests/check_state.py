"""检查小红书搜索页面状态"""

import json
import requests
import websockets.sync.client as ws_client

CDP_HOST = "127.0.0.1"
CDP_PORT = 9222

url = f"http://{CDP_HOST}:{CDP_PORT}/json"
resp = requests.get(url, timeout=5)
data = resp.json()

pages = [p for p in data if p.get("type") == "page" and "xiaohongshu.com" in p.get("url", "")]
if not pages:
    print("没有小红书页面")
    exit(1)

ws_url = pages[0].get("webSocketDebuggerUrl", "")
print(f"连接: {ws_url}")

ws = ws_client.connect(ws_url)

def send_cmd(method, params=None):
    msg_id = 1
    msg = {"id": msg_id, "method": method}
    if params:
        msg["params"] = params
    ws.send(json.dumps(msg))
    while True:
        raw = ws.recv(timeout=10)
        data = json.loads(raw)
        if data.get("id") == msg_id:
            return data.get("result", {})

# 导航到搜索
send_cmd("Page.navigate", {"url": "https://www.xiaohongshu.com/search_result?keyword=大海&source=web_explore_feed"})

import time
print('等待页面加载...')
time.sleep(10)  # 增加等待时间

# 检查 __INITIAL_STATE__
result = send_cmd("Runtime.evaluate", {
    "expression": """
        (() => {
            const state = window.__INITIAL_STATE__;
            if (!state) return {error: 'no state'};
            
            const keys = Object.keys(state);
            const search = state.search;
            
            return {
                keys: keys,
                hasSearch: !!search,
                searchKeys: search ? Object.keys(search) : [],
                feedsType: search?.feeds ? (typeof search.feeds) : null,
                feedsKeys: search?.feeds ? Object.keys(search.feeds) : [],
                feedsValue: search?.feeds?.value,
                feedsValueLen: search?.feeds?.value?.length,
                feedsUnder: search?.feeds?._value?.length,
                
                // 检查用户信息
                hasUser: !!state.user,
                userName: state.user?.userName || state.user?.nickname,
            };
        })()
    """,
    "returnByValue": True
})

print(f"Runtime.evaluate 返回: {result}")
value = result.get("result", {}).get("result", {}).get("value", {})
print("\n=== __INITIAL_STATE__ 结构 ===")
print(json.dumps(value, indent=2, ensure_ascii=False))

# 检查 DOM
result2 = send_cmd("Runtime.evaluate", {
    "expression": """
        (() => {
            // 检查是否有搜索结果卡片
            const cards = document.querySelectorAll('[class*="note-item"], [class*="feeds-item"], [class*="card"]');
            const imgs = document.querySelectorAll('img[src*="xhscdn"]');
            
            return {
                cardCount: cards.length,
                imgCount: imgs.length,
                imgUrls: Array.from(imgs).slice(0, 5).map(img => (img.getAttribute('src') || '').substring(0, 80)),
                pageText: document.body ? document.body.innerText.substring(0, 200) : ''
            };
        })()
    """,
    "returnByValue": True
})

value2 = result2.get("result", {}).get("result", {}).get("value", {})
print("\n=== DOM 状态 ===")
print(json.dumps(value2, indent=2, ensure_ascii=False))

ws.close()