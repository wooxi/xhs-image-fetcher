"""小红书搜索脚本 - CDP 版本（使用已部署的 Chrome DevTools Protocol 浏览器）。

功能：
1. search: 根据关键词搜索小红书帖子
2. detail: 获取帖子详细信息（标题、内容、图片、点赞、收藏等）
3. search_detail: 搜索并批量获取详情
4. check-login: 检查浏览器登录状态

特性：
- 集成人类行为模拟，防止被检测
- 智能等待，基于页面状态而非固定时间
- Cookie持久化，避免重复登录

前置条件：
- Chrome/Chromium 浏览器已启动并开启远程调试端口（默认 9224）
- 浏览器中已登录小红书账号

输出: JSON 格式
"""

import os
import argparse
import json
import sys
import time
import base64
import re
import random
from typing import Any, Optional
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv

load_dotenv()

import requests
import websockets.sync.client as ws_client

# 导入人类行为模拟模块
try:
    from human_behavior import (
        HumanBehaviorSimulator,
        SessionManager,
        random_think_pause,
        smart_wait_for_load,
    )
    HUMAN_BEHAVIOR_ENABLED = True
except ImportError:
    print("[xhs_cdp] 警告: 无法导入 human_behavior 模块，人类行为模拟功能不可用")
    HUMAN_BEHAVIOR_ENABLED = False

OUTPUT_DIR = Path("/tmp/xhs_search")

CDP_HOST = os.getenv("CDP_HOST", "192.168.100.4")
CDP_PORT = int(os.getenv("CDP_PORT", "9224"))

# URL 常量
SEARCH_BASE_URL = "https://www.xiaohongshu.com/search_result"
XHS_HOME_URL = "https://www.xiaohongshu.com"


class CDPError(Exception):
    """CDP 通信错误。"""


