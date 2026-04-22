"""小红书自动搜索定时任务模块（优化版）。

功能：
1. 定时执行搜索任务（分钟级别，精细控制）
2. 高峰时段规避（避开12:00-14:00, 18:00-22:00）
3. 失败重试机制（指数退避）
4. 任务队列管理（优先级排序）
5. 随机时间间隔（防封号）
6. 支持图片上传到图床
7. 记录详细执行日志

用法：
    python main.py start-scheduler
"""

import random
import time
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from db import XhsDatabase
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入搜索模块
try:
    from xhs_search_cdp import search_and_detail, XHSCDPClient
except ImportError:
    print("[scheduler] 错误: 无法导入 xhs_search_cdp 模块")
    sys.exit(1)

# 导入图片上传模块
try:
    from upload_images import ImageUploader
except ImportError:
    print("[scheduler] 警告: 无法导入 upload_images 模块，图片上传功能不可用")
    ImageUploader = None


class SchedulerConfig:
    """调度器配置（精细时间控制）。"""

    # 检查间隔：每分钟检查一次（精细化控制）
    CHECK_INTERVAL_SECONDS = 60

    # 基础周期：10分钟（作为随机等待的基准）
    BASE_CYCLE_SECONDS = 600

    # 随机等待范围（周期开始前，防封号）
    RANDOM_WAIT_MIN = 0
    RANDOM_WAIT_MAX = 300  # 0-5分钟随机等待

    # 搜索间隔随机等待（防封号）
    SEARCH_DELAY_MIN = 3
    SEARCH_DELAY_MAX = 8

    # 详情获取间隔
    DETAIL_DELAY_MIN = 2
    DETAIL_DELAY_MAX = 5

    # 每次搜索帖子数
    SEARCH_LIMIT = 10

    # 图片上传间隔
    IMAGE_UPLOAD_DELAY = 0.5

    # ==================== 高峰时段规避 ====================

    # 高峰时段（小红书用户活跃高峰）
    # (开始小时, 结束小时)
    PEAK_HOURS = [(12, 14), (18, 22)]

    # 高峰时段延迟倍数（高峰时更慢）
    PEAK_DELAY_MULTIPLIER = 2.5

    # 是否启用高峰规避
    PEAK_AVOIDANCE_ENABLED = True

    # ==================== 重试机制 ====================

    # 最大重试次数
    MAX_RETRIES = 3

    # 重试退避基数（指数退避）
    RETRY_BACKOFF_BASE = 2.0

    # 最大重试延迟（秒）
    RETRY_DELAY_MAX = 3600  # 1小时

    # 重试失败后降低优先级
    RETRY_PRIORITY_DOWNGRADE = True


