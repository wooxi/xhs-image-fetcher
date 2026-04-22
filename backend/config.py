"""项目配置模块 - 集中管理所有配置项。

包含：
1. 人类行为模拟配置（鼠标、滚动、打字）
2. 调度器配置（时间控制、高峰规避、重试）
3. CDP浏览器配置
4. 数据库配置
5. 图床配置

所有配置支持环境变量覆盖。
"""

import os
from typing import List, Tuple

from dotenv import load_dotenv

load_dotenv()


# ==================== 人类行为模拟配置 ====================

class HumanBehaviorConfig:
    """人类行为模拟配置。"""

    # 鼠标移动
    MOUSE_SPEED_MIN = int(os.getenv("MOUSE_SPEED_MIN", "50"))      # px/s 最小速度
    MOUSE_SPEED_MAX = int(os.getenv("MOUSE_SPEED_MAX", "200"))     # px/s 最大速度
    MOUSE_PATH_JITTER = int(os.getenv("MOUSE_PATH_JITTER", "5"))   # 随机路径抖动（像素）
    MOUSE_MOVE_STEPS = int(os.getenv("MOUSE_MOVE_STEPS", "20"))    # 移动步数

    # 滚动行为
    SCROLL_SPEED_MIN = int(os.getenv("SCROLL_SPEED_MIN", "30"))    # px/s 最小滚动速度
    SCROLL_SPEED_MAX = int(os.getenv("SCROLL_SPEED_MAX", "150"))   # px/s 最大滚动速度
    SCROLL_PAUSE_MIN = float(os.getenv("SCROLL_PAUSE_MIN", "0.3")) # 滚动暂停最小时间（秒）
    SCROLL_PAUSE_MAX = float(os.getenv("SCROLL_PAUSE_MAX", "2.0")) # 滚动暂停最大时间（秒）
    SCROLL_CHUNK_MIN = int(os.getenv("SCROLL_CHUNK_MIN", "50"))    # 每次滚动最小像素
    SCROLL_CHUNK_MAX = int(os.getenv("SCROLL_CHUNK_MAX", "300"))   # 每次滚动最大像素

    # 打字速度
    TYPING_SPEED_MIN = int(os.getenv("TYPING_SPEED_MIN", "50"))    # ms 每字符最小间隔
    TYPING_SPEED_MAX = int(os.getenv("TYPING_SPEED_MAX", "150"))   # ms 每字符最大间隔
    TYPING_WORD_PAUSE = float(os.getenv("TYPING_WORD_PAUSE", "0.2"))  # 词边界暂停（秒）
    TYPING_THINK_PAUSE = float(os.getenv("TYPING_THINK_PAUSE", "0.5"))  # 思考暂停概率
    TYPING_THINK_DURATION = float(os.getenv("TYPING_THINK_DURATION", "1.0"))  # 思考暂停时长

    # 等待时间
    THINK_PAUSE_MIN = float(os.getenv("THINK_PAUSE_MIN", "0.5"))   # 思考暂停最小时间（秒）
    THINK_PAUSE_MAX = float(os.getenv("THINK_PAUSE_MAX", "3.0"))   # 思考暂停最大时间（秒）
    PAGE_LOAD_TIMEOUT = float(os.getenv("PAGE_LOAD_TIMEOUT", "30.0"))  # 页面加载超时
    NETWORK_IDLE_TIMEOUT = float(os.getenv("NETWORK_IDLE_TIMEOUT", "5.0"))  # 网络空闲超时

    # 随机化因子
    RANDOM_FACTOR = float(os.getenv("RANDOM_FACTOR", "0.3"))       # 所有时间的随机变化因子

    # 会话管理（参考XiaohongshuSkills）
    SESSION_CACHE_DIR = os.getenv("SESSION_CACHE_DIR", "/tmp/xhs_session")
    SESSION_CACHE_HOURS = int(os.getenv("SESSION_CACHE_HOURS", "12"))  # 会话有效期（小时）