class XHSCDPClient:
    """小红书 CDP 客户端，连接到已部署的 Chrome 浏览器。

    集成人类行为模拟，防止被检测。
    """

    def __init__(self, host: str = CDP_HOST, port: int = CDP_PORT, use_human_behavior: bool = True):
        self.host = host
        self.port = port
        self.ws: Optional[ws_client.WebSocketClientConnection] = None
        self._msg_id = 0
        self.target_id: Optional[str] = None
        self.use_human_behavior = use_human_behavior and HUMAN_BEHAVIOR_ENABLED
        self.human_simulator: Optional[HumanBehaviorSimulator] = None
        self.session_manager: Optional[SessionManager] = None

        if self.use_human_behavior:
            self.session_manager = SessionManager()
            print("[xhs_cdp] 人类行为模拟已启用")

    def _get_targets(self) -> list[dict]:
        """获取浏览器所有 targets（tabs）。"""
        url = f"http://{self.host}:{self.port}/json"
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise CDPError(f"无法连接到 Chrome ({self.host}:{self.port}): {e}")

    def _find_or_create_tab(self, target_url_prefix: str = "") -> str:
        """找到或创建一个 tab，返回 WebSocket URL。"""
        targets = self._get_targets()
        pages = [
            t for t in targets
            if t.get("type") == "page" and t.get("webSocketDebuggerUrl")
        ]

        # 如果指定了 URL 前缀，优先找匹配的 tab
        if target_url_prefix:
            for t in pages:
                if t.get("url", "").startswith(target_url_prefix):
                    self.target_id = t.get("id")
                    return t["webSocketDebuggerUrl"]

        # 否则找小红书相关的 tab
        for t in pages:
            url = t.get("url", "")
            if "xiaohongshu.com" in url:
                self.target_id = t.get("id")
                return t["webSocketDebuggerUrl"]

        # 创建新 tab
        try:
            resp = requests.put(
                f"http://{self.host}:{self.port}/json/new?about:blank",
                timeout=5,
            )
            if resp.ok:
                data = resp.json()
                self.target_id = data.get("id")
                return data.get("webSocketDebuggerUrl", "")
        except Exception:
            pass

        # Fallback: 使用第一个可用的 page
        if pages:
            self.target_id = pages[0].get("id")
            return pages[0]["webSocketDebuggerUrl"]

        raise CDPError("没有可用的浏览器 tab")

    def connect(self, target_url_prefix: str = "", max_retries: int = 3):
        """连接到浏览器 tab（带重试机制）。"""
        for attempt in range(max_retries):
            try:
                ws_url = self._find_or_create_tab(target_url_prefix)
                if not ws_url:
                    raise CDPError("无法获取 WebSocket URL")

                print(f"[xhs_cdp] 连接到: {ws_url} (尝试 {attempt + 1}/{max_retries})")
                self.ws = ws_client.connect(ws_url)
                print("[xhs_cdp] 已连接")

                # 初始化人类行为模拟器
                if self.use_human_behavior:
                    self.human_simulator = HumanBehaviorSimulator(self.ws)

                    # 尝试加载缓存的会话
                    if self.session_manager and self.session_manager.is_session_valid():
                        print("[xhs_cdp] 发现有有效的缓存会话，尝试加载...")
                        self.session_manager.load_cookies(self.ws)

                return  # 连接成功
            except Exception as e:
                print(f"[xhs_cdp] 连接失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if self.ws:
                    try:
                        self.ws.close()
                    except:
                        pass
                    self.ws = None

                if attempt < max_retries - 1:
                    wait_time = 0.5 * (2 ** attempt)  # 指数退避: 0.5s, 1s, 2s
                    print(f"[xhs_cdp] 等待 {wait_time}s 后重试...")
                    time.sleep(wait_time)
                else:
                    raise CDPError(f"连接失败，已重试 {max_retries} 次: {e}")

    def _reconnect(self):
        """重新连接到浏览器（在连接断开时使用）。"""
        print("[xhs_cdp] 尝试重新连接...")
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
            self.ws = None

        # 重连时使用较短的超时
        self.connect(max_retries=2)

    def disconnect(self):
        """断开连接（保存会话）。"""
        # 保存会话Cookies（如果有人类行为模块）
        if self.use_human_behavior and self.session_manager and self.ws:
            try:
                self.session_manager.save_cookies(self.ws)
            except Exception as e:
                print(f"[xhs_cdp] 保存会话失败: {e}")

        if self.ws:
            self.ws.close()
            self.ws = None

    def _send(self, method: str, params: dict = None, timeout: float = 30.0, max_retries: int = 3) -> dict:
        """发送 CDP 命令并等待响应（带重试机制）。"""
        for attempt in range(max_retries):
            if not self.ws:
                if attempt < max_retries - 1:
                    try:
                        self._reconnect()
                        continue
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise CDPError(f"未连接且重连失败: {e}")
                else:
                    raise CDPError("未连接，请先调用 connect()")

            self._msg_id += 1
            msg_id = self._msg_id
            msg = {"id": msg_id, "method": method}
            if params:
                msg["params"] = params

            try:
                self.ws.send(json.dumps(msg))
            except Exception as send_err:
                print(f"[xhs_cdp] 发送失败: {send_err}")
                if attempt < max_retries - 1:
                    try:
                        self._reconnect()
                        wait_time = 0.5 * (2 ** attempt)
                        time.sleep(wait_time)
                        continue
                    except:
                        pass
                raise CDPError(f"发送命令失败: {send_err}")

            deadline = time.monotonic() + timeout

            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break  # 超时，进入重试逻辑

                try:
                    raw = self.ws.recv(timeout=max(0.1, remaining))
                except TimeoutError:
                    break  # 超时，进入重试逻辑
                except Exception as recv_err:
                    print(f"[xhs_cdp] 接收失败: {recv_err}")
                    if attempt < max_retries - 1:
                        try:
                            self._reconnect()
                            wait_time = 0.5 * (2 ** attempt)
                            time.sleep(wait_time)
                            continue  # 重试整个发送流程
                        except:
                            pass
                    raise CDPError(f"接收响应失败: {recv_err}")

                data = json.loads(raw)
                if data.get("id") == msg_id:
                    if "error" in data:
                        raise CDPError(f"CDP 错误: {data['error']}")
                    return data.get("result", {})

            # 超时，检查是否需要重试
            if attempt < max_retries - 1:
                wait_time = 0.5 * (2 ** attempt)  # 指数退避
                print(f"[xhs_cdp] {method} 超时，等待 {wait_time}s 后重试 (尝试 {attempt + 2}/{max_retries})")
                time.sleep(wait_time)
                try:
                    self._reconnect()
                except:
                    pass  # 重连失败也会继续重试
            else:
                raise CDPError(f"等待 CDP 响应超时: {method} (已重试 {max_retries} 次)")

        raise CDPError(f"等待 CDP 响应超时: {method}")

    def _evaluate(self, expression: str, timeout: float = 30.0) -> Any:
        """执行 JavaScript 并返回结果值。"""
        result = self._send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
            timeout=timeout,
        )
        remote_obj = result.get("result", {})
        if remote_obj.get("subtype") == "error":
            raise CDPError(f"JS 执行错误: {remote_obj.get('description', remote_obj)}")
        return remote_obj.get("value")

    def _navigate(self, url: str, wait_time: float = 3.0):
        """导航到 URL（带人类行为模拟）。"""
        print(f"[xhs_cdp] 导航到: {url}")

        # 人类行为模拟：在导航前可能随机移动鼠标
        if self.use_human_behavior and self.human_simulator:
            # 随机停顿，模拟"思考"
            random_think_pause()

        self._send("Page.enable")
        self._send("Page.navigate", {"url": url})

        # 智能等待加载（而非固定时间）
        if self.use_human_behavior:
            # 使用智能等待
            loaded = self._smart_wait_for_load(timeout=max(wait_time, 30.0))
            if not loaded:
                print("[xhs_cdp] 智能等待超时，使用固定等待")
                time.sleep(wait_time)
        else:
            time.sleep(wait_time)

    def _wait_for_load(self, timeout: float = 30.0):
        """等待页面加载完成。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                state = self._evaluate("document.readyState")
                if state == "complete":
                    return
            except CDPError:
                pass
            time.sleep(0.5)

    def _wait_for_initial_state(self, timeout: float = 20.0):
        """等待 __INITIAL_STATE__ 就绪。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                ready = self._evaluate("window.__INITIAL_STATE__ !== undefined")
                if ready:
                    return
            except CDPError:
                pass
            time.sleep(0.5)
        print("[xhs_cdp] 等待 __INITIAL_STATE__ 超时")

    def _wait_for_search_state(self, timeout: float = 25.0):
        """等待搜索结果就绪。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                ready = self._evaluate("""
                    window.__INITIAL_STATE__ &&
                    window.__INITIAL_STATE__.search &&
                    window.__INITIAL_STATE__.search.feeds
                """)
                if ready:
                    return
            except CDPError:
                pass
            time.sleep(0.6)
        print("[xhs_cdp] 等待搜索结果超时")

    def _wait_for_detail_state(self, timeout: float = 25.0):
        """等待详情页就绪。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                ready = self._evaluate("""
                    window.__INITIAL_STATE__ &&
                    window.__INITIAL_STATE__.note &&
                    window.__INITIAL_STATE__.note.noteDetailMap
                """)
                if ready:
                    return
            except CDPError:
                pass
            time.sleep(0.6)
        print("[xhs_cdp] 等待详情数据超时")

    def _smart_wait_for_load(self, timeout: float = 30.0) -> bool:
        """智能等待页面加载完成（基于状态而非固定时间）。"""
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            try:
                state = self._evaluate("document.readyState")
                if state == "complete":
                    # 添加随机"耐心"等待
                    if self.use_human_behavior:
                        patience = random.uniform(0.3, 1.5)
                        time.sleep(patience)
                    return True
            except CDPError:
                pass
            time.sleep(0.3)

        return False

    def _simulate_human_browsing(self, duration: float = 2.0):
        """模拟人类浏览行为（滚动 + 停顿）。

        适用于：进入页面后的自然浏览模拟
        """
        if not self.use_human_behavior or not self.human_simulator:
            return

        # 随机滚动
        scroll_amount = random.randint(100, 400)
        try:
            self._evaluate(f"window.scrollBy(0, {scroll_amount})")
            time.sleep(random.uniform(0.5, 1.5))

            # 可能回滚
            if random.random() < 0.3:
                back_scroll = random.randint(50, 200)
                self._evaluate(f"window.scrollBy(0, -{back_scroll})")
                time.sleep(random.uniform(0.3, 0.8))

        except CDPError:
            pass

        # 随机思考停顿
        random_think_pause()


