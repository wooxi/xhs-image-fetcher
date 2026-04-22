"""人类行为模拟模块 - 模拟真实人类浏览器操作以防止被检测。

功能：
1. 鼠标移动模拟（贝塞尔曲线路径，非直线）
2. 滚动行为模拟（阅读式滚动，随机暂停）
3. 打字速度模拟（字符间隔，词边界暂停）
4. 智能等待（基于页面状态而非固定时间）
5. 会话管理（Cookie持久化，避免重复登录）

参考: https://github.com/white0dew/XiaohongshuSkills
"""

import os
import json
import time
import random
import math
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta

import websockets.sync.client as ws_client

from dotenv import load_dotenv

load_dotenv()

# 会话缓存目录
SESSION_CACHE_DIR = Path(os.getenv("SESSION_CACHE_DIR", "/tmp/xhs_session"))
SESSION_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cookie文件路径
COOKIE_FILE = SESSION_CACHE_DIR / "cookies.json"
SESSION_META_FILE = SESSION_CACHE_DIR / "session_meta.json"

# 会话有效期（小时）- 参考 XiaohongshuSkills
SESSION_CACHE_HOURS = 12


class HumanBehaviorConfig:
    """人类行为模拟配置。"""

    # 鼠标移动
    MOUSE_SPEED_MIN = 50      # px/s 最小速度
    MOUSE_SPEED_MAX = 200     # px/s 最大速度
    MOUSE_PATH_JITTER = 5     # 随机路径抖动（像素）
    MOUSE_MOVE_STEPS = 20     # 移动步数

    # 滚动行为
    SCROLL_SPEED_MIN = 30     # px/s 最小滚动速度
    SCROLL_SPEED_MAX = 150    # px/s 最大滚动速度
    SCROLL_PAUSE_MIN = 0.3    # 滚动暂停最小时间（秒）
    SCROLL_PAUSE_MAX = 2.0    # 滚动暂停最大时间（秒）
    SCROLL_CHUNK_MIN = 50     # 每次滚动最小像素
    SCROLL_CHUNK_MAX = 300    # 每次滚动最大像素

    # 打字速度
    TYPING_SPEED_MIN = 50     # ms 每字符最小间隔
    TYPING_SPEED_MAX = 150    # ms 每字符最大间隔
    TYPING_WORD_PAUSE = 0.2   # 词边界暂停（秒）
    TYPING_THINK_PAUSE = 0.5  # 思考暂停概率
    TYPING_THINK_DURATION = 1.0  # 思考暂停时长

    # 等待时间
    THINK_PAUSE_MIN = 0.5     # 思考暂停最小时间（秒）
    THINK_PAUSE_MAX = 3.0     # 思考暂停最大时间（秒）
    PAGE_LOAD_TIMEOUT = 30.0  # 页面加载超时
    NETWORK_IDLE_TIMEOUT = 5.0  # 网络空闲超时

    # 随机化因子
    RANDOM_FACTOR = 0.3       # 所有时间的随机变化因子


class CDPError(Exception):
    """CDP 通信错误。"""


def random_duration(base: float, config_key: str = None) -> float:
    """生成随机化的时间间隔。

    Args:
        base: 基础时间
        config_key: 配置键名（可选，用于获取MIN/MAX）

    Returns:
        随机化的时间
    """
    if config_key:
        # 使用配置中的MIN/MAX范围
        min_val = getattr(HumanBehaviorConfig, f"{config_key}_MIN", base * 0.5)
        max_val = getattr(HumanBehaviorConfig, f"{config_key}_MAX", base * 1.5)
        return random.uniform(min_val, max_val)

    # 使用随机因子
    factor = HumanBehaviorConfig.RANDOM_FACTOR
    return base * (1 + random.uniform(-factor, factor))


