from abc import ABC, abstractmethod
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

class AccountLogFilter(logging.Filter):
    """自定义日志过滤器，为日志记录添加账户名称。"""
    def __init__(self, account_name):
        super().__init__()
        self.account_name = account_name

    def filter(self, record):
        record.account_name = self.account_name
        return True

class BasePublisher(ABC):
    """发布器基类，定义所有发布器必须实现的接口"""
    
    def __init__(self, config: dict, account_name: str):
        self.config = config
        self.account_name = account_name
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.addFilter(AccountLogFilter(account_name))
        self.logger.setLevel(logging.INFO)
        
    def log_debug(self, message: str):
        """记录调试信息"""
        self.logger.debug(message)
        
    def log_info(self, message: str):
        """记录一般信息"""
        self.logger.info(f"ℹ️ {message}")
        
    def log_warning(self, message: str):
        """记录警告信息"""
        self.logger.warning(f"⚠️ {message}")
        
    def log_error(self, message: str, exc_info=False):
        """记录错误信息
        
        Args:
            message: 错误信息
            exc_info: 是否记录异常堆栈
        """
        self.logger.error(f"❌ {message}", exc_info=exc_info)
        
    def log_success(self, message: str):
        """记录成功信息"""
        self.logger.info(f"✅ {message}")
        
    @abstractmethod
    def publish(self, content_path: str, **kwargs) -> bool:
        """发布内容到平台
        
        Args:
            content_path: 内容文件路径
            **kwargs: 其他参数
            
        Returns:
            bool: 发布是否成功
        """
        pass
    
    @abstractmethod
    def upload_image(self, image_path: str) -> Optional[str]:
        """上传图片到平台
        
        Args:
            image_path: 本地图片路径
            
        Returns:
            str: 图片URL，上传失败返回None
        """
        pass
    
    def process_markdown(self, file_path: str) -> Tuple[str, dict]:
        """处理Markdown文件，返回HTML内容和元数据
        
        Args:
            file_path: Markdown文件路径
            
        Returns:
            tuple: (html_content, metadata)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 这里可以添加Markdown到HTML的转换逻辑
            # 暂时返回原始内容和空元数据
            return content, {}
            
        except Exception as e:
            self.logger.error(f"处理Markdown文件时出错: {e}")
            raise
            
    def log_success(self, message: str):
        """记录成功日志"""
        self.logger.info(f"✅ {message}")
        
    def log_error(self, message: str, exc_info=None):
        """记录错误日志"""
        self.logger.error(f"❌ {message}", exc_info=exc_info)
        
    def log_warning(self, message: str):
        """记录警告日志"""
        self.logger.warning(f"⚠️ {message}")
