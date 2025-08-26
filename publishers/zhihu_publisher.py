from .base_publisher import BasePublisher

class ZhihuPublisher(BasePublisher):
    def __init__(self, account_info):
        super().__init__(account_info)

    def publish(self, article):
        print(f"Publishing '{article.title}' to Zhihu...")
        # Placeholder for Zhihu publishing logic
        print("Zhihu publisher is not implemented yet.")
        return True