def make_search_url(keyword: str) -> str:
    """构建搜索 URL。"""
    params = urlencode({"keyword": keyword.strip(), "source": "web_explore_feed"})
    return f"{SEARCH_BASE_URL}?{params}"


def make_feed_detail_url(feed_id: str, xsec_token: str) -> str:
    """构建帖子详情 URL（手机端可打开格式）。"""
    return f"https://www.xiaohongshu.com/discovery/item/{feed_id}?source=webshare&xhsshare=pc_web&xsec_token={xsec_token}&xsec_source=pc_share"


def extract_note_id(url: str) -> str:
    """从 URL 中提取 note_id。"""
    # /explore/{note_id} 格式
    match = re.search(r"/explore/([a-f0-9]+)", url)
    if match:
        return match.group(1)
    # /discovery/item/{note_id} 格式
    match = re.search(r"/discovery/item/([a-f0-9]+)", url)
    if match:
        return match.group(1)
    # noteId= 参数格式
    match = re.search(r"noteId=([a-f0-9]+)", url)
    if match:
        return match.group(1)
    # 纯 note_id 格式
    match = re.search(r"^[a-f0-9]{24}$", url)
    if match:
        return url
    return "unknown"


def convert_to_hd_url(url: str) -> str:
    """将预览图 URL 转换为高清格式。
    
    转换规则：
    - 协议: http:// -> https://
    - 后缀: !nc_n_webp_prv_1 -> !nd_dft_wlteh_webp_3
    - 后缀: !nc_n_webp_mw_1 -> !nd_dft_wlteh_webp_3
    """
    if not url:
        return url
    
    # 协议转换: http -> https
    if url.startswith("http://"):
        url = "https://" + url[7:]
    
    # 后缀转换: 预览/缩略图 -> 高清
    # 常见的预览图后缀格式
    preview_suffixes = [
        "!nc_n_webp_prv_1",
        "!nc_n_webp_mw_1",
        "!nc_n_webp_prv",
        "!nc_n_webp_mw",
    ]
    
    # 高清格式后缀
    hd_suffix = "!nd_dft_wlteh_webp_3"
    
    for suffix in preview_suffixes:
        if url.endswith(suffix):
            url = url[:-len(suffix)] + hd_suffix
            break
    
    return url


