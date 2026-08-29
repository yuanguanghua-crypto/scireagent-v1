"""T2: LLM 提取 provider 抽象（顶部链 AI 生成管线）。

三层护栏①落地于服务层：OpenAI 兼容协议 provider，
key/base_url/model 全部环境变量可配（后期换 key/换服务商零代码变更）。
无 key 优雅降级：is_available=False，extract 抛 LLMNotConfigured（命令转 dry-run 报错）。
"""
import json
import time

import pytest

from apps.knowledge.services.llm_extractor import (
    LLMExtractor, LLMNotConfigured,
    build_prompt, parse_llm_json, llm_config,
)


class TestConfig:
    """环境变量配置：key 后期提供/变更的架构保证。"""

    def test_no_key_not_available(self, monkeypatch):
        monkeypatch.delenv('SCIREAGENT_LLM_API_KEY', raising=False)
        c = llm_config()
        assert c['available'] is False

    def test_key_available_with_defaults(self, monkeypatch):
        monkeypatch.setenv('SCIREAGENT_LLM_API_KEY', 'sk-test')
        c = llm_config()
        assert c['available'] is True
        assert c['base_url'] == 'https://api.openai.com/v1'
        assert c['model'] == 'gpt-4o-mini'

    def test_custom_base_and_model(self, monkeypatch):
        """换服务商（如 DeepSeek/通义/混元）零代码变更。"""
        monkeypatch.setenv('SCIREAGENT_LLM_API_KEY', 'sk-test')
        monkeypatch.setenv('SCIREAGENT_LLM_BASE_URL',
                           'https://dashscope.aliyuncs.com/compatible-mode/v1')
        monkeypatch.setenv('SCIREAGENT_LLM_MODEL', 'qwen-plus')
        c = llm_config()
        assert 'dashscope' in c['base_url']
        assert c['model'] == 'qwen-plus'


class TestPrompt:
    def test_prompt_includes_protocol_fields(self):
        p = build_prompt(name='CuAAC Click Protocol', objective='Label RNA in vitro',
                         principle='copper catalyzed azide-alkyne', reagents='CuSO4')
        assert 'CuAAC Click Protocol' in p
        assert 'Label RNA in vitro' in p
        assert 'CuSO4' in p

    def test_system_prompt_requires_strict_json(self):
        from apps.knowledge.services.llm_extractor import _SYSTEM_PROMPT
        assert 'STRICT JSON' in _SYSTEM_PROMPT

    def test_system_prompt_forbids_invention(self):
        from apps.knowledge.services.llm_extractor import _SYSTEM_PROMPT
        assert 'do not invent' in _SYSTEM_PROMPT.lower()


class TestParse:
    """LLM 输出解析：裸 JSON / markdown 围栏 / 非法降级 / 空输出。"""

    def test_plain_json(self):
        r = parse_llm_json(
            '{"research_goals":[{"name":"RNA Analysis","confidence":0.9}],'
            '"applications":[]}')
        assert r['research_goals'][0]['name'] == 'RNA Analysis'

    def test_markdown_fence(self):
        r = parse_llm_json('```json\n{"research_goals":[],"applications":[]}\n```')
        assert r == {'research_goals': [], 'applications': []}

    def test_empty_output_ok(self):
        r = parse_llm_json('{"research_goals":[],"applications":[]}')
        assert r['research_goals'] == []
        assert r['applications'] == []

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_llm_json('this is not json at all')


class TestExtract:
    """extract_topchain：无 key 拒绝、HTTP 成功、网络异常降级。"""

    def test_no_key_raises(self):
        ex = LLMExtractor(api_key='')
        with pytest.raises(LLMNotConfigured):
            ex.extract_topchain('any text')

    def test_http_success(self, monkeypatch):
        """mock urlopen：OpenAI 完整响应 → 结构化提取结果。"""
        inner = {'research_goals': [{'name': 'RNA Analysis', 'confidence': 0.85}],
                 'applications': [{'name': 'RNA Fluorescent Labeling', 'confidence': 0.7}]}
        body = {'choices': [{'message': {'content': json.dumps(inner)}}]}
        fake_resp = _FakeResp(json.dumps(body))
        monkeypatch.setattr('urllib.request.urlopen', lambda req, timeout: fake_resp)
        ex = LLMExtractor(api_key='sk-test', base_url='https://x/v1', model='m')
        r = ex.extract_topchain('protocol text here')
        assert r['research_goals'][0]['name'] == 'RNA Analysis'
        assert r['applications'][0]['name'] == 'RNA Fluorescent Labeling'

    def test_http_error_raises(self, monkeypatch):
        def boom(req, timeout):
            raise OSError('connection refused')
        monkeypatch.setattr('urllib.request.urlopen', boom)
        ex = LLMExtractor(api_key='sk-test')
        with pytest.raises(OSError):
            ex.extract_topchain('text')

    def test_empty_extraction_ok(self, monkeypatch):
        inner = {'research_goals': [], 'applications': []}
        body = {'choices': [{'message': {'content': json.dumps(inner)}}]}
        fake_resp = _FakeResp(json.dumps(body))
        monkeypatch.setattr('urllib.request.urlopen', lambda req, timeout: fake_resp)
        ex = LLMExtractor(api_key='sk-test')
        r = ex.extract_topchain('boring protocol')
        assert r['research_goals'] == []
        assert r['applications'] == []

    def test_timeout_retried_then_success(self, monkeypatch):
        """超时（实测 p=200 现象）→ 重试 2 次内成功。"""
        inner = {'research_goals': [{'name': 'CITE-seq', 'confidence': 0.9}],
                 'applications': []}
        body = {'choices': [{'message': {'content': json.dumps(inner)}}]}
        calls = {'n': 0}

        def flaky(req, timeout):
            calls['n'] += 1
            if calls['n'] < 3:
                raise TimeoutError('The read operation timed out')
            return _FakeResp(json.dumps(body))

        monkeypatch.setattr('urllib.request.urlopen', flaky)
        monkeypatch.setattr(time, 'sleep', lambda s: None)
        ex = LLMExtractor(api_key='sk-test')
        r = ex.extract_topchain('text')
        assert calls['n'] == 3  # 2 次失败 + 1 次成功
        assert r['research_goals'][0]['name'] == 'CITE-seq'

    def test_timeout_exhausted_raises(self, monkeypatch):
        """重试耗尽后抛原始错误（不静默）。"""
        def always_timeout(req, timeout):
            raise TimeoutError('The read operation timed out')

        monkeypatch.setattr('urllib.request.urlopen', always_timeout)
        monkeypatch.setattr(time, 'sleep', lambda s: None)
        ex = LLMExtractor(api_key='sk-test')
        with pytest.raises(TimeoutError):
            ex.extract_topchain('text')


class _FakeResp:
    def __init__(self, text):
        self._text = text

    def read(self):
        return self._text.encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False
