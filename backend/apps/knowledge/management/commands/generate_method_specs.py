"""
generate_method_specs — 用「语料证据 + LLM 判读」为 canonical Method 生成
advantages / limitations / timeline 初稿。

## 为什么现在做（2026-10-31 生产实测）

与本仓 `generate_method_descriptions`（只管 summary/purpose）的矛盾说明：
旧命令 docstring 断言「advantages/limitations 语料里没有」以及
「protocol_step.duration_seconds 全部为 0 ⇒ timeline 无来源」。本次实测推翻了一半：

| 字段 | 实测底数 | 结论 |
|---|---|---|
| `advantages` | `advantag` 命中 **432** 条 published 协议，覆盖 **67/83** 方法 | 可提取**证据**，但只能到「某论文某变体」层级，不能自动合成结论 |
| `limitations` | `limitation/drawback/caveat/pitfall` 命中 **278** 条，覆盖 **65/83** | 同上 |
| `timeline` | 步骤正文 **26.0%** 含时间表述；**79.1%** 协议可算出耗时；**83/83** 方法有覆盖 | 有数据，但**纯正则不够格** |
| `cost_band` | **零来源** | 不生成（见下） |

### timeline 为什么不能只用正则

粗暴求和跑出来 `#559 CLARITY = 1923h（80 天）`，来源是原文
`mice (6-8 weeks, 25.4-28.6g, n=4)` —— **小鼠周龄被当成实验耗时**。
排除「样本规格 / 试剂保存期 / 无动作语境」三类误判后，用 11 个有教科书
基准的方法验证：sum 法 8/11（72.7%），max 法 7/11（63.6%）。错的三个方向一致，
全是**低估长周期**（干细胞培养 weeks→days、文库构建 days→hours）。

⇒ 正则只作**候选值**，最终档位由 LLM 判定；两者不一致时落 LLM 值并强制进审核表
（LLM 能看到「这是细胞培养」这类语义，正则看不到）。

### timeline 语义（2026-10-31 用户定稿）

「做一次该方法的**典型总周期**，含样本准备、细胞/动物培养、孵育与等待时间；
不含试剂保存期、不含样本的年龄体重规格。」

### advantages / limitations 为什么是「证据 + 综合」而不是纯生成

若纯 LLM 生成，产物是以「事实」面貌出现的模型常识；若纯语料聚合，每个方法手上有
12~25 条来自不同论文的表述且**互相矛盾**（A 论文说 simple and reliable，
B 论文说 laborious and error-prone，两者都对，说的是不同变体）。
⇒ 把证据喂给 LLM，要求「只报共识、略去变体特有评价、证据不足处只用教科书稳定共识」。

### cost_band 为什么完全不生成

枚举定义是 `<$50 / $50-200 / >$200 per sample`。全仓唯一价格来源是 SKU 36 条
（$59~$989，试剂单价，且只有 15 个可见产品），与 83 个方法**零映射**。
PCR 做一次 per-sample 可能 <$5，但买一管 Taq 要 $200+ —— 拿 SKU 价推成本档是错的。
且该枚举写死美元，对中国用户本身是设计缺陷。
**用户 2026-10-31 拍板：留空。** 故本命令永不写 cost_band。

## 审核标记

写入后 `specs_reviewed_at` 保持 **null**（= AI 初稿未审）。与
`description_reviewed_at` 分开，因为两者是不同批次、不同来源的产物。

## 用法

    python manage.py generate_method_specs --limit 3 --dry-run
    python manage.py generate_method_specs --limit 3 --apply
    python manage.py generate_method_specs --limit 0 --apply --csv docs/methods83_specs_review.csv
    python manage.py generate_method_specs --verify
"""
import csv
import json
import os
import re
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.bridges.models import MethodProtocol
from apps.knowledge.models import Method, Protocol, ProtocolStep
from apps.knowledge.services.llm_extractor import LLMExtractor, LLMNotConfigured

# ─────────────────────────── 时间表述正则（已在 _ana6 单测通过）───────────────
NUM = r'\d+(?:\.\d+)?'
UNIT_SEC = r'(?:s|secs?|seconds?)'
UNIT_MIN = r'(?:min|mins?|minutes?)'
UNIT_HR = r'(?:h|hr|hrs|hours?)'
UNIT_DAY = r'(?:d|days?)'
UNIT_WK = r'(?:wks?|weeks?)'
UNITS = '(?:' + UNIT_SEC + '|' + UNIT_MIN + '|' + UNIT_HR + '|' + UNIT_DAY + '|' + UNIT_WK + ')'

