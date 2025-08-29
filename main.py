#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
from pathlib import Path
import argparse
from pathlib import Path
from typing import Dict
import logging
# from watchdog.observers import Observer
# from watchdog.events import FileSystemEventHandler, LoggingEventHandler
# Watchdog 在当前环境下行为异常，我们用手动轮询替代。

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.absolute()))

from utils.config import Config
from utils.logger import setup_logging, get_logger
from publishers.base import BasePublisher
from utils.file_utils import move_file_to_published

logger = get_logger('main')

class AccountNameFilter(logging.Filter):
    """为没有 account_name 的日志记录添加默认值 'System'"""
    def filter(self, record):
        if not hasattr(record, 'account_name'):
            record.account_name = 'System'
        return True

class DocumentHandler:
    """处理文件发布逻辑"""
    def __init__(self, config: Config, publishers: Dict[str, BasePublisher]):
        self.config = config
        self.publishers = publishers
        self.logger = get_logger('handler')
        self.processing_files = set()

    def _is_markdown_file(self, file_path: str) -> bool:
        """检查文件是否是Markdown文件"""
        file_ext = Path(file_path).suffix.lower()
        watch_config = self.config.get_watch_config()
        allowed_exts = watch_config.get('file_types', ['.md', '.markdown'])
        return file_ext in [ext if ext.startswith('.') else f'.{ext}' for ext in allowed_exts]

    def _process_file(self, file_path: str, processed_files: set) -> None:
        """处理单个文件"""
        file_path_obj = Path(file_path).resolve()

        if str(file_path_obj) in self.processing_files:
            self.logger.info(f"文件 {file_path_obj.name} 正在处理中，跳过")
            return

        if file_path in processed_files:
            self.logger.info(f"文件 {file_path_obj.name} 已经处理过，跳过")
            return

        watch_dir = Path(self.config.get_paths().get('watch_dir', 'documents')).resolve()
        try:
            file_path_obj.relative_to(watch_dir)
        except ValueError:
            self.logger.warning(f"文件 {file_path_obj} 不在监控目录 {watch_dir} 中，跳过")
            return

        self.logger.info(f"检测到文件变更: {file_path_obj}")
        self.processing_files.add(str(file_path_obj))

        time.sleep(1)

        try:
            results = {}
            rel_path = file_path_obj.relative_to(watch_dir)
            account_name = rel_path.parts[0] if len(rel_path.parts) > 1 else None

            if not account_name:
                self.logger.warning(f"文件 {file_path_obj.name} 不在任何账户子目录下，跳过")
                return

            publisher = self.publishers.get(account_name)

            if not publisher:
                self.logger.warning(f"在 config.yaml 中未找到名为 '{account_name}' 的账户配置，跳过")
                return

            self.logger.info(f"使用发布器 {account_name} 处理文件: {file_path_obj.name}")
            try:
                success = publisher.publish(str(file_path_obj))
                results[account_name] = success
            except Exception as e:
                self.logger.error(f"发布器 {account_name} 处理时发生异常: {e}", exc_info=True)
                results[account_name] = False
            
            if not results:
                self.logger.warning(f"没有为文件 {file_path_obj.name} 找到匹配的发布器")
                return

            move_on_success = self.config.get('publish', {}).get('move_on_success', 'all').lower()

            if (move_on_success == 'all' and all(results.values())) or \
               (move_on_success == 'any' and any(results.values())):
                self.logger.info(f"文件 {file_path_obj.name} 发布成功，将被移动。")
                published_dir = self.config.get_paths().get('published_dir', 'published')
                move_file_to_published(file_path_obj, str(watch_dir), published_dir)
            else:
                failed_platforms = [k for k, v in results.items() if not v]
                self.logger.error(f"文件 {file_path_obj.name} 未能成功发布到: {', '.join(failed_platforms)}")

        except Exception as e:
            self.logger.error(f"处理文件时发生错误: {e}", exc_info=True)
        finally:
            self.processing_files.discard(str(file_path_obj))
            processed_files.add(file_path)

def load_publisher_classes(directory: str) -> Dict[str, type[BasePublisher]]:
    """动态加载指定目录下的所有发布器类。"""
    publisher_classes = {}
    publishers_dir = Path(__file__).parent / directory
    for filename in os.listdir(publishers_dir):
        if filename.endswith('.py') and not filename.startswith('__') and not filename.startswith('base'):
            module_name = f"{directory}.{filename[:-3]}"
            try:
                module = __import__(module_name, fromlist=['*'])
                for attr in dir(module):
                    cls = getattr(module, attr)
                    if isinstance(cls, type) and issubclass(cls, BasePublisher) and cls is not BasePublisher:
                        if hasattr(cls, 'platform_name') and isinstance(cls.platform_name, str):
                            publisher_classes[cls.platform_name] = cls
                            logger.debug(f"[System] - 动态加载发布器: {cls.platform_name}")
                        else:
                            logger.warning(f"[System] - 发布器类 {cls.__name__} 缺少 'platform_name' 属性，无法加载。")
            except ImportError as e:
                logger.error(f"[System] - 导入模块 {module_name} 失败: {e}")
    return publisher_classes

def initialize_publishers(config: Dict) -> Dict[str, BasePublisher]:
    """根据配置初始化所有发布器。"""
    publishers = {}
    common_config = config.get('common', {})
    accounts_config = config.get('accounts', {})
    publisher_classes = load_publisher_classes('publishers')

    if not accounts_config:
        logger.error("[System] - 配置文件 config.yaml 中未找到 'accounts' 部分。")
        return {}

    for account_name, account_config in accounts_config.items():
        platform = account_config.get('platform')
        if not platform:
            logger.error(f"[System] - 账户 '{account_name}' 缺少 'platform' 字段。")
            continue

        if platform not in publisher_classes:
            logger.warning(f"[System] - 未找到平台 '{platform}' 的发布器实现 (账户: {account_name})。")
            continue

        PublisherClass = publisher_classes[platform]
        publishers[account_name] = PublisherClass(account_name, account_config, common_config)
        logger.info(f"[System] - 成功加载账户: {account_name} (平台: {platform})")

    return publishers

def create_directories(config: Config):
    """创建必要的目录"""
    paths = config.get_paths()
    watch_dir = Path(paths.get('watch_dir', 'documents'))
    published_dir = Path(paths.get('published_dir', 'published'))
    
    watch_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"监控目录: {watch_dir.absolute()}")
    logger.info(f"已发布目录: {published_dir.absolute()}")

def main():
    """主函数，负责程序的整体生命周期管理。"""
    print("[诊断] main() 函数已开始执行。")
    # 1. 初始化和配置加载
    parser = argparse.ArgumentParser(description='多平台内容发布工具')
    parser.add_argument('--once', action='store_true', help='只发布一次，然后退出')
    parser.add_argument('--config', '-c', default='config.yaml', help='配置文件路径')
    parser.add_argument('--env', '-e', default='.env', help='环境变量文件路径')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')

    args = parser.parse_args()

    # 提前加载配置以获取日志设置
    try:
        config = Config(config_path=args.config, env_path=args.env)
    except Exception as e:
        logging.basicConfig()
        logging.error(f"初始化配置失败: {e}", exc_info=True)
        return 1

    log_file = config.get('common.log_file', 'publisher.log')
    log_level = logging.DEBUG if args.debug else logging.INFO

    # 创建一个顶级的日志记录器
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # 创建文件处理器，强制使用 UTF-8 编码
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(log_level)

    # 创建控制台处理器，强制使用 UTF-8 编码
    ch = logging.StreamHandler()
    ch.setLevel(log_level)

    # 创建格式化器并将其添加到处理器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(account_name)s] - %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # 创建并添加自定义过滤器
    account_filter = AccountNameFilter()
    fh.addFilter(account_filter)
    ch.addFilter(account_filter)

    # 将处理器添加到日志记录器
    logger.addHandler(fh)
    logger.addHandler(ch)

    logger.info("--- 正在启动多平台内容发布工具 ---")
    try:
        create_directories(config)
        publishers = initialize_publishers(config.get_config())
        if not publishers:
            logger.error("没有加载任何发布器，程序将退出。请检查您的配置。")
            return 1
    except Exception as e:
        logger.error(f"初始化失败: {e}", exc_info=True)
        return 1

    # 2. 初始化文件监控
    watch_dir = Path(config.get_paths().get('watch_dir', 'documents')).resolve()
    published_dir = Path(config.get_paths().get('published_dir', 'published')).resolve()

    logger.info(f"监控目录: {watch_dir}")
    logger.info(f"已发布目录: {published_dir}")

    if not watch_dir.exists():
        logger.error(f"错误：监控目录不存在: {watch_dir}")
        return 1

    event_handler = DocumentHandler(config, publishers)
    processed_files = set()
    file_states = {}
    POLL_INTERVAL = 2  # 每2秒检查一次

    logger.info(f"--- 启动文件监控轮询 (每 {POLL_INTERVAL} 秒)... 按 CTRL+C 退出 ---")

    try:
        while True:
            print(f"\n[{time.strftime('%H:%M:%S')}] --- 正在轮询目录: {watch_dir}")
            # 扫描目录获取当前所有md文件
            current_files = set()
            for root, _, files in os.walk(watch_dir):
                for file in files:
                    if file.endswith(('.md', '.markdown')):
                        current_files.add(os.path.join(root, file))
            
            if not current_files:
                print(f"[{time.strftime('%H:%M:%S')}] -> 未发现 .md/.markdown 文件。")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] -> 发现文件: {[Path(f).name for f in current_files]}")

            # 检查文件变更
            for path in current_files:
                try:
                    mtime = os.path.getmtime(path)
                    print(f"[{time.strftime('%H:%M:%S')}]    - 正在检查: {Path(path).name} (修改时间: {mtime})")
                    if path not in file_states:
                        print(f"[{time.strftime('%H:%M:%S')}]      -> [发现新文件]，准备处理...")
                        logger.info(f"发现新文件: {path}")
                        file_states[path] = mtime
                        event_handler._process_file(path, processed_files)
                    elif file_states[path] != mtime:
                        print(f"[{time.strftime('%H:%M:%S')}]      -> [文件被修改] (旧时间: {file_states[path]})，准备处理...")
                        logger.info(f"文件被修改: {path}")
                        file_states[path] = mtime
                        event_handler._process_file(path, processed_files)
                except FileNotFoundError:
                    # 文件可能在扫描和获取mtime之间被删除
                    if path in file_states: del file_states[path]
                    continue
            
            # 检查已删除的文件
            deleted_files = set(file_states.keys()) - current_files
            for path in deleted_files:
                logger.info(f"文件被删除: {path}")
                del file_states[path]

            # 如果设置了 --once，则在处理完所有文件后退出
            if args.once:
                logger.info("已完成一次性发布任务，程序将退出。")
                break

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        logger.info("\n检测到手动中断 (CTRL+C)，程序正在退出...")
    finally:
        logger.info("轮询监控已停止。")
    
    return 0 # 正常退出

if __name__ == '__main__':
    print("[诊断] 程序启动，进入 __main__。")
    exit_code = 1
    try:
        exit_code = main()
    except Exception as e:
        # 在主函数之外捕获任何未预料到的异常
        print(f"\n程序发生致命错误，无法继续运行: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"--- 程序已退出，退出码: {exit_code} ---")
        sys.exit(exit_code)