"""改进版：监听 loadingFinished 事件获取图片响应体。

问题分析：
- 图片请求会触发 loadingFinished，但可能不触发 responseReceived
- favicon.ico 的 responseReceived 错误匹配了

改进：
- 同时监听 loadingFinished 和 responseReceived
- 匯集所有 requestId，尝试用 loadingFinished 的 requestId 获取响应体
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

IMAGE_URL = "https://sns-webpic-qc.xhscdn.com/202604200031/ed0a2b4e59e550ec948130a60661821c/1040g00831givc1cujo0g49n0obchdq6mk73hk2g!nd_dft_wlteh_webp_3"


def create_new_tab():
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


def download_with_network(conn, url, save_path, timeout=30.0):
    """使用 Network.getResponseBody 方式下载图片。
    
    改进版：
    - 同时监听 loadingFinished 和 responseReceived
    - 收集所有可能的 requestId
    - 尝试多个 requestId 获取响应体
    """
    print(f"\n[network] 测试下载: {url[:80]}...")
    
    # 启用 Network
    print("[network] 步骤1: Network.enable")
    conn.send_cmd("Network.enable")
    conn.send_cmd("Page.enable")
    
    # 导航
    print("[network] 步骤2: Page.navigate")
    conn.send_cmd("Page.navigate", {"url": url})
    
    # 监听事件
    print("[network] 步骤3: 监听事件...")
    
    # 收集 requestId
    request_ids = []  # loadingFinished 的 requestId
    response_ids = []  # responseReceived 的 requestId
    request_urls = {}  # requestId -> url 映射
    
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
        
        # requestWillBeSent: 记录 requestId -> url
        if method == "Network.requestWillBeSent":
            req_id = params.get("requestId", "")
            req_url = params.get("request", {}).get("url", "")
            request_urls[req_id] = req_url
            print(f"[network] requestWillBeSent: {req_id[:10]} -> {req_url[:50]}...")
        
        # responseReceived: 记录响应 requestId
        elif method == "Network.responseReceived":
            req_id = params.get("requestId", "")
            resp = params.get("response", {})
            resp_url = resp.get("url", "")
            mime = resp.get("mimeType", "")
            request_urls[req_id] = resp_url
            
            # 检查是否是图片（排除 favicon）
            if "image" in mime.lower() and "favicon" not in resp_url.lower():
                response_ids.append(req_id)
                print(f"[network] responseReceived (image): {req_id[:10]} -> {resp_url[:50]}...")
            else:
                print(f"[network] responseReceived: {req_id[:10]} mime={mime}")
        
        # loadingFinished: 这是关键！图片请求完成后触发
        elif method == "Network.loadingFinished":
            req_id = params.get("requestId", "")
            request_ids.append(req_id)
            req_url = request_urls.get(req_id, "")
            print(f"[network] loadingFinished: {req_id[:10]} -> {req_url[:50]}...")
        
        # 页面加载完成
        elif method == "Page.loadEventFired":
            page_loaded = True
            print("[network] loadEventFired")
    
    print(f"\n[network] 收集到:")
    print(f"  loadingFinished requestId: {request_ids}")
    print(f"  responseReceived requestId: {response_ids}")
    print(f"  URL 映射: {list(request_urls.items())}")
    
    # 找到目标图片的 requestId
    target_url_base = url.split("!")[0]
    
    # 方法1: 从 loadingFinished 找
    image_request_id = None
    for req_id in request_ids:
        req_url = request_urls.get(req_id, "")
        if req_url == url or req_url.startswith(target_url_base):
            image_request_id = req_id
            print(f"[network] ✅ 从 loadingFinished 找到: {req_id}")
            break
    
    # 方法2: 从 responseReceived 找
    if not image_request_id:
        for req_id in response_ids:
            req_url = request_urls.get(req_id, "")
            if req_url == url or req_url.startswith(target_url_base):
                image_request_id = req_id
                print(f"[network] ✅ 从 responseReceived 找到: {req_id}")
                break
    
    # 方法3: 尝试第一个 loadingFinished requestId（排除 favicon）
    if not image_request_id and request_ids:
        # 尝试第一个不是 favicon 的
        for req_id in request_ids:
            req_url = request_urls.get(req_id, "")
            if "favicon" not in req_url.lower():
                image_request_id = req_id
                print(f"[network] 尝试第一个非 favicon: {req_id}")
                break
    
    if not image_request_id:
        print("[network] ❌ 未找到图片 requestId")
        return {"success": False, "error": "未找到图片 requestId", "request_ids": request_ids}
    
    # 步骤4: 获取响应体
    print(f"\n[network] 步骤4: Network.getResponseBody(requestId={image_request_id})")
    body_result = conn.send_cmd("Network.getResponseBody", {"requestId": image_request_id})
    
    if body_result.get("error"):
        print(f"[network] getResponseBody 错误: {body_result['error']}")
        return {"success": False, "error": f"getResponseBody 失败: {body_result['error']}"}
    
    body = body_result.get("body", "")
    base64_encoded = body_result.get("base64Encoded", False)
    
    print(f"[network] 响应体: base64={base64_encoded}, len={len(body)}")
    
    if not body:
        # 尝试其他 requestId
        print("[network] 响应体为空，尝试其他 requestId...")
        for req_id in request_ids:
            if req_id != image_request_id:
                print(f"[network] 尝试: {req_id}")
                body_result = conn.send_cmd("Network.getResponseBody", {"requestId": req_id})
                if not body_result.get("error"):
                    body = body_result.get("body", "")
                    if body:
                        base64_encoded = body_result.get("base64Encoded", False)
                        print(f"[network] ✅ 找到数据: requestId={req_id}")
                        break
    
    if not body:
        return {"success": False, "error": "所有 requestId 响应体都为空"}
    
    # 解码保存
    if base64_encoded:
        image_data = base64.b64decode(body)
    else:
        image_data = body.encode() if isinstance(body, str) else body
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(image_data)
    
    file_size = os.path.getsize(save_path)
    print(f"[network] ✅ 保存成功: {save_path} ({file_size} bytes)")
    
    return {
        "success": True,
        "path": save_path,
        "size": file_size,
        "url": url,
        "method": "Network.getResponseBody",
        "request_id": image_request_id,
    }


def main():
    print("="*60)
    print("测试 Network.getResponseBody 方式下载小红书图片")
    print("="*60)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    ws_url, tab_id = create_new_tab()
    print(f"[main] 创建 tab: {tab_id}")
    
    conn = CDPConnection(ws_url)
    
    try:
        timestamp = int(time.time())
        save_path = str(OUTPUT_DIR / f"network_v2_{timestamp}.jpg")
        
        result = download_with_network(conn, IMAGE_URL, save_path)
        
        if result.get("success"):
            print("\n" + "="*60)
            print("✅ 测试成功!")
            print(f"图片路径: {save_path}")
            print(f"文件大小: {result['size']} bytes")
            print("="*60)
            
            return {
                "success": True,
                "image_path": save_path,
                "file_size": result["size"],
                "download_method": "Network.getResponseBody",
                "request_id": result.get("request_id"),
            }
        else:
            print("\n" + "="*60)
            print("❌ 测试失败: " + result.get("error", ""))
            print("="*60)
            return result
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
    
    finally:
        conn.close()
        close_tab(tab_id)


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, ensure_ascii=False, indent=2))