TIME_HIT = re.compile(
    r'(?:' + NUM + r'[ \t]*(?:-|~|to|–)[ \t]*)?(' + NUM + r')[ \t]*(' + UNITS + r')\b'
    r'|\b(overnight)\b',
    re.I,
)
# ① 样本规格（小鼠 6-8 周龄、括号里的规格）—— 不计入耗时
SPEC_RX = re.compile(
    r'\b(?:aged?|age of|weeks?[ \t]*(?:of[ \t]*)?old|old[ \t]*|at[ \t]+the[ \t]+age)\b', re.I)
BRACKET_SPEC = re.compile(
    r'[\(\[]\s*(?:' + NUM + r'[ \t]*(?:-|~|to|–)[ \t]*)?' + NUM + r'[ \t]*'
    r'(?:weeks?|days?|months?)\s*[,;\)\]]', re.I)
# ② 试剂保存期
STORE_RX = re.compile(
    r'stor(?:e|ed|age|ing)|can[ \t]+be[ \t]+kept|stable[ \t]+for|shelf[ \t]*life|'
    r'keep[ \t]+at|use[ \t]+within|discard[ \t]+after|expir', re.I)
# ③ 动作语境（时间表述必须紧邻实验动作才算操作耗时）
ACTION_RX = re.compile(
    r'incubat|wait|leave|stand|settle|shake|rock|rotat|centrifug|spin|heat|bake|dry|'
    r'wash|rinse|run|electrophor|block|stain|rest|grow|cultur|adapt|fix|permeabil|'
    r'hybridi|digest|lyse|lysis|autoradiograph|expos|develop|overnight|at[ \t]+\d+\s*°?C',
    re.I)

VALID_TIMELINE = ('minutes', 'hours', 'days', 'weeks')
BAND_HUMAN = {
    'minutes': 'minutes (<30 min)', 'hours': 'hours (30 min-4 h)',
    'days': 'days (1-7 d)', 'weeks': 'weeks (>1 week)',
}

ADV_RX = re.compile(r'\badvantag', re.I)
LIM_RX = re.compile(r'\blimitation|\bdrawback|\bcaveat|\bpitfall', re.I)
# 营销词黑名单 —— 出现即视为不合格行
MARKETING = re.compile(
    r'\b(revolutionary|cutting-edge|state-of-the-art|powerful|breakthrough|'
    r'world-class|best-in-class|game-changing|unparalleled|superior)\b', re.I)
# 变体级信号：出现具体试剂/耗材/仪器细节 ⇒ 说的是某个 protocol 的做法，不是方法本身的优劣。
# 不剔行（有些是通用描述），只记入审核表供人工判读。
VARIANT_HINT = re.compile(
    r'\b(?:\d{2,4}[-\s]?well|CTAB|SDS|Trizol|TRIzol|chloroform|phenol|'
    r'bead[-\s]?beating|magnetic[-\s]bead|silica[-\s]?column|column[-\s]based|'
    r'multiplex[-\s]free|universal[-\s]primer|redundant[-\s]primer|'
    r'in[-\s]house|kit[-\s]based)\b', re.I)


def _scale(unit):
    u = unit.lower().rstrip('s')
    if u.startswith('sec') or u == 's':
        return 1
    if u.startswith('min'):
        return 60
    if u.startswith('h'):
        return 3600
    if u.startswith('d'):
        return 86400
    if u.startswith('w'):
        return 604800
    return 1


def parse_step_seconds(text):
    """从单步正文取耗时秒数；已排除样本规格 / 保存期 / 无动作语境。"""
    out = []
    for m in TIME_HIT.finditer(text):
        i, j = max(0, m.start() - 60), min(len(text), m.end() + 60)
        ctx = text[i:j].replace('\n', ' ')
        has_action = bool(ACTION_RX.search(ctx))
        if not has_action:
            continue
        if BRACKET_SPEC.search(ctx) or SPEC_RX.search(ctx) or STORE_RX.search(ctx):
            continue
        if m.group(3):
            out.append(8 * 3600)
            continue
        out.append(float(m.group(1)) * _scale(m.group(2)))
    return out


def band_of(sec):
    if sec < 30 * 60:
        return 'minutes'
    if sec < 4 * 3600:
        return 'hours'
    if sec < 7 * 86400:
        return 'days'
    return 'weeks'


