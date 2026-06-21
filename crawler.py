import urllib.request
import urllib.error
import http.cookiejar
import json
from bs4 import BeautifulSoup
import database

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 公共 RSSHub 镜像列表，用于降级和规避限制
RSSHUB_MIRRORS = [
    "https://rsshub.rssforever.com",
    "https://hub.slarker.me",
    "https://rsshub.app"
]

def fetch_weibo_hot():
    # 微博 API 直接请求会返回 403，需要使用 CookieJar 模拟访问主页获取客体会话 Token 后再请求
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [
        ("User-Agent", HEADERS["User-Agent"]),
        ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
        ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8")
    ]
    
    # 1. 握手访问主页获取 Cookie
    try:
        opener.open("https://weibo.com/", timeout=8)
    except Exception:
        # 握手失败，直接走 RSSHub 降级
        return fetch_weibo_rss_fallback()

    # 2. 带 Cookie 请求 AJAX 接口
    api_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://weibo.com/",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    try:
        req = urllib.request.Request("https://weibo.com/ajax/side/hotSearch", headers=api_headers)
        with opener.open(req, timeout=8) as res:
            data = json.loads(res.read().decode('utf-8'))
            realtime = data.get("data", {}).get("realtime", [])
            results = []
            for item in realtime[:50]:
                title = item.get("word", "")
                if not title:
                    continue
                url_link = f"https://s.weibo.com/weibo?q={title}"
                popularity = item.get("num", 0)
                results.append({"title": title, "url": url_link, "platform": "weibo", "popularity": popularity})
            return results, False  # 抓取成功，未启用降级
    except Exception:
        return fetch_weibo_rss_fallback()

def fetch_weibo_rss_fallback():
    # 遍历 RSSHub 镜像尝试抓取
    for mirror in RSSHUB_MIRRORS:
        rss_url = f"{mirror}/weibo/search/hot/fulltext"
        try:
            req = urllib.request.Request(rss_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8) as res:
                soup = BeautifulSoup(res.read(), "xml")
                items = soup.find_all("item")
                results = []
                for idx, item in enumerate(items[:50]):
                    title = item.title.text if item.title else "微博热搜项"
                    link = item.link.text if item.link else "https://s.weibo.com"
                    results.append({"title": title, "url": link, "platform": "weibo", "popularity": 100000 - idx})
                if results:
                    return results, True  # 降级成功
        except Exception:
            continue
    return [], True

def fetch_zhihu_hot():
    # 知乎 API (api.zhihu.com) 存在严苛的 IP 访问流控，直接在本地请求频繁报错 403/401。
    # 因此，我们优先从公共 RSSHub 镜像中读取（镜像自带缓存，极不容易被封），如果失败再尝试直接请求 API 降级。
    for mirror in RSSHUB_MIRRORS:
        rss_url = f"{mirror}/zhihu/hot"
        try:
            req = urllib.request.Request(rss_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8) as res:
                soup = BeautifulSoup(res.read(), "xml")
                items = soup.find_all("item")
                results = []
                for idx, item in enumerate(items[:50]):
                    title = item.title.text if item.title else "知乎热点项"
                    link = item.link.text if item.link else "https://www.zhihu.com"
                    results.append({"title": title, "url": link, "platform": "zhihu", "popularity": 500000 - idx * 10000})
                if results:
                    return results, False  # 走公共镜像缓存也是常规且推荐的方案
        except Exception:
            continue
    
    # 如果镜像全部失败，最后尝试直接调用 client API（有 403 风险）
    try:
        req = urllib.request.Request("https://api.zhihu.com/topstory/hot-lists/total?limit=50", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as res:
            data = json.loads(res.read().decode('utf-8'))
            items = data.get("data", [])
            results = []
            for item in items[:50]:
                target = item.get("target", {})
                title = target.get("title", "")
                if not title:
                    continue
                id_num = target.get("id", "")
                url_link = f"https://www.zhihu.com/question/{id_num}" if id_num else "https://www.zhihu.com"
                metrics = item.get("detail_text", "0")
                try:
                    popularity = int(metrics.replace(" 万热度", "").replace("万", "").strip()) * 10000
                except ValueError:
                    popularity = 500000
                results.append({"title": title, "url": url_link, "platform": "zhihu", "popularity": popularity})
            return results, True  # 标记为降级/异常源
    except Exception:
        return [], True

def fetch_zhihu_pins():
    # 获取知乎想法（24小时新闻汇总）
    for mirror in RSSHUB_MIRRORS:
        rss_url = f"{mirror}/zhihu/pin/daily"
        try:
            req = urllib.request.Request(rss_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8) as res:
                soup = BeautifulSoup(res.read(), "xml")
                items = soup.find_all("item")
                results = []
                for idx, item in enumerate(items[:50]):
                    title = item.title.text if item.title else "知乎想法项"
                    link = item.link.text if item.link else "https://www.zhihu.com"
                    results.append({"title": title, "url": link, "platform": "zhihu_pin", "popularity": 300000 - idx * 5000})
                if results:
                    return results, False  # 正常获取
        except Exception:
            continue
    return [], True  # 所有镜像失败，返回异常

def crawl_and_save_all():
    database.init_db()
    weibo_list, weibo_fallback = fetch_weibo_hot()
    zhihu_list, zhihu_fallback = fetch_zhihu_hot()
    pin_list, pin_fallback = fetch_zhihu_pins()
    
    weibo_count = 0
    for item in weibo_list:
        if database.save_hot_event(item["title"], item["url"], item["platform"], item["popularity"]):
            weibo_count += 1
            
    zhihu_count = 0
    for item in zhihu_list:
        if database.save_hot_event(item["title"], item["url"], item["platform"], item["popularity"]):
            zhihu_count += 1
            
    pin_count = 0
    for item in pin_list:
        if database.save_hot_event(item["title"], item["url"], item["platform"], item["popularity"]):
            pin_count += 1
            
    return {
        "weibo_inserted": weibo_count,
        "weibo_fallback": weibo_fallback,
        "zhihu_inserted": zhihu_count,
        "zhihu_fallback": zhihu_fallback,
        "zhihu_pin_inserted": pin_count,
        "zhihu_pin_fallback": pin_fallback
    }
