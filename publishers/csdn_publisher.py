import os
import re
import time
import json
import uuid
import hashlib
import requests
from typing import Dict, Optional, List, Any, Tuple
from urllib.parse import urljoin, quote

from .base_publisher import BasePublisher

class CSDNPublisher(BasePublisher):
    """CSDN平台发布器"""
    
    BASE_URL = "https://mp.csdn.net"
    LOGIN_URL = "https://passport.csdn.net/v1/register/pc/login/doLogin"
    UPLOAD_IMAGE_URL = "https://mp-action.csdn.net/interact/wenhu/picture/upload"
    
    def __init__(self, config: dict, account_name: str):
        super().__init__(config, account_name)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://mp.csdn.net/',
            'Origin': 'https://mp.csdn.net',
        })
        self.username = None
        self.password = None
        self._login()
    
    def _get_csrf_token(self) -> Optional[str]:
        """获取CSRF Token"""
        try:
            response = self.session.get('https://bizapi.csdn.net/')
            match = re.search(r'window.csrfToken = "(.*?)"', response.text)
            if match:
                return match.group(1)
        except Exception as e:
            self.log_error(f"获取CSRF Token失败: {e}")
        return None
    
    def _login(self) -> bool:
        """登录CSDN账号"""
        self.username = self.config.get('username')
        self.password = self.config.get('password')
        
        if not self.username or not self.password:
            self.log_error("缺少CSDN账号或密码配置")
            return False
            
        try:
            # 获取登录页面，获取必要的cookies
            self.session.get('https://passport.csdn.net/login')
            
            # 获取CSRF Token
            csrf_token = self._get_csrf_token()
            if not csrf_token:
                self.log_error("获取CSRF Token失败")
                return False
            
            # 发送登录请求
            login_data = {
                'loginType': '1',
                'userIdentification': self.username,
                'pwdOrVerifyCode': self.password,
                'uaToken': '',
                'webUmidToken': '',
                'webSessionId': '',
                'account': '',
                'user': '0',
                'phone': '',
                'sms_code': '',
                'unionLoginType': 'qq',
                'accessToken': '',
                'uuid': str(uuid.uuid4()),
                'loginType': '1',
                'userIdentification': self.username,
                'pwdOrVerifyCode': self.password,
                'uaToken': '',
                'webUmidToken': '',
                'webSessionId': '',
                'account': '',
                'user': '0',
                'phone': '',
                'sms_code': '',
                'unionLoginType': 'qq',
                'accessToken': '',
                'uuid': str(uuid.uuid4())
            }
            
            headers = {
                'Content-Type': 'application/json;charset=UTF-8',
                'X-CSRF-TOKEN': csrf_token,
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://passport.csdn.net/login',
                'Origin': 'https://passport.csdn.net'
            }
            
            response = self.session.post(
                self.LOGIN_URL,
                json=login_data,
                headers=headers
            )
            
            if response.status_code != 200:
                self.log_error(f"登录失败: HTTP {response.status_code}")
                return False
                
            data = response.json()
            if data.get('code') != 200:
                self.log_error(f"登录失败: {data.get('message')}")
                return False
                
            self.log_success(f"登录成功: {data.get('data', {}).get('username')}")
            return True
            
        except Exception as e:
            self.log_error(f"登录过程中发生错误: {e}", exc_info=True)
            return False
    
    def upload_image(self, image_path: str) -> Optional[str]:
        """上传图片到CSDN"""
        try:
            with open(image_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(image_path), f, 'image/jpeg')
                }
                response = self.session.post(
                    self.UPLOAD_IMAGE_URL,
                    files=files,
                    headers={
                        'Referer': 'https://mp.csdn.net/mdeditor',
                        'Origin': 'https://mp.csdn.net'
                    }
                )
                
            if response.status_code != 200:
                self.log_error(f"上传图片失败: HTTP {response.status_code}")
                return None
                
            data = response.json()
            if data.get('code') != 200:
                self.log_error(f"上传图片失败: {data.get('message')}")
                return None
                
            image_url = data['data']['url']
            self.log_success(f"图片上传成功: {os.path.basename(image_path)}")
            return image_url
            
        except Exception as e:
            self.log_error(f"上传图片过程中发生错误: {e}", exc_info=True)
            return None
    
    def _process_content(self, content: str, image_dir: str) -> str:
        """处理内容中的图片"""
        # 使用正则表达式匹配Markdown图片
        def replace_image(match):
            alt_text = match.group(1)
            image_path = match.group(2)
            
            # 处理相对路径
            if not image_path.startswith(('http://', 'https://')):
                full_path = os.path.join(image_dir, image_path)
                if os.path.exists(full_path):
                    remote_url = self.upload_image(full_path)
                    if remote_url:
                        return f'![{alt_text}]({remote_url})'
            
            # 如果上传失败或已经是远程URL，则返回原内容
            return match.group(0)
        
        # 匹配Markdown图片语法 ![alt](url)
        content = re.sub(r'!\[(.*?)\]\((.*?)\)', replace_image, content)
        
        return content
    
    def publish(self, content_path: str, **kwargs) -> bool:
        """发布内容到CSDN"""
        try:
            # 读取Markdown内容
            with open(content_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取元数据
            metadata = {}
            if content.startswith('---'):
                _, frontmatter, content = content.split('---', 2)
                for line in frontmatter.strip().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        metadata[key.strip()] = value.strip()
            
            title = metadata.get('title', os.path.splitext(os.path.basename(content_path))[0])
            
            # 处理内容中的图片
            content_dir = os.path.dirname(content_path)
            processed_content = self._process_content(content, content_dir)
            
            # 准备发布数据
            article_data = {
                'title': title,
                'content': processed_content,
                'description': metadata.get('description', '')[:200],
                'tags': metadata.get('tags', self.config.get('tags', '技术,编程')).split(','),
                'categories': metadata.get('categories', self.config.get('categories', '后端,Python')).split(','),
                'articleedittype': '1',  # 1: markdown, 2: 富文本
                'markdowncontent': processed_content,
                'contentType': '1',  # 1: 原创, 2: 转载, 3: 翻译
                'status': '0',  # 0: 草稿, 2: 发布
                'readType': 'public',  # public: 公开, private: 私密, fans: 粉丝可见
                'articletype': '1',  # 1: 普通文章, 2: 专栏文章
                'id': '',  # 文章ID，新建时为空
                'channel': 'tech',  # 频道
                'planToPublish': 'false',  # 是否定时发布
                'planToPublishTime': ''  # 定时发布时间
            }
            
            # 获取CSRF Token
            csrf_token = self._get_csrf_token()
            if not csrf_token:
                self.log_error("获取CSRF Token失败")
                return False
            
            # 发布文章
            publish_url = f"{self.BASE_URL}/content/operate/article/publish"
            headers = {
                'Content-Type': 'application/json;charset=UTF-8',
                'X-CSRF-TOKEN': csrf_token,
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://mp.csdn.net/mdeditor',
                'Origin': 'https://mp.csdn.net'
            }
            
            response = self.session.post(
                publish_url,
                json=article_data,
                headers=headers
            )
            
            if response.status_code != 200:
                self.log_error(f"发布失败: HTTP {response.status_code}")
                return False
                
            data = response.json()
            if data.get('code') != 200:
                self.log_error(f"发布失败: {data.get('message')}")
                return False
                
            article_id = data['data']['id']
            article_url = f"https://blog.csdn.net/article/details/{article_id}"
            
            self.log_success(f"文章发布成功: {article_url}")
            return True
            
        except Exception as e:
            self.log_error(f"发布过程中发生错误: {e}", exc_info=True)
            return False
