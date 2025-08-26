from .base_publisher import BasePublisher

class ToutiaoPublisher(BasePublisher):
    def __init__(self, account_info):
        super().__init__(account_info)

    def publish(self, article):
        print(f"Publishing '{article.title}' to Toutiao...")
        # Placeholder for Toutiao publishing logic
        print("Toutiao publisher is not implemented yet.")
        return True