# ==================== 调度器配置 ====================

class SchedulerConfig:
    """调度器配置（精细时间控制）。"""

    # 检查间隔
    CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))  # 每分钟检查
    BASE_CYCLE_SECONDS = int(os.getenv("BASE_CYCLE_SECONDS", "600"))  # 10分钟周期

    # 随机等待（防封号）
    RANDOM_WAIT_MIN = int(os.getenv("RANDOM_WAIT_MIN", "0"))
    RANDOM_WAIT_MAX = int(os.getenv("RANDOM_WAIT_MAX", "300"))  # 0-5分钟

    # 搜索间隔
    SEARCH_DELAY_MIN = float(os.getenv("SEARCH_DELAY_MIN", "3"))
    SEARCH_DELAY_MAX = float(os.getenv("SEARCH_DELAY_MAX", "8"))

    # 详情获取间隔
    DETAIL_DELAY_MIN = float(os.getenv("DETAIL_DELAY_MIN", "2"))
    DETAIL_DELAY_MAX = float(os.getenv("DETAIL_DELAY_MAX", "5"))

    # 搜索限制
    SEARCH_LIMIT = int(os.getenv("SEARCH_LIMIT", "10"))  # 每次搜索帖子数
    IMAGE_UPLOAD_DELAY = float(os.getenv("IMAGE_UPLOAD_DELAY", "0.5"))  # 图片上传间隔

    # ==================== 高峰时段规避 ====================

    # 高峰时段（开始小时, 结束小时）
    # 格式: "12-14,18-22"
    PEAK_HOURS_STR = os.getenv("PEAK_HOURS", "12-14,18-22")

    @classmethod
    def get_peak_hours(cls) -> List[Tuple[int, int]]:
        """解析高峰时段配置。"""
        try:
            pairs = []
            for pair in cls.PEAK_HOURS_STR.split(","):
                start, end = pair.strip().split("-")
                pairs.append((int(start), int(end)))
            return pairs
        except Exception:
            return [(12, 14), (18, 22)]  # 默认值

    PEAK_HOURS = property(get_peak_hours)

    # 高峰时段延迟倍数
    PEAK_DELAY_MULTIPLIER = float(os.getenv("PEAK_DELAY_MULTIPLIER", "2.5"))

    # 是否启用高峰规避
    PEAK_AVOIDANCE_ENABLED = os.getenv("PEAK_AVOIDANCE_ENABLED", "true").lower() == "true"

    # ==================== 重试机制 ====================

    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_BACKOFF_BASE = float(os.getenv("RETRY_BACKOFF_BASE", "2.0"))
    RETRY_DELAY_MAX = int(os.getenv("RETRY_DELAY_MAX", "3600"))  # 1小时
    RETRY_PRIORITY_DOWNGRADE = os.getenv("RETRY_PRIORITY_DOWNGRADE", "true").lower() == "true"


# ==================== CDP浏览器配置 ====================

class CDPConfig:
    """Chrome DevTools Protocol 配置。"""

    HOST = os.getenv("CDP_HOST", "192.168.100.4")
    PORT = int(os.getenv("CDP_PORT", "9224"))

    # 是否启用人类行为模拟
    USE_HUMAN_BEHAVIOR = os.getenv("USE_HUMAN_BEHAVIOR", "true").lower() == "true"

    # 连接超时
    CONNECT_TIMEOUT = float(os.getenv("CDP_CONNECT_TIMEOUT", "30.0"))

    # 请求超时
    REQUEST_TIMEOUT = float(os.getenv("CDP_REQUEST_TIMEOUT", "30.0"))


# ==================== 数据库配置 ====================