def extract_image_url(img_data: dict) -> str:
    """从图片数据中提取 URL，优先高清链接。
    
    搜索结果的 imageList 结构: {infoList: [{imageScene, url}]}
    详情页的 imageList 结构: {urlDefault, urlPre, infoList: [...]}"""
    # 优先从 infoList 提取高清预览图 (WB_PRV)
    for info in img_data.get("infoList", []) or []:
        if info.get("imageScene") == "WB_PRV":
            url = info.get("url")
            if url:
                return convert_to_hd_url(url)
    # 其次从 infoList 提取默认图 (WB_DFT)
    for info in img_data.get("infoList", []) or []:
        if info.get("imageScene") == "WB_DFT":
            url = info.get("url")
            if url:
                return convert_to_hd_url(url)
    # 最后使用 urlDefault 或 urlPre
    url = img_data.get("urlDefault") or img_data.get("urlPre") or img_data.get("url") or ""
    return convert_to_hd_url(url)


def format_search_results(feeds: list[dict]) -> list[dict]:
    """格式化搜索结果。"""
    formatted = []
    for feed in feeds:
        if not isinstance(feed, dict):
            continue

        note_card = feed.get("noteCard", {})
        user = note_card.get("user", {})
        interact_info = note_card.get("interactInfo", {})
        cover = note_card.get("cover", {})

        # 提取所有图片链接
        images = []
        # 从 imageList 提取所有图片
        for img in note_card.get("imageList", []) or []:
            img_url = extract_image_url(img)
            if img_url:
                images.append(img_url)
        # 如果没有 imageList，使用 cover
        if not images:
            cover_url = cover.get("urlDefault") or cover.get("url")
            if cover_url:
                images.append(cover_url)

        item = {
            "id": feed.get("id", ""),
            "url": f"https://www.xiaohongshu.com/explore/{feed.get('id', '')}",
            "xsec_token": feed.get("xsecToken", ""),
            "title": note_card.get("displayTitle", ""),
            "type": note_card.get("type", ""),
            "likes": interact_info.get("likedCount", "0"),
            "collects": interact_info.get("collectedCount", "0"),
            "comments": interact_info.get("commentCount", "0"),
            "author": {
                "id": user.get("userId", ""),
                "name": user.get("nickname", ""),
            },
            "cover": cover.get("urlDefault", cover.get("url", "")),
            "images": images,  # 所有图片链接数组
        }

        # 构建完整 URL（手机端可打开格式）
        if item["id"] and item["xsec_token"]:
            item["url"] = f"https://www.xiaohongshu.com/discovery/item/{item['id']}?source=webshare&xhsshare=pc_web&xsec_token={item['xsec_token']}&xsec_source=pc_share"

        formatted.append(item)

    return formatted


def extract_video_url(video_data: dict) -> str:
    """从视频数据中提取最优视频链接。
    
    视频结构: video.media.stream.{h264, h265, av1, h266}
    优先级: h265 高分辨率 > h264 高分辨率 > h264 默认
    """
    media = video_data.get("media", {})
    stream = media.get("stream", {})
    
    # 优先 H265 (HEVC) 高分辨率版本
    h265_streams = stream.get("h265", []) or []
    if h265_streams:
        # 按分辨率排序，优先最高
        sorted_h265 = sorted(h265_streams, key=lambda x: x.get("height", 0) * x.get("width", 0), reverse=True)
        if sorted_h265:
            return sorted_h265[0].get("masterUrl", "")
    
    # 其次 H264 高分辨率版本
    h264_streams = stream.get("h264", []) or []
    if h264_streams:
        # 按分辨率排序，优先最高
        sorted_h264 = sorted(h264_streams, key=lambda x: x.get("height", 0) * x.get("width", 0), reverse=True)
        if sorted_h264:
            return sorted_h264[0].get("masterUrl", "")
    
    # 其他编码格式
    for codec in ["av1", "h266"]:
        codec_streams = stream.get(codec, []) or []
        if codec_streams:
            return codec_streams[0].get("masterUrl", "")
    
    return ""


