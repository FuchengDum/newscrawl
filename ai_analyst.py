import os
import json
import requests
from dotenv import load_dotenv
import database

# 加载环境变量
load_dotenv()

def analyze_hot_topic(title, platform):
    # 每次调用时动态重载环境变量，确保能读取到最新配置
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
        
    api_url = os.getenv("GEMINI_API_URL", "https://elysiver.h-e.top/v1/chat/completions")
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

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

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        res_data = response.json()
        content = res_data["choices"][0]["message"]["content"]
        analysis = json.loads(content.strip())
        return analysis
    except Exception as e:
        return {
            "status": "failed",
            "has_value": False,
            "value_score": 1,
            "target_audience": "错误",
            "pain_point": f"API 报错: {str(e)}",
            "product_concept": "分析失败",
            "difficulty": "easy",
            "analysis_summary": "API调用异常"
        }

def trigger_event_analysis(event_id, title, platform):
    # 抓取原始信息后调用 AI 并回填数据库
    analysis = analyze_hot_topic(title, platform)
    database.update_analysis(event_id, analysis)
    return analysis


def generate_daily_report_markdown(date, events):
    """
    纯本地字符串格式化，不调用 AI API。
    生成指定日期的热点需求日报 Markdown。
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
