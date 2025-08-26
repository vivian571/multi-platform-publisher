"""
多平台内容发布器
"""

__version__ = '0.2.0'

from .base_publisher import BasePublisher
from .wechat_publisher import WeChatPublisher
from .juejin_publisher import JuejinPublisher
from .csdn_publisher import CSDNPublisher

# 发布器注册表
PUBLISHER_REGISTRY = {
    'wechat': WeChatPublisher,
    'juejin': JuejinPublisher,
    'csdn': CSDNPublisher,
}

def get_publisher(platform: str, config: dict, account_name: str) -> BasePublisher:
    """
    根据平台名称获取发布器实例
    
    Args:
        platform: 平台名称，如 'wechat', 'juejin', 'csdn' 等
        config: 发布器配置
        account_name: 账户名称
        
    Returns:
        发布器实例
        
    Raises:
        ValueError: 当平台不受支持时抛出异常
    """
    platform = platform.lower()
    if platform not in PUBLISHER_REGISTRY:
        raise ValueError(f"不支持的平台: {platform}")
    if platform == 'wechat':
        app_id = config.get('app_id')
        app_secret = config.get('app_secret')
        if not app_id or not app_secret:
            raise ValueError(f"账户 '{account_name}' 的配置缺少 'app_id' 或 'app_secret'")
        return WeChatPublisher(config, account_name)
    return PUBLISHER_REGISTRY[platform](config, account_name)