def fmt_hours(sec):
    if sec is None:
        return ''
    if sec >= 86400:
        return f'{sec / 86400:.1f} d'
    if sec >= 3600:
        return f'{sec / 3600:.1f} h'
    return f'{sec / 60:.0f} min'


SYSTEM_PROMPT = (
    "You are a senior molecular biologist writing catalogue copy for a reagent "
    "supplier's knowledge base. Your readers are working researchers choosing "
    "which technique to use.\n\n"
    "Hard rules:\n"
    "- Ground every statement in the evidence provided. Where evidence is absent you may "
    "state only textbook-stable consensus about the named technique.\n"
    "- NEVER invent numbers, sensitivities, yields, detection limits, turnaround times, "
    "or vendor/catalogue claims.\n"
    "- Never mention vendors, brand names, or catalogue numbers.\n"
    "- No marketing adjectives (revolutionary, cutting-edge, powerful, breakthrough...).\n"
    "- If evidence is contradictory, report the CONSENSUS and omit variant-specific "
    "opinions rather than averaging them into a vague claim.\n"
    "- Output strict JSON only, no markdown fence, no commentary.\n\n"
    "LEVEL OF ABSTRACTION — the most common failure, read carefully:\n"
    "- Write about the METHOD AS A WHOLE, never about one protocol variant.\n"
    "- BAD (variant-level): \"CTAB-chloroform chemistry is adaptable to 96-well format\", "
    "\"universal primer designs exploit conserved regions\", \"SDS-based lysis buffers "
    "stabilise samples for archiving\".\n"
    "- GOOD (method-level): \"Yields high-molecular-weight DNA suitable for long-read "
    "sequencing\", \"Tolerates degraded and low-input samples\", \"Needs only a thermal "
    "cycler and standard lab reagents\".\n"
    "- Test each line: would it still be true if a different lab ran this method with a "
    "different protocol? If not, it is variant-level — generalise it or drop it.\n"
    "- An advantage must be a genuine ADVANTAGE (why choose this method), not a "
    "description of what the method does. \"Amplifies a target region\" is a description; "
    "\"detects as little as a single copy\" is an advantage."
)

USER_TEMPLATE = """Method name: {name}

Evidence 1 — measured durations from {n_proto} published protocols that use this
method. Already filtered to exclude specimen age/size specs and reagent storage
periods:
  band distribution: minutes {d_minutes} / hours {d_hours} / days {d_days} / weeks {d_weeks}
  median per-protocol total: {median}
  heuristic band: {re_band}

Evidence 2 — representative protocols (title + objective excerpt):
{titles}

Evidence 3 — verbatim protocol text that happens to mention ADVANTAGES.
Two caveats: (a) these come from single papers and mostly describe ONE VARIANT,
so use them only to stay consistent with the corpus — do NOT restate the
variant-specific details; (b) some excerpts may come from protocols only loosely
related to this method name — ignore any excerpt that does not clearly concern
this method:
{adv_evidence}

Evidence 4 — same caveat, verbatim text mentioning LIMITATIONS / DRAWBACKS:
{lim_evidence}

Now produce:
- "timeline": exactly one of minutes | hours | days | weeks.
  Definition: total elapsed time from starting a TYPICAL COMPLETE run of this
  method to obtaining the final result, INCLUDING sample preparation,
  cell/animal culture and incubation/waiting periods. EXCLUDING reagent shelf
  life and specimen age/weight specifications.
  If the method inherently spans multiple weeks (establishing a cell line,
  differentiating stem cells, breeding animals, multi-cycle selection), choose
  weeks even when individual hands-on sessions are short.
  Use the measured data as the primary signal; override it when the measured
  value is clearly an artefact (e.g. a specimen age mistaken for a duration).
- "timeline_reason": <= 20 words explaining the band choice.
- "advantages": 2-4 lines, one short METHOD-LEVEL advantage per line, newline
  separated, each <= 25 words. No numbering, no bullet characters.
- "limitations": 2-4 lines, same format and same method-level rule.

Return exactly:
{{"timeline": "...", "timeline_reason": "...", "advantages": "...", "limitations": "..."}}"""


