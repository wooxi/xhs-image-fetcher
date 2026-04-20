"""完整测试：导航搜索页 -> 获取图片 URL -> Network.getResponseBody 下载"""

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


def create_new_tab():
    """创建新空白 tab，返回 WebSocket URL 和 tab ID。"""
    url = f"http://{CDP_HOST}:{CDP_PORT}/json/new?about:blank"
    resp = requests.put(url, timeout=5)
    data = resp.json()
    return data.get("webSocketDebuggerUrl", ""), data.get("id", "")


def close_tab(tab_id):
    """关闭 tab。"""
    try:
        requests.get(f"http://{CDP_HOST}:{CDP_PORT}/json/close/{tab_id}", timeout=5)
    except Exception:
        pass


class CDPConnection:
    """CDP WebSocket 连接封装。"""
    
    def __init__(self, ws_url):
        self.ws = ws_client.connect(ws_url)
        self.msg_id = 0
    
    def close(self):
        if self.ws:
            self.ws.close()
    
    def send(self, method, params=None):
        """发送命令并等待响应。"""
        self.msg_id += 1
        msg = {"id": self.msg_id, "method": method}
        if params:
            msg["params"] = params
        
        self.ws.send(json.dumps(msg))
        
        while True:
            raw = self.ws.recv(timeout=60.0)
            data = json.loads(raw)
            if data.get("id") == self.msg_id:
                if "error" in data:
                    raise Exception(f"CDP error: {data['error']}")
                return data.get("result", {})
    
    def recv_event(self, timeout=1.0):
        """接收事件（不等待特定 ID）。"""
        try:
            raw = self.ws.recv(timeout=timeout)
            return json.loads(raw)
        except TimeoutError:
            return None
    
    def evaluate(self, expression):
        """执行 JavaScript。"""
        result = self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        return result.get("result", {}).get("result", {}).get("value")


def wait_for_search_feeds(conn, timeout=30.0):
    """等待搜索结果 feeds 加载。"""
    deadline = time.monotonic() + timeout
    
    while time.monotonic() < deadline:
        try:
            count = conn.evaluate("""
                (() => {
                    const state = window.__INITIAL_STATE__;
                    if (!state?.search?.feeds) return 0;
                    const feeds = state.search.feeds.value || state.search.feeds._value || [];
                    return feeds.length;
                })()
            """)
            
            if count > 0:
                print(f"[wait] feeds 数量: {count}")
                return True
        except Exception:
            pass
        
        time.sleep(0.5)
    
    print("[wait] 等待 feeds 超时")
    return False


def get_first_image_url(conn):
    """获取第一张图片 URL（高清格式）。"""
    images = conn.evaluate("""
        (() => {
            let results = [];
            
            // 从 DOM 收集 sns-webpic 图片（排除头像）
            const imgs = document.querySelectorAll('img[src*="xhscdn"]');
            imgs.forEach((img) => {
                const src = img.getAttribute('src') || '';
                // 排除头像和图标
                if (src && !src.includes('avatar') && !src.includes('icon') && !src.includes('logo')) {
                    results.push(src);
                }
            });
            
            // 如果 DOM 没找到，从 state 提取
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
    """)
    
    if not images or len(images) == 0:
        return None
    
    # 转换为高清 URL
    url = images[0]
    if url.endswith("!nc_n_webp_prv_1") or url.endswith("!nc_n_webp_mw_1"):
        url = url.rsplit("!", 1)[0] + "!nd_dft_wlteh_webp_3"
    
    # 转换为 HTTPS
    if url.startswith("http://"):
        url = "https://" + url[7:]
    
    return url