class TaskQueueManager:
    """任务队列管理器 - 管理调度任务的优先级和状态。"""

    def __init__(self, db: XhsDatabase):
        self.db = db
        self.task_queue: List[Dict[str, Any]] = []
        self.running_tasks: Dict[str, Dict] = {}  # 正在执行的任务
        self.failed_tasks: Dict[str, int] = {}  # 失败计数

    def refresh_queue(self) -> None:
        """刷新任务队列（从数据库获取最新配置）。"""
        keywords = self.db.get_auto_search_keywords()
        self.task_queue = sorted(
            keywords,
            key=lambda k: (
                # 优先级排序：high > normal > low
                {'high': 0, 'normal': 1, 'low': 2}.get(k.get('priority', 'normal'), 1),
                # 然后按下次执行时间
                k.get('next_search_time') or k.get('last_search_time') or ''
            )
        )
        print(f"[scheduler] 任务队列刷新: {len(self.task_queue)} 个任务")

    def get_next_task(self) -> Optional[Dict[str, Any]]:
        """获取下一个待执行任务。"""
        if not self.task_queue:
            self.refresh_queue()

        for task in self.task_queue:
            keyword = task.get('keyword')
            # 跳过正在执行的任务
            if keyword in self.running_tasks:
                continue
            return task

        return None

    def mark_task_running(self, keyword: str) -> None:
        """标记任务开始执行。"""
        self.running_tasks[keyword] = {
            'start_time': datetime.now(),
            'progress': 0,
            'status': 'running'
        }

    def mark_task_complete(self, keyword: str) -> None:
        """标记任务完成。"""
        if keyword in self.running_tasks:
            del self.running_tasks[keyword]
        # 重置失败计数
        if keyword in self.failed_tasks:
            del self.failed_tasks[keyword]
        self.db.reset_retry_count(keyword)

    def mark_task_failed(self, keyword: str, error: str) -> None:
        """标记任务失败（增加重试计数）。"""
        if keyword in self.running_tasks:
            del self.running_tasks[keyword]

        # 增加失败计数
        self.failed_tasks[keyword] = self.failed_tasks.get(keyword, 0) + 1
        self.db.increment_retry_count(keyword, error)

        # 如果超过最大重试次数，降低优先级
        if self.failed_tasks[keyword] >= SchedulerConfig.MAX_RETRIES:
            if SchedulerConfig.RETRY_PRIORITY_DOWNGRADE:
                self.db.update_keyword_priority(keyword, 'low')
                print(f"[scheduler] 关键词 {keyword} 失败次数过多，优先级降为 low")

    def get_retry_delay(self, keyword: str) -> int:
        """计算重试延迟（指数退避）。"""
        fail_count = self.failed_tasks.get(keyword, 0)
        base_delay = 60  # 1分钟基础延迟

        delay = base_delay * (SchedulerConfig.RETRY_BACKOFF_BASE ** fail_count)
        return min(delay, SchedulerConfig.RETRY_DELAY_MAX)

    def get_running_count(self) -> int:
        """获取正在执行的任务数。"""
        return len(self.running_tasks)

    def get_status(self) -> Dict[str, Any]:
        """获取队列状态。"""
        return {
            'queue_size': len(self.task_queue),
            'running_count': self.get_running_count(),
            'running_tasks': list(self.running_tasks.keys()),
            'failed_count': len(self.failed_tasks),
        }


def is_peak_time() -> bool:
    """检查当前是否在高峰时段。

    Returns:
        True: 在高峰时段，False: 非高峰时段
    """
    if not SchedulerConfig.PEAK_AVOIDANCE_ENABLED:
        return False

    current_hour = datetime.now().hour

    for start, end in SchedulerConfig.PEAK_HOURS:
        if start <= current_hour < end:
            return True

    return False


def get_peak_delay_factor() -> float:
    """获取高峰时段延迟倍数。"""
    return SchedulerConfig.PEAK_DELAY_MULTIPLIER if is_peak_time() else 1.0


def calculate_next_search_time(interval_hours: float, last_time: datetime = None) -> datetime:
    """计算下次搜索时间（考虑高峰规避和随机抖动）。

    Args:
        interval_hours: 搜索间隔（小时，支持小数如0.1=6分钟）
        last_time: 上次搜索时间（None则从现在开始）

    Returns:
        下次计划搜索时间
    """
    if last_time is None:
        last_time = datetime.now()

    # 基础间隔（小时转秒）
    base_seconds = interval_hours * 3600

    # 高峰时段增加延迟
    delay_factor = get_peak_delay_factor()
    adjusted_seconds = base_seconds * delay_factor

    # 随机抖动（±10%）
    jitter = adjusted_seconds * random.uniform(-0.1, 0.1)
    final_seconds = adjusted_seconds + jitter

    next_time = last_time + timedelta(seconds=max(0, final_seconds))

    # 如果计算出的时间在高峰时段，尝试推迟到高峰结束后
    if is_peak_time() and SchedulerConfig.PEAK_AVOIDANCE_ENABLED:
        current_hour = datetime.now().hour
        for start, end in SchedulerConfig.PEAK_HOURS:
            if start <= next_time.hour < end:
                # 推迟到高峰结束
                next_time = next_time.replace(hour=end, minute=0, second=0)
                print(f"[scheduler] 推迟搜索到高峰结束后: {next_time}")
                break

    return next_time


class XhsScheduler:
    """小红书定时搜索调度器（优化版）。"""

    def __init__(self, upload_images: bool = True):
        self.db = XhsDatabase()
        self.upload_images = upload_images
        self.image_uploader = None
        self.running = False
        self.task_queue = TaskQueueManager(self.db)
        self.cycle_count = 0

        # 初始化图片上传器
        if upload_images and ImageUploader:
            try:
                self.image_uploader = ImageUploader()
                print("[scheduler] 图片上传功能已启用")
            except Exception as e:
                print(f"[scheduler] 图片上传器初始化失败: {e}")
                self.upload_images = False

        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """处理终止信号。"""
        print(f"\n[scheduler] 收到终止信号 {signum}，正在停止...")
        self.running = False

    def init(self) -> bool:
        """初始化数据库。"""
        if not self.db.init_database():
            print("[scheduler] 数据库初始化失败")
            return False
        return True

    def should_search(self, keyword_config: Dict[str, Any]) -> bool:
        """检查是否应该执行搜索。

        Args:
            keyword_config: 关键词配置（包含 search_interval, last_search_time, next_search_time）

        Returns:
            True: 需要执行搜索
            False: 还不到搜索时间
        """
        search_interval = keyword_config.get('search_interval', 24)  # 小时（支持小数）
        last_search_time = keyword_config.get('last_search_time')
        next_search_time = keyword_config.get('next_search_time')

        # 如果有预计算的下次搜索时间，直接比较
        if next_search_time:
            if isinstance(next_search_time, str):
                try:
                    next_search_time = datetime.fromisoformat(next_search_time)
                except ValueError:
                    pass
            if isinstance(next_search_time, datetime):
                return datetime.now() >= next_search_time

        # 否则基于上次搜索时间和间隔计算
        if not last_search_time:
            # 没有上次搜索记录，应该执行
            return True

        # 解析时间
        if isinstance(last_search_time, str):
            try:
                last_search_time = datetime.fromisoformat(last_search_time)
            except ValueError:
                return True

        # 计算下次搜索时间
        next_time = calculate_next_search_time(search_interval, last_search_time)
        now = datetime.now()

        return now >= next_time

    def _process_images_for_note(self, note: Dict[str, Any]) -> Dict[str, Any]:
        """处理单个帖子的图片，上传到图床。

        Returns:
            处理后的帖子数据，包含上传统计
        """
        if not self.image_uploader:
            return note

        images = note.get("images", [])
        if not images:
            note["images_upload_success"] = 0
            note["images_upload_fail"] = 0
            return note

        print(f"[scheduler] 处理帖子 {note.get('id', '')} 的 {len(images)} 张图片")

        new_images = []
        upload_success = 0
        upload_fail = 0

        for i, img_url in enumerate(images):
            print(f"[scheduler] 上传第 {i+1}/{len(images)} 张图片...")

            result = self.image_uploader.upload_image(img_url)

            if result.get("success"):
                new_url = result.get("url", "")
                new_images.append(new_url)
                upload_success += 1
            else:
                # 上传失败，保留原链接
                new_images.append(img_url)
                upload_fail += 1

            # 上传间隔
            if i < len(images) - 1:
                time.sleep(SchedulerConfig.IMAGE_UPLOAD_DELAY)

        note["images"] = new_images
        note["images_upload_success"] = upload_success
        note["images_upload_fail"] = upload_fail

        return note

    def execute_search(self, keyword: str) -> Dict[str, Any]:
        """执行单次搜索任务。

        Args:
            keyword: 搜索关键词

        Returns:
            执行结果统计
        """
        start_time = time.time()

        result = {
            "keyword": keyword,
            "posts_found": 0,
            "posts_inserted": 0,
            "posts_skipped": 0,
            "images_found": 0,
            "images_uploaded": 0,
            "images_failed": 0,
            "duration_seconds": 0,
            "error": None,
        }

        try:
            print(f"[scheduler] 开始搜索: {keyword}")

            # 标记任务开始
            self.task_queue.mark_task_running(keyword)

            # 高峰时段增加延迟
            delay_factor = get_peak_delay_factor()
            base_delay = random.uniform(SchedulerConfig.DETAIL_DELAY_MIN, SchedulerConfig.DETAIL_DELAY_MAX)
            actual_delay = base_delay * delay_factor

            # 执行搜索（获取详情）
            search_result = search_and_detail(
                keyword,
                limit=SchedulerConfig.SEARCH_LIMIT,
                delay=actual_delay,
                sort_by="general"
            )

            if not search_result.get("success", False):
                result["error"] = search_result.get("error", "搜索失败")
                print(f"[scheduler] 搜索失败: {result['error']}")

                # 标记失败（用于重试机制）
                self.task_queue.mark_task_failed(keyword, result["error"])

                return result

            notes = search_result.get("notes", [])
            result["posts_found"] = len(notes)
            print(f"[scheduler] 搜索到 {len(notes)} 条帖子")

            # 处理每个帖子
            for note in notes:
                note_id = note.get("id", "")
                note_url = note.get("url", "")

                # 随机等待（防封号）
                wait_time = random.uniform(SchedulerConfig.DETAIL_DELAY_MIN, SchedulerConfig.DETAIL_DELAY_MAX)
                wait_time *= get_peak_delay_factor()  # 高峰时段更慢
                print(f"[scheduler] 等待 {wait_time:.1f} 秒...")
                time.sleep(wait_time)

                # 检查是否重复
                if self.db.is_note_exists(note_id=note_id, url=note_url):
                    print(f"[scheduler] 跳过重复帖子: {note_id}")
                    result["posts_skipped"] += 1
                    continue

                # 处理图片上传
                if self.upload_images:
                    note = self._process_images_for_note(note)
                    result["images_found"] += len(note.get("images", []))
                    result["images_uploaded"] += note.get("images_upload_success", 0)
                    result["images_failed"] += note.get("images_upload_fail", 0)

                # 存入数据库
                if self.db.insert_note(note, keyword, "general"):
                    result["posts_inserted"] += 1
                    print(f"[scheduler] 入库成功: {note_id}")
                else:
                    result["posts_skipped"] += 1

            # 更新上次搜索时间
            self.db.update_last_search_time(keyword)

            # 计算并保存下次搜索时间
            search_interval = 24  # 默认24小时
            # 从配置获取实际间隔
            keywords_config = self.db.get_auto_search_keywords()
            for kc in keywords_config:
                if kc.get('keyword') == keyword:
                    search_interval = kc.get('search_interval', 24)
                    break

            next_time = calculate_next_search_time(search_interval, datetime.now())
            self.db.update_next_search_time(keyword, next_time)

            # 标记任务完成
            self.task_queue.mark_task_complete(keyword)

        except Exception as e:
            result["error"] = str(e)
            print(f"[scheduler] 执行异常: {e}")
            self.task_queue.mark_task_failed(keyword, str(e))

        result["duration_seconds"] = int(time.time() - start_time)
        return result

    def run_cycle(self):
        """执行一个完整的搜索周期。"""
        self.cycle_count += 1
        print(f"[scheduler] ===== 开始搜索周期 #{self.cycle_count} =====")
        print(f"[scheduler] 时间: {datetime.now().isoformat()}")

        # 高峰时段检测
        if is_peak_time():
            print(f"[scheduler] 当前为高峰时段，将增加延迟 {SchedulerConfig.PEAK_DELAY_MULTIPLIER}x")

        # 获取任务队列状态
        queue_status = self.task_queue.get_status()
        print(f"[scheduler] 任务队列: {queue_status['queue_size']} 个待执行, {queue_status['running_count']} 个运行中")

        # 刷新任务队列
        self.task_queue.refresh_queue()

        # 获取需要自动搜索的关键词
        keywords = self.db.get_auto_search_keywords()

        if not keywords:
            print("[scheduler] 没有需要自动搜索的关键词")
            return

        print(f"[scheduler] 找到 {len(keywords)} 个自动搜索关键词")

        for keyword_config in keywords:
            keyword = keyword_config.get('keyword')

            # 检查重试状态
            retry_count = keyword_config.get('retry_count', 0)
            if retry_count >= SchedulerConfig.MAX_RETRIES:
                # 计算重试延迟
                retry_delay = self.task_queue.get_retry_delay(keyword)
                last_error_time = keyword_config.get('last_search_time')

                if last_error_time:
                    if isinstance(last_error_time, str):
                        try:
                            last_error_time = datetime.fromisoformat(last_error_time)
                        except ValueError:
                            pass

                    if isinstance(last_error_time, datetime):
                        elapsed = (datetime.now() - last_error_time).total_seconds()
                        if elapsed < retry_delay:
                            print(f"[scheduler] 跳过 {keyword}: 重试等待中 (需等待 {retry_delay}s, 已过 {elapsed:.0f}s)")
                            continue

            # 检查是否应该执行搜索
            if not self.should_search(keyword_config):
                print(f"[scheduler] 跳过 {keyword}：未到搜索时间")
                continue

            # 随机等待（防封号）
            wait_time = random.uniform(SchedulerConfig.SEARCH_DELAY_MIN, SchedulerConfig.SEARCH_DELAY_MAX)
            wait_time *= get_peak_delay_factor()
            print(f"[scheduler] 搜索前等待 {wait_time:.1f} 秒...")
            time.sleep(wait_time)

            # 执行搜索
            result = self.execute_search(keyword)

            # 记录日志
            self.db.log_search_result(
                keyword=result["keyword"],
                posts_found=result["posts_found"],
                posts_inserted=result["posts_inserted"],
                posts_skipped=result["posts_skipped"],
                images_found=result["images_found"],
                images_uploaded=result["images_uploaded"],
                images_failed=result["images_failed"],
                duration_seconds=result["duration_seconds"],
                error_message=result["error"],
            )

            print(f"[scheduler] 搜索完成: {keyword}")
            print(f"[scheduler] 发现: {result['posts_found']}, 入库: {result['posts_inserted']}, 跳过: {result['posts_skipped']}")
            print(f"[scheduler] 图片: 发现 {result['images_found']}, 上传 {result['images_uploaded']}, 失败 {result['images_failed']}")
            print(f"[scheduler] 耗时: {result['duration_seconds']} 秒")

        print(f"[scheduler] ===== 周期 #{self.cycle_count} 结束 =====")

    def run_scheduler(self):
        """运行调度器主循环（精细时间控制）。"""
        print("[scheduler] 调度器启动（优化版）")
        print(f"[scheduler] 检查间隔: {SchedulerConfig.CHECK_INTERVAL_SECONDS} 秒")
        print(f"[scheduler] 高峰时段规避: {'启用' if SchedulerConfig.PEAK_AVOIDANCE_ENABLED else '禁用'}")
        if SchedulerConfig.PEAK_AVOIDANCE_ENABLED:
            print(f"[scheduler] 高峰时段: {SchedulerConfig.PEAK_HOURS}")
        print(f"[scheduler] 最大重试次数: {SchedulerConfig.MAX_RETRIES}")
        print(f"[scheduler] 图片上传: {'启用' if self.upload_images else '禁用'}")

        self.running = True

        while self.running:
            # 随机等待（周期开始前）
            wait_time = random.randint(SchedulerConfig.RANDOM_WAIT_MIN, SchedulerConfig.RANDOM_WAIT_MAX)
            if wait_time > 0:
                print(f"[scheduler] 周期开始前随机等待 {wait_time} 秒 ({wait_time/60:.1f} 分钟)...")

            # 分段等待，以便响应终止信号
            while wait_time > 0 and self.running:
                sleep_chunk = min(wait_time, SchedulerConfig.CHECK_INTERVAL_SECONDS)
                time.sleep(sleep_chunk)
                wait_time -= sleep_chunk

            if not self.running:
                break

            # 执行搜索周期
            self.run_cycle()

            # 等待下一个周期（检查间隔）
            remaining_time = SchedulerConfig.BASE_CYCLE_SECONDS
            while remaining_time > 0 and self.running:
                sleep_chunk = min(remaining_time, SchedulerConfig.CHECK_INTERVAL_SECONDS)
                time.sleep(sleep_chunk)
                remaining_time -= sleep_chunk

        print("[scheduler] 调度器已停止")


def run_scheduler(upload_images: bool = True):
    """启动调度器（入口函数）。"""
    scheduler = XhsScheduler(upload_images=upload_images)

    if not scheduler.init():
        print("[scheduler] 初始化失败，退出")
        return False

    scheduler.run_scheduler()
    return True


if __name__ == "__main__":
    run_scheduler()