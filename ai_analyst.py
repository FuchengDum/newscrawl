import os
import json
import time
import requests
from dotenv import load_dotenv
from typing import Tuple, Dict, Any, Optional, Set, List
import database

# 加载环境变量
load_dotenv()

# Track successful providers and consecutive failures to implement circuit-breaker skipping
_successful_providers: Set[str] = set()
_consecutive_provider_failures: Dict[str, int] = {}

def _is_server_or_network_error(error: Optional[Exception]) -> bool:
    """Helper to identify if an error is a server or network-level failure.

    Args:
        error: The Exception object to check.

    Returns:
        True if it's a server or network failure, False otherwise.
    """
    if not error:
        return False
    if isinstance(error, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True
    if isinstance(error, requests.exceptions.HTTPError):
        status_code = error.response.status_code if error.response is not None else 0
        if status_code >= 500:
            return True
    err_str = str(error).lower()
    if "connection" in err_str or "timeout" in err_str or "dns" in err_str or "ssl" in err_str:
        return True
    return False

def _call_openai_compatible_api(
    api_url: str,
    api_key: str,
    model_name: str,
    prompt: str,
    max_retries: int = 3
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[Exception]]:
    """Calls an OpenAI compatible API with retry and logs results.

    If a provider at a specific api_url was attempted but never succeeded, it is skipped.

    Args:
        api_url: The endpoint URL.
        api_key: The authorization bearer token.
        model_name: Name of the model to call.
        prompt: User prompt content.
        max_retries: Maximum attempts to retry on 5xx status codes.

    Returns:
        A tuple of (success, analysis_data, error_object).
    """
    failures = _consecutive_provider_failures.get(api_url, 0)
    has_succeeded = api_url in _successful_providers

    if (not has_succeeded and failures > 0) or (has_succeeded and failures >= 3):
        return False, None, Exception(
            f"Provider at {api_url} was skipped due to consecutive failures ({failures} failures)."
        )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    
    last_error = None
    for attempt in range(max_retries):
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            res_data = response.json()
            content = res_data["choices"][0]["message"]["content"]
            analysis = json.loads(content.strip())
            _successful_providers.add(api_url)
            _consecutive_provider_failures[api_url] = 0
            return True, analysis, None
        except requests.exceptions.HTTPError as e:
            last_error = e
            status_code = e.response.status_code if e.response is not None else 0
            if status_code >= 500 and attempt < max_retries - 1:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            break
        except Exception as e:
            last_error = e
            break
            
    return False, None, last_error

def analyze_hot_topic(title: str, platform: str) -> Dict[str, Any]:
    """Analyzes a hot topic to see if there is potential for a software product/SaaS.

    Args:
        title: Title of the hot topic.
        platform: Platform source of the hot topic.

    Returns:
        A dictionary containing the analysis results.
    """
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {
            "status": "failed",
            "has_value": False,
            "value_score": 1,
            "target_audience": "未配置API密钥",
            "pain_point": "请检查环境变量或.env文件中的GEMINI_API_KEY",
            "product_concept": "未配置密钥",
            "difficulty": "easy",
            "analysis_summary": "请先配置密钥"
        }
        
    api_url = os.getenv("GEMINI_API_URL")
    model_raw = os.getenv("GEMINI_MODEL", "")
    primary_models = [m.strip() for m in model_raw.split(",") if m.strip()]

    prompt = f"""
    你是一名经验丰富的产品经理与天使投资分析师。
    请分析以下热点事件，并评估从中是否能挖掘出特定的用户痛点，从而开发出对应的软件产品、SaaS 接口、浏览器插件或轻量级小程序。

    事件标题：{title}
    来源平台：{platform}

    请严格按以下 JSON 格式输出，不要包含任何额外的 Markdown 格式字符：
    {{
      "has_value": true/false (是否具有产品化开发的价值，明星娱乐八卦、宏观国际政治等无开发价值的设为 false),
      "value_score": 1-10 之间的整数 (产品化商业开发价值评分，无开发价值的设为 1-3),
      "target_audience": "清晰精准的目标受众描述",
      "pain_point": "用户面临的深层核心痛点或吐槽点",
      "product_concept": "具体的解决方案/产品功能构想",
      "difficulty": "easy/medium/hard (开发难度评估)",
      "analysis_summary": "100字以内的卡片简短摘要"
    }}
    """
    
    # 第一阶段：尝试主调用（支持多个模型依次重试）
    success = False
    analysis = None
    last_error = None
    if api_url and primary_models:
        for model_name in primary_models:
            success, analysis, last_error = _call_openai_compatible_api(
                api_url, api_key, model_name, prompt, max_retries=3
            )
            if success:
                break
        
        # If the entire primary provider stage failed, increment its failures
        if not success:
            _consecutive_provider_failures[api_url] = _consecutive_provider_failures.get(api_url, 0) + 1
    
    # 第二阶段：容灾回退
    fb_url = os.getenv("FALLBACK_API_URL")
    fb_key = os.getenv("FALLBACK_API_KEY")
    fb_models_raw = os.getenv("FALLBACK_MODELS", "")
    fb_models = [m.strip() for m in fb_models_raw.split(",") if m.strip()]
    
    if not success and fb_url and fb_key and fb_models:
        for fb_model in fb_models:
            success, analysis, fb_error = _call_openai_compatible_api(
                fb_url, fb_key, fb_model, prompt, max_retries=2
            )
            if success:
                break
            else:
                last_error = fb_error
                
        # If the entire fallback provider stage failed, increment its failures
        if not success:
            _consecutive_provider_failures[fb_url] = _consecutive_provider_failures.get(fb_url, 0) + 1

    if success:
        return analysis

    return {
        "status": "failed",
        "has_value": False,
        "value_score": 1,
        "target_audience": "错误",
        "pain_point": f"API 报错: {str(last_error)}",
        "product_concept": "分析失败",
        "difficulty": "easy",
        "analysis_summary": "API调用异常"
    }

def trigger_event_analysis(event_id: int, title: str, platform: str) -> Dict[str, Any]:
    """Triggers analysis for a specific hot event and updates the database.

    Args:
        event_id: The database ID of the hot event.
        title: Title of the hot event.
        platform: Source platform.

    Returns:
        The analysis results.
    """
    # 抓取原始信息后调用 AI 并回填数据库
    analysis = analyze_hot_topic(title, platform)
    database.update_analysis(event_id, analysis)
    return analysis


def generate_daily_report_markdown(date: str, events: List[Dict[str, Any]]) -> str:
    """纯本地字符串格式化，不调用 AI API。

    生成指定日期的热点需求日报 Markdown。

    Args:
        date: Target date string for the report.
        events: List of events data.

    Returns:
        Generated report markdown.
    """
    from datetime import datetime as dt

    platform_map = {
        "weibo": "微博热搜",
        "zhihu": "知乎热榜",
        "zhihu_pin": "知乎想法"
    }
    difficulty_map = {
        "easy": "简单",
        "medium": "中等",
        "hard": "困难"
    }

    # 统计平台分布
    platform_counts = {}
    max_score = 0
    for e in events:
        p = e.get("platform", "unknown")
        platform_counts[p] = platform_counts.get(p, 0) + 1
        score = e.get("value_score", 0) or 0
        if score > max_score:
            max_score = score

    platform_summary = " / ".join(
        f"{platform_map.get(p, p)} {c} 条" for p, c in platform_counts.items()
    )

    lines = []
    lines.append(f"# 📊 热点需求日报 — {date}")
    lines.append("")
    lines.append("## 概要")
    lines.append(f"- 高价值热点数: {len(events)} 条")
    lines.append(f"- 平台分布: {platform_summary}")
    lines.append(f"- 最高评分: {max_score} 分")
    lines.append("")
    lines.append("## 🔥 高价值热点详情")
    lines.append("")

    for idx, e in enumerate(events, 1):
        title = e.get("title", "未知标题")
        score = e.get("value_score", 0) or 0
        platform = platform_map.get(e.get("platform", ""), e.get("platform", "未知"))
        audience = e.get("target_audience", "未知")
        pain = e.get("pain_point", "未知")
        concept = e.get("product_concept", "未知")
        diff = difficulty_map.get(e.get("difficulty", ""), e.get("difficulty", "未知"))
        summary = e.get("analysis_summary", "暂无摘要")

        lines.append(f"### {idx}. {title} (⭐ 评分: {score}/10)")
        lines.append(f"- **来源平台**: {platform}")
        lines.append(f"- **目标客群**: {audience}")
        lines.append(f"- **核心痛点**: {pain}")
        lines.append(f"- **产品构想**: {concept}")
        lines.append(f"- **开发难度**: {diff}")
        lines.append(f"- **分析摘要**: {summary}")
        lines.append("")

    lines.append("---")
    lines.append(f"*报告生成时间: {dt.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    lines.append("")

    return "\n".join(lines)