def download_with_network(conn, url, save_path, timeout=30.0):
    """使用 Network.getResponseBody 方式下载图片。
    
    关键步骤：
    1. 启用 Network domain
    2. 导航到图片 URL
    3. 监听 responseReceived 事件
    4. 用 Network.getResponseBody 获取响应体
    
    注意：这里使用 recv_event 来监听事件，而不是 send 等待响应。
    """
    print(f"\n[network] 下载: {url[:80]}...")
    
    # 启用 Network domain
    print("[network] 启用 Network domain...")
    conn.send("Network.enable")
    conn.send("Page.enable")
    
    # 导航到图片 URL
    print("[network] 导航到图片 URL...")
    conn.send("Page.navigate", {"url": url})
    
    # 监听 responseReceived 事件（用 recv_event，不用 send）
    print("[network] 监听网络事件...")
    
    request_id = None
    deadline = time.monotonic() + timeout
    
    while time.monotonic() < deadline:
        event = conn.recv_event(timeout=1.0)
        
        if event is None:
            continue
        
        method = event.get("method", "")
        
        # 打印所有事件（调试）
        if method.startswith("Network.") or method.startswith("Page."):
            print(f"[network] 事件: {method}")
        
        if method == "Network.responseReceived":
            params = event.get("params", {})
            resp = params.get("response", {})
            req_id = params.get("requestId", "")
            mime_type = resp.get("mimeType", "")
            resp_url = resp.get("url", "")
            
            print(f"[network] 响应: mime={mime_type}, url={resp_url[:60]}...")
            
            # 检查是否是图片
            if (
                "image" in mime_type.lower() or
                "xhscdn" in resp_url.lower() or
                resp_url == url or
                resp_url.startswith(url.split("!")[0])
            ):
                request_id = req_id
                print(f"[network] ✅ 找到图片请求: requestId={request_id}")
                break
        
        # 页面加载完成也可以作为检查点
        if method == "Page.loadEventFired":
            print("[network] 页面加载完成")
    
    if not request_id:
        print("[network] ❌ 未收到图片 responseReceived")
        return {"success": False, "error": "未收到 Network.responseReceived 事件"}
    
    # 获取响应体
    print(f"[network] 获取响应体: requestId={request_id}")
    body_result = conn.send("Network.getResponseBody", {"requestId": request_id})
    
    body = body_result.get("body", "")
    base64_encoded = body_result.get("base64Encoded", False)
    
    print(f"[network] 响应体: base64={base64_encoded}, length={len(body)}")
    
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
    
    file_size = os.path.getsize(save_path)
    print(f"[network] ✅ 保存成功: {save_path} ({file_size} bytes)")
    
    return {
        "success": True,
        "path": save_path,
        "size": file_size,
        "method": "Network.getResponseBody",
    }


def main():
    """完整测试流程。"""
    print("="*60)
    print("测试 CDP Network.getResponseBody 方式下载图片")
    print("="*60)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 创建新 tab 用于搜索
    ws_url, tab_id = create_new_tab()
    print(f"[main] 创建新 tab: {tab_id}")
    
    conn = CDPConnection(ws_url)
    
    try:
        # 启用基础 domains
        conn.send("Page.enable")
        conn.send("Runtime.enable")
        
        # 导航到搜索页面
        search_url = "https://www.xiaohongshu.com/search_result?keyword=大海&source=web_explore_feed"
        print(f"[main] 导航搜索页: {search_url}")
        conn.send("Page.navigate", {"url": search_url})
        
        # 等待页面加载
        time.sleep(3.0)
        
        # 等待搜索结果
        if not wait_for_search_feeds(conn, timeout=20.0):
            print("[main] ❌ 搜索结果未加载")
            return {"success": False, "error": "搜索结果未加载"}
        
        # 获取图片 URL
        print("[main] 获取图片 URL...")
        image_url = get_first_image_url(conn)
        
        if not image_url:
            print("[main] ❌ 未找到图片 URL")
            return {"success": False, "error": "未找到图片 URL"}
        
        print(f"[main] 图片 URL: {image_url[:100]}...")
        
        # 创建另一个新 tab 用于下载图片
        dl_ws_url, dl_tab_id = create_new_tab()
        print(f"[main] 创建下载 tab: {dl_tab_id}")
        
        dl_conn = CDPConnection(dl_ws_url)
        
        try:
            # 使用 Network 方式下载
            timestamp = int(time.time())
            save_path = str(OUTPUT_DIR / f"network_dl_{timestamp}.jpg")
            
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
                print("\n❌ 测试失败")
                print(f"错误: {result.get('error')}")
                return result
                
        finally:
            dl_conn.close()
            close_tab(dl_tab_id)
            
    except Exception as e:
        print(f"\n❌ 异常: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
        
    finally:
        conn.close()
        close_tab(tab_id)


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, ensure_ascii=False, indent=2))