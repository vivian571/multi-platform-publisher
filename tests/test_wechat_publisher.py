import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add project root to path to allow module imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from publishers.wechat_publisher import WeChatPublisher

@pytest.fixture
def mock_config():
    """Fixture for mock configuration."""
    return {
        'app_id': 'test_app_id',
        'app_secret': 'test_app_secret',
        'author': '默认作者',
    }

@pytest.fixture
def publisher(mock_config):
    """Fixture for WeChatPublisher instance."""
    return WeChatPublisher(config=mock_config, account_name='test_account')


def test_publish_success(publisher, tmp_path):
    """Test the entire publish process with mocks for external APIs."""
    # Create a dummy article file and image file for the test
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    article_path = fixtures_dir / "test_article.md"
    article_path.write_text(
        """---
title: '测试文章'
author: '测试作者'
---

# 测试标题

内容部分。

![图片](image.png)
""", encoding='utf-8'
    )
    image_path = fixtures_dir / "image.png"
    image_path.touch()

    # Mock the external API calls
    with patch.object(publisher, '_get_access_token', return_value='mock_token') as mock_token:
        with patch.object(publisher, 'upload_image', return_value='http://mock.url/image.png') as mock_upload:
            with patch.object(publisher.session, 'post') as mock_post:
                # Mock the response from WeChat API for draft creation
                mock_response = MagicMock()
                mock_response.json.return_value = {'errcode': 0, 'media_id': 'mock_media_id'}
                mock_post.return_value = mock_response

                # Call the publish method
                success = publisher.publish(str(article_path))

                # Assertions
                assert success is True
                
                # Verify that access token was fetched
                mock_token.assert_called_once()
                
                # Verify that image was uploaded
                mock_upload.assert_called_once_with(str(image_path))
                
                # Verify that the draft was created with the correct payload
                mock_post.assert_called_once()
                args, kwargs = mock_post.call_args
                payload = kwargs.get('json', {})
                
                assert 'articles' in payload
                assert len(payload['articles']) == 1
                article_payload = payload['articles'][0]
                
                assert article_payload['title'] == "'测试文章'"
                assert article_payload['author'] == "'测试作者'"
                assert 'http://mock.url/image.png' in article_payload['content']

def test_get_access_token_failure(publisher):
    """Test failure to get access token."""
    with patch.object(publisher.session, 'get') as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {'errcode': 40001, 'errmsg': 'invalid credential'}
        mock_get.return_value = mock_response
        
        token = publisher._get_access_token()
        assert token is None
