"""使用已登录页面获取图片 URL，然后 Network.getResponseBody 下载"""

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

# 直接使用已登录的小红书页面
SEARCH_URL = "https://www.xiaohongshu.com/search_result?keyword=大海&source=web_explore_feed"


def get_existing_xhs_page():
    """获取已有的小红书页面。"""
    url = f"http://{CDP_HOST}:{CDP_PORT}/json"
    resp = requests.get(url, timeout=5)
    data = resp.json()
    
    # 找小红书页面
    pages = [p for p in data if p.get("type") == "page" and "xiaohongshu.com" in p.get("url", "")]
    
    if pages:
        return pages[0].get("webSocketDebuggerUrl", ""), pages[0].get("id", "")
    
    # 没有小红书页面，创建新的
    new_url = f"http://{CDP_HOST}:{CDP_PORT}/json/new?{SEARCH_URL}"
    resp = requests.put(new_url, timeout=5)
    data = resp.json()
    return data.get("webSocketDebuggerUrl", ""), data.get("id", "")


class CDPConnection:
    """CDP WebSocket 连接。"""
    
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


def wait_for_feeds(conn, timeout=20.0):
    """等待 feeds 加载。"""
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


def get_image_url(conn):
    """获取图片 URL。"""
    images = conn.evaluate("""
        (() => {
            let results = [];
            
            // 从 DOM 收集 xhscdn 图片（排除头像）
            const imgs = document.querySelectorAll('img[src*="xhscdn"]');
            imgs.forEach((img) => {
                const src = img.getAttribute('src') || '';
                if (src && !src.includes('avatar') && !src.includes('icon') && !src.includes('logo')) {
                    results.push(src);
                }
            });
            
            // 从 state 提取
            if (results.length === 0) {
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
            }
            
            return results;
        })()
    """) or []
    
    if not images:
        return None
    
    url = images[0]
    
    # 转换高清格式
    if url.endswith("!nc_n_webp_prv_1") or url.endswith("!nc_n_webp_mw_1"):
        url = url.rsplit("!", 1)[0] + "!nd_dft_wlteh_webp_3"
    
    if url.startswith("http://"):
        url = "https://" + url[7:]
    
    return url


def download_with_network(conn, url, save_path, timeout=30.0):
    """使用 Network.getResponseBody 方式下载图片。
    
    核心步骤：
    1. Network.enable 启用网络监听
    2. Page.navigate 导航到图片 URL
    3. recv_event 监听 responseReceived 事件（关键：用 recv 而不是 send）
    4. Network.getResponseBody 获取响应体
    """
    print(f"\n[network] 开始下载: {url[:80]}...")
    
    # 启用 Network domain
    print("[network] 启用 Network domain...")
    conn.send_cmd("Network.enable")
    conn.send_cmd("Page.enable")
    
    # 导航到图片 URL
    print("[network] 导航到图片 URL...")
    conn.send_cmd("Page.navigate", {"url": url})
    
    # 监听 responseReceived 事件
    print("[network] 监听网络事件...")
    
    request_id = None
    deadline = time.monotonic() + timeout
    
    while time.monotonic() < deadline:
        event = conn.recv_event(timeout=1.0)
        
        if event is None:
            continue
        
        method = event.get("method", "")
        
        # 打印事件（调试）
        if "Network" in method or "Page" in method:
            params = event.get("params", {})
            
            if method == "Network.requestWillBeSent":
                print(f"[network] 请求: {params.get('request', {}).get('url', '')[:50]}...")
            
            elif method == "Network.responseReceived":
                resp = params.get("response", {})
                mime = resp.get("mimeType", "")
                resp_url = resp.get("url", "")
                print(f"[network] 响应: mime={mime}, url={resp_url[:50]}...")
                
                req_id = params.get("requestId", "")
                
                # 检查是否是图片响应
                if (
                    "image" in mime.lower() or
                    "xhscdn" in resp_url.lower() or
                    resp_url == url or
                    resp_url.startswith(url.split("!")[0])
                ):
                    request_id = req_id
                    print(f"[network] ✅ 找到图片请求: requestId={request_id}")
                    break
            
            elif method == "Page.loadEventFired":
                print("[network] 页面加载完成")
    
    if not request_id:
        print("[network] ❌ 未收到图片 responseReceived")
        return {"success": False, "error": "未收到 Network.responseReceived"}
    
    # 获取响应体
    print(f"[network] 获取响应体: requestId={request_id}")
    body_result = conn.send_cmd("Network.getResponseBody", {"requestId": request_id})
    
    if body_result.get("error"):
        return {"success": False, "error": f"getResponseBody 失败: {body_result['error']}"}
    
    body = body_result.get("body", "")
    base64_encoded = body_result.get("base64Encoded", False)
    
    print(f"[network] 响应体: base64={base64_encoded}, len={len(body)}")
    
    if not body:
        return {"success": False, "error": "响应体为空"}
    
    # 解码
    if base64_encoded:
        image_data = base64.b64decode(body)
    else:
        image_data = body.encode() if isinstance(body, str) else body
    
    # 保存
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(image_data)
    
    size = os.path.getsize(save_path)
    print(f"[network] ✅ 保存成功: {save_path} ({size} bytes)")
    
    return {"success": True, "path": save_path, "size": size, "method": "Network.getResponseBody"}


