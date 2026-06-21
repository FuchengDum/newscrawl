import ai_analyst
from dotenv import load_dotenv
import os

def test_mock_analysis_without_key():
    # 测试在未提供 API 密钥时能正确回退并报错
    os.environ["GEMINI_API_KEY"] = ""
    res = ai_analyst.analyze_hot_topic("加班报销难", "weibo")
    assert res["has_value"] is False
    assert "GEMINI_API_KEY" in res["pain_point"]
    assert res["status"] == "failed"

def test_ai_generation_output():
    # 如果当前环境有可用的 KEY，进行真实集成测试
    load_dotenv()
    real_key = os.getenv("GEMINI_API_KEY")
    if real_key:
        os.environ["GEMINI_API_KEY"] = real_key
        res = ai_analyst.analyze_hot_topic("程序员加班脱发问题", "zhihu")
        assert "value_score" in res
        assert isinstance(res["value_score"], int)
        assert "target_audience" in res