def format_detail_result(data: dict) -> dict:
    """格式化帖子详情。"""
    note = data.get("note", {})
    user = note.get("user", {})
    interact_info = note.get("interactInfo", {})

    # 提取所有图片链接（优先高清链接）
    images = []
    for img in note.get("imageList", []) or []:
        img_url = extract_image_url(img)
        if img_url:
            images.append(img_url)

    # 提取视频信息（如果是视频笔记）
    video_url = ""
    video_cover = ""
    video_duration = 0
    if note.get("type") == "video":
        video = note.get("video", {})
        video_url = extract_video_url(video)
        video_cover = images[0] if images else ""  # 视频封面就是第一张图片
        # 提取视频时长
        capa = video.get("capa", {})
        video_duration = capa.get("duration", 0)
        # 也从 media.video.duration 提取（秒）
        media_video = video.get("media", {}).get("video", {})
        if not video_duration:
            video_duration = media_video.get("duration", 0)

    return {
        "id": note.get("noteId", ""),
        "title": note.get("title", ""),
        "content": note.get("desc", ""),
        "type": note.get("type", ""),
        "images": images,  # 所有图片链接数组
        "video": video_url,  # 视频链接（如果是视频笔记）
        "video_cover": video_cover,  # 视频封面
        "video_duration": video_duration,  # 视频时长（秒）
        "likes": interact_info.get("likedCount", "0"),
        "collects": interact_info.get("collectedCount", "0"),
        "comments": interact_info.get("commentCount", "0"),
        "shares": interact_info.get("sharedCount", "0"),
        "author": {
            "id": user.get("userId", ""),
            "name": user.get("nickname", ""),
            "avatar": user.get("avatar", ""),
        },
        "ip_location": note.get("ipLocation", ""),
        "time": note.get("time", 0),
    }


def check_login(client: XHSCDPClient) -> dict:
    """检查登录状态。"""
    try:
        client.connect("xiaohongshu.com")
        client._navigate(XHS_HOME_URL)
        client._wait_for_load()

        # 检查是否有登录弹窗关键词
        login_keywords = [
            "登录后推荐更懂你的笔记",
            "请登录",
            "扫码登录",
        ]

        page_text = client._evaluate("document.body ? document.body.innerText : ''")
        if isinstance(page_text, str):
            for kw in login_keywords:
                if kw in page_text:
                    return {
                        "logged_in": False,
                        "message": f"未登录，检测到关键词: {kw}",
                        "hint": "请在浏览器中登录小红书账号",
                    }

        # 检查是否有用户信息
        has_user = client._evaluate("""
            document.querySelector('.user-info, .nickname, [class*="user"]') !== null ||
            (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.user)
        """)

        if has_user:
            return {
                "logged_in": True,
                "message": "已登录",
            }

        return {
            "logged_in": False,
            "message": "未检测到登录状态",
            "hint": "请在浏览器中登录小红书账号",
        }

    except CDPError as e:
        return {
            "logged_in": False,
            "message": "连接失败",
            "error": str(e),
            "hint": "请确保 Chrome 浏览器已启动并开启远程调试端口 9222",
        }
    finally:
        client.disconnect()


def search_notes(keyword: str, limit: int = 10, sort_by: str = "general", save: bool = True) -> dict:
    """搜索小红书笔记。

    Args:
        keyword: 搜索关键词
        limit: 返回结果数量
        sort_by: 排序方式 (general/popular/latest)
        save: 是否保存结果到文件（默认 True）
    """
    print(f"[xhs_cdp] 搜索关键词: {keyword}, 排序: {sort_by}")

    client = XHSCDPClient()
    try:
        # 连接到浏览器
        client.connect("xiaohongshu.com")

        # 导航到搜索页
        search_url = make_search_url(keyword)
        client._navigate(search_url)
        client._wait_for_load()
        client._wait_for_initial_state()

        # 模拟人类浏览行为（防止被检测）
        client._simulate_human_browsing()

        # 等待搜索结果
        client._wait_for_search_state()

        # 提取搜索结果
        raw = client._evaluate("""
            (() => {
                if (
                    window.__INITIAL_STATE__ &&
                    window.__INITIAL_STATE__.search &&
                    window.__INITIAL_STATE__.search.feeds
                ) {
                    const feeds = window.__INITIAL_STATE__.search.feeds;
                    const data = feeds.value !== undefined ? feeds.value : feeds._value;
                    if (data) {
                        return JSON.stringify(data);
                    }
                }
                return "";
            })()
        """)

        if not raw or not isinstance(raw, str):
            return {
                "success": False,
                "error": "未获取到搜索结果",
                "hint": "可能未登录或关键词无效",
            }

        try:
            feeds = json.loads(raw)
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"解析搜索结果失败: {e}",
            }

        if not isinstance(feeds, list):
            return {
                "success": False,
                "error": "搜索结果格式异常",
            }

        # 格式化并限制数量
        formatted = format_search_results(feeds)[:limit]

        output = {
            "success": True,
            "keyword": keyword,
            "sort_by": sort_by,
            "count": len(formatted),
            "notes": formatted,
        }

        # 保存结果（可选）
        if save:
            save_result(output, f"search_{keyword}.json")

        return output

    except CDPError as e:
        return {
            "success": False,
            "error": str(e),
            "hint": "请确保 Chrome 浏览器已启动并开启远程调试端口 9222",
        }
    finally:
        client.disconnect()


