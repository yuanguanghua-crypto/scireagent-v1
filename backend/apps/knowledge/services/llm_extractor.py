"""顶部链 AI 生成管线 — LLM 提取 provider（OpenAI 兼容协议）。

三层护栏①（origin 溯源）的服务层基础：
- key/base_url/model 全环境变量可配，后期换 key/换服务商**零代码变更**
  （SCIREAGENT_LLM_API_KEY / SCIREAGENT_LLM_BASE_URL / SCIREAGENT_LLM_MODEL）
- 无 key 优雅降级：llm_config()['available']=False；extract_topchain 抛
  LLMNotConfigured（命令层转 dry-run 报错，不崩溃不造数据）
- 协议文本 → prompt → chat/completions → STRICT JSON → 结构化候选
  （research_goals / applications，各带 confidence 供黄金集抽检）

铁律（宁缺毋滥）：prompt 明确禁止臆造实体；空输出合法。
"""
import json
import os
import time
import urllib.error
import urllib.request

ENV_KEY = 'SCIREAGENT_LLM_API_KEY'
ENV_BASE = 'SCIREAGENT_LLM_BASE_URL'
ENV_MODEL = 'SCIREAGENT_LLM_MODEL'
DEFAULT_BASE_URL = 'https://api.openai.com/v1'
DEFAULT_MODEL = 'gpt-4o-mini'
TIMEOUT = 60

_SYSTEM_PROMPT = (
    'You are a scientific knowledge graph curator. Given an experimental '
    'protocol, extract two kinds of entities it supports:\n'
    '1. research_goals: broad research directions/fields (e.g. "RNA Analysis", '
    '"DNA Sequencing", "Click Chemistry")\n'
    '2. applications: specific experimental scenarios/techniques the protocol '
    'implements (e.g. "RNA Fluorescent Labeling", "Sanger Sequencing")\n'
    'Rules:\n'
    '- Only extract entities explicitly supported by the protocol content; '
    'do not invent or guess from general knowledge.\n'
    '- If the protocol content is empty or unrelated, output empty lists.\n'
    '- Output STRICT JSON only, no markdown, no commentary:\n'
    '{"research_goals":[{"name":"...","confidence":0.0-1.0}],'
    '"applications":[{"name":"...","confidence":0.0-1.0}]}\n'
    '- confidence: how directly the protocol supports the entity (0-1).\n'
    '- Use English entity names where possible; keep original language otherwise.'
)


class LLMNotConfigured(Exception):
    """LLM key 未配置。"""


def llm_config():
    """从环境变量读取配置。available=False 时 extract 不可用。"""
    api_key = os.getenv(ENV_KEY, '').strip()
    return {
        'api_key': api_key,
        'base_url': os.getenv(ENV_BASE, DEFAULT_BASE_URL).strip().rstrip('/'),
        'model': os.getenv(ENV_MODEL, DEFAULT_MODEL).strip(),
        'available': bool(api_key),
    }


def build_prompt(name, objective, principle, reagents):
    """协议文本 → 提取 prompt（含协议上下文 + STRICT JSON 约束）。"""
    return (
        'Protocol to analyze:\n'
        f'--- name: {name}\n'
        f'--- objective: {objective}\n'
        f'--- principle: {principle}\n'
        f'--- reagents: {reagents}\n'
        '\nExtract research_goals and applications per the instructions.'
    )


def parse_llm_json(content):
    """LLM 输出 → dict。容错 markdown 围栏；非法 JSON 抛 ValueError。"""
    text = (content or '').strip()
    if text.startswith('```'):
        # 去掉 ```json ... ``` 围栏
        lines = text.splitlines()
        if lines and lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        text = '\n'.join(lines).strip()
    if not text:
        raise ValueError('LLM 返回空内容')
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError('LLM 返回非对象 JSON')
    return {
        'research_goals': data.get('research_goals') or [],
        'applications': data.get('applications') or [],
    }


class LLMExtractor:
    """OpenAI 兼容 chat/completions 调用器（urllib 实现，零第三方依赖）。

    超时重试：读取超时（LLM 长输出常见）自动重试 RETRIES 次，
    指数退避（2s, 4s）；网络/HTTP 错误不重试（非瞬态）。
    """

    RETRIES = 2

    def __init__(self, api_key=None, base_url=None, model=None, timeout=TIMEOUT):
        self.api_key = (api_key or '').strip()
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip('/')
        self.model = model or DEFAULT_MODEL
        self.timeout = timeout

    @property
    def is_available(self):
        return bool(self.api_key)

    def extract_topchain(self, protocol_text, temperature=0):
        """协议文本 → {research_goals, applications}。无 key 抛 LLMNotConfigured。"""
        if not self.is_available:
            raise LLMNotConfigured(
                f'{ENV_KEY} 未配置——顶部链 AI 提取不可用。'
                '提供 key 后自动恢复（可后期变更，零代码改动）。'
            )
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': _SYSTEM_PROMPT},
                {'role': 'user', 'content': protocol_text},
            ],
            'temperature': temperature,
        }
        last_err = None
        for attempt in range(self.RETRIES + 1):
            try:
                req = urllib.request.Request(
                    f'{self.base_url}/chat/completions',
                    data=json.dumps(payload).encode('utf-8'),
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {self.api_key}',
                    },
                    method='POST',
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode('utf-8'))
                break
            except (TimeoutError, urllib.error.URLError, OSError) as e:
                last_err = e
                if attempt < self.RETRIES:
                    time.sleep(2 * (attempt + 1))  # 2s, 4s 退避
        else:
            raise last_err
        try:
            content = body['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError):
            raise ValueError(f'LLM 响应结构异常: {str(body)[:200]}')
        return parse_llm_json(content)
