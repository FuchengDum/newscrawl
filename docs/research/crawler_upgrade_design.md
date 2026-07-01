# 🛠️ 爬虫代理池与免登录多源热点设计方案 (详细补充案)

针对项目评估中指出的两个核心痛点：
1. **爬虫代理池如何配置及使用方式**。
2. **微博/知乎查看受限（需要登录）的解决，以及无壁垒科技数据源的拓展**。

我们在本设计案中给出详细的系统级实施方案与技术实现。

---

## 一、 爬虫代理池配置及使用方案

为了提升爬虫的健壮性，防止被平台（或 RSSHub 镜像）限制 IP，我们设计了一套**兼容“开源免费代理池”与“商业隧道代理”的双轨制代理机制**。

### 1. 环境变量配置 (`.env`)

在 [`.env`](file:///Users/dum/google/proj/ainews/.env) 中新增代理相关配置：

```ini
# 代理模式: 'none' (不使用), 'api' (拉取API池), 'tunnel' (商业隧道代理)
PROXY_MODE=none

# 1. 针对商业隧道代理配置 (如快代理、阿布云，固定入口，每次请求自动换IP)
PROXY_TUNNEL_URL=http://username:password@tunnel_host:port

# 2. 针对开源免费代理池 API 配置 (如 Python 开源项目 proxy_pool，自建在本地)
PROXY_API_URL=http://localhost:5010/get/
PROXY_DELETE_URL=http://localhost:5010/delete/
```

### 2. 代码实现设计 (`proxy_helper.py`)

创建独立代理助手模块，负责提供代理 IP、汇报失效代理，并具备自动退避/重试逻辑：

```python
import os
import requests
from typing import Optional, Dict

def get_proxy_config() -> Optional[Dict[str, str]]:
    """根据配置获取当前可用的代理字典，返回给 requests/httpx 消耗。"""
    mode = os.getenv("PROXY_MODE", "none").lower()
    
    if mode == "none":
        return None
        
    if mode == "tunnel":
        tunnel_url = os.getenv("PROXY_TUNNEL_URL")
        if tunnel_url:
            return {"http": tunnel_url, "https": tunnel_url}
        return None
        
    if mode == "api":
        api_url = os.getenv("PROXY_API_URL")
        if not api_url:
            return None
        try:
            # 向自建代理池拉取一个可用 IP
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                proxy_ip = response.json().get("proxy")
                if proxy_ip:
                    # 格式为 '123.45.67.89:8080'
                    url = f"http://{proxy_ip}"
                    return {"http": url, "https": url}
        except Exception as e:
            print(f"Error fetching proxy from API pool: {e}")
    return None

def report_failed_proxy(proxy_dict: Optional[Dict[str, str]]) -> None:
    """当某个代理 IP 请求超时或返回 403 封锁时，向开源代理池发送删除指令。"""
    if not proxy_dict or os.getenv("PROXY_MODE", "none").lower() != "api":
        return
        
    proxy_url = proxy_dict.get("http", "")
    # 提取 '123.45.67.89:8080'
    proxy_ip = proxy_url.replace("http://", "")
    
    delete_api = os.getenv("PROXY_DELETE_URL")
    if delete_api and proxy_ip:
        try:
            requests.get(f"{delete_api}?proxy={proxy_ip}", timeout=3)
            print(f"Reported and removed bad proxy: {proxy_ip}")
        except Exception:
            pass
```

### 3. 在爬虫中的使用示例

在 [`crawler.py`](file:///Users/dum/google/proj/ainews/crawler.py) 中，将原先的原始请求方法封装，加入代理尝试与失效重试：

```python
import requests
from proxy_helper import get_proxy_config, report_failed_proxy

def fetch_html_with_retry(url: str, max_attempts: int = 3) -> str:
    """带代理重试机制的页面 HTML 获取器"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)..."
    }
    
    for attempt in range(max_attempts):
        proxy = get_proxy_config()
        try:
            response = requests.get(url, headers=headers, proxies=proxy, timeout=8)
            # 如果被要求登录或限制，手动抛出异常以触发重试
            if response.status_code == 403 or "login" in response.url:
                raise requests.exceptions.RequestException("Encountered 403 or Login redirect")
                
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1} failed for {url} using proxy {proxy}: {e}")
            # 如果使用的是 API 代理，汇报其损坏，以便代理池删除
            if proxy:
                report_failed_proxy(proxy)
            if attempt == max_attempts - 1:
                raise
```

---

## 二、 免登录直看热点优化与数据源拓展

当前 Weibo / Zhihu 官方链接和搜索结果对于未登录的访客设置了强烈的“登录壁垒”（弹窗拦截），影响了看板用户的进一步阅读。

```
[原链路] s.weibo.com / zhihu.com ──> 遇到登录拦截 🚫 无法查阅
[优化后] m.weibo.cn / oia.zhihu.com ──> 免登录直接阅读完整正文/回复 ✅
```

### 1. 当前源（微博/知乎）的免登录入口替换

我们在生成卡片和数据库存盘时，对跳转链接进行如下转换优化：

*   **微博热搜转换**：
    *   **现状**：跳转至 `https://s.weibo.com/weibo?q={title}`（PC端搜索页），未登录极易被拦截。
    *   **优化**：转换为微博移动版网页端链接 `https://m.weibo.cn/search?containerid=100103type%3D1%26q%3D{encode(title)}`，移动端网页支持免登录免客户端浏览热门讨论与博文。
*   **知乎热榜转换**：
    *   **现状**：跳转至 `https://www.zhihu.com/question/{id}`，PC端经常强制扫码。
    *   **优化**：转换为知乎移动版唤起页或知乎单页链接 `https://oia.zhihu.com/questions/{id}`，或者使用知乎日报的只读镜像，大幅减少弹窗频次。

---

### 2. 拓展四大高价值、完全免登录的科技/开发者数据源

针对寻找 SaaS 商机的受众（独立开发者/产品经理），我们额外接入四个完全不需要登录便可直接阅读全部回复的“纯干货”热点源：

#### 数据源 1：V2EX 每日热议 (V2EX Hot)
*   **开发商机指数**：⭐⭐⭐⭐⭐ (极高。充斥着大量程序员的吐槽、对已有工具的抱怨、新奇的痛点提问)
*   **API 接口**：`https://www.v2ex.com/api/topics/hot.json` (官方 JSON API，完全公开，不需要登录)
*   **落地链接**：`https://www.v2ex.com/t/{topic_id}` (纯静态页面，所有非注册用户可无缝浏览全部讨论)

#### 数据源 2：少数派 热门文章 (Sspai Popular)
*   **开发商机指数**：⭐⭐⭐⭐ (效率工具的风向标。介绍最新数码、软件提效思路，文章下有大量深入的使用痛点评论)
*   **RSS 接口**：`https://rsshub.app/sspai/matrix` 或 `https://rsshub.app/sspai/index`
*   **落地链接**：`https://sspai.com/post/{post_id}` (高质量的软文与长文，无任何阅读限制)

#### 数据源 3：36氪 资讯热榜 (36Kr News)
*   **开发商机指数**：⭐⭐⭐ (追踪大厂动态、AI 初创项目新概念、投融资动态，利于寻找宏观商机)
*   **API/RSS 接口**：`https://rsshub.app/36kr/newsflashes`
*   **落地链接**：`https://36kr.com/newsflashes` (快讯聚合页，免登录直达)

#### 数据源 4：GitHub Trending (GitHub 热门项目)
*   **开发商机指数**：⭐⭐⭐⭐⭐ (全球开源趋势。某新热门开源库的出现，预示着将其“包装为 SaaS 服务/浏览器插件”的巨大短线机会)
*   **RSS 接口**：`https://rsshub.app/github/trending/daily/any` (今日全球最火项目)
*   **落地链接**：`https://github.com/{author}/{repo}` (完全开放，免登录查阅)

---

### 3. 数据表兼容性扩展 (`database.py`)

为完美接入上述新渠道，SQLite 的 `hot_events` 表中的 `platform` 字段完全兼容新渠道类型：

| 平台标识 (platform) | 外部中文名 | 免登录入口形式 | 包含的信息类型 |
| :--- | :--- | :--- | :--- |
| `weibo` | 微博热搜 | `m.weibo.cn` 移动版 | 社会综合热点 |
| `zhihu` | 知乎热榜 | `oia.zhihu.com` 移动版 | 深度民生与大众知识 |
| `v2ex` | V2EX 热议 | `v2ex.com/t/{id}` | 程序员职场、开发工具痛点 |
| `sspai` | 少数派热门 | `sspai.com/post/{id}` | 效率工具、新形态应用评测 |
| `github` | GitHub 趋势 | `github.com/{repo}` | 技术风向标、可包装的底层库 |