def get_note_detail(note_url: str, xsec_token: str = "") -> dict:
    """获取笔记详情。

    Args:
        note_url: 笔记 URL 或 note_id
        xsec_token: 安全 token（可选）
    """
    print(f"[xhs_cdp] 获取笔记详情: {note_url}")

    client = XHSCDPClient()
    try:
        # 解析 note_id
        note_id = extract_note_id(note_url)

        # 确定详情 URL：优先使用传入的完整 URL
        if note_url.startswith("https://") and "xiaohongshu.com" in note_url:
            # 传入的是完整 URL，直接使用
            detail_url = note_url
        elif xsec_token:
            # 只有 note_id 和 xsec_token，构建 URL
            detail_url = make_feed_detail_url(note_id, xsec_token)
        else:
            # 只有 note_id，构建基础 URL
            detail_url = f"https://www.xiaohongshu.com/discovery/item/{note_id}?source=webshare&xhsshare=pc_web"

        # 连接并导航
        client.connect("xiaohongshu.com")
        client._navigate(detail_url, wait_time=5.0)  # 增加等待时间
        client._wait_for_load()
        client._wait_for_initial_state(timeout=30.0)  # 增加超时时间

        # 模拟人类浏览行为（防止被检测）
        client._simulate_human_browsing(duration=3.0)

        client._wait_for_detail_state(timeout=30.0)  # 增加超时时间

        # 提取详情数据
        raw = client._evaluate(f"""
            (() => {{
                const feedId = "{note_id}";
                const state = window.__INITIAL_STATE__;
                if (!state || !state.note || !state.note.noteDetailMap) {{
                    return "";
                }}

                const detailMap = state.note.noteDetailMap;
                if (detailMap[feedId]) {{
                    return JSON.stringify(detailMap[feedId]);
                }}

                const keys = Object.keys(detailMap || {{}});
                if (keys.length === 1 && detailMap[keys[0]]) {{
                    return JSON.stringify(detailMap[keys[0]]);
                }}
                return "";
            }})()
        """)

        if not raw or not isinstance(raw, str):
            return {
                "success": False,
                "error": "未获取到笔记详情",
                "hint": "可能未登录或笔记不存在",
            }

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"解析详情数据失败: {e}",
            }

        # 从 DOM 中提取高清图片链接（使用精确XPath定位主贴图片）
        # XPath: /html/body/div[5]/div[1]/div[2]/div/div/div[2]/div/div[2]/div/div/img
        dom_images = client._evaluate("""
            (() => {
                let images = [];

                // 策略1: 使用用户指定的精确XPath（只获取主贴图片）
                const xpath = '/html/body/div[5]/div[1]/div[2]/div/div/div[2]/div/div[2]/div/div/img';
                let xpathResult = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                for (let i = 0; i < xpathResult.snapshotLength; i++) {
                    const img = xpathResult.snapshotItem(i);
                    const url = img.getAttribute('src') || img.getAttribute('data-src') || '';
                    if (url && url.includes('xhscdn.com') && !images.includes(url)) {
                        images.push(url);
                    }
                }

                // 策略2: 如果XPath没找到，尝试轮播区域的图片容器
                if (images.length === 0) {
                    // 尝试多种可能的轮播容器结构
                    const selectors = [
                        // 主贴图片轮播容器（排除评论区）
                        '.swiper-wrapper:not([class*="comment"]) img',
                        '.swiper-slide:not([class*="comment"]) img',
                        'div[class*="swiper-wrapper"] img',
                        // 小红书主贴图片区域
                        'div[class*="noteContainer"] > div[class*="swiper"] img',
                        'div[class*="noteContainer"] > div > div[class*="swiper"] img'
                    ];

                    for (const selector of selectors) {
                        const imgs = document.querySelectorAll(selector);
                        if (imgs.length > 0) {
                            imgs.forEach(img => {
                                const url = img.getAttribute('src') || img.getAttribute('data-src') || '';
                                // 只收集sns-webpic的高清图片，排除头像、图标、评论
                                if (url && url.includes('sns-webpic') && !url.includes('avatar') && !url.includes('icon') && !url.includes('comment') && !images.includes(url)) {
                                    images.push(url);
                                }
                            });
                            if (images.length > 0) {
                                console.log('使用selector找到:', images.length);
                                break;
                            }
                        }
                    }
                }

                // 策略3: 通过位置过滤（主贴图片在页面左侧上半部分）
                if (images.length === 0) {
                    const allImgs = document.querySelectorAll('img[src*="sns-webpic"]');
                    allImgs.forEach(img => {
                        const rect = img.getBoundingClientRect();
                        const url = img.getAttribute('src') || '';
                        // 主贴图片特征：宽度大于100px，位置在页面左侧40%区域内
                        if (url && rect.width > 100 && rect.left < window.innerWidth * 0.4) {
                            if (!url.includes('avatar') && !url.includes('icon') && !url.includes('comment') && !images.includes(url)) {
                                images.push(url);
                            }
                        }
                    });
                }

                return images;
            })()
        """)

        # 格式化详情
        detail = format_detail_result(data)
        detail["url"] = detail_url
        detail["success"] = True
        
        # 如果 DOM 中有高清图片链接，优先使用这些链接
        if dom_images and isinstance(dom_images, list) and len(dom_images) > 0:
            # 检查链接是否为高清格式（sns-webpic-qc.xhscdn.com）
            hd_images = [url for url in dom_images if 'sns-webpic' in url or 'xhscdn.com' in url]
            if hd_images:
                print(f"[xhs_cdp] 从 DOM 提取到 {len(hd_images)} 张高清图片")
                detail["images"] = hd_images
                # 更新视频封面（如果是视频笔记）
                if detail.get("type") == "video" and hd_images:
                    detail["video_cover"] = hd_images[0]

        # 保存结果
        save_result(detail, f"detail_{note_id}.json")

        return detail

    except CDPError as e:
        return {
            "success": False,
            "error": str(e),
            "hint": "请确保 Chrome 浏览器已启动并开启远程调试端口 9222",
        }
    finally:
        client.disconnect()


def search_and_detail(keyword: str, limit: int = 5, delay: float = 2.0, sort_by: str = "general", db: Any = None, skip_existing: bool = True) -> dict:
    """搜索并批量获取笔记详情（智能补充搜索 + 随机排序）。

    Args:
        keyword: 搜索关键词
        limit: 需要获取的新帖子数量（最终目标）
        delay: 每次请求间隔（秒）
        sort_by: 排序方式（可以是 "random" 表示每次随机选择）
        db: 数据库实例（可选，用于去重检查）
        skip_existing: 是否跳过已存在的帖子（默认 True）

    Returns:
        包含 notes, posts_found, posts_new, posts_skipped 的结果字典
    """
    print(f"[xhs_cdp] 搜索并获取详情: {keyword}, 目标新帖子数: {limit}")

    # 支持的排序方式
    sort_options = ["general", "popular", "latest"]  # 综合、热门、最新

    detailed_notes = []
    posts_new = 0
    posts_skipped = 0
    total_searched = 0
    seen_note_ids = set()  # 已处理过的帖子ID（防止重复）
    max_search_attempts = limit * 4  # 最大搜索尝试次数（防止无限循环）
    batch_count = 0

    # 循环搜索直到获取足够的新帖子
    while posts_new < limit and total_searched < max_search_attempts:
        batch_count += 1
        # 计算本次需要搜索的数量：多搜索一些以补偿跳过的
        batch_limit = min(limit * 2, 30)

        # 每批次随机选择排序方式（如果指定了 "random" 或每次都随机）
        if sort_by == "random":
            current_sort = random.choice(sort_options)
        else:
            # 为了获取更多不同结果，每批次随机切换排序
            current_sort = random.choice(sort_options)

        print(f"[xhs_cdp] 搜索批次 #{batch_count}: 目标 {limit} 个新帖子，当前已有 {posts_new} 个，还需 {limit - posts_new} 个，排序: {current_sort}")

        # 执行搜索
        search_result = search_notes(keyword, batch_limit, current_sort, save=False)

        if not search_result.get("success", False):
            if total_searched == 0:
                return search_result  # 第一次搜索失败则返回错误
            break  # 后续搜索失败则结束

        notes = search_result.get("notes", [])
        if not notes:
            print("[xhs_cdp] 搜索结果为空，结束搜索")
            break

        total_searched += len(notes)
        batch_new = 0  # 本批次新帖子数

        # 处理本轮搜索结果
        for i, note in enumerate(notes):
            note_id = note.get("id", "")
            url = note.get("url", "")
            xsec_token = note.get("xsec_token", "")

            # 检查是否已经处理过（防止重复）
            if note_id in seen_note_ids:
                continue
            seen_note_ids.add(note_id)

            # 去重检查：在获取详情前检查帖子是否已存在数据库
            if skip_existing and db and note_id:
                try:
                    if db.is_note_exists(note_id=note_id, url=url):
                        print(f"[xhs_cdp] 跳过已存在帖子: {note_id}")
                        posts_skipped += 1
                        # 帖子之间添加随机停顿（模拟人类行为）
                        pause = random.uniform(0.3, 0.8)
                        time.sleep(pause)
                        continue
                except Exception as e:
                    print(f"[xhs_cdp] 去重检查失败: {e}")

            # 检查是否已达到目标
            if posts_new >= limit:
                print(f"[xhs_cdp] 已达到目标数量 {limit}，停止获取")
                break

            if url:
                print(f"[xhs_cdp] 获取详情 [{posts_new + 1}/{limit}]: {note_id}")
                detail = get_note_detail(url, xsec_token)

                # 合并搜索结果和详情
                if detail.get("success", False):
                    combined = {**note, **detail}
                    combined["images"] = detail.get("images", [note.get("cover", "")])
                    detailed_notes.append(combined)
                    posts_new += 1
                    batch_new += 1
                else:
                    print(f"[xhs_cdp] 获取详情失败: {detail.get('error', '未知错误')}")

                # 间隔等待（使用随机停顿）
                pause = random.uniform(delay * 0.7, delay * 1.5)
                if random.random() < 0.2:
                    pause += random.uniform(0.5, 1.5)
                time.sleep(pause)

        # 如果本轮没有获取到任何新帖子，可能需要翻页或停止
        if batch_new == 0 and len(notes) > 0:
            print(f"[xhs_cdp] 本轮搜索未获取到新帖子（全部已存在），可能已到达重复边界")
            # 可以选择停止或继续尝试（取决于是否需要翻页）
            # 这里继续尝试，但增加等待时间
            time.sleep(random.uniform(2.0, 3.0))

        # 如果还需要更多帖子，等待后继续
        if posts_new < limit and batch_new > 0:
            time.sleep(random.uniform(1.0, 2.0))

    print(f"[xhs_cdp] 搜索完成: 共搜索 {total_searched} 条，跳过 {posts_skipped} 条已存在，获取 {posts_new} 条新帖子")

    output = {
        "success": True,
        "keyword": keyword,
        "sort_by": sort_by,
        "posts_found": total_searched,
        "posts_new": posts_new,
        "posts_skipped": posts_skipped,
        "count": len(detailed_notes),
        "notes": detailed_notes,
    }

    # 保存完整结果（统一命名格式）
    save_result(output, f"search_{keyword}.json")

    return output


