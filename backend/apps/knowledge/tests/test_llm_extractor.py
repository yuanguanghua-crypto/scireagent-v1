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
        # 封闭性：清除本机 backend/.env 可能配的 base_url/model，确保断言 openai 默认值
        monkeypatch.delenv('SCIREAGENT_LLM_BASE_URL', raising=False)
        monkeypatch.delenv('SCIREAGENT_LLM_MODEL', raising=False)
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


class TestThinkingMode:
    """思考模式治理（2026-09-04 成本事故修复）。

    根因：deepseek-v4-flash **默认开启思考模式且 effort=high**
    （官方文档：思考模式开关，默认 enabled / effort 默认 high）。思维链输出
    按 ¥9/百万（高峰）计费，占单次成本约 80% —— 这是 T2 实测单价
    （¥0.0116/次）比按 prompt 体量推算（¥0.0008/次）高 14 倍的原因。

    T2/T3/summary 均为抽取生成类任务，不需要深度推理 → chat() 默认关闭思考模式。
    另：官方文档明确「思考模式不支持 temperature 参数」——关闭后 temperature=0
    才真正生效，抽取确定性更强（对"宁 miss 不错配"是正向收益）。

    extract_topchain 保持原行为不动（已通过 T4 验收，改它会影响已验证准确性）。
    """

    @staticmethod
    def _spy(monkeypatch, captured, content='{"methods": []}'):
        def spy(req, timeout):
            captured['payload'] = json.loads(req.data.decode('utf-8'))
            return _FakeResp(json.dumps(
                {'choices': [{'message': {'content': content}}]}
            ))
        monkeypatch.setattr('urllib.request.urlopen', spy)

    def test_chat_default_disables_thinking(self, monkeypatch):
        captured = {}
        self._spy(monkeypatch, captured)
        ex = LLMExtractor(api_key='sk-test', base_url='https://x/v1', model='m')
        ex.chat('sys prompt', 'user prompt')
        assert captured['payload'].get('thinking') == {'type': 'disabled'}, (
            'chat() 默认必须关闭思考模式——deepseek-v4-flash 默认 effort=high，'
            '思维链输出按 ¥9/百万计费，是 T2 成本失控根因'
        )

    def test_chat_can_enable_thinking_when_asked(self, monkeypatch):
        captured = {}
        self._spy(monkeypatch, captured)
        ex = LLMExtractor(api_key='sk-test', base_url='https://x/v1', model='m')
        ex.chat('sys', 'user', thinking='enabled')
        assert captured['payload'].get('thinking') == {'type': 'enabled'}

    def test_chat_keeps_temperature(self, monkeypatch):
        captured = {}
        self._spy(monkeypatch, captured)
        ex = LLMExtractor(api_key='sk-test', base_url='https://x/v1', model='m')
        ex.chat('sys', 'user', temperature=0)
        assert captured['payload']['temperature'] == 0

    def test_extract_topchain_behavior_unchanged(self, monkeypatch):
        """回归保护：顶部链提取不加 thinking 字段（保持 T4 验收时行为）。"""
        captured = {}
        inner = {'research_goals': [], 'applications': []}

        def spy(req, timeout):
            captured['payload'] = json.loads(req.data.decode('utf-8'))
            return _FakeResp(json.dumps(
                {'choices': [{'message': {'content': json.dumps(inner)}}]}
            ))
        monkeypatch.setattr('urllib.request.urlopen', spy)
        ex = LLMExtractor(api_key='sk-test')
        ex.extract_topchain('protocol text')
        assert 'thinking' not in captured['payload']