def bezier_curve_points(start: Tuple[float, float], end: Tuple[float, float],
                        steps: int = 20, jitter: float = 5) -> List[Tuple[float, float]]:
    """生成贝塞尔曲线路径点（模拟人类鼠标移动）。

    Args:
        start: 起点坐标 (x, y)
        end: 终点坐标 (x, y)
        steps: 路径点数
        jitter: 随机抖动量

    Returns:
        路径点列表 [(x, y), ...]
    """
    # 计算中间控制点（在起点和终点之间随机偏移）
    mid_x = (start[0] + end[0]) / 2 + random.uniform(-jitter * 5, jitter * 5)
    mid_y = (start[1] + end[1]) / 2 + random.uniform(-jitter * 5, jitter * 5)

    # 二次贝塞尔曲线
    points = []
    for i in range(steps + 1):
        t = i / steps
        # 贝塞尔公式: B(t) = (1-t)²P0 + 2(1-t)tP1 + t²P2
        x = (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * mid_x + t ** 2 * end[0]
        y = (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * mid_y + t ** 2 * end[1]
        # 添加随机抖动
        x += random.uniform(-jitter, jitter)
        y += random.uniform(-jitter, jitter)
        points.append((x, y))

    return points


def simulate_mouse_movement(ws: ws_client.WebSocketClientConnection,
                            start: Tuple[float, float], end: Tuple[float, float],
                            msg_id_counter: List[int] = None) -> None:
    """通过CDP模拟鼠标移动。

    Args:
        ws: WebSocket连接
        start: 起点坐标
        end: 终点坐标
        msg_id_counter: 消息ID计数器（可变列表）
    """
    if msg_id_counter is None:
        msg_id_counter = [0]

    # 生成贝塞尔曲线路径
    steps = HumanBehaviorConfig.MOUSE_MOVE_STEPS
    path = bezier_curve_points(start, end, steps, HumanBehaviorConfig.MOUSE_PATH_JITTER)

    # 计算总移动时间
    distance = math.sqrt((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2)
    speed = random.uniform(HumanBehaviorConfig.MOUSE_SPEED_MIN, HumanBehaviorConfig.MOUSE_SPEED_MAX)
    total_time = distance / speed if speed > 0 else 1.0

    # 每步时间
    step_time = total_time / steps

    for point in path:
        msg_id_counter[0] += 1
        msg = {
            "id": msg_id_counter[0],
            "method": "Input.dispatchMouseEvent",
            "params": {
                "type": "mouseMoved",
                "x": point[0],
                "y": point[1],
                "button": "none"
            }
        }
        ws.send(json.dumps(msg))
        time.sleep(step_time)


def simulate_scroll(ws: ws_client.WebSocketClientConnection,
                    direction: str = "down", amount: int = None,
                    msg_id_counter: List[int] = None) -> None:
    """模拟人类式滚动。

    Args:
        ws: WebSocket连接
        direction: 滚动方向 ('down' or 'up')
        amount: 滚动量（像素），None则随机
        msg_id_counter: 消息ID计数器
    """
    if msg_id_counter is None:
        msg_id_counter = [0]

    if amount is None:
        amount = random.randint(HumanBehaviorConfig.SCROLL_CHUNK_MIN,
                                HumanBehaviorConfig.SCROLL_CHUNK_MAX)

    # 获取当前滚动位置
    msg_id_counter[0] += 1
    msg = {
        "id": msg_id_counter[0],
        "method": "Runtime.evaluate",
        "params": {
            "expression": "window.scrollY",
            "returnByValue": True
        }
    }
    ws.send(json.dumps(msg))

    # 简化：直接执行滚动
    scroll_direction = 1 if direction == "down" else -1
    target_scroll = scroll_direction * amount

    msg_id_counter[0] += 1
    scroll_msg = {
        "id": msg_id_counter[0],
        "method": "Runtime.evaluate",
        "params": {
            "expression": f"window.scrollBy(0, {target_scroll})",
            "returnByValue": True
        }
    }
    ws.send(json.dumps(scroll_msg))

    # 模拟滚动后的阅读暂停
    pause = random_duration(0, "SCROLL_PAUSE")
    time.sleep(pause)


def simulate_reading_scroll(ws: ws_client.WebSocketClientConnection,
                            total_scroll: int = 800,
                            msg_id_counter: List[int] = None) -> None:
    """模拟阅读式滚动（多次小滚动，随机暂停）。

    Args:
        ws: WebSocket连接
        total_scroll: 总滚动量
        msg_id_counter: 消息ID计数器
    """
    if msg_id_counter is None:
        msg_id_counter = [0]

    # 分多次滚动
    remaining = total_scroll
    scrolls = 0
    max_scrolls = 10

    while remaining > 0 and scrolls < max_scrolls:
        chunk = min(remaining, random.randint(50, 200))
        simulate_scroll(ws, "down", chunk, msg_id_counter)
        remaining -= chunk
        scrolls += 1

        # 随机暂停（模拟阅读）
        if random.random() < 0.7:
            pause = random_duration(0, "SCROLL_PAUSE")
            time.sleep(pause)


def simulate_typing(ws: ws_client.WebSocketClientConnection,
                    selector: str, text: str,
                    msg_id_counter: List[int] = None) -> None:
    """模拟人类打字速度。

    Args:
        ws: WebSocket连接
        selector: 输入框选择器
        text: 要输入的文本
        msg_id_counter: 消息ID计数器
    """
    if msg_id_counter is None:
        msg_id_counter = [0]

    # 先聚焦输入框
    msg_id_counter[0] += 1
    focus_msg = {
        "id": msg_id_counter[0],
        "method": "Runtime.evaluate",
        "params": {
            "expression": f"document.querySelector('{selector}').focus()",
            "returnByValue": True
        }
    }
    ws.send(json.dumps(focus_msg))

    # 逐字符输入
    words = text.split()
    for i, word in enumerate(words):
        for char in word:
            msg_id_counter[0] += 1
            type_msg = {
                "id": msg_id_counter[0],
                "method": "Input.dispatchKeyEvent",
                "params": {
                    "type": "keyDown",
                    "text": char
                }
            }
            ws.send(json.dumps(type_msg))

            # 字符间隔
            char_delay = random_duration(0, "TYPING_SPEED") / 1000
            time.sleep(char_delay)

            # keyUp
            msg_id_counter[0] += 1
            ws.send(json.dumps({
                "id": msg_id_counter[0],
                "method": "Input.dispatchKeyEvent",
                "params": {"type": "keyUp"}
            }))

        # 词边界暂停
        if i < len(words) - 1:
            # 空格
            msg_id_counter[0] += 1
            ws.send(json.dumps({
                "id": msg_id_counter[0],
                "method": "Input.dispatchKeyEvent",
                "params": {"type": "keyDown", "text": " "}
            }))
            time.sleep(HumanBehaviorConfig.TYPING_WORD_PAUSE)

        # 随机思考暂停
        if random.random() < 0.1:
            time.sleep(HumanBehaviorConfig.TYPING_THINK_DURATION)


def smart_wait_for_load(ws: ws_client.WebSocketClientConnection,
                        timeout: float = None,
                        msg_id_counter: List[int] = None) -> bool:
    """智能等待页面加载完成（基于状态而非固定时间）。

    Args:
        ws: WebSocket连接
        timeout: 超时时间
        msg_id_counter: 消息ID计数器

    Returns:
        True: 加载完成, False: 超时
    """
    if timeout is None:
        timeout = HumanBehaviorConfig.PAGE_LOAD_TIMEOUT

    if msg_id_counter is None:
        msg_id_counter = [0]

    deadline = time.monotonic() + timeout
    last_progress = 0

    while time.monotonic() < deadline:
        try:
            # 检查 document.readyState
            msg_id_counter[0] += 1
            msg = {
                "id": msg_id_counter[0],
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "document.readyState",
                    "returnByValue": True
                }
            }
            ws.send(json.dumps(msg))

            # 等待响应
            while time.monotonic() < deadline:
                try:
                    raw = ws.recv(timeout=0.5)
                    data = json.loads(raw)
                    if data.get("id") == msg_id_counter[0]:
                        state = data.get("result", {}).get("result", {}).get("value", "")
                        if state == "complete":
                            # 添加随机"耐心"等待
                            patience = random_duration(0.5, "THINK_PAUSE")
                            time.sleep(patience)
                            return True
                        break
                except TimeoutError:
                    break

            # 检查进度，如果没变化则可能卡住了
            msg_id_counter[0] += 1
            progress_msg = {
                "id": msg_id_counter[0],
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "document.documentElement.scrollHeight - window.innerHeight",
                    "returnByValue": True
                }
            }
            ws.send(json.dumps(progress_msg))

            time.sleep(0.3)

        except Exception:
            time.sleep(0.5)

    return False


def random_think_pause() -> float:
    """随机思考暂停（模拟人类阅读/思考）。

    Returns:
        暂停时长（秒）
    """
    return random_duration(0, "THINK_PAUSE")


def random_mouse_position(page_width: int = 1200, page_height: int = 800) -> Tuple[float, float]:
    """生成随机鼠标位置（在页面内容区域）。

    Args:
        page_width: 页面宽度
        page_height: 页面高度

    Returns:
        (x, y) 坐标
    """
    # 避免边缘区域
    margin = 50
    x = random.uniform(margin, page_width - margin)
    y = random.uniform(margin, page_height - margin)
    return (x, y)


class SessionManager:
    """会话管理器 - Cookie持久化和会话有效性检查。"""

    def __init__(self, cache_dir: Path = SESSION_CACHE_DIR):
        self.cache_dir = cache_dir
        self.cookie_file = cache_dir / "cookies.json"
        self.meta_file = cache_dir / "session_meta.json"

    def save_cookies(self, ws: ws_client.WebSocketClientConnection,
                     msg_id_counter: List[int] = None) -> bool:
        """保存当前会话的Cookies。

        Args:
            ws: WebSocket连接
            msg_id_counter: 消息ID计数器

        Returns:
            True: 成功保存
        """
        if msg_id_counter is None:
            msg_id_counter = [0]

        try:
            msg_id_counter[0] += 1
            msg = {
                "id": msg_id_counter[0],
                "method": "Network.getAllCookies"
            }
            ws.send(json.dumps(msg))

            # 等待响应
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                try:
                    raw = ws.recv(timeout=1.0)
                    data = json.loads(raw)
                    if data.get("id") == msg_id_counter[0]:
                        cookies = data.get("result", {}).get("cookies", [])

                        # 过滤小红书相关cookies
                        xhs_cookies = [c for c in cookies if "xiaohongshu.com" in c.get("domain", "")]

                        # 保存到文件
                        with open(self.cookie_file, "w") as f:
                            json.dump(xhs_cookies, f, indent=2)

                        # 保存元数据（时间戳）
                        meta = {
                            "saved_at": datetime.now().isoformat(),
                            "expires_at": (datetime.now() + timedelta(hours=SESSION_CACHE_HOURS)).isoformat(),
                            "count": len(xhs_cookies)
                        }
                        with open(self.meta_file, "w") as f:
                            json.dump(meta, f, indent=2)

                        print(f"[session] 已保存 {len(xhs_cookies)} 个Cookies")
                        return True
                except TimeoutError:
                    continue

            return False

        except Exception as e:
            print(f"[session] 保存Cookies失败: {e}")
            return False

    def load_cookies(self, ws: ws_client.WebSocketClientConnection,
                     msg_id_counter: List[int] = None) -> bool:
        """加载之前保存的Cookies。

        Args:
            ws: WebSocket连接
            msg_id_counter: 消息ID计数器

        Returns:
            True: 成功加载
        """
        if msg_id_counter is None:
            msg_id_counter = [0]

        if not self.cookie_file.exists():
            print("[session] 无缓存的Cookies")
            return False

        try:
            with open(self.cookie_file, "r") as f:
                cookies = json.load(f)

            if not cookies:
                return False

            # 设置每个cookie
            for cookie in cookies:
                msg_id_counter[0] += 1
                msg = {
                    "id": msg_id_counter[0],
                    "method": "Network.setCookie",
                    "params": {
                        "name": cookie.get("name"),
                        "value": cookie.get("value"),
                        "domain": cookie.get("domain", ".xiaohongshu.com"),
                        "path": cookie.get("path", "/"),
                        "secure": cookie.get("secure", True),
                        "httpOnly": cookie.get("httpOnly", False),
                    }
                }
                # 可选：添加expires
                if cookie.get("expires"):
                    msg["params"]["expires"] = cookie.get("expires")

                ws.send(json.dumps(msg))

            print(f"[session] 已加载 {len(cookies)} 个Cookies")
            return True

        except Exception as e:
            print(f"[session] 加载Cookies失败: {e}")
            return False

    def is_session_valid(self) -> bool:
        """检查缓存会话是否有效（未过期）。

        Returns:
            True: 会话有效可复用
        """
        if not self.meta_file.exists():
            return False

        try:
            with open(self.meta_file, "r") as f:
                meta = json.load(f)

            expires_at = meta.get("expires_at")
            if not expires_at:
                return False

            # 检查是否过期
            expires_dt = datetime.fromisoformat(expires_at)
            return datetime.now() < expires_dt

        except Exception:
            return False

    def clear_session(self) -> None:
        """清除缓存的会话数据。"""
        for f in [self.cookie_file, self.meta_file]:
            if f.exists():
                f.unlink()
        print("[session] 会话缓存已清除")


class HumanBehaviorSimulator:
    """人类行为模拟器 - 整合所有模拟功能。"""

    def __init__(self, ws: ws_client.WebSocketClientConnection = None):
        self.ws = ws
        self.msg_id_counter = [0]
        self.session_manager = SessionManager()

    def set_ws(self, ws: ws_client.WebSocketClientConnection) -> None:
        """设置WebSocket连接。"""
        self.ws = ws

    def mouse_move_to(self, target: Tuple[float, float],
                      start: Tuple[float, float] = None) -> None:
        """移动鼠标到目标位置。

        Args:
            target: 目标坐标
            start: 起点坐标（None则随机）
        """
        if start is None:
            start = random_mouse_position()

        simulate_mouse_movement(self.ws, start, target, self.msg_id_counter)

    def scroll_down(self, amount: int = None) -> None:
        """向下滚动。

        Args:
            amount: 滚动量（None则随机）
        """
        simulate_scroll(self.ws, "down", amount, self.msg_id_counter)

    def scroll_up(self, amount: int = None) -> None:
        """向上滚动。

        Args:
            amount: 滚动量（None则随机）
        """
        simulate_scroll(self.ws, "up", amount, self.msg_id_counter)

    def reading_scroll(self, total: int = 800) -> None:
        """阅读式滚动（多次小滚动，模拟阅读）。

        Args:
            total: 总滚动量
        """
        simulate_reading_scroll(self.ws, total, self.msg_id_counter)

    def type_text(self, selector: str, text: str) -> None:
        """模拟打字输入。

        Args:
            selector: 输入框选择器
            text: 输入文本
        """
        simulate_typing(self.ws, selector, text, self.msg_id_counter)

    def think_pause(self) -> None:
        """思考暂停。"""
        pause = random_think_pause()
        time.sleep(pause)

    def wait_for_page_load(self, timeout: float = None) -> bool:
        """智能等待页面加载。"""
        return smart_wait_for_load(self.ws, timeout, self.msg_id_counter)

    def simulate_browsing_behavior(self) -> None:
        """模拟浏览行为（随机鼠标移动 + 滚动 + 停顿）。

        适用于：进入页面后的自然浏览模拟
        """
        # 随机鼠标移动
        for _ in range(random.randint(2, 5)):
            target = random_mouse_position()
            self.mouse_move_to(target)
            self.think_pause()

        # 随机滚动
        self.reading_scroll(random.randint(300, 600))

        # 最后停顿
        self.think_pause()

    def save_session(self) -> bool:
        """保存当前会话。"""
        return self.session_manager.save_cookies(self.ws, self.msg_id_counter)

    def load_session(self) -> bool:
        """加载缓存的会话。"""
        return self.session_manager.load_cookies(self.ws, self.msg_id_counter)

    def has_valid_session(self) -> bool:
        """检查是否有有效缓存会话。"""
        return self.session_manager.is_session_valid()


# 便捷函数
def create_human_simulator(ws: ws_client.WebSocketClientConnection) -> HumanBehaviorSimulator:
    """创建人类行为模拟器。"""
    return HumanBehaviorSimulator(ws)


if __name__ == "__main__":
    print("=== 人类行为模拟模块测试 ===")

    # 测试贝塞尔曲线生成
    start = (100, 100)
    end = (500, 300)
    path = bezier_curve_points(start, end, 20, 5)
    print(f"生成 {len(path)} 个路径点")
    print(f"起点: {path[0]}, 终点: {path[-1]}")

    # 测试随机时间生成
    durations = [random_duration(1.0, "THINK_PAUSE") for _ in range(10)]
    print(f"随机暂停时间: {durations}")

    # 测试会话管理
    sm = SessionManager()
    print(f"会话有效: {sm.is_session_valid()}")

    print("\n=== 测试完成 ===")