def save_result(data: dict, filename: str) -> None:
    """保存结果到文件。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[xhs_cdp] 结果已保存: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        prog="xhs-search-cdp",
        description="小红书搜索脚本（CDP 版本）",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # search 命令
    sub = subparsers.add_parser("search", help="搜索小红书笔记")
    sub.add_argument("keyword", help="搜索关键词")
    sub.add_argument("--limit", "-n", type=int, default=10, help="结果数量")
    sub.add_argument("--sort", "-s", default="general", choices=["general", "popular", "latest"], help="排序方式")
    sub.set_defaults(func=lambda a: print(json.dumps(search_notes(a.keyword, a.limit, a.sort), ensure_ascii=False, indent=2)))

    # detail 命令
    sub = subparsers.add_parser("detail", help="获取笔记详情")
    sub.add_argument("note_url", help="笔记 URL 或 ID")
    sub.add_argument("--xsec-token", "-x", default="", help="xsec_token（可选）")
    sub.set_defaults(func=lambda a: print(json.dumps(get_note_detail(a.note_url, a.xsec_token), ensure_ascii=False, indent=2)))

    # search-detail 命令
    sub = subparsers.add_parser("search-detail", help="搜索并获取详情")
    sub.add_argument("keyword", help="搜索关键词")
    sub.add_argument("--limit", "-n", type=int, default=5, help="结果数量")
    sub.add_argument("--sort", "-s", default="general", choices=["general", "popular", "latest"], help="排序方式")
    sub.add_argument("--delay", "-d", type=float, default=2.0, help="请求间隔（秒）")
    sub.set_defaults(func=lambda a: print(json.dumps(search_and_detail(a.keyword, a.limit, a.delay, a.sort), ensure_ascii=False, indent=2)))

    # check-login 命令
    sub = subparsers.add_parser("check-login", help="检查浏览器登录状态")
    sub.set_defaults(func=lambda a: print(json.dumps(check_login(XHSCDPClient()), ensure_ascii=False, indent=2)))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()