def create_download_tab():
    """创建单独的下载 tab。"""
    url = f"http://{CDP_HOST}:{CDP_PORT}/json/new?about:blank"
    resp = requests.put(url, timeout=5)
    data = resp.json()
    return data.get("webSocketDebuggerUrl", ""), data.get("id", "")


def close_tab(tab_id):
    try:
        requests.get(f"http://{CDP_HOST}:{CDP_PORT}/json/close/{tab_id}", timeout=5)
    except:
        pass


def main():
    print("="*60)
    print("测试 Network.getResponseBody 方式下载小红书图片")
    print("="*60)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 获取已登录的小红书页面
    ws_url, page_id = get_existing_xhs_page()
    print(f"[main] 连接页面: {page_id}")
    
    conn = CDPConnection(ws_url)
    
    try:
        # 确保在搜索页面
        current_url = conn.evaluate("window.location.href") or ""
        print(f"[main] 当前 URL: {current_url[:50]}...")
        
        if "search_result" not in current_url or "大海" not in current_url:
            print("[main] 导航到搜索页...")
            conn.send_cmd("Page.navigate", {"url": SEARCH_URL})
            time.sleep(3.0)
            
            if not wait_for_feeds(conn, timeout=20.0):
                print("[main] ❌ 搜索结果未加载")
                return {"success": False, "error": "搜索结果未加载（可能未登录）"}
        
        # 获取图片 URL
        print("[main] 获取图片 URL...")
        image_url = get_image_url(conn)
        
        if not image_url:
            print("[main] ❌ 未找到图片 URL")
            return {"success": False, "error": "未找到图片 URL"}
        
        print(f"[main] 图片 URL: {image_url[:100]}...")
        
        # 创建单独的下载 tab
        dl_ws_url, dl_tab_id = create_download_tab()
        print(f"[main] 创建下载 tab: {dl_tab_id}")
        
        dl_conn = CDPConnection(dl_ws_url)
        
        try:
            # 用 Network 方式下载
            timestamp = int(time.time())
            save_path = str(OUTPUT_DIR / f"network_{timestamp}.jpg")
            
            result = download_with_network(dl_conn, image_url, save_path)
            
            if result.get("success"):
                print("\n" + "="*60)
                print("✅ 测试成功!")
                print(f"图片路径: {save_path}")
                print(f"文件大小: {result['size']} bytes")
                print(f"下载方式: {result['method']}")
                print("="*60)
                
                return {
                    "success": True,
                    "image_path": save_path,
                    "file_size": result["size"],
                    "download_method": result["method"],
                    "image_url": image_url,
                }
            else:
                print("\n❌ 测试失败: " + result.get("error", ""))
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
    result = main()
    print(json.dumps(result, ensure_ascii=False, indent=2))