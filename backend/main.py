"""小红书搜索入库主脚本。

功能：
1. 搜索小红书帖子
2. 自动存入 MySQL 数据库
3. 支持批量获取详情
4. 图片上传到 Lsky Pro 图床（可选）

用法：
    python main.py search "关键词"
    python main.py search-detail "关键词" --limit 5 --upload-images
    python main.py stats
    python main.py init-db
"""

import argparse
import json
import sys
import time
from typing import Dict, Any

from db import XhsDatabase, DatabaseConfig, test_connection
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入 CDP 搜索模块
try:
    from xhs_search_cdp import (
        search_notes,
        get_note_detail,
        search_and_detail,
        check_login,
        XHSCDPClient,
    )
except ImportError:
    print("[main] 错误: 无法导入 xhs_search_cdp 模块")
    print("[main] 请确保 xhs_search_cdp.py 在同一目录下")
    sys.exit(1)

# 导入图片上传模块（新版图片处理器）
try:
    from image_processor import ImageProcessor, ImageProcessorLogger, process_images_for_notes
except ImportError:
    print("[main] 警告: 无法导入 image_processor 模块，图片上传功能不可用")
    ImageProcessor = None
    process_images_for_notes = None


class XhsSearchToDB:
    """小红书搜索入库类。"""

    def __init__(self, upload_images: bool = True):  # 默认启用图片上传
        self.db = XhsDatabase()
        self.upload_images = upload_images
        self.image_uploader = None

        # 默认启用图片上传，初始化图片处理器
        if upload_images and ImageProcessor:
            try:
                from image_processor import ImageProcessorLogger
                logger = ImageProcessorLogger()
                self.image_uploader = ImageProcessor(logger=logger)
                print("[main] 图片上传功能已启用（新版处理器）")
            except Exception as e:
                print(f"[main] 图片处理器初始化失败: {e}")
                print("[main] 将直接存储原始图片链接")
                self.upload_images = False
        elif upload_images:
            print("[main] 警告: image_processor模块不可用，图片上传功能禁用")
            self.upload_images = False

    def init(self) -> bool:
        """初始化数据库连接和表结构。"""
        # 测试连接
        if not test_connection():
            print("[main] 数据库连接失败，请检查 .env 配置")
            return False

        # 初始化数据库
        if not self.db.init_database():
            print("[main] 数据库初始化失败")
            return False

        return True

    def search_and_store(self, keyword: str, limit: int = 10, sort_by: str = "general") -> Dict[str, Any]:
        """搜索并存储到数据库。"""
        print(f"[main] 搜索关键词: {keyword}, 数量: {limit}, 排序: {sort_by}")

        # 执行搜索
        result = search_notes(keyword, limit, sort_by, save=False)

        if not result.get("success", False):
            print(f"[main] 搜索失败: {result.get('error', '未知错误')}")
            return result

        notes = result.get("notes", [])
        print(f"[main] 搜索到 {len(notes)} 条帖子")

        # 存入数据库
        success_count = self.db.insert_notes_batch(notes, keyword, sort_by)
        print(f"[main] 成功入库 {success_count} 条帖子")

        result["stored_count"] = success_count
        return result

    def _process_images_for_note(self, note: Dict[str, Any]) -> Dict[str, Any]:
        """处理单个帖子的图片，上传到图床（使用新版处理器）。

        Args:
            note: 帖子数据

        Returns:
            处理后的帖子数据（images 字段替换为图床链接）
        """
        if not self.image_uploader:
            return note

        images = note.get("images", [])
        if not images:
            return note

        post_id = note.get("id", "")
        post_title = note.get("title", "")[:30]
        print(f"\n[main] ========== 帖子 [{post_id}] \"{post_title}\" 共{len(images)}张图片 ==========")

        # 使用新版图片处理器
        processed_note = self.image_uploader.process_images_for_note(note)

        return processed_note
    
    def search_detail_and_store(
        self,
        keyword: str,
        limit: int = 5,
        sort_by: str = "general",
        delay: float = 2.0,
        skip_existing: bool = True,
    ) -> Dict[str, Any]:
        """搜索、获取详情并存储到数据库。

        Args:
            keyword: 搜索关键词
            limit: 搜索数量
            sort_by: 排序方式
            delay: 请求间隔（秒）
            skip_existing: 是否跳过已存在的帖子（默认 True）
        """
        print(f"[main] 搜索并获取详情: {keyword}, 数量: {limit}")

        # 执行搜索和获取详情（传入db实例进行去重）
        result = search_and_detail(
            keyword, limit, delay, sort_by,
            db=self.db,  # 传入数据库实例用于去重检查
            skip_existing=skip_existing  # 获取详情前跳过已存在的帖子
        )

        if not result.get("success", False):
            print(f"[main] 搜索失败: {result.get('error', '未知错误')}")
            return result

        notes = result.get("notes", [])
        posts_skipped = result.get("posts_skipped", 0)
        print(f"[main] 获取到 {len(notes)} 条新详情，跳过 {posts_skipped} 条已存在帖子")
        
        # 如果启用图片上传，处理每张图片
        if self.upload_images and self.image_uploader:
            print(f"[main] 开始上传图片到图床...")
            total_images = sum(len(n.get("images", [])) for n in notes)
            print(f"[main] 共 {total_images} 张图片需要处理")
            
            processed_notes = []
            for note in notes:
                processed_note = self._process_images_for_note(note)
                processed_notes.append(processed_note)
            
            notes = processed_notes
            print(f"[main] 图片处理完成")

        # 存入数据库
        success_count = self.db.insert_notes_batch(notes, keyword, sort_by)
        print(f"[main] 成功入库 {success_count} 条帖子")

        result["stored_count"] = success_count
        return result

    def get_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息。"""
        return self.db.get_stats()

    def query_notes(self, keyword: str = None, limit: int = 50) -> list:
        """查询数据库中的帖子。"""
        return self.db.query_notes(keyword, limit)

    def check_browser_login(self) -> Dict[str, Any]:
        """检查浏览器登录状态。"""
        client = XHSCDPClient()
        return check_login(client)


def main():
    parser = argparse.ArgumentParser(
        prog="xhs-db",
        description="小红书搜索入库脚本",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init-db 命令
    sub = subparsers.add_parser("init-db", help="初始化数据库")
    sub.set_defaults(func=lambda a, x: print(json.dumps({"success": x.init()}, ensure_ascii=False)))

    # search 命令
    sub = subparsers.add_parser("search", help="搜索并入库")
    sub.add_argument("keyword", help="搜索关键词")
    sub.add_argument("--limit", "-n", type=int, default=10, help="结果数量")
    sub.add_argument("--sort", "-s", default="general", choices=["general", "popular", "latest"], help="排序方式")
    sub.set_defaults(func=lambda a, x: print(json.dumps(x.search_and_store(a.keyword, a.limit, a.sort), ensure_ascii=False, indent=2)))

    # search-detail 命令
    sub = subparsers.add_parser("search-detail", help="搜索获取详情并入库")
    sub.add_argument("keyword", help="搜索关键词")
    sub.add_argument("--limit", "-n", type=int, default=5, help="结果数量")
    sub.add_argument("--sort", "-s", default="general", choices=["general", "popular", "latest"], help="排序方式")
    sub.add_argument("--delay", "-d", type=float, default=2.0, help="请求间隔（秒）")
    sub.add_argument("--upload-images", "-u", action="store_true", help="上传图片到 Lsky Pro 图床")
    sub.add_argument("--skip-existing", action="store_true", default=True, help="跳过已存在的帖子（默认启用）")
    sub.add_argument("--no-skip", action="store_true", help="不跳过已存在的帖子")
    sub.set_defaults(func=lambda a, x: print(json.dumps(x.search_detail_and_store(
        a.keyword, a.limit, a.sort, a.delay, skip_existing=not a.no_skip
    ), ensure_ascii=False, indent=2)))

    # stats 命令
    sub = subparsers.add_parser("stats", help="获取数据库统计")
    sub.set_defaults(func=lambda a, x: print(json.dumps(x.get_stats(), ensure_ascii=False, indent=2)))

    # query 命令
    sub = subparsers.add_parser("query", help="查询数据库帖子")
    sub.add_argument("--keyword", "-k", default=None, help="筛选关键词")
    sub.add_argument("--limit", "-n", type=int, default=50, help="结果数量")
    sub.set_defaults(func=lambda a, x: print(json.dumps(x.query_notes(a.keyword, a.limit), ensure_ascii=False, indent=2)))

    # check-login 命令
    sub = subparsers.add_parser("check-login", help="检查浏览器登录状态")
    sub.set_defaults(func=lambda a, x: print(json.dumps(x.check_browser_login(), ensure_ascii=False, indent=2)))

    # ==================== 定时任务和日志命令 ====================

    # start-scheduler 命令：启动定时任务
    sub = subparsers.add_parser("start-scheduler", help="启动定时搜索任务")
    sub.add_argument("--no-upload", "-n", action="store_true", help="禁用图片上传")
    sub.set_defaults(func=lambda a, x: _run_scheduler(a))

    # logs 命令：查看搜索日志
    sub = subparsers.add_parser("logs", help="查看搜索执行日志")
    sub.add_argument("--keyword", "-k", default=None, help="筛选关键词")
    sub.add_argument("--limit", "-n", type=int, default=20, help="日志数量")
    sub.set_defaults(func=lambda a, x: print(json.dumps(x.db.get_search_logs(a.keyword, a.limit), ensure_ascii=False, indent=2)))

    # ==================== Keywords 管理命令 ====================

    # keywords 命令：列出所有搜索词
    sub = subparsers.add_parser("keywords", help="列出所有配置的搜索词")
    sub.set_defaults(func=lambda a, x: print(json.dumps(x.db.get_keywords(), ensure_ascii=False, indent=2)))

    # add-keyword 命令：添加搜索词
    sub = subparsers.add_parser("add-keyword", help="添加搜索词")
    sub.add_argument("keyword", help="搜索关键词")
    sub.add_argument("--auto", "-a", action="store_true", help="启用自动搜索")
    sub.add_argument("--interval", "-i", type=int, default=24, help="自动搜索间隔（小时）")
    sub.set_defaults(func=lambda a, x: print(json.dumps(x.db.add_keyword(a.keyword, a.auto, a.interval), ensure_ascii=False, indent=2)))

    # remove-keyword 命令：删除搜索词
    sub = subparsers.add_parser("remove-keyword", help="删除搜索词")
    sub.add_argument("keyword", help="搜索关键词")
    sub.set_defaults(func=lambda a, x: print(json.dumps(x.db.remove_keyword(a.keyword), ensure_ascii=False, indent=2)))

    # enable-keyword 命令：启用自动搜索
    sub = subparsers.add_parser("enable-keyword", help="启用自动搜索")
    sub.add_argument("keyword", help="搜索关键词")
    sub.add_argument("--interval", "-i", type=int, default=24, help="自动搜索间隔（小时）")
    sub.set_defaults(func=lambda a, x: print(json.dumps(x.db.enable_auto_search(a.keyword, a.interval), ensure_ascii=False, indent=2)))

    # disable-keyword 命令：禁用自动搜索
    sub = subparsers.add_parser("disable-keyword", help="禁用自动搜索")
    sub.add_argument("keyword", help="搜索关键词")
    sub.set_defaults(func=lambda a, x: print(json.dumps(x.db.disable_auto_search(a.keyword), ensure_ascii=False, indent=2)))

    args = parser.parse_args()

    # 创建实例并初始化
    # 根据 --upload-images 参数决定是否启用图片上传
    upload_images = getattr(args, 'upload_images', False)
    xhs = XhsSearchToDB(upload_images=upload_images)

    # 执行命令（除了 init-db，其他命令都需要初始化数据库）
    if args.command != "init-db":
        if not xhs.init():
            print(json.dumps({"success": False, "error": "数据库初始化失败"}, ensure_ascii=False))
            sys.exit(1)

    args.func(args, xhs)


def _run_scheduler(args):
    """运行调度器。"""
    from scheduler import run_scheduler
    upload_images = not args.no_upload
    run_scheduler(upload_images=upload_images)
    return True


if __name__ == "__main__":
    main()