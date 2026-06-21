import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
import database

load_dotenv()

# 初始化配置
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def analyze_hot_topic(title, platform):
    global api_key
    if not api_key:
        return {
            "has_value": False,
            "value_score": 1,
            "target_audience": "未配置API密钥",
            "pain_point": "请检查环境变量或.env文件中的GEMINI_API_KEY",
            "product_concept": "未配置密钥",
            "difficulty": "easy",
            "analysis_summary": "请先配置密钥"
        }
        
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
    
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        analysis = json.loads(response.text.strip())
        return analysis
    except Exception as e:
        return {
            "has_value": False,
            "value_score": 1,
            "target_audience": "错误",
            "pain_point": f"Gemini API 报错: {str(e)}",
            "product_concept": "分析失败",
            "difficulty": "easy",
            "analysis_summary": "API调用异常"
        }

def trigger_event_analysis(event_id, title, platform):
    # 抓取原始信息后调用 AI 并回填数据库
    analysis = analyze_hot_topic(title, platform)
    database.update_analysis(event_id, analysis)
    return analysis
