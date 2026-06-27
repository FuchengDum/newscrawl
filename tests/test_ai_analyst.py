import pytest
import ai_analyst
from dotenv import load_dotenv
import os
from unittest.mock import patch, MagicMock

@pytest.fixture(autouse=True)
def clean_model_cache():
    # Clear attempted and successful models sets before each test to prevent test pollution
    ai_analyst._attempted_models.clear()
    ai_analyst._successful_models.clear()


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

def test_ai_generation_failover_refactored():
    from unittest.mock import patch, MagicMock
    import requests
    
    def mock_post_side_effect(url, headers, json, timeout=30):
        if "elysiver.h-e.top" in url:
            response = MagicMock()
            response.status_code = 500
            response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error", response=response)
            return response
        elif "wzw.pp.ua" in url:
            response = MagicMock()
            response.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": '{"has_value": true, "value_score": 9, "target_audience": "开发者", "pain_point": "重复编写代码", "product_concept": "AI辅助工具", "difficulty": "easy", "analysis_summary": "DeepSeek极简辅助"}'
                        }
                    }
                ]
            }
            return response
        else:
            raise ValueError(f"Unexpected request to {url}")

    with patch("requests.post", side_effect=mock_post_side_effect) as mock_post:
        os.environ["GEMINI_API_KEY"] = "mock_key"
        old_url = os.environ.get("GEMINI_API_URL")
        os.environ["GEMINI_API_URL"] = "https://elysiver.h-e.top/v1/chat/completions"
        
        old_fb_url = os.environ.get("FALLBACK_API_URL")
        old_fb_key = os.environ.get("FALLBACK_API_KEY")
        old_fb_models = os.environ.get("FALLBACK_MODELS")
        
        os.environ["FALLBACK_API_URL"] = "https://wzw.pp.ua/v1/chat/completions"
        os.environ["FALLBACK_API_KEY"] = "mock_fallback_key"
        os.environ["FALLBACK_MODELS"] = "deepseek-ai/deepseek-v4-flash,deepseek-ai/deepseek-v4-pro"
        
        try:
            res = ai_analyst.analyze_hot_topic("程序员脱发问题", "zhihu")
            assert res["has_value"] is True
            assert res["value_score"] == 9
            assert res["analysis_summary"] == "DeepSeek极简辅助"
            
            called_urls = [args[0] for args, kwargs in mock_post.call_args_list]
            assert any("elysiver.h-e.top" in u for u in called_urls)
            assert any("wzw.pp.ua" in u for u in called_urls)
        finally:
            if old_url is not None:
                os.environ["GEMINI_API_URL"] = old_url
            else:
                os.environ.pop("GEMINI_API_URL", None)
            if old_fb_url is not None:
                os.environ["FALLBACK_API_URL"] = old_fb_url
            else:
                os.environ.pop("FALLBACK_API_URL", None)
            if old_fb_key is not None:
                os.environ["FALLBACK_API_KEY"] = old_fb_key
            else:
                os.environ.pop("FALLBACK_API_KEY", None)
            if old_fb_models is not None:
                os.environ["FALLBACK_MODELS"] = old_fb_models
            else:
                os.environ.pop("FALLBACK_MODELS", None)

def test_model_skip_on_repeated_failure():
    # Reset tracking sets for the test
    ai_analyst._attempted_models.clear()
    ai_analyst._successful_models.clear()

    # Mock post to fail
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = Exception("HTTP 500 Error")

    with patch("requests.post", return_value=mock_response) as mock_post:
        # First attempt should fail and call post
        success, analysis, error = ai_analyst._call_openai_compatible_api(
            "https://test-url.com/v1", "key", "test-model", "hello", max_retries=1
        )
        assert success is False
        assert mock_post.call_count == 1

        # Second attempt should skip and NOT call post
        success, analysis, error = ai_analyst._call_openai_compatible_api(
            "https://test-url.com/v1", "key", "test-model", "hello", max_retries=1
        )
        assert success is False
        assert "skipped" in str(error)
        assert mock_post.call_count == 1  # Should still be 1!

        # Now, if we try another model, it should NOT skip it
        success, analysis, error = ai_analyst._call_openai_compatible_api(
            "https://test-url.com/v1", "key", "another-model", "hello", max_retries=1
        )
        assert success is False
        assert mock_post.call_count == 2


def test_ai_primary_model_switching():
    # Test that multiple models in GEMINI_MODEL are tried in sequence if they fail
    from unittest.mock import patch, MagicMock
    import requests

    def mock_post_side_effect(url, headers, json, timeout=30):
        model = json.get("model")
        if model == "gemini-2.5-flash":
            # Fail the first model
            response = MagicMock()
            response.status_code = 500
            response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error", response=response)
            return response
        elif model == "gemini-1.5-flash":
            # Succeed on the second model
            response = MagicMock()
            response.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": '{"has_value": true, "value_score": 7, "target_audience": "开发者", "pain_point": "重复编写代码", "product_concept": "AI辅助工具", "difficulty": "easy", "analysis_summary": "切换模型成功"}'
                        }
                    }
                ]
            }
            return response
        else:
            raise ValueError(f"Unexpected model {model}")

    with patch("requests.post", side_effect=mock_post_side_effect) as mock_post:
        # Reset tracking sets
        ai_analyst._attempted_models.clear()
        ai_analyst._successful_models.clear()
        
        old_key = os.environ.get("GEMINI_API_KEY")
        old_url = os.environ.get("GEMINI_API_URL")
        old_models = os.environ.get("GEMINI_MODEL")
        
        os.environ["GEMINI_API_KEY"] = "mock_key"
        os.environ["GEMINI_API_URL"] = "https://elysiver.h-e.top/v1/chat/completions"
        os.environ["GEMINI_MODEL"] = "gemini-2.5-flash,gemini-1.5-flash"
        
        try:
            res = ai_analyst.analyze_hot_topic("程序员脱发问题", "zhihu")
            assert res["has_value"] is True
            assert res["value_score"] == 7
            assert res["analysis_summary"] == "切换模型成功"
            
            called_models = [kwargs["json"]["model"] for args, kwargs in mock_post.call_args_list]
            assert "gemini-2.5-flash" in called_models
            assert "gemini-1.5-flash" in called_models
        finally:
            if old_key is not None:
                os.environ["GEMINI_API_KEY"] = old_key
            else:
                os.environ.pop("GEMINI_API_KEY", None)
            if old_url is not None:
                os.environ["GEMINI_API_URL"] = old_url
            else:
                os.environ.pop("GEMINI_API_URL", None)
            if old_models is not None:
                os.environ["GEMINI_MODEL"] = old_models
            else:
                os.environ.pop("GEMINI_MODEL", None)

