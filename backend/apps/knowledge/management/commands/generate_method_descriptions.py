"""
generate_method_descriptions — 用 LLM 为 canonical Method 生成 summary / purpose 初稿。

## 背景

2026-10-30 实测：B 方案阶段 3 之后，83 个 canonical Method 的
`summary / purpose / advantages / limitations / cost_band / timeline` **全部为空**。
方法页因此只剩「名字 + 所属应用 + 协议列表」，没有任何说明。

前 20 个方法覆盖 **55.3%** 的协议面，所以先补它们性价比最高。

## 为什么只生成这两个字段

| 字段 | 有无依据 | 做法 |
|---|---|---|
| `summary` | **有**：方法名 + 关联的几百条协议标题 | 本命令生成初稿 |
| `purpose` | 同上 | 本命令生成初稿 |
| `advantages` / `limitations` | **无**：语料里没有优劣性表述 | ❌ 不生成，留人工 |
| `cost_band` / `timeline` | **无**：`protocol_step.duration_seconds` 全部为 0 | ❌ 不生成，留人工 |

**编造 `cost_band` / `timeline` 就是造假数据**，宁缺勿错。

## 审核标记

生成后 `description_reviewed_at` 保持 **null**（= AI 初稿未审）。
前台会据此标注「AI draft, pending review」，领域专家确认后再打时间戳。

## 用法

    python manage.py generate_method_descriptions --limit 20 --dry-run
    python manage.py generate_method_descriptions --limit 20 --apply
    python manage.py generate_method_descriptions --verify
"""
import json
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from apps.bridges.models import MethodProtocol
from apps.knowledge.models import Method
from apps.knowledge.services.llm_extractor import LLMExtractor, LLMNotConfigured

SYSTEM_PROMPT = (
    "You are a senior molecular biologist writing concise catalogue copy for a "
    "reagent supplier's knowledge base. Your readers are working researchers.\n\n"
    "Hard rules:\n"
    "- Do NOT invent numbers, sensitivities, yields, detection limits, or comparisons.\n"
    "- Do NOT mention vendors, catalog numbers, or product names.\n"
    "- Do NOT use marketing adjectives (powerful, cutting-edge, revolutionary).\n"
    "- If a detail is uncertain, omit it rather than guess.\n"
    "- Output strict JSON only, no markdown fence, no commentary."
)

USER_TEMPLATE = """Method name: {name}

Example protocols that use this method (titles only):
{titles}

Write:
- "summary": 2-3 sentences (max 60 words) describing what this method does and when a
  researcher would choose it.
- "purpose": ONE sentence (max 20 words) stating the concrete goal it achieves.

Return exactly: {{"summary": "...", "purpose": "..."}}"""


