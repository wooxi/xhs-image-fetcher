"""测试 CDP Network.getResponseBody 方式下载图片。

直接使用当前浏览器页面获取图片 URL，然后用 Network 方式下载。
"""

import json
import base64
import time
import os
from pathlib import Path

import requests

try:
    import websockets.sync.client as ws_client
except ImportError:
    from websockets.sync import client as ws_client

OUTPUT_DIR = Path("/tmp/xhs_images_test")
CDP_HOST = "127.0.0.1"
CDP_PORT = 9222


def get_current_page_ws_url() -> str:
    """获取当前页面 WebSocket URL。"""
    url = f"http://{CDP_HOST}:{CDP_PORT}/json"
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    pages = [p for p in data if p.get("type") == "page"]
    if not pages:
        raise Exception("没有找到浏览器页面")
    return pages[0].get("webSocketDebuggerUrl", "")


def get_image_urls_from_page(ws) -> list:
    """从当前页面获取图片 URL。"""
    # 发送 Runtime.evaluate 命令
    msg_id = 1
    ws.send(json.dumps({
        "id": msg_id,
        "method": "Runtime.evaluate",
        "params": {
            "expression": """
                (() => {
                    let results = [];
                    
                    // 从 DOM 收集 sns-webpic 图片
                    const hdImgs = document.querySelectorAll('img[src*="sns-webpic"]');
                    hdImgs.forEach((img, idx) => {
                        const url = img.getAttribute('src') || '';
                        if (url && url.includes('sns-webpic') && !url.includes('avatar')) {
                            results.push({index: idx, url: url, type: 'dom_image'});
                        }
                    });
                    
                    // 如果没找到，从 __INITIAL_STATE__ 提取
                    if (results.length === 0) {
                        const state = window.__INITIAL_STATE__;
                        if (state?.search?.feeds) {
                            const feeds = state.search.feeds.value || state.search.feeds._value || [];
                            feeds.forEach((feed, idx) => {
                                const cover = feed.noteCard?.cover || {};
                                const url = cover.urlDefault || cover.url || '';
                                if (url) {
                                    results.push({index: idx, url: url, type: 'state_data'});
                                }
                            });
                        }
                    }
                    
                    return results;
                })()
            """,
            "returnByValue": True,
        }
    }))
    
    # 等待响应
    while True:
        raw = ws.recv(timeout=10.0)
        data = json.loads(raw)
        if data.get("id") == msg_id:
            if "error" in data:
                raise Exception(f"JS 执行错误: {data['error']}")
            return data.get("result", {}).get("result", {}).get("value", [])


def download_with_network_response_body(ws, url: str, save_path: str, timeout: float = 30.0) -> dict:
    """使用 Network.getResponseBody 方式下载图片。
    
    流程：
    1. 在当前页面启用 Network domain
    2. 导航到图片 URL（新建一个 tab 来下载）
    3. 监听 responseReceived 事件
    4. 用 Network.getResponseBody 获取响应体
    
    Args:
        ws: WebSocket 连接
        url: 图片 URL
        save_path: 本地保存路径
        timeout: 超时时间
    """
    print(f"\n[network_dl] 开始下载: {url[:80]}...")
    
    # 转换为 HTTPS
    if url.startswith("http://"):
        url = "https://" + url[7:]
    
    # 转换为高清 URL
    if url.endswith("!nc_n_webp_prv_1") or url.endswith("!nc_n_webp_mw_1"):
        url = url.rsplit("!", 1)[0] + "!nd_dft_wlteh_webp_3"
    
    msg_id_counter = [0]  # 使用列表以便在闭包中修改
    
    def send_cmd(method: str, params: dict = None) -> dict:
        """发送命令并等待响应。"""
        msg_id_counter[0] += 1
        msg_id = msg_id_counter[0]
        msg = {"id": msg_id, "method": method}
        if params:
            msg["params"] = params
        
        ws.send(json.dumps(msg))
        
        # 等待响应
        while True:
            raw = ws.recv(timeout=30.0)
            data = json.loads(raw)
            if data.get("id") == msg_id:
                if "error" in data:
                    return {"error": data["error"]}
                return data.get("result", {})
    
    # 创建新 tab 用于下载图片
    print("[network_dl] 创建新 tab...")
    new_tab_url = f"http://{CDP_HOST}:{CDP_PORT}/json/new?about:blank"
    resp = requests.put(new_tab_url, timeout=5)
    new_tab_data = resp.json()
    new_tab_ws_url = new_tab_data.get("webSocketDebuggerUrl", "")
    
    if not new_tab_ws_url:
        return {"success": False, "error": "无法创建新 tab"}
    
    print(f"[network_dl] 连接新 tab: {new_tab_ws_url}")
    new_ws = ws_client.connect(new_tab_ws_url)
    
    try:
        # 在新 tab 中启用 Network domain
        print("[network_dl] 启用 Network domain...")
        
        new_msg_id = [0]
        
        def new_send(method: str, params: dict = None) -> dict:
            new_msg_id[0] += 1
            msg_id = new_msg_id[0]
            msg = {"id": msg_id, "method": method}
            if params:
                msg["params"] = params
            new_ws.send(json.dumps(msg))
            while True:
                raw = new_ws.recv(timeout=30.0)
                data = json.loads(raw)
                if data.get("id") == msg_id:
                    if "error" in data:
                        return {"error": data["error"]}
                    return data.get("result", {})
        
        # 启用 Network
        new_send("Network.enable")
        new_send("Page.enable")
        
        # 导航到图片 URL
        print("[network_dl] 导航到图片 URL...")
        new_send("Page.navigate", {"url": url})
        
        # 监听 responseReceived 事件
        print("[network_dl] 监听网络事件...")
        
        request_id = None
        deadline = time.monotonic() + timeout
        
        while time.monotonic() < deadline:
            try:
                raw = new_ws.recv(timeout=1.0)
            except TimeoutError:
                continue
            
            data = json.loads(raw)
            method = data.get("method", "")
            
            print(f"[network_dl] 事件: {method}")
            
            if method == "Network.responseReceived":
                params = data.get("params", {})
                resp_info = params.get("response", {})
                req_id = params.get("requestId", "")
                mime_type = resp_info.get("mimeType", "")
                resp_url = resp_info.get("url", "")
                
                print(f"[network_dl] 响应: mimeType={mime_type}, url={resp_url[:60]}...")
                
                # 检查是否是图片
                if (
                    "image" in mime_type.lower() or
                    "xhscdn" in resp_url.lower() or
                    resp_url == url or
                    resp_url.startswith(url.split("!")[0])
                ):
                    request_id = req_id
                    print(f"[network_dl] 找到图片请求: requestId={request_id}")
                    break
        
        if not request_id:
            print("[network_dl] 未收到图片 responseReceived")
            return {
                "success": False,
                "error": "未收到 Network.responseReceived 事件",
                "url": url,
            }
        
        # 获取响应体
        print(f"[network_dl] 获取响应体...")
        body_result = new_send("Network.getResponseBody", {"requestId": request_id})
        
        if body_result.get("error"):
            return {
                "success": False,
                "error": f"Network.getResponseBody 失败: {body_result['error']}",
                "url": url,
            }
        
        body = body_result.get("body", "")
        base64_encoded = body_result.get("base64Encoded", False)
        
        print(f"[network_dl] 响应体: base64Encoded={base64_encoded}, length={len(body)}")
        
        if not body:
            return {
                "success": False,
                "error": "响应体为空",
                "url": url,
            }
        
        # 解码响应体
        if base64_encoded:
            image_data = base64.b64decode(body)
        else:
            image_data = body.encode() if isinstance(body, str) else body
        
        # 保存文件
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(image_data)
        
        file_size = os.path.getsize(save_path)
        print(f"[network_dl] 保存成功: {save_path} ({file_size} bytes)")
        
        return {
            "success": True,
            "path": save_path,
            "size": file_size,
            "url": url,
            "method": "Network.getResponseBody",
        }
        
    finally:
        new_ws.close()
        # 关闭新 tab
        try:
            tab_id = new_tab_data.get("id")
            requests.get(f"http://{CDP_HOST}:{CDP_PORT}/json/close/{tab_id}", timeout=5)
        except Exception:
            pass


def test_network_download():
    """测试 Network.getResponseBody 方式下载图片。"""
    print("\n" + "="*60)
    print("[test] 开始测试 Network.getResponseBody 方式下载")
    print("="*60 + "\n")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 连接当前浏览器页面
    ws_url = get_current_page_ws_url()
    print(f"[test] 连接到: {ws_url}")
    
    ws = ws_client.connect(ws_url)
    
    try:
        # 获取图片 URL
        print("[test] 获取图片 URL...")
        images = get_image_urls_from_page(ws)
        
        if not images:
            print("[test] 未找到图片 URL")
            return {"success": False, "error": "未找到图片 URL"}
        
        print(f"[test] 找到 {len(images)} 张图片")
        
        # 使用第一张图片
        first_url = images[0].get("url")
        print(f"[test] 第一张图片: {first_url[:100]}...")
        
        # 生成保存路径
        timestamp = int(time.time())
        save_path = str(OUTPUT_DIR / f"network_test_{timestamp}.jpg")
        
        # 下载图片
        result = download_with_network_response_body(ws, first_url, save_path)
        
        if result.get("success"):
            print("\n" + "="*60)
            print("[test] ✅ 测试成功!")
            print(f"[test] 图片保存路径: {save_path}")
            print(f"[test] 文件大小: {result.get('size')} bytes")
            print(f"[test] 下载方式: {result.get('method')}")
            print("="*60)
            
            return {
                "success": True,
                "image_path": save_path,
                "file_size": result.get("size"),
                "download_method": result.get("method"),
                "image_url": first_url,
            }
        else:
            print("\n[test] ❌ 测试失败")
            print(f"[test] 错误: {result.get('error')}")
            return result
            
    except Exception as e:
        print(f"\n[test] ❌ 异常: {e}")
        return {"success": False, "error": str(e)}
        
    finally:
        ws.close()


if __name__ == "__main__":
    result = test_network_download()
    print(json.dumps(result, ensure_ascii=False, indent=2))