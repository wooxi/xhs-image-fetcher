"""测试 CDP Network.getResponseBody 方式下载图片。

关键：
1. 启用 Network domain 监听
2. 导航到图片 URL
3. 监听 WebSocket 的 responseReceived 事件（用 recv，不用 _send 等待）
4. 用 Network.getResponseBody(requestId) 获取响应体
"""

import json
import base64
import time
import sys
from pathlib import Path

import requests
import websockets.sync.client as ws_client

sys.path.insert(0, "/root/.openclaw/skills/xhs-search/scripts")
from xhs_search_cdp import (
    XHSCDPClient,
    CDPError,
    make_search_url,
    convert_to_hd_url,
)

OUTPUT_DIR = Path("/tmp/xhs_images_test")


class NetworkImageDownloader:
    """使用 CDP Network.getResponseBody 方式下载图片。"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 9222):
        self.host = host
        self.port = port
        self.ws = None
        self._msg_id = 0
        self.target_id = None
    
    def connect(self):
        """连接到浏览器新 tab。"""
        # 创建新空白 tab
        url = f"http://{self.host}:{self.port}/json/new?about:blank"
        resp = requests.put(url, timeout=5)
        if not resp.ok:
            raise CDPError("无法创建新 tab")
        
        data = resp.json()
        self.target_id = data.get("id")
        ws_url = data.get("webSocketDebuggerUrl", "")
        
        if not ws_url:
            raise CDPError("无法获取 WebSocket URL")
        
        print(f"[network_dl] 连接到: {ws_url}")
        self.ws = ws_client.connect(ws_url)
        print("[network_dl] 已连接")
        
        # 启用 Network domain
        self._send_sync("Network.enable")
        self._send_sync("Page.enable")
        print("[network_dl] Network domain 已启用")
    
    def disconnect(self):
        """断开连接。"""
        if self.ws:
            self.ws.close()
            self.ws = None
    
    def _send_sync(self, method: str, params: dict = None) -> dict:
        """发送 CDP 命令并等待响应（同步方式）。"""
        self._msg_id += 1
        msg_id = self._msg_id
        msg = {"id": msg_id, "method": method}
        if params:
            msg["params"] = params
        
        self.ws.send(json.dumps(msg))
        
        # 等待对应 ID 的响应
        while True:
            raw = self.ws.recv(timeout=10.0)
            data = json.loads(raw)
            if data.get("id") == msg_id:
                if "error" in data:
                    raise CDPError(f"CDP 错误: {data['error']}")
                return data.get("result", {})
    
    def download_image(self, url: str, save_path: str, timeout: float = 30.0) -> dict:
        """下载图片（使用 Network.getResponseBody 方式）。
        
        流程：
        1. 导航到图片 URL
        2. 监听 WebSocket responseReceived 事件
        3. 找到图片请求的 requestId
        4. 用 Network.getResponseBody 获取响应体
        
        Args:
            url: 图片 URL
            save_path: 本地保存路径
            timeout: 超时时间
            
        Returns:
            {"success": bool, "path": str, "error": str}
        """
        print(f"\n[network_dl] 下载图片: {url[:80]}...")
        
        # 确保 URL 使用 HTTPS
        if url.startswith("http://"):
            url = "https://" + url[7:]
        
        request_id = None
        response_received = False
        deadline = time.monotonic() + timeout
        
        try:
            # 导航到图片 URL
            print("[network_dl] 导航到图片 URL...")
            self._send_sync("Page.navigate", {"url": url})
            
            # 监听 WebSocket 事件（用 recv，不等待 _send）
            print("[network_dl] 监听网络事件...")
            
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                
                try:
                    raw = self.ws.recv(timeout=min(1.0, remaining))
                except TimeoutError:
                    # 超时但还没收到 responseReceived，继续等待
                    continue
                
                data = json.loads(raw)
                method = data.get("method", "")
                
                # 监听 responseReceived 事件
                if method == "Network.responseReceived":
                    params = data.get("params", {})
                    resp = params.get("response", {})
                    req_id = params.get("requestId", "")
                    mime_type = resp.get("mimeType", "")
                    resp_url = resp.get("url", "")
                    
                    print(f"[network_dl] 收到 response: mimeType={mime_type}, url={resp_url[:60]}...")
                    
                    # 检查是否是图片响应
                    if (
                        "image" in mime_type.lower() or
                        "xhscdn" in resp_url.lower() or
                        resp_url == url or
                        resp_url.startswith(url.split("!")[0])
                    ):
                        request_id = req_id
                        response_received = True
                        print(f"[network_dl] 找到图片请求: requestId={request_id}")
                        break
                
                # 处理加载完成事件
                elif method == "Page.loadEventFired":
                    print("[network_dl] 页面加载完成")
            
            if not response_received or not request_id:
                # 尭试另一种方式：直接在当前页面用 JS 获取图片
                print("[network_dl] 未收到 responseReceived 事件，尝试直接获取...")
                return self._fallback_download(url, save_path, timeout)
            
            # 使用 Network.getResponseBody 获取响应体
            print(f"[network_dl] 获取响应体: requestId={request_id}")
            body_result = self._send_sync("Network.getResponseBody", {"requestId": request_id})
            
            body = body_result.get("body", "")
            base64_encoded = body_result.get("base64Encoded", False)
            
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
            import os
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
            
        except Exception as e:
            print(f"[network_dl] 下载失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "url": url,
            }
    
    def _fallback_download(self, url: str, save_path: str, timeout: float) -> dict:
        """备用下载方式：直接用 JS 获取图片数据。"""
        print("[network_dl] 使用备用方式...")
        
        try:
            # 等待页面稳定
            time.sleep(2.0)
            
            # 检查页面是否是图片
            is_image_page = self._send_sync("Runtime.evaluate", {
                "expression": "document.body && document.body.querySelector('img') !== null",
                "returnByValue": True,
            }).get("result", {}).get("value", False)
            
            if is_image_page:
                # 直接获取页面上图片的 src
                img_src = self._send_sync("Runtime.evaluate", {
                    "expression": "document.body.querySelector('img')?.src || ''",
                    "returnByValue": True,
                }).get("result", {}).get("value", "")
                
                print(f"[network_dl] 页面图片 src: {img_src[:60]}...")
                
                # 用 canvas 获取数据
                js_code = """
                    (() => {
                        const img = document.body.querySelector('img');
                        if (!img) return {success: false, error: 'no image'};
                        
                        // 等待图片加载
                        if (!img.complete) {
                            return {success: false, error: 'image not loaded'};
                        }
                        
                        const canvas = document.createElement('canvas');
                        canvas.width = img.naturalWidth;
                        canvas.height = img.naturalHeight;
                        
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0);
                        
                        try {
                            const dataUrl = canvas.toDataURL('image/jpeg', 0.95);
                            const base64 = dataUrl.split(',')[1];
                            return {
                                success: true,
                                base64: base64,
                                width: canvas.width,
                                height: canvas.height
                            };
                        } catch (e) {
                            return {success: false, error: e.toString()};
                        }
                    })()
                """
                
                result = self._send_sync("Runtime.evaluate", {
                    "expression": js_code,
                    "returnByValue": True,
                    "awaitPromise": True,
                }).get("result", {}).get("value", {})
                
                if result.get("success"):
                    import os
                    base64_data = result.get("base64", "")
                    image_data = base64.b64decode(base64_data)
                    
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    with open(save_path, "wb") as f:
                        f.write(image_data)
                    
                    file_size = os.path.getsize(save_path)
                    print(f"[network_dl] 备用方式保存成功: {save_path} ({file_size} bytes)")
                    
                    return {
                        "success": True,
                        "path": save_path,
                        "size": file_size,
                        "url": url,
                        "method": "canvas_fallback",
                        "width": result.get("width"),
                        "height": result.get("height"),
                    }
                else:
                    return {
                        "success": False,
                        "error": f"备用方式失败: {result.get('error', 'unknown')}",
                        "url": url,
                    }
            else:
                return {
                    "success": False,
                    "error": "页面不是图片页面",
                    "url": url,
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"备用方式异常: {e}",
                "url": url,
            }


def test_network_download(keyword: str = "大海") -> dict:
    """测试 Network.getResponseBody 方式下载图片。
    
    步骤：
    1. 使用现有 CDP 客户端搜索小红书
    2. 获取第一张图片 URL
    3. 使用 Network 方式下载
    """
    print(f"\n{'='*60}")
    print(f"[test] 开始测试 - 关键词: {keyword}")
    print(f"{'='*60}\n")
    
    # 第一步：搜索获取图片 URL
    client = XHSCDPClient()
    try:
        client.connect("xiaohongshu.com")
        
        search_url = make_search_url(keyword)
        client._navigate(search_url)
        client._wait_for_load()
        client._wait_for_initial_state()
        client._wait_for_search_state()
        
        # 提取图片 URL
        dom_images = client._evaluate("""
            (() => {
                let results = [];
                
                // 直接收集 sns-webpic 图片
                const hdImgs = document.querySelectorAll('img[src*="sns-webpic"]');
                hdImgs.forEach((img, idx) => {
                    const url = img.getAttribute('src') || '';
                    if (url && url.includes('sns-webpic')) {
                        const parent = img.closest('[class*="avatar"], [class*="icon"]');
                        if (!parent) {
                            results.push({index: idx, url: url, type: 'hd_image'});
                        }
                    }
                });
                
                // 如果没找到，从 state 提取
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
        """)
        
        if not dom_images:
            return {
                "success": False,
                "error": "未获取到图片 URL",
            }
        
        # 转换为高清 URL
        for item in dom_images:
            if item.get("url"):
                item["url"] = convert_to_hd_url(item["url"])
        
        first_url = dom_images[0].get("url")
        if not first_url:
            return {
                "success": False,
                "error": "第一张图片 URL 无效",
            }
        
        print(f"[test] 获取到图片 URL: {first_url[:100]}...")
        
    except CDPError as e:
        return {
            "success": False,
            "error": f"搜索失败: {e}",
        }
    finally:
        client.disconnect()
    
    # 第二步：使用 Network 方式下载
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    save_path = str(OUTPUT_DIR / f"xhs_{keyword}_{timestamp}_network.jpg")
    
    downloader = NetworkImageDownloader()
    try:
        downloader.connect()
        result = downloader.download_image(first_url, save_path)
        
        if result.get("success"):
            print(f"\n{'='*60}")
            print(f"[test] 测试成功!")
            print(f"[test] 图片已保存到: {save_path}")
            print(f"[test] 下载方式: {result.get('method')}")
            print(f"[test] 文件大小: {result.get('size')} bytes")
            print(f"{'='*60}\n")
            
            return {
                "success": True,
                "keyword": keyword,
                "image_path": save_path,
                "image_url": first_url,
                "file_size": result.get("size"),
                "download_method": result.get("method"),
                "width": result.get("width"),
                "height": result.get("height"),
            }
        else:
            print(f"[test] 下载失败: {result.get('error')}")
            return {
                "success": False,
                "error": result.get("error"),
                "url": first_url,
                "debug": result,
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"下载异常: {e}",
            "url": first_url,
        }
    finally:
        downloader.disconnect()


if __name__ == "__main__":
    result = test_network_download("大海")
    print(json.dumps(result, ensure_ascii=False, indent=2))