class Command(BaseCommand):
    help = '用 LLM 为 canonical Method 生成 summary/purpose 初稿（默认 dry-run）'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20,
                            help='只处理协议数最多的前 N 个（默认 20；0 = 全部 83 个）')
        parser.add_argument('--titles', type=int, default=10,
                            help='每个方法取多少条协议标题作为上下文（默认 10）')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--verify', action='store_true')
        parser.add_argument('--backup-dir', default='/tmp/method_desc_backup')

    def handle(self, *args, **opts):
        if opts['verify']:
            return self._verify()

        methods = list(
            Method.objects.filter(status='active', application_id__isnull=True)
            .annotate(n_proto=Count('method_protocols'))
            .order_by('-n_proto')
        )
        if opts['limit']:
            methods = methods[:opts['limit']]

        self.stdout.write(f'待生成方法 {len(methods)} 个（按协议数降序）')
        if not methods:
            return

        extractor = LLMExtractor(
            api_key=os.getenv('SCIREAGENT_LLM_API_KEY'),
            base_url=os.getenv('SCIREAGENT_LLM_BASE_URL'),
            model=os.getenv('SCIREAGENT_LLM_MODEL'),
        )
        if not extractor.is_available:
            raise LLMNotConfigured(
                'SCIREAGENT_LLM_API_KEY 未配置，无法生成。配置后无需改代码。')

        results, failures = [], []
        for i, m in enumerate(methods, 1):
            titles = list(
                MethodProtocol.objects
                .filter(method=m, status='active', protocol__status='published')
                .order_by('-id').values_list('protocol__name', flat=True)[:opts['titles']]
            )
            if not titles:
                failures.append((m.id, m.name, '无 published 协议可作上下文'))
                continue
            user_prompt = USER_TEMPLATE.format(
                name=m.name,
                titles='\n'.join(f'{j}. {t[:150]}' for j, t in enumerate(titles, 1)),
            )
            try:
                raw = extractor.chat(SYSTEM_PROMPT, user_prompt)
                payload = self._parse(raw)
            except Exception as exc:  # 单个失败不中断整批
                failures.append((m.id, m.name, f'{type(exc).__name__}: {exc}'[:120]))
                continue
            if not payload.get('summary') or not payload.get('purpose'):
                failures.append((m.id, m.name, '返回缺字段'))
                continue
            results.append((m.id, m.name, payload['summary'].strip(),
                            payload['purpose'].strip(), len(titles)))
            self.stdout.write(f'  [{i}/{len(methods)}] {m.name[:40]} … ok')

        self.stdout.write(f'\n成功 {len(results)}｜失败 {len(failures)}')
        for f in failures[:10]:
            self.stdout.write(self.style.WARNING(f'  id={f[0]} {f[1][:34]} → {f[2]}'))

        if not opts['apply']:
            self.stdout.write('\n=== 样本（前 3 条）===')
            for r in results[:3]:
                self.stdout.write(f'\nid={r[0]}  {r[1]}')
                self.stdout.write(f'  summary: {r[2]}')
                self.stdout.write(f'  purpose: {r[3]}')
            self.stdout.write(self.style.WARNING('\n预演，未写库。加 --apply 执行。'))
            return

        os.makedirs(opts['backup_dir'], exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        path = os.path.join(opts['backup_dir'], f'method_desc_{ts}.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump({'created_at': ts, 'items': [
                {'id': r[0], 'name': r[1], 'summary': r[2], 'purpose': r[3]}
                for r in results]}, fh, ensure_ascii=False, indent=1)
        self.stdout.write(f'备份：{path}')

        n = 0
        for mid, name, summary, purpose, _n in results:
            # description_reviewed_at 保持 None —— 明确标记为「AI 初稿未审」
            n += Method.objects.filter(id=mid).update(
                summary=summary, purpose=purpose, description_reviewed_at=None)
        self.stdout.write(self.style.SUCCESS(
            f'\n已写入 {n} 个方法（description_reviewed_at 保持空 = 未审）'))
        self._verify()

    # ---------- 工具 ----------

    def _parse(self, raw):
        text = (raw or '').strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.lstrip().lower().startswith('json'):
                text = text.split('\n', 1)[1] if '\n' in text else ''
        start, end = text.find('{'), text.rfind('}')
        if start < 0 or end <= start:
            raise ValueError(f'非 JSON: {text[:80]!r}')
        return json.loads(text[start:end + 1])

    def _verify(self):
        qs = Method.objects.filter(status='active', application_id__isnull=True)
        total = qs.count()
        with_summary = qs.exclude(summary='').count()
        with_purpose = qs.exclude(purpose='').count()
        reviewed = qs.filter(description_reviewed_at__isnull=False).count()
        self.stdout.write('=== 核查 ===')
        self.stdout.write(f'canonical 方法        {total}')
        self.stdout.write(f'  有 summary          {with_summary}')
        self.stdout.write(f'  有 purpose          {with_purpose}')
        self.stdout.write(f'  已审核              {reviewed}'
                          + ('（其余为 AI 初稿待审）' if reviewed < with_summary else ''))
