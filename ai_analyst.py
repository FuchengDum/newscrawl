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
