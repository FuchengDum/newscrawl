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