class Command(BaseCommand):
    help = '为 canonical Method 生成 advantages/limitations/timeline 初稿（默认 dry-run）'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20,
                            help='只处理协议数最多的前 N 个（默认 20；0 = 全部）')
        parser.add_argument('--fields', default='all',
                            help='all | timeline | advantages | limitations')
        parser.add_argument('--titles', type=int, default=5,
                            help='上下文取多少条协议（默认 5）')
        parser.add_argument('--evidence', type=int, default=4,
                            help='adv/lim 各取多少条原文片段（默认 4；多了会灌入变体噪声）')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--verify', action='store_true')
        parser.add_argument('--csv', default='',
                            help='--apply 时把审核表写到该路径')
        parser.add_argument('--sample', type=int, default=3,
                            help='dry-run 时打印前 N 条供人工判读（默认 3；判读多方法时调大）')
        parser.add_argument('--backup-dir', default='/home/admin/scireagent/scireagent_backups')

    def handle(self, *args, **opts):
        if opts['verify']:
            return self._verify()

        fields = opts['fields']
        want_tl = fields in ('all', 'timeline')
        want_adv = fields in ('all', 'advantages')
        want_lim = fields in ('all', 'limitations')

        methods = list(
            Method.objects.filter(status='active', application_id__isnull=True)
            .annotate(n_proto=Count('method_protocols'))
            .order_by('-n_proto')
        )
        if opts['limit']:
            methods = methods[:opts['limit']]
        self.stdout.write(f'待处理方法 {len(methods)} 个（按协议数降序）｜字段 {fields}')
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
            try:
                ctx = self._gather(m, opts['titles'], opts['evidence'])
            except Exception as exc:
                failures.append((m.id, m.name, f'取证据失败 {type(exc).__name__}: {exc}'[:120]))
                continue
            if not ctx['n_proto']:
                failures.append((m.id, m.name, '无 published 协议可作上下文'))
                continue

            try:
                raw = extractor.chat(SYSTEM_PROMPT, self._user_prompt(m.name, ctx))
                payload = self._parse(raw)
            except Exception as exc:  # 单个失败不中断整批
                failures.append((m.id, m.name, f'{type(exc).__name__}: {exc}'[:120]))
                continue

            cleaned, problems = self._validate(payload, want_tl, want_adv, want_lim)
            agree = ''
            if want_tl and ctx['re_band']:
                agree = 'agree' if cleaned['timeline'] == ctx['re_band'] else 'DISAGREE'

            results.append({
                'id': m.id, 'name': m.name, 'n_proto': ctx['n_proto'],
                're_band': ctx['re_band'], 're_median': ctx['re_median'],
                'dist': ctx['dist'],
                'advantage': cleaned['advantages'], 'limitations': cleaned['limitations'],
                'timeline': cleaned['timeline'], 'reason': cleaned['timeline_reason'],
                'agree': agree, 'problems': problems,
                'adv_n': len(ctx['adv_evidence']), 'lim_n': len(ctx['lim_evidence']),
            })
            flag = ' ⚠️' + ';'.join(problems) if problems else ''
            self.stdout.write(f'  [{i}/{len(methods)}] {m.name[:36]:<38} '
                              f'tl={cleaned["timeline"] or "—":<8} {agree}{flag}')

        self.stdout.write(f'\n成功 {len(results)}｜失败 {len(failures)}')
        for f in failures[:12]:
            self.stdout.write(self.style.WARNING(f'  id={f[0]} {f[1][:34]} → {f[2]}'))

        if not opts['apply']:
            n_show = max(1, opts['sample'])
            self.stdout.write(f'\n=== 样本（前 {n_show} 条）===')
            for r in results[:n_show]:
                self._dump_one(r)
            self.stdout.write(self.style.WARNING('\n预演，未写库。加 --apply 执行。'))
            return

        self._write_backup(results, opts['backup_dir'])
        n = 0
        for r in results:
            upd = {}
            if want_adv and r['advantage']:
                upd['advantages'] = r['advantage']
            if want_lim and r['limitations']:
                upd['limitations'] = r['limitations']
            if want_tl and r['timeline']:
                upd['timeline'] = r['timeline']
            if not upd:
                continue
            # specs_reviewed_at 保持 None —— 明确标记为「AI 初稿未审」
            n += Method.objects.filter(id=r['id']).update(**upd, specs_reviewed_at=None)
        self.stdout.write(self.style.SUCCESS(
            f'\n已写入 {n} 个方法（specs_reviewed_at 保持空 = 未审）'))

        if opts['csv']:
            self._write_csv(results, opts['csv'])
        self._verify()

    # ───────────────────────────── 取证据 ─────────────────────────────
    def _gather(self, method, n_titles, n_evidence):
        links = list(
            MethodProtocol.objects
            .filter(method=method, status='active', protocol__status='published')
            .values_list('protocol_id', flat=True)
        )
        pids = list(dict.fromkeys(links))
        ctx = {'n_proto': len(pids), 're_band': '', 're_median': None,
               'dist': {}, 'titles': [], 'adv_evidence': [], 'lim_evidence': []}
        if not pids:
            return ctx

        names = dict(Protocol.objects.filter(id__in=pids[:n_titles])
                     .values_list('id', 'name'))
        objs = dict(Protocol.objects.filter(id__in=pids[:n_titles])
                    .values_list('id', 'objective'))
        for pid in pids[:n_titles]:
            nm = (names.get(pid) or '')[:150]
            ob = ' '.join((objs.get(pid) or '').split())[:180]
            ctx['titles'].append(f'{nm}' + (f' — {ob}' if ob else ''))

        # 耗时聚合
        per_proto = {}
        for st in ProtocolStep.objects.filter(protocol_id__in=pids) \
                .only('protocol_id', 'body').iterator(chunk_size=2000):
            secs = parse_step_seconds(st.body or '')
            if secs:
                per_proto[st.protocol_id] = per_proto.get(st.protocol_id, 0) + sum(secs)
        if per_proto:
            vals = sorted(per_proto.values())
            med = vals[len(vals) // 2]
            ctx['re_median'] = med
            ctx['re_band'] = band_of(med)
            dist = {}
            for v in vals:
                b = band_of(v)
                dist[b] = dist.get(b, 0) + 1
            ctx['dist'] = dist

        # adv/lim 证据
        # ⚠️ 三条循环都必须检查上限：只在最内层 break 会让每个协议都追加一条，
        #    实测 `--evidence 4` 最后拿到 16 条（去重后），证据池失去控制。
        seen_adv, seen_lim = [], []
        adv_keys, lim_keys = set(), set()
        for p in Protocol.objects.filter(id__in=pids) \
                .only('id', 'objective', 'principle', 'troubleshooting',
                      'expected_results').iterator(chunk_size=500):
            if len(seen_adv) >= n_evidence and len(seen_lim) >= n_evidence:
                break
            adv_text = ' '.join(filter(None, [p.objective, p.principle, p.troubleshooting]))
            lim_text = ' '.join(filter(None, [p.objective, p.principle, p.troubleshooting,
                                              p.expected_results]))
            for text, rx, bucket, keys in (
                (adv_text, ADV_RX, seen_adv, adv_keys),
                (lim_text, LIM_RX, seen_lim, lim_keys),
            ):
                if not text or len(bucket) >= n_evidence:
                    continue
                for mm in rx.finditer(text):
                    i = max(0, mm.start() - 150)
                    frag = ' '.join(text[i:mm.end() + 170].split())
                    key = frag[:80]
                    if key in keys:
                        continue
                    keys.add(key)
                    bucket.append(frag)
                    if len(bucket) >= n_evidence:
                        break
        ctx['adv_evidence'] = seen_adv
        ctx['lim_evidence'] = seen_lim
        return ctx

    def _user_prompt(self, name, ctx):
        d = ctx['dist']
        adv = '\n'.join(f'- {s[:320]}' for s in ctx['adv_evidence']) or '(none found)'
        lim = '\n'.join(f'- {s[:320]}' for s in ctx['lim_evidence']) or '(none found)'
        return USER_TEMPLATE.format(
            name=name,
            n_proto=ctx['n_proto'],
            d_minutes=d.get('minutes', 0), d_hours=d.get('hours', 0),
            d_days=d.get('days', 0), d_weeks=d.get('weeks', 0),
            median=fmt_hours(ctx['re_median']) or 'unknown',
            re_band=BAND_HUMAN.get(ctx['re_band'], 'unknown'),
            titles='\n'.join(f'{i}. {t}' for i, t in enumerate(ctx['titles'], 1)) or '(none)',
            adv_evidence=adv, lim_evidence=lim,
        )

    # ───────────────────────────── 校验 ─────────────────────────────
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

    def _clean_lines(self, value, max_lines=4):
        """把 LLM 输出规整成「每行一条」，去掉编号/项目符号，剔除营销词行。"""
        raw = (value or '').strip()
        if not raw:
            return ''
        lines = []
        for ln in raw.split('\n'):
            s = ln.strip().lstrip('-•*·').strip()
            s = re.sub(r'^\d+[\.\)、]\s*', '', s)
            s = re.sub(r'^[a-zA-Z][\.\)]\s*', '', s)
            s = ' '.join(s.split())
            if not s:
                continue
            if MARKETING.search(s):
                continue
            if len(s.split()) > 40:      # 过长说明模型在写段落，不是条目
                s = ' '.join(s.split()[:40])
            lines.append(s)
            if len(lines) >= max_lines:
                break
        return '\n'.join(lines)

    def _validate(self, payload, want_tl, want_adv, want_lim):
        problems = []
        out = {'timeline': '', 'timeline_reason': '', 'advantages': '', 'limitations': ''}
        if want_tl:
            tl = str(payload.get('timeline') or '').strip().lower()
            if tl in VALID_TIMELINE:
                out['timeline'] = tl
            else:
                problems.append(f'非法 timeline={tl!r}')
            out['timeline_reason'] = ' '.join(
                str(payload.get('timeline_reason') or '').split())[:160]
        if want_adv:
            out['advantages'] = self._clean_lines(payload.get('advantages'))
            if not out['advantages']:
                problems.append('advantages 空')
        if want_lim:
            out['limitations'] = self._clean_lines(payload.get('limitations'))
            if not out['limitations']:
                problems.append('limitations 空')
        # 变体级细节检测：不剔行，只记入审核表（人工判读时优先看这些）
        for key in ('advantages', 'limitations'):
            if not out[key]:
                continue
            hits = sorted({m.group(0).lower() for m in VARIANT_HINT.finditer(out[key])})
            if hits:
                problems.append(f'{key} 含变体级细节 {"/".join(hits[:3])}')
        return out, problems

    # ───────────────────────────── 落盘 ─────────────────────────────
    def _write_backup(self, results, backup_dir):
        try:
            os.makedirs(backup_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d-%H%M%S')
            path = os.path.join(backup_dir, f'method_specs_{ts}.json')
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump({'created_at': ts, 'items': results}, fh,
                          ensure_ascii=False, indent=1)
            self.stdout.write(f'备份：{path}')
        except OSError as exc:
            self.stdout.write(self.style.WARNING(f'备份失败（不影响写库）：{exc}'))

    def _write_csv(self, results, path):
        cols = ['method_id', 'method_name', 'protocols', 're_band', 're_median',
                'llm_timeline', 'agree', 'timeline_reason', 'problems',
                'adv_evidence_n', 'lim_evidence_n', 'advantages', 'limitations',
                'verdict', 'new_timeline', 'new_advantages', 'new_limitations', 'note']
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for r in results:
                w.writerow([
                    r['id'], r['name'], r['n_proto'], r['re_band'],
                    fmt_hours(r['re_median']), r['timeline'], r['agree'],
                    r['reason'], ';'.join(r['problems']), r['adv_n'], r['lim_n'],
                    r['advantage'], r['limitations'], '', '', '', '', '',
                ])
        self.stdout.write(f'审核表：{path}（{len(results)} 行）')

    def _dump_one(self, r):
        self.stdout.write(f'\nid={r["id"]}  {r["name"]}  （{r["n_proto"]} 协议）')
        self.stdout.write(f'  timeline: {r["timeline"] or "—"}'
                          f'  [正则候选 {r["re_band"] or "无"} / 中位 '
                          f'{fmt_hours(r["re_median"]) or "—"}]  {r["agree"]}')
        self.stdout.write(f'  reason  : {r["reason"]}')
        self.stdout.write(f'  adv证据 {r["adv_n"]} 条｜lim证据 {r["lim_n"]} 条')
        for label, val in (('advantages', r['advantage']),
                           ('limitations', r['limitations'])):
            self.stdout.write(f'  {label}:')
            for ln in (val or '').split('\n'):
                self.stdout.write(f'    · {ln}')

    def _verify(self):
        qs = Method.objects.filter(status='active', application_id__isnull=True)
        total = qs.count()
        self.stdout.write('\n=== 核查 ===')
        self.stdout.write(f'canonical 方法        {total}')
        for f in ('summary', 'advantages', 'limitations', 'cost_band', 'timeline'):
            self.stdout.write(f'  有 {f:<14} {qs.exclude(**{f: ""}).count()}')
        self.stdout.write(f'  描述已审            '
                          f'{qs.filter(description_reviewed_at__isnull=False).count()}')
        self.stdout.write(f'  规格已审            '
                          f'{qs.filter(specs_reviewed_at__isnull=False).count()}')
        bad = qs.exclude(timeline='').exclude(timeline__in=VALID_TIMELINE).count()
        self.stdout.write(f'  非法 timeline 值    {bad}'
                          + (' ← 必须为 0' if bad else ''))
