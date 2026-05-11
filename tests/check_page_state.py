"""直接检查当前页面状态并获取图片 URL。"""

import json
import requests
import websockets.sync.client as ws_client

CDP_HOST = "127.0.0.1"
CDP_PORT = 9222

def get_page_ws_url():
    url = f"http://{CDP_HOST}:{CDP_PORT}/json"
    resp = requests.get(url, timeout=5)
    data = resp.json()
    pages = [p for p in data if p.get("type") == "page"]
    return pages[0].get("webSocketDebuggerUrl", "") if pages else ""

ws_url = get_page_ws_url()
print(f"连接: {ws_url}")

ws = ws_client.connect(ws_url)

# 发送命令
def send_cmd(method, params=None):
    msg_id = 1
    msg = {"id": msg_id, "method": method}
    if params:
        msg["params"] = params
    ws.send(json.dumps(msg))
    
    while True:
        raw = ws.recv(timeout=30.0)
        data = json.loads(raw)
        if data.get("id") == msg_id:
            return data

# 检查 __INITIAL_STATE__
print("\n=== 检查 __INITIAL_STATE__ ===")
result = send_cmd("Runtime.evaluate", {
    "expression": """
        (() => {
            const state = window.__INITIAL_STATE__;
            if (!state) return {error: 'no state'};
            
            const search = state.search;
            if (!search) return {error: 'no search'};
            
            const feeds = search.feeds;
            if (!feeds) return {error: 'no feeds'};
            
            const data = feeds.value || feeds._value || [];
            
            return {
                hasFeeds: !!data,
                feedCount: data.length,
                firstFeed: data[0] ? {
                    id: data[0].id,
                    noteCard: data[0].noteCard ? {
                        cover: data[0].noteCard.cover
                    } : null
                } : null
            };
        })()
    """,
    "returnByValue": True
})

value = result.get("result", {}).get("result", {}).get("value", {})
print(json.dumps(value, indent=2))

# 检查 DOM 图片
print("\n=== 检查 DOM 图片 ===")
result2 = send_cmd("Runtime.evaluate", {
    "expression": """
        (() => {
            const imgs = document.querySelectorAll('img');
            const results = [];
            
            imgs.forEach((img, i) => {
                if (i < 10) {
                    const src = img.getAttribute('src') || '';
                    const className = img.className || '';
                    const parentClass = img.parentElement?.className || '';
                    results.push({
                        index: i,
                        src: src.substring(0, 80),
                        className: className.substring(0, 50),
                        parentClass: parentClass.substring(0, 50),
                        hasWebpic: src.includes('webpic') || src.includes('xhscdn')
                    });
                }
            });
            
            return results;
        })()
    """,
    "returnByValue": True
})

value2 = result2.get("result", {}).get("result", {}).get("value", [])
print(json.dumps(value2, indent=2))

ws.close()