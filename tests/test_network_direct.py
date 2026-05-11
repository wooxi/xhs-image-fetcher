"""直接测试 Network.getResponseBody 方式下载小红书图片。

使用已知图片 URL，不依赖搜索功能。
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

# 已知的小红书图片 URL（从之前的详情获取）
IMAGE_URL = "https://sns-webpic-qc.xhscdn.com/202604200031/ed0a2b4e59e550ec948130a60661821c/1040g00831givc1cujo0g49n0obchdq6mk73hk2g!nd_dft_wlteh_webp_3"


def create_new_tab():
    """创建新空白 tab。"""
    url = f"http://{CDP_HOST}:{CDP_PORT}/json/new?about:blank"
    resp = requests.put(url, timeout=5)
    data = resp.json()
    return data.get("webSocketDebuggerUrl", ""), data.get("id", "")


def close_tab(tab_id):
    try:
        requests.get(f"http://{CDP_HOST}:{CDP_PORT}/json/close/{tab_id}", timeout=5)
    except:
        pass


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
                    print(f"[cdp] 错误: {data['error']}")
                    return {"error": data["error"]}
                return data.get("result", {})
    
    def recv_event(self, timeout=1.0):
        """接收事件（关键：用 recv 监听事件，不等待特定 ID）。"""
        try:
            raw = self.ws.recv(timeout=timeout)
            return json.loads(raw)
        except TimeoutError:
            return None


def download_with_network(conn, url, save_path, timeout=30.0):
    """使用 Network.getResponseBody 方式下载图片。
    
    核心：
    1. Network.enable - 启用网络监听
    2. Page.navigate - 导航到图片 URL
    3. recv_event 监听 responseReceived（关键：用 recv 而非 send）
    4. Network.getResponseBody - 获取响应体
    """
    print(f"\n[network] 测试下载: {url[:80]}...")
    
    # 1. 启用 Network domain
    print("[network] 步骤1: Network.enable")
    conn.send_cmd("Network.enable")
    conn.send_cmd("Page.enable")
    
    # 2. 导航到图片 URL
    print("[network] 步骤2: Page.navigate")
    conn.send_cmd("Page.navigate", {"url": url})
    
    # 3. 监听 responseReceived 事件（关键：用 recv_event 监听）
    print("[network] 步骤3: 监听 Network.responseReceived 事件")
    
    request_id = None
    all_events = []
    deadline = time.monotonic() + timeout
    
    while time.monotonic() < deadline:
        event = conn.recv_event(timeout=1.0)
        
        if event is None:
            continue
        
        method = event.get("method", "")
        all_events.append(method)
        
        # 打印关键事件
        if "Network" in method or "Page" in method:
            params = event.get("params", {})
            
            if method == "Network.requestWillBeSent":
                req_url = params.get("request", {}).get("url", "")
                print(f"[network] 事件 requestWillBeSent: {req_url[:60]}...")
            
            elif method == "Network.responseReceived":
                resp = params.get("response", {})
                mime = resp.get("mimeType", "")
                resp_url = resp.get("url", "")
                req_id = params.get("requestId", "")
                
                print(f"[network] 事件 responseReceived: mime={mime}, url={resp_url[:60]}...")
                
                # 检查是否是目标图片
                if (
                    "image" in mime.lower() or
                    "xhscdn" in resp_url.lower() or
                    resp_url == url or
                    resp_url.startswith(url.split("!")[0])
                ):
                    request_id = req_id
                    print(f"[network] ✅ 找到目标图片 requestId: {request_id}")
                    break
            
            elif method == "Network.loadingFinished":
                print(f"[network] 事件 loadingFinished: requestId={params.get('requestId')}")
            
            elif method == "Page.loadEventFired":
                print("[network] 事件 loadEventFired")
    
    print(f"[network] 收到事件: {all_events}")
    
    if not request_id:
        print("[network] ❌ 未找到图片 responseReceived")
        return {"success": False, "error": "未收到 Network.responseReceived", "events": all_events}
    
    # 4. 获取响应体
    print(f"[network] 步骤4: Network.getResponseBody(requestId={request_id})")
    body_result = conn.send_cmd("Network.getResponseBody", {"requestId": request_id})
    
    if body_result.get("error"):
        return {"success": False, "error": f"getResponseBody 失败: {body_result['error']}"}
    
    body = body_result.get("body", "")
    base64_encoded = body_result.get("base64Encoded", False)
    
    print(f"[network] 响应体结果: base64Encoded={base64_encoded}, body_length={len(body)}")
    
    if not body:
        return {"success": False, "error": "响应体为空"}
    
    # 解码响应体
    if base64_encoded:
        image_data = base64.b64decode(body)
        print(f"[network] Base64 解码后大小: {len(image_data)} bytes")
    else:
        image_data = body.encode() if isinstance(body, str) else body
    
    # 保存文件
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(image_data)
    
    file_size = os.path.getsize(save_path)
    print(f"[network] ✅ 文件已保存: {save_path} ({file_size} bytes)")
    
    return {
        "success": True,
        "path": save_path,
        "size": file_size,
        "url": url,
        "method": "Network.getResponseBody",
        "base64_encoded": base64_encoded,
    }


def main():
    """测试 Network.getResponseBody 方式下载。"""
    print("="*60)
    print("测试 CDP Network.getResponseBody 方式下载小红书图片")
    print("="*60)
    print(f"\n测试 URL: {IMAGE_URL}")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 创建新 tab 用于下载
    ws_url, tab_id = create_new_tab()
    print(f"\n[main] 创建新 tab: {tab_id}")
    
    conn = CDPConnection(ws_url)
    
    try:
        timestamp = int(time.time())
        save_path = str(OUTPUT_DIR / f"network_test_{timestamp}.jpg")
        
        result = download_with_network(conn, IMAGE_URL, save_path)
        
        if result.get("success"):
            print("\n" + "="*60)
            print("✅ 测试成功!")
            print(f"图片路径: {save_path}")
            print(f"文件大小: {result['size']} bytes")
            print(f"下载方式: Network.getResponseBody")
            print("="*60)
            
            return {
                "success": True,
                "image_path": save_path,
                "file_size": result["size"],
                "download_method": "Network.getResponseBody",
                "image_url": IMAGE_URL,
            }
        else:
            print("\n" + "="*60)
            print("❌ 测试失败")
            print(f"错误: {result.get('error', '')}")
            print("="*60)
            return result
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
    
    finally:
        conn.close()
        close_tab(tab_id)
        print(f"\n[main] 已关闭 tab: {tab_id}")


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, ensure_ascii=False, indent=2))