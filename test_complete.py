"""完整测试：搜索小红书 -> Network.getResponseBody 下载第一张图片

成功方案：
1. Network.enable 启用监听
2. Page.navigate 导航到图片 URL
3. 监听 loadingFinished 事件（关键！不是 responseReceived）
4. 用 loadingFinished 的 requestId 获取响应体
"""

import json
import base64
import time
import os
from pathlib import Path

import requests
import websockets.sync.client as ws_client

OUTPUT_DIR = Path("/tmp/xhs_images_test")
CDP_HOST = "127.0.0.1"
CDP_PORT = 9222


class CDPConnection:
    """CDP WebSocket 连接封装。"""
    
    def __init__(self, ws_url):
        self.ws = ws_client.connect(ws_url)
        self.msg_id = 0
    
    def close(self):
        if self.ws:
            self.ws.close()
    
    def send_cmd(self, method, params=None):
        """发送命令并等待响应。"""
        self.msg_id += 1
        msg = {"id": self.msg_id, "method": method}
        if params:
            msg["params"] = params
        self.ws.send(json.dumps(msg))
        while True:
            raw = self.ws.recv(timeout=30.0)
            data = json.loads(raw)
            if data.get("id") == self.msg_id:
                if "error" in data:
                    return {"error": data["error"]}
                return data.get("result", {})
    
    def recv_event(self, timeout=1.0):
        """接收事件。"""
        try:
            raw = self.ws.recv(timeout=timeout)
            return json.loads(raw)
        except TimeoutError:
            return None
    
    def evaluate(self, expression):
        """执行 JavaScript。"""
        result = self.send_cmd("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
        })
        if result.get("error"):
            return None
        return result.get("result", {}).get("result", {}).get("value")


def create_tab(url="about:blank"):
    """创建新 tab。"""
    tab_url = f"http://{CDP_HOST}:{CDP_PORT}/json/new?{url}"
    resp = requests.put(tab_url, timeout=5)
    data = resp.json()
    return data.get("webSocketDebuggerUrl", ""), data.get("id", "")


def close_tab(tab_id):
    try:
        requests.get(f"http://{CDP_HOST}:{CDP_PORT}/json/close/{tab_id}", timeout=5)
    except:
        pass


def wait_for_feeds(conn, timeout=20.0):
    """等待搜索结果 feeds 加载。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        count = conn.evaluate("""
            (() => {
                const state = window.__INITIAL_STATE__;
                if (!state?.search?.feeds) return 0;
                const feeds = state.search.feeds.value || state.search.feeds._value || [];
                return feeds.length;
            })()
        """) or 0
        if count > 0:
            print(f"[wait] feeds 数量: {count}")
            return True
        time.sleep(0.5)
    return False


def get_first_image_url(conn):
    """获取第一张图片 URL。"""
    images = conn.evaluate("""
        (() => {
            let results = [];
            
            // 从 state 提取封面图
            const state = window.__INITIAL_STATE__;
            if (state?.search?.feeds) {
                const feeds = state.search.feeds.value || state.search.feeds._value || [];
                feeds.forEach((feed) => {
                    const cover = feed.noteCard?.cover || {};
                    const url = cover.urlDefault || cover.url || '';
                    if (url) {
                        results.push(url);
                    }
                });
            }
            
            // 从 DOM 提取（备用）
            if (results.length === 0) {
                const imgs = document.querySelectorAll('img[src*="xhscdn"]');
                imgs.forEach((img) => {
                    const src = img.getAttribute('src') || '';
                    if (src && !src.includes('avatar') && !src.includes('icon')) {
                        results.push(src);
                    }
                });
            }
            
            return results;
        })()
    """) or []
    
    if not images:
        return None
    
    url = images[0]
    
    # 转换高清格式
    if "!nc_" in url:
        url = url.rsplit("!", 1)[0] + "!nd_dft_wlteh_webp_3"
    elif not url.endswith("!"):
        url = url.rsplit("!", 1)[0] + "!nd_dft_wlteh_webp_3"
    
    if url.startswith("http://"):
        url = "https://" + url[7:]
    
    return url


def download_with_network(conn, url, save_path, timeout=30.0):
    """使用 Network.getResponseBody 方式下载图片。
    
    关键发现：
    - 图片请求不会触发 responseReceived
    - 但会触发 loadingFinished
    - 用 loadingFinished 的 requestId 获取响应体
    """
    print(f"\n[network] 下载: {url[:80]}...")
    
    # 启用 Network
    print("[network] 启用 Network domain...")
    conn.send_cmd("Network.enable")
    conn.send_cmd("Page.enable")
    
    # 导航
    print("[network] 导航...")
    conn.send_cmd("Page.navigate", {"url": url})
    
    # 监听 loadingFinished
    print("[network] 监听事件...")
    
    request_ids = []
    request_urls = {}
    deadline = time.monotonic() + timeout
    page_loaded = False
    
    while time.monotonic() < deadline:
        event = conn.recv_event(timeout=1.0)
        if event is None:
            if page_loaded and len(request_ids) > 0:
                break
            continue
        
        method = event.get("method", "")
        params = event.get("params", {})
        
        if method == "Network.requestWillBeSent":
            req_id = params.get("requestId", "")
            req_url = params.get("request", {}).get("url", "")
            request_urls[req_id] = req_url
        
        elif method == "Network.loadingFinished":
            req_id = params.get("requestId", "")
            req_url = request_urls.get(req_id, "")
            if "favicon" not in req_url.lower():
                request_ids.append(req_id)
                print(f"[network] loadingFinished: {req_id[:10]} ({req_url[:40]}...)")
        
        elif method == "Page.loadEventFired":
            page_loaded = True
            print("[network] loadEventFired")
    
    if not request_ids:
        return {"success": False, "error": "未收到 loadingFinished"}
    
    # 尝试获取响应体
    for req_id in request_ids:
        print(f"[network] 尝试 getResponseBody: {req_id}")
        body_result = conn.send_cmd("Network.getResponseBody", {"requestId": req_id})
        
        if body_result.get("error"):
            continue
        
        body = body_result.get("body", "")
        if not body:
            continue
        
        base64_encoded = body_result.get("base64Encoded", False)
        
        # 解码保存
        if base64_encoded:
            image_data = base64.b64decode(body)
        else:
            image_data = body.encode() if isinstance(body, str) else body
        
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(image_data)
        
        file_size = os.path.getsize(save_path)
        print(f"[network] ✅ 成功: {save_path} ({file_size} bytes)")
        
        return {
            "success": True,
            "path": save_path,
            "size": file_size,
            "method": "Network.getResponseBody",
            "request_id": req_id,
        }
    
    return {"success": False, "error": "所有 requestId 响应体为空"}


def main(keyword="大海"):
    """完整测试流程。"""
    print("="*60)
    print(f"测试: 搜索 '{keyword}' -> Network.getResponseBody 下载")
    print("="*60)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 步骤1: 创建搜索 tab
    search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_explore_feed"
    ws_url, tab_id = create_tab(search_url)
    print(f"[main] 创建搜索 tab: {tab_id}")
    
    conn = CDPConnection(ws_url)
    
    try:
        conn.send_cmd("Page.enable")
        conn.send_cmd("Runtime.enable")
        
        # 等待 feeds
        if not wait_for_feeds(conn, timeout=20.0):
            print("[main] ❌ 搜索结果未加载（可能未登录）")
            return {"success": False, "error": "搜索结果未加载"}
        
        # 获取图片 URL
        print("[main] 获取图片 URL...")
        image_url = get_first_image_url(conn)
        
        if not image_url:
            print("[main] ❌ 未找到图片 URL")
            return {"success": False, "error": "未找到图片 URL"}
        
        print(f"[main] 图片 URL: {image_url[:100]}...")
        
        # 步骤2: 创建下载 tab
        dl_ws_url, dl_tab_id = create_tab()
        print(f"[main] 创建下载 tab: {dl_tab_id}")
        
        dl_conn = CDPConnection(dl_ws_url)
        
        try:
            timestamp = int(time.time())
            save_path = str(OUTPUT_DIR / f"xhs_{keyword}_{timestamp}.jpg")
            
            result = download_with_network(dl_conn, image_url, save_path)
            
            if result.get("success"):
                print("\n" + "="*60)
                print("✅ 测试成功!")
                print(f"关键词: {keyword}")
                print(f"图片路径: {save_path}")
                print(f"文件大小: {result['size']} bytes")
                print(f"下载方式: Network.getResponseBody")
                print("="*60)
                
                return {
                    "success": True,
                    "keyword": keyword,
                    "image_path": save_path,
                    "file_size": result["size"],
                    "download_method": "Network.getResponseBody",
                    "image_url": image_url,
                }
            else:
                return result
        
        finally:
            dl_conn.close()
            close_tab(dl_tab_id)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
    
    finally:
        conn.close()
        close_tab(tab_id)


if __name__ == "__main__":
    import sys
    keyword = sys.argv[1] if len(sys.argv) > 1 else "大海"
    result = main(keyword)
    print(json.dumps(result, ensure_ascii=False, indent=2))