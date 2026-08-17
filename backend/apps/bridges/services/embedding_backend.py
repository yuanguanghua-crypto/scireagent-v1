"""轴C embedding 后端（离线预计算用，决策 Q4）。

生产 recompute 在离线子进程中调用：须在 django.setup() 之前把 emb3_venv
（py3.12 + sentence-transformers 3.3.1 + tokenizers 0.21.1）的 site-packages
注入 sys.path，否则 backend venv(py3.13) 的 transformers 5.14.1 会触发版本冲突。

本模块被 relevance.compute_axis_c 的默认 embedding_fn 惰性调用；测试通过注入
embedding_fn 绕开本模块，故测试环境不会加载模型。
"""
import os
import sys

# 缺省仅为本地开发机的历史路径；部署环境须用 EMB3_VENV 环境变量或
# settings.EMB3_VENV_PATH 覆盖（服务器不存在 D 盘，硬编码必然失败）。
DEFAULT_EMB3_VENV = r"D:\emb3_venv"
_MODEL_NAME = "all-MiniLM-L6-v2"

_model = None
_injected = False


def emb3_venv_path():
    """emb3 venv 根路径：环境变量 > Django settings > 本地缺省。"""
    env = os.environ.get("EMB3_VENV")
    if env:
        return env
    try:
        from django.conf import settings
        configured = getattr(settings, "EMB3_VENV_PATH", None)
    except Exception:
        configured = None
    return configured or DEFAULT_EMB3_VENV


def _ensure_injected():
    global _injected
    if _injected:
        return
    site = os.path.join(emb3_venv_path(), "Lib", "site-packages")
    if os.path.isdir(site) and site not in sys.path:
        sys.path.insert(0, site)
    _injected = True


def _get_model():
    global _model
    if _model is not None:
        return _model
    _ensure_injected()
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer(_MODEL_NAME)
    return _model


_PROTOCOL_CACHE = {}


def _protocol_embedding(protocol):
    key = protocol.id
    vec = _PROTOCOL_CACHE.get(key)
    if vec is None:
        text = " ".join([
            getattr(protocol, 'name', '') or '',
            getattr(protocol, 'objective', '') or '',
            getattr(protocol, 'summary', '') or '',
            getattr(protocol, 'purpose', '') or '',
        ])
        vec = _get_model().encode(text, normalize_embeddings=True)
        _PROTOCOL_CACHE[key] = vec
    return vec


def embed_similarity(product, protocol):
    """返回 product.usage 与协议文本的余弦相似度 ∈[-1,1]；不可用时抛异常由调用方降级。"""
    usage = getattr(product, 'usage', None)
    if not usage:
        return 0.0
    model = _get_model()
    u_vec = model.encode(usage, normalize_embeddings=True)
    p_vec = _protocol_embedding(protocol)
    # 归一化后点积即余弦
    score = float(u_vec @ p_vec)
    return max(-1.0, min(1.0, score))
