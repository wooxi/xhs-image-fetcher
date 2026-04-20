"""完整测试 v3：使用已登录页面搜索 -> Network.getResponseBody 下载

问题：新 tab 没有登录状态
解决：使用已登录的小红书页面导航搜索
"""

import json
import base64
import time
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

import requests
import websockets.sync.client as ws_client

OUTPUT_DIR = Path("/tmp/xhs_images_test")
CDP_HOST = "127.0.0.1"
CDP_PORT = 9222


class CDPConnection:
    def __init__(self, ws_url):
        self.ws = ws_client.connect(ws_url)
        self.msg_id = 0
    
    def close(self):
        if self.ws:
            self.ws.close()
    
    def send_cmd(self, method, params=None):
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
        try:
            raw = self.ws.recv(timeout=timeout)
            return json.loads(raw)
        except TimeoutError:
            return None
    
    def evaluate(self, expression):
        result = self.send_cmd("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
        })
        if result.get("error"):
            return None
        return result.get("result", {}).get("result", {}).get("value")


def get_or_create_xhs_tab():
    """获取已登录的小红书页面或创建新的。"""
    url = f"http://{CDP_HOST}:{CDP_PORT}/json"
    resp = requests.get(url, timeout=5)
    data = resp.json()
    
    # 找小红书页面
    pages = [p for p in data if p.get("type") == "page" and "xiaohongshu.com" in p.get("url", "")]
    
    if pages:
        return pages[0].get("webSocketDebuggerUrl", ""), pages[0].get("id", ""), True
    
    # 创建新页面
    new_url = f"http://{CDP_HOST}:{CDP_PORT}/json/new?https://www.xiaohongshu.com"
    resp = requests.put(new_url, timeout=5)
    data = resp.json()
    return data.get("webSocketDebuggerUrl", ""), data.get("id", ""), False


def create_blank_tab():
    url = f"http://{CDP_HOST}:{CDP_PORT}/json/new?about:blank"
    resp = requests.put(url, timeout=5)
    data = resp.json()
    return data.get("webSocketDebuggerUrl", ""), data.get("id", "")


def close_tab(tab_id):
    try:
        requests.get(f"http://{CDP_HOST}:{CDP_PORT}/json/close/{tab_id}", timeout=5)
    except:
        pass


def wait_for_feeds(conn, timeout=30.0):
    """等待 feeds 加载。"""
    deadline = time.monotonic() + timeout
    
    # 先等待页面稳定
    time.sleep(2.0)
    
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
            
            // 从 __INITIAL_STATE__ 提取
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
                    if (src && !src.includes('avatar') && !src.includes('icon') && !src.includes('logo')) {
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
    
    if url.startswith("http://"):
        url = "https://" + url[7:]
    
    return url


def download_with_network(conn, url, save_path, timeout=30.0):
    """Network.getResponseBody 方式下载。
    
    关键：监听 loadingFinished，不是 responseReceived
    """
    print(f"\n[network] 下载: {url[:80]}...")
    
    conn.send_cmd("Network.enable")
    conn.send_cmd("Page.enable")
    conn.send_cmd("Page.navigate", {"url": url})
    
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
                print(f"[network] loadingFinished: {req_id[:10]}")
        
        elif method == "Page.loadEventFired":
            page_loaded = True
    
    for req_id in request_ids:
        body_result = conn.send_cmd("Network.getResponseBody", {"requestId": req_id})
        if body_result.get("error") or not body_result.get("body"):
            continue
        
        body = body_result.get("body", "")
        base64_encoded = body_result.get("base64Encoded", False)
        
        if base64_encoded:
            image_data = base64.b64decode(body)
        else:
            image_data = body.encode() if isinstance(body, str) else body
        
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(image_data)
        
        file_size = os.path.getsize(save_path)
        print(f"[network] ✅ 成功: {save_path} ({file_size} bytes)")
        
        return {"success": True, "path": save_path, "size": file_size, "method": "Network.getResponseBody"}
    
    return {"success": False, "error": "响应体获取失败"}


def main(keyword="大海"):
    print("="*60)
    print(f"测试: 搜索 '{keyword}' -> Network.getResponseBody 下载")
    print("="*60)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 使用已登录的小红书页面
    ws_url, search_tab_id, is_existing = get_or_create_xhs_tab()
    print(f"[main] 使用页面: {search_tab_id} (已存在: {is_existing})")
    
    conn = CDPConnection(ws_url)
    
    try:
        conn.send_cmd("Page.enable")
        conn.send_cmd("Runtime.enable")
        
        # 导航到搜索页面
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_explore_feed"
        print(f"[main] 导航搜索: {search_url}")
        conn.send_cmd("Page.navigate", {"url": search_url})
        
        if not wait_for_feeds(conn, timeout=25.0):
            print("[main] ❌ 搜索结果未加载")
            return {"success": False, "error": "搜索结果未加载（可能需要登录）"}
        
        image_url = get_first_image_url(conn)
        if not image_url:
            print("[main] ❌ 未找到图片 URL")
            return {"success": False, "error": "未找到图片 URL"}
        
        print(f"[main] 图片 URL: {image_url[:100]}...")
        
        # 创建下载 tab
        dl_ws_url, dl_tab_id = create_blank_tab()
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


if __name__ == "__main__":
    keyword = sys.argv[1] if len(sys.argv) > 1 else "大海"
    result = main(keyword)
    print(json.dumps(result, ensure_ascii=False, indent=2))