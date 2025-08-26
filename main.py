#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
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
from publishers import get_publisher, BasePublisher
from utils.file_utils import move_file_to_published

logger = get_logger('main')

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

    def _process_file(self, file_path: str) -> None:
        """处理单个文件"""
        file_path_obj = Path(file_path).resolve()

        if str(file_path_obj) in self.processing_files:
            self.logger.info(f"文件 {file_path_obj.name} 正在处理中，跳过")
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
            account_name = rel_path.parts[0] if len(rel_path.parts) > 1 else 'default'

            for name, publisher in self.publishers.items():
                if account_name.lower() in name.lower() or account_name == 'default':
                    self.logger.info(f"使用发布器 {name} 处理文件: {file_path_obj.name}")
                    try:
                        success = publisher.publish(str(file_path_obj))
                        results[name] = success
                    except Exception as e:
                        self.logger.error(f"发布器 {name} 处理时发生异常: {e}", exc_info=True)
                        results[name] = False
            
            if not results:
                self.logger.warning(f"没有为文件 {file_path_obj.name} 找到匹配的发布器")
                return

            if all(results.values()):
                self.logger.info(f"文件 {file_path_obj.name} 成功发布到所有目标平台。")
                published_dir = self.config.get_paths().get('published_dir', 'published')
                move_file_to_published(file_path_obj, str(watch_dir), published_dir)
            else:
                failed_platforms = [k for k, v in results.items() if not v]
                self.logger.error(f"文件 {file_path_obj.name} 未能成功发布到: {', '.join(failed_platforms)}")

        except Exception as e:
            self.logger.error(f"处理文件时发生错误: {e}", exc_info=True)
        finally:
            self.processing_files.discard(str(file_path_obj))

def load_publishers(config: Config) -> Dict[str, 'BasePublisher']:
    """加载所有配置的发布器"""
    publishers = {}
    accounts = config.get('accounts', {})
    if not accounts:
        logger.warning("未找到账户配置")
        return publishers

    for account_name, account_config in accounts.items():
        if not isinstance(account_config, dict):
            logger.warning(f"账户 {account_name} 的配置不是字典格式，已跳过")
            continue
        
        platform = account_config.get('type', 'wechat').lower()
        try:
            publisher = get_publisher(platform, account_config, account_name)
            publishers[account_name] = publisher
            logger.info(f"已加载发布器: {account_name} ({platform})")
        except ValueError as e:
            logger.warning(f"不支持的发布平台 '{platform}' 或配置无效，账户: {account_name}。错误: {e}")
        except Exception as e:
            logger.error(f"加载发布器 {account_name} 时发生未知错误: {e}", exc_info=True)
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

def manual_file_check(watch_dir, logger):
    """手动轮询检查文件变化，用于调试"""
    logger.info("[Manual Check] 手动检查线程已启动。")
    file_mtimes = {}
    while True:
        try:
            for root, _, files in os.walk(watch_dir):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    try:
                        current_mtime = os.path.getmtime(filepath)
                        if filepath not in file_mtimes:
                            file_mtimes[filepath] = current_mtime
                            logger.info(f"[Manual Check] 开始追踪文件: {filepath}")
                        elif file_mtimes[filepath] != current_mtime:
                            logger.warning(f"[Manual Check] 检测到文件修改! -> {filepath}")
                            file_mtimes[filepath] = current_mtime
                    except FileNotFoundError:
                        if filepath in file_mtimes:
                            del file_mtimes[filepath]
                            logger.info(f"[Manual Check] 文件已删除: {filepath}")
                        continue
                    except Exception as e:
                        logger.error(f"[Manual Check] 检查文件时出错 {filepath}: {e}")
            time.sleep(5)  # 每5秒检查一次
        except (KeyboardInterrupt, SystemExit):
            logger.info("[Manual Check] 手动检查线程正在停止。")
            break
        except Exception as e:
            logger.error(f"[Manual Check] 线程发生严重错误: {e}")
            time.sleep(10)

def main():
    """主函数，负责程序的整体生命周期管理。"""
    # 1. 初始化和配置加载
    parser = argparse.ArgumentParser(description='多平台内容发布工具')
    parser.add_argument('--config', '-c', default='config.yaml', help='配置文件路径')
    parser.add_argument('--env', '-e', default='.env', help='环境变量文件路径')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    args = parser.parse_args()

    log_level = 'DEBUG' if args.debug else 'INFO'
    setup_logging(level=log_level)

    logger.info("--- 正在启动多平台内容发布工具 ---")
    try:
        config = Config(config_path=args.config, env_path=args.env)
        create_directories(config)
        publishers = load_publishers(config)
        if not publishers:
            logger.error("没有加载任何发布器，程序将退出。请检查您的配置。")
            return 1
    except Exception as e:
        logger.error(f"初始化失败: {e}", exc_info=True)
        return 1

    # 2. 开始手动轮询监控
    watch_dir = os.path.abspath(config.get_paths().get('watch_dir', 'documents'))
    logger.info(f"开始监控目录: {watch_dir}")
    if not os.path.exists(watch_dir):
        logger.error(f"错误：监控目录不存在: {watch_dir}")
        return 1

    event_handler = DocumentHandler(config, publishers)
    file_states = {}
    POLL_INTERVAL = 2  # 每2秒检查一次

    logger.info(f"--- 工具已启动，每 {POLL_INTERVAL} 秒轮询一次... 按 CTRL+C 退出 ---")

    try:
        while True:
            # 扫描目录获取当前所有md文件
            current_files = set()
            for root, _, files in os.walk(watch_dir):
                for file in files:
                    if file.endswith(('.md', '.markdown')):
                        current_files.add(os.path.join(root, file))
            
            # 检查文件变更
            for path in current_files:
                try:
                    mtime = os.path.getmtime(path)
                    if path not in file_states:
                        logger.info(f"发现新文件: {path}")
                        file_states[path] = mtime
                        event_handler._process_file(path)
                    elif file_states[path] != mtime:
                        logger.info(f"文件被修改: {path}")
                        file_states[path] = mtime
                        event_handler._process_file(path)
                except FileNotFoundError:
                    # 文件可能在扫描和获取mtime之间被删除
                    if path in file_states: del file_states[path]
                    continue
            
            # 检查已删除的文件
            deleted_files = set(file_states.keys()) - current_files
            for path in deleted_files:
                logger.info(f"文件被删除: {path}")
                del file_states[path]

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        logger.info("\n检测到手动中断 (CTRL+C)，程序正在退出...")
    finally:
        logger.info("轮询监控已停止。")
    
    return 0 # 正常退出

if __name__ == '__main__':
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