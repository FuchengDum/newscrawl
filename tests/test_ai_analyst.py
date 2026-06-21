import ai_analyst
from dotenv import load_dotenv
import os
from unittest.mock import patch, MagicMock

def test_mock_analysis_without_key():
    # 测试在未提供 API 密钥时能正确回退并报错
    os.environ["GEMINI_API_KEY"] = ""
    res = ai_analyst.analyze_hot_topic("加班报销难", "weibo")
    assert res["has_value"] is False
    assert "GEMINI_API_KEY" in res["pain_point"]
    assert res["status"] == "failed"

def test_ai_generation_output_mocked():
    # 模拟 requests.post 以便在无真实 API Key 时完成单元测试
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"has_value": true, "value_score": 8, "target_audience": "开发者", "pain_point": "重复编写代码", "product_concept": "AI辅助工具", "difficulty": "medium", "analysis_summary": "极简辅助"}'
                }
            }
        ]
    }
    
    with patch("requests.post", return_value=mock_response) as mock_post:
        os.environ["GEMINI_API_KEY"] = "mock_key"
        res = ai_analyst.analyze_hot_topic("程序员加班脱发问题", "zhihu")
        
        assert res["has_value"] is True
        assert res["value_score"] == 8
        assert res["target_audience"] == "开发者"
        mock_post.assert_called_once()

def test_ai_generation_output_live():
    # 如果当前环境有可用的 KEY，进行真实集成测试
    load_dotenv()
    real_key = os.getenv("GEMINI_API_KEY")
    if real_key and real_key != "your_actual_gemini_api_key_here":
        os.environ["GEMINI_API_KEY"] = real_key
        res = ai_analyst.analyze_hot_topic("程序员加班脱发问题", "zhihu")
        assert "value_score" in res
        assert isinstance(res["value_score"], int)
        assert "target_audience" in res
