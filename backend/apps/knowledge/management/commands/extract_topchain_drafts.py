"""顶部链 AI 生成管线 pilot 命令 — extract_topchain_drafts。

从协议提取 RG/AP 候选（dry-run 默认，不落库），输出候选报告 + 黄金集抽检 md。
无 LLM key 时明确报错退出（不崩溃不造数据）。

用法：
  python manage.py extract_topchain_drafts                        # 10 协议 dry-run
  python manage.py extract_topchain_drafts --protocol-ids 1,2,3   # 指定协议
  python manage.py extract_topchain_drafts --count 20             # 取 20 个
  python manage.py extract_topchain_drafts --report <abs-path>    # 报告路径
"""
import json
import os

from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.models import Protocol
from apps.knowledge.services.llm_extractor import (
    LLMExtractor, LLMNotConfigured,
    build_prompt, llm_config,
)


class Command(BaseCommand):
    help = '顶部链 AI 生成 pilot：协议 → RG/AP 候选（dry-run，黄金集抽检）'

    def add_arguments(self, parser):
        parser.add_argument('--protocol-ids', type=str, default='',
                            help='逗号分隔的协议 ID 列表（优先于 --count）')
        parser.add_argument('--count', type=int, default=10,
                            help='默认取样数（正文最丰富的 N 个协议）')
        parser.add_argument('--report', type=str, default='',
                            help='报告 JSON 输出路径（写前自动建目录）')

    def handle(self, *args, **options):
        cfg = llm_config()
        if not cfg['available']:
            raise CommandError(
                'LLM key 未配置（SCIREAGENT_LLM_API_KEY）。'
                '提供 key 后重跑即可——key/base_url/model 均可后期变更，零代码改动。'
            )

        qs = self._pick_protocols(options)
        self.stdout.write(f'取样 {qs.count()} 个协议（共 {Protocol.objects.count()}）')

        extractor = LLMExtractor(
            api_key=cfg['api_key'], base_url=cfg['base_url'], model=cfg['model'])
        rows = []
        for p in qs:
            try:
                result = extractor.extract_topchain(build_prompt(
                    name=p.name, objective=p.objective,
                    principle=p.principle, reagents=p.reagents))
            except Exception as e:  # noqa: BLE001 —— pilot 阶段单协议失败不中断全量
                result = {'error': str(e)}
            rows.append({
                'protocol_id': p.id,
                'protocol_name': p.name,
                'research_goals': result.get('research_goals', []),
                'applications': result.get('applications', []),
                'error': result.get('error'),
            })
            self.stdout.write(f'  p={p.id} {p.name[:40]} '
                              f'RG={len(result.get("research_goals", []))} '
                              f'AP={len(result.get("applications", []))}')

        report = self._build_report(cfg, rows)
        self._write_report(report, options['report'])
        self._write_review_md(rows, options['report'])

    def _pick_protocols(self, options):
        ids = [int(x) for x in options['protocol_ids'].split(',') if x.strip()]
        if ids:
            return Protocol.objects.filter(id__in=ids)
        # 正文最丰富的非测试协议优先（LLM 提取效果最好）
        return (Protocol.objects.exclude(objective='')
                .exclude(principle='')
                .order_by('-objective')[:options['count']])

    def _build_report(self, cfg, rows):
        n_rg = sum(len(r['research_goals']) for r in rows)
        n_ap = sum(len(r['applications']) for r in rows)
        n_empty = sum(1 for r in rows if not r['research_goals']
                      and not r['applications'] and not r.get('error'))
        return {
            'mode': 'dry-run',
            'llm': {'model': cfg['model'], 'base_url': cfg['base_url']},
            'stats': {
                'protocols': len(rows),
                'research_goals': n_rg,
                'applications': n_ap,
                'empty_output': n_empty,
                'errors': sum(1 for r in rows if r.get('error')),
            },
            'rows': rows,
        }

    def _write_report(self, report, path):
        if not path:
            return
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        self.stdout.write(f'报告已写入 {path}')

    def _write_review_md(self, rows, report_path):
        """黄金集抽检 md（与 C1 pilot_review.md 同款方法论）。"""
        if not report_path:
            return
        base = os.path.splitext(report_path)[0]
        path = base + '_review.md'
        lines = [
            '# 顶部链 AI 提取 pilot — 黄金集抽检报告',
            '',
            '> 目的：三层护栏②黄金集闸门——请你人工核对提取的 RG/AP 与协议的相关性，',
            '> 准确率 ≥90% 才放行 T4 全量。',
            '> 判定标准：该协议是否确实服务该研究目标/实验场景（与协议内容直接相关）。',
            '',
        ]
        idx = 0
        for r in rows:
            cands = [(t, e) for t in ('research_goals', 'applications')
                     for e in r.get(t, [])]
            if not cands and not r.get('error'):
                continue
            lines.append(f"## 协议 p={r['protocol_id']}：{r['protocol_name']}")
            if r.get('error'):
                lines.append(f"- 提取失败: {r['error']}")
            else:
                for t, e in cands:
                    idx += 1
                    lines.append(
                        f"- [{idx}] **{t}** `{e['name']}` "
                        f"置信度 {e.get('confidence', '?')}")
            lines.append('')
        lines += [
            '## 判定方式',
            '1. 逐条给出「相关 / 不相关」；',
            f'2. 准确率 = 相关数 / {idx}；≥90% → 放行 T4 全量提取；',
            '3. 不达标 → 收紧 prompt（如提高置信度阈值）或人工修正后重跑。',
            '',
        ]
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        self.stdout.write(f'黄金集报告已写入 {path}')