class DatabaseConfig:
    """MySQL 数据库配置。"""

    HOST = os.getenv("DB_HOST", "localhost")
    PORT = int(os.getenv("DB_PORT", "3306"))
    USER = os.getenv("DB_USER", "root")
    PASSWORD = os.getenv("DB_PASSWORD", "")
    DATABASE = os.getenv("DB_DATABASE", "xhs_notes")

    # 连接池大小
    POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))

    # 连接超时
    CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))


# ==================== 图床配置 ====================

class LskyProConfig:
    """Lsky Pro 图床配置。"""

    URL = os.getenv("LSKY_PRO_URL", "http://192.168.100.4:5021")
    EMAIL = os.getenv("LSKY_PRO_EMAIL", "")
    PASSWORD = os.getenv("LSKY_PRO_PASSWORD", "")
    TOKEN = os.getenv("LSKY_PRO_TOKEN", "")

    # 图片临时目录
    TEMP_DIR = os.getenv("TEMP_DIR", "/tmp/xhs_images")

    # 上传超时
    UPLOAD_TIMEOUT = int(os.getenv("LSKY_UPLOAD_TIMEOUT", "30"))


# ==================== 常量配置 ====================

# 小红书URL常量
SEARCH_BASE_URL = "https://www.xiaohongshu.com/search_result"
XHS_HOME_URL = "https://www.xiaohongshu.com"

# 小红书CDN域名
XHS_CDN_DOMAINS = [
    "sns-webpic-qc.xhscdn.com",
    "sns-webpic-cn.xhscdn.com",
    "sns-webpic.xhscdn.com",
    "xhscdn.com",
]

# 图片预览后缀转换
IMAGE_PREVIEW_SUFFIXES = [
    "!nc_n_webp_prv_1",
    "!nc_n_webp_mw_1",
    "!nc_n_webp_prv",
    "!nc_n_webp_mw",
]

IMAGE_HD_SUFFIX = "!nd_dft_wlteh_webp_3"


def get_all_config() -> dict:
    """获取所有配置的字典形式（用于调试或API响应）。"""
    return {
        "human_behavior": {
            "mouse_speed_range": (HumanBehaviorConfig.MOUSE_SPEED_MIN, HumanBehaviorConfig.MOUSE_SPEED_MAX),
            "scroll_speed_range": (HumanBehaviorConfig.SCROLL_SPEED_MIN, HumanBehaviorConfig.SCROLL_SPEED_MAX),
            "typing_speed_range": (HumanBehaviorConfig.TYPING_SPEED_MIN, HumanBehaviorConfig.TYPING_SPEED_MAX),
            "session_cache_hours": HumanBehaviorConfig.SESSION_CACHE_HOURS,
        },
        "scheduler": {
            "check_interval": SchedulerConfig.CHECK_INTERVAL_SECONDS,
            "peak_hours": SchedulerConfig.get_peak_hours(),
            "peak_avoidance": SchedulerConfig.PEAK_AVOIDANCE_ENABLED,
            "max_retries": SchedulerConfig.MAX_RETRIES,
        },
        "cdp": {
            "host": CDPConfig.HOST,
            "port": CDPConfig.PORT,
            "human_behavior": CDPConfig.USE_HUMAN_BEHAVIOR,
        },
        "database": {
            "host": DatabaseConfig.HOST,
            "port": DatabaseConfig.PORT,
            "database": DatabaseConfig.DATABASE,
        },
        "lsky_pro": {
            "url": LskyProConfig.URL,
            "temp_dir": LskyProConfig.TEMP_DIR,
        },
    }


if __name__ == "__main__":
    print("=== 配置模块测试 ===")
    print(json.dumps(get_all_config(), indent=2, ensure_ascii=False))

    import json
    from datetime import datetime

    # 测试高峰时段检测
    peak_hours = SchedulerConfig.get_peak_hours()
    print(f"\n高峰时段: {peak_hours}")
    current_hour = datetime.now().hour
    is_peak = any(start <= current_hour < end for start, end in peak_hours)
    print(f"当前小时: {current_hour}, 是否高峰: {is_peak}")