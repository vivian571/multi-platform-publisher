from .base import BasePublisher

class ZhihuPublisher(BasePublisher):
    platform_name = 'zhihu'
    def __init__(self, account_name: str, platform_config: dict, common_config: 'Config'):
        super().__init__(account_name, platform_config, common_config)

    def publish(self, article):
        print(f"Publishing '{article.title}' to Zhihu...")
        # Placeholder for Zhihu publishing logic
        print("Zhihu publisher is not implemented yet.")
        return True
