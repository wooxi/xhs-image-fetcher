"""图片处理器模块 - 下载小红书图片并上传到图床。

功能：
1. 通过CDP浏览器下载小红书图片（绕过防盗链）
2. 上传到Lsky Pro图床
3. 返回图床链接
4. 实时进度日志记录

流程：
原图URL → CDP下载 → Lsky Pro上传 → 图床URL → 存入MySQL
"""

import os
import time
import json
import base64
import requests
import websockets.sync.client as ws_client
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# 配置常量
LSKY_PRO_URL = os.getenv("LSKY_PRO_URL", "http://192.168.100.4:5021")
LSKY_PRO_TOKEN = os.getenv("LSKY_PRO_TOKEN", "")
TEMP_DIR = Path(os.getenv("TEMP_DIR", "/tmp/xhs_images"))

# CDP 配置
CDP_HOST = os.getenv("CDP_HOST", "192.168.100.4")
CDP_PORT = int(os.getenv("CDP_PORT", "9224"))

# 小红书 CDN 域名
XHS_CDN_DOMAINS = ["sns-webpic-qc.xhscdn.com", "sns-webpic-cn.xhscdn.com", "sns-webpic.xhscdn.com", "xhscdn.com"]


class ImageProcessorLogger:
    """图片处理器日志器 - 支持实时进度记录到数据库。"""

    def __init__(self, db=None, search_log_id=None):
        self.db = db
        self.search_log_id = search_log_id
        self.progress_logs: List[Dict[str, Any]] = []
        self.start_time = time.time()
        self.images_found = 0
        self.images_uploaded = 0
        self.images_failed = 0
        self.current_post = ""
        self.current_image = 0

    def log(self, message: str, level: str = "info"):
        """记录日志消息。"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        elapsed = int(time.time() - self.start_time)
        log_entry = {
            "timestamp": timestamp,
            "elapsed": elapsed,
            "level": level,
            "message": message,
            "images_found": self.images_found,
            "images_uploaded": self.images_uploaded,
            "images_failed": self.images_failed,
        }
        self.progress_logs.append(log_entry)

        # 打印到控制台（带颜色）
        prefix = f"[{timestamp} +{elapsed}s]"
        if level == "error":
            print(f"{prefix} ❌ {message}")
        elif level == "success":
            print(f"{prefix} ✅ {message}")
        elif level == "warn":
            print(f"{prefix} ⚠️ {message}")
        else:
            print(f"{prefix} 📷 {message}")

        # 如果有数据库连接，实时更新进度
        if self.db and self.search_log_id:
            self._update_db_progress()

    def log_post_start(self, post_id: str, post_title: str, total_images: int):
        """记录帖子开始处理。"""
        self.current_post = post_id
        self.images_found += total_images
        title_preview = post_title[:30] if post_title else "无标题"
        self.log(f"开始处理帖子 [{post_id}] \"{title_preview}\" - 共{total_images}张图片")

    def log_image_progress(self, image_index: int, total: int, status: str, url: str = None):
        """记录图片处理进度。"""
        self.current_image = image_index
        if status == "downloading":
            self.log(f"下载第{image_index}/{total}张图片...")
        elif status == "uploading":
            self.log(f"上传第{image_index}/{total}张图片...")
        elif status == "success":
            self.images_uploaded += 1
            self.log(f"第{image_index}/{total}张图片上传成功", "success")
        elif status == "failed":
            self.images_failed += 1
            error_preview = url[:50] if url else ""
            self.log(f"第{image_index}/{total}张图片处理失败: {error_preview}...", "error")

    def log_post_complete(self, post_id: str, success_count: int, fail_count: int):
        """记录帖子处理完成。"""
        status = "success" if fail_count == 0 else "warn"
        self.log(f"帖子 [{post_id}] 完成: 成功{success_count}张, 失败{fail_count}张", status)

    def log_batch_complete(self, total_posts: int, total_success: int, total_fail: int):
        """记录批量处理完成。"""
        elapsed = int(time.time() - self.start_time)
        status = "success" if total_fail == 0 else "warn"
        self.log(f"批量处理完成: {total_posts}个帖子, {total_success}张成功, {total_fail}张失败, 耗时{elapsed}秒", status)

    def get_summary(self) -> Dict[str, Any]:
        """获取处理摘要。"""
        return {
            "images_found": self.images_found,
            "images_uploaded": self.images_uploaded,
            "images_failed": self.images_failed,
            "duration_seconds": int(time.time() - self.start_time),
            "logs": self.progress_logs[-50:],  # 最近50条日志
        }

    def _update_db_progress(self):
        """更新数据库进度记录。"""
        # 这里可以更新 search_logs 表的实时进度
        # 为简化实现，暂时只记录最终结果
        pass


class ImageProcessor:
    """图片处理器 - 下载并上传图片到图床。"""

    def __init__(self, lsky_url: str = None, lsky_token: str = None, logger: ImageProcessorLogger = None):
        self.lsky_url = lsky_url or LSKY_PRO_URL
        self.token = lsky_token or LSKY_PRO_TOKEN
        self.temp_dir = TEMP_DIR
        self.logger = logger or ImageProcessorLogger()

        # 创建临时目录
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # 验证 Token
        if not self.token:
            self.logger.log("未配置图床Token，尝试自动获取...", "warn")
            self.token = self._get_token()

        if not self.token:
            raise ValueError("无法获取Lsky Pro Token，请检查配置")

        self.logger.log(f"图床连接成功: {self.lsky_url}", "success")

    def _get_token(self) -> str:
        """通过API获取Token。"""
        email = os.getenv("LSKY_PRO_EMAIL", "wooxi@foxmail.com")
        password = os.getenv("LSKY_PRO_PASSWORD", "ulikem00n")

        try:
            resp = requests.post(
                f"{self.lsky_url}/api/v1/tokens",
                json={"email": email, "password": password},
                headers={"Accept": "application/json"},
                timeout=10
            )

            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") and data.get("data", {}).get("token"):
                    token = data["data"]["token"]
                    self.logger.log(f"获取Token成功", "success")
                    return token
        except Exception as e:
            self.logger.log(f"获取Token失败: {e}", "error")

        return ""

    def is_xhs_image_url(self, url: str) -> bool:
        """判断URL是否为小红书CDN图片。"""
        if not url:
            return False
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            for xhs_domain in XHS_CDN_DOMAINS:
                if xhs_domain in domain or domain.endswith(xhs_domain):
                    return True
            return False
        except Exception:
            return False

    def download_image_via_cdp(self, image_url: str, timeout: float = 30.0, max_retries: int = 3) -> bytes:
        """通过CDP浏览器下载图片（绕过防盗链），带重试机制和HTTP备用方案。"""
        ws = None
        msg_id = 0
        image_request_id = None

        for attempt in range(max_retries):
            try:
                # 获取CDP页面列表
                base_url = f"http://{CDP_HOST}:{CDP_PORT}"
                resp = requests.get(f"{base_url}/json", timeout=10)
                resp.raise_for_status()
                pages = resp.json()

                # 找一个可用页面
                ws_url = None
                for page in pages:
                    if page.get("type") == "page" and page.get("webSocketDebuggerUrl"):
                        ws_url = page.get("webSocketDebuggerUrl")
                        break

                if not ws_url:
                    raise Exception("没有可用的CDP页面")

                ws = ws_client.connect(ws_url)

                def send_cdp(method: str, params: dict = None) -> dict:
                    nonlocal msg_id, image_request_id
                    msg_id += 1
                    msg = {"id": msg_id, "method": method}
                    if params:
                        msg["params"] = params
                    ws.send(json.dumps(msg))

                    deadline = time.monotonic() + timeout
                    while time.monotonic() < deadline:
                        try:
                            remaining = max(0.1, deadline - time.monotonic())
                            raw = ws.recv(timeout=remaining)
                            data = json.loads(raw)

                            # 监听图片请求
                            if "method" in data and data["method"] == "Network.responseReceived":
                                evt_params = data.get("params", {})
                                resp_url = evt_params.get("response", {}).get("url", "")
                                rid = evt_params.get("requestId")
                                if image_url in resp_url or ("xhscdn.com" in resp_url and rid):
                                    image_request_id = rid

                            if data.get("id") == msg_id:
                                if "error" in data:
                                    raise Exception(f"CDP错误: {data['error']}")
                                return data.get("result", {})
                        except TimeoutError:
                            continue
                    raise Exception(f"超时: {method}")

                # 启用Network监听
                send_cdp("Network.enable")
                send_cdp("Page.enable")

                # 导航到图片URL
                send_cdp("Page.navigate", {"url": image_url})
                time.sleep(1.5)

                # 获取图片数据
                if image_request_id:
                    result = send_cdp("Network.getResponseBody", {"requestId": image_request_id})
                    body = result.get("body", "")
                    base64_encoded = result.get("base64Encoded", False)

                    if body:
                        if base64_encoded:
                            image_bytes = base64.b64decode(body)
                        else:
                            image_bytes = body.encode("utf-8") if isinstance(body, str) else body

                        ws.close()
                        return image_bytes

                raise Exception("无法获取图片数据")

            except Exception as e:
                if ws:
                    try:
                        ws.close()
                    except:
                        pass
                    ws = None

                # CDP失败后尝试HTTP备用方案
                if attempt == max_retries - 1:
                    print(f"[image_processor] CDP下载失败，尝试HTTP备用方案: {e}")
                    try:
                        # HTTP备用方案：使用小红书请求头绕过防盗链
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                            "Referer": "https://www.xiaohongshu.com/",
                            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                            "Cache-Control": "no-cache",
                            "Pragma": "no-cache",
                        }

                        resp = requests.get(image_url, headers=headers, timeout=30)
                        if resp.status_code == 200 and len(resp.content) > 1000:
                            print(f"[image_processor] HTTP备用方案成功，大小: {len(resp.content)} bytes")
                            return resp.content
                        else:
                            print(f"[image_processor] HTTP备用方案失败: HTTP {resp.status_code}, size: {len(resp.content)}")
                    except Exception as http_err:
                        print(f"[image_processor] HTTP备用方案失败: {http_err}")

                    raise Exception(f"CDP和HTTP下载均失败: {e}")

                # 重试前等待
                wait_time = 0.5 * (2 ** attempt)
                print(f"[image_processor] CDP下载失败，等待 {wait_time}s 后重试 (尝试 {attempt + 2}/{max_retries})")
                time.sleep(wait_time)

    def upload_to_lsky(self, image_bytes: bytes, filename: str = "xhs_image.jpg") -> Dict[str, Any]:
        """上传图片到Lsky Pro图床。"""
        try:
            files = {"file": (filename, image_bytes, "image/jpeg")}
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            }

            resp = requests.post(
                f"{self.lsky_url}/api/v1/upload",
                files=files,
                headers=headers,
                timeout=60
            )

            if resp.status_code == 200:
                data = resp.json()
                if data.get("status"):
                    links = data.get("data", {}).get("links", {})
                    return {
                        "success": True,
                        "url": links.get("url", ""),
                        "key": data.get("data", {}).get("key", ""),
                        "thumbnail": links.get("thumbnail_url", ""),
                    }
                else:
                    error = data.get("message", "未知错误")
                    return {"success": False, "error": error}
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def process_image(self, image_url: str, index: int = 1, total: int = 1) -> Dict[str, Any]:
        """处理单张图片：下载 → 上传。"""
        self.logger.log_image_progress(index, total, "downloading", image_url)

        try:
            # 下载图片
            if self.is_xhs_image_url(image_url):
                image_bytes = self.download_image_via_cdp(image_url)
            else:
                # 非小红书图片，直接请求
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.xiaohongshu.com/",
                }
                resp = requests.get(image_url, headers=headers, timeout=30)
                image_bytes = resp.content

            self.logger.log_image_progress(index, total, "uploading")

            # 生成文件名
            ext = ".jpg"
            for possible_ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                if possible_ext in image_url.lower():
                    ext = possible_ext
                    break
            filename = f"xhs_{int(time.time() * 1000)}_{index}{ext}"

            # 上传到图床
            upload_result = self.upload_to_lsky(image_bytes, filename)

            if upload_result.get("success"):
                self.logger.log_image_progress(index, total, "success")
                return {
                    "success": True,
                    "original_url": image_url,
                    "lsky_url": upload_result.get("url", ""),
                    "thumbnail": upload_result.get("thumbnail", ""),
                }
            else:
                self.logger.log_image_progress(index, total, "failed", upload_result.get("error"))
                return {
                    "success": False,
                    "original_url": image_url,
                    "error": upload_result.get("error", "上传失败"),
                }

        except Exception as e:
            self.logger.log_image_progress(index, total, "failed", str(e))
            return {
                "success": False,
                "original_url": image_url,
                "error": str(e),
            }

    def process_images_for_note(self, note: Dict[str, Any]) -> Dict[str, Any]:
        """处理单个帖子的所有图片。"""
        post_id = note.get("id", "unknown")
        post_title = note.get("title", "")
        images = note.get("images", [])

        if not images:
            return note

        self.logger.log_post_start(post_id, post_title, len(images))

        new_images = []
        upload_success = 0
        upload_fail = 0

        for i, img_url in enumerate(images):
            result = self.process_image(img_url, i + 1, len(images))

            if result.get("success"):
                new_images.append(result.get("lsky_url", img_url))
                upload_success += 1
            else:
                # 上传失败，保留原图URL（但可能无法显示）
                new_images.append(img_url)
                upload_fail += 1

            # 上传间隔（避免过快）
            if i < len(images) - 1:
                time.sleep(0.3)

        # 更新帖子数据
        note["images"] = new_images
        note["images_upload_success"] = upload_success
        note["images_upload_fail"] = upload_fail

        self.logger.log_post_complete(post_id, upload_success, upload_fail)

        return note

    def process_batch(self, notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量处理多个帖子的图片。"""
        total_images = sum(len(n.get("images", [])) for n in notes)
        self.logger.log(f"开始批量处理: {len(notes)}个帖子, 共{total_images}张图片")

        processed_notes = []
        total_success = 0
        total_fail = 0

        for note in notes:
            processed_note = self.process_images_for_note(note)
            processed_notes.append(processed_note)
            total_success += processed_note.get("images_upload_success", 0)
            total_fail += processed_note.get("images_upload_fail", 0)

            # 帖子间隔
            time.sleep(0.5)

        self.logger.log_batch_complete(len(notes), total_success, total_fail)

        return processed_notes


def process_images_for_notes(notes: List[Dict[str, Any]], db=None, search_log_id=None) -> List[Dict[str, Any]]:
    """处理笔记列表中的所有图片（便捷函数）。"""
    logger = ImageProcessorLogger(db, search_log_id)
    processor = ImageProcessor(logger=logger)
    return processor.process_batch(notes)


if __name__ == "__main__":
    print("=== 图片处理器测试 ===")

    # 测试图床连接
    processor = ImageProcessor()

    # 测试下载和上传（使用真实图片URL）
    test_url = "https://sns-webpic-qc.xhscdn.com/202604222103/3dd78a145fcee4d10e3f0eb3351057b0/notes_pre_post/1040g3k031v1plp0u3u004avbaim8jr7r8l500ig!nd_dft_wlteh_webp_3"

    result = processor.process_image(test_url)
    print(f"\n处理结果: {json.dumps(result, indent=2, ensure_ascii=False)}")