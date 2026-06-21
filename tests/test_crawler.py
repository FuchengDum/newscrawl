import crawler
import database
import os

def setup_module(module):
    database.DB_FILE = "test_ainews.db"
    database.init_db()

def teardown_module(module):
    if os.path.exists("test_ainews.db"):
        os.remove("test_ainews.db")

def test_weibo_crawling():
    # 这里进行实际的网络请求，测试微博API解析
    data, fallback = crawler.fetch_weibo_hot()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "title" in data[0]
        assert data[0]["platform"] == "weibo"

def test_crawl_and_save():
    summary = crawler.crawl_and_save_all()
    assert "weibo_inserted" in summary
    assert "zhihu_inserted" in summary
    assert "zhihu_pin_inserted" in summary

import json
from unittest.mock import patch, MagicMock

def test_zhihu_hot_official_first_success():
    # Test that Zhihu official API is tried first and returns fallback=False when successful
    mock_res = MagicMock()
    mock_res_data = {
        "data": [
            {
                "target": {"title": "Official Title", "id": "123"},
                "detail_text": "123.4 万热度"
            }
        ]
    }
    mock_res.read.return_value = json.dumps(mock_res_data).encode('utf-8')
    mock_res.__enter__.return_value = mock_res
    
    called_urls = []
    def mock_urlopen(req, *args, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else req
        called_urls.append(url)
        if "api.zhihu.com" in url:
            return mock_res
        raise Exception("RSSHub should not be called when official API succeeds")
        
    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        results, fallback = crawler.fetch_zhihu_hot()
        
    assert fallback is False
    assert len(results) == 1
    assert results[0]["title"] == "Official Title"
    assert results[0]["popularity"] == 1234000
    assert len(called_urls) == 1
    assert "api.zhihu.com" in called_urls[0]

def test_zhihu_hot_official_fails_fallback_success(capsys):
    # Test that when official API fails, it logs warning and falls back to RSSHub mirrors, returning fallback=True
    mock_rss_res = MagicMock()
    mock_rss_xml = """<rss><channel>
        <item>
            <title>RSS Title</title>
            <link>https://www.zhihu.com/question/1</link>
        </item>
    </channel></rss>"""
    mock_rss_res.read.return_value = mock_rss_xml.encode('utf-8')
    mock_rss_res.__enter__.return_value = mock_rss_res
    
    called_urls = []
    def mock_urlopen(req, *args, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else req
        called_urls.append(url)
        if "api.zhihu.com" in url:
            raise Exception("Official API HTTP 403 Forbidden")
        return mock_rss_res
        
    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        results, fallback = crawler.fetch_zhihu_hot()
        
    assert fallback is True
    assert len(results) == 1
    assert results[0]["title"] == "RSS Title"
    assert len(called_urls) > 1
    assert "api.zhihu.com" in called_urls[0]
    
    # Check warning printed
    captured = capsys.readouterr()
    assert "Warning" in captured.out or "warning" in captured.out.lower()
    assert "official API failed" in captured.out or "zhihu official api failed" in captured.out.lower()

def test_weibo_hot_warning_on_fallback(capsys):
    # Test that weibo hot logs warning on fallback
    with patch("urllib.request.OpenerDirector.open", side_effect=Exception("Handshake Error")):
        with patch("urllib.request.urlopen", side_effect=Exception("RSSHub Error")):
            results, fallback = crawler.fetch_weibo_hot()
            
    assert fallback is True
    captured = capsys.readouterr()
    assert "Warning" in captured.out or "warning" in captured.out.lower()

def test_zhihu_pins_warning_on_fallback(capsys):
    # Test that zhihu pins logs warning when a mirror fails or fallback occurs
    with patch("urllib.request.urlopen", side_effect=Exception("RSSHub Error")):
        results, fallback = crawler.fetch_zhihu_pins()
        
    assert fallback is True
    captured = capsys.readouterr()
    assert "Warning" in captured.out or "warning" in captured.out.lower()

def test_crawl_and_save_calls_cleanup():
    # Test that crawl_and_save_all calls database.delete_old_unanalyzed_events
    with patch("database.delete_old_unanalyzed_events") as mock_delete:
        with patch("crawler.fetch_weibo_hot", return_value=([], False)):
            with patch("crawler.fetch_zhihu_hot", return_value=([], False)):
                with patch("crawler.fetch_zhihu_pins", return_value=([], False)):
                    crawler.crawl_and_save_all()
                    mock_delete.assert_called_once()

