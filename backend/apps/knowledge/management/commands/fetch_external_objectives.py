"""
fetch_external_objectives — A 类补全：授权外部抓取补齐 Protocol.objective 空缺口。

背景：98 个 Protocol.objective 为空（95 curated + 3 bioprocorpus）。
用户决策：全量 98 个；数据源 Bio-protocol + PubMed 都试，取最匹配一条写入。
铁律：宁 miss 不错配（标题相似度 < 门槛 → 跳过，绝不误写）。

数据源可达性（2026-08-07/08-08 实测）：
- PubMed E-utilities：沙箱内可直接访问（复用 core/datasource_client 限速+重试）。
- Bio-protocol：沙箱内 HTTPS 证书已过期（各本地 TLS 栈均报错），in-process 不可达；
  故 Bio-protocol 经 WebFetch 离线路预取，结果存为 overrides JSON（--bio-protocol-file），
  命令消费该文件如同 in-process 源。
- Europe PMC（--epmc，默认关）：沙箱内可直达，resultType=core 一次请求即内嵌摘要，
  且覆盖 PubMed 不索引的预印本平台（protocols.exchange / Research Square / bioRxiv）。
  默认关闭是为了不改变既有跑法的结果；需要时显式打开。
三源仍是「都试，取最匹配」。

契约：
- 默认只处理 objective='' 的 Protocol（除非 --force 覆盖非空）
- 默认 --only=all（curated + bioprocorpus 全量 98）；可 --only=curated / --only=bioprocorpus
- --dry-run（默认）：只报告候选，不落库
- --apply：原地 UPDATE Protocol.objective（不新建 Protocol / ProductProtocol 行）
- --record-source：把来源 PMID/URL 追加进 references 字段（可归因，默认关）
- --bio-protocol-file：Bio-protocol overrides JSON（{name: {objective, source_title, url}}）
- 幂等
"""
import json
import os

from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.models import Protocol
from apps.knowledge.services.pubmed_client import PubMedClient
from apps.knowledge.services.europepmc_client import EuropePMCClient
from apps.knowledge.services import external_objective as eo

BATCH = 500


def _load_allowlist(value):
    """解析 --allowlist：JSON 文件路径 或 逗号分隔 id 串。

    JSON 支持 [1,2,3] / {"ids":[1,2,3]} / [{"id":1},...] 三种形态。
    返回 set[int]；解析不出任何 id 视为配置错误。
    """
    ids = set()
    if os.path.isfile(value):
        with open(value, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get('ids') or []
        for item in data or []:
            if isinstance(item, dict):
                item = item.get('id')
            try:
                ids.add(int(item))
            except (TypeError, ValueError):
                continue
    else:
        for tok in str(value).replace('\n', ',').split(','):
            tok = tok.strip()
            if not tok:
                continue
            try:
                ids.add(int(tok))
            except ValueError:
                raise CommandError(f"--allowlist 无法解析为 id：{tok!r}")
    if not ids:
        raise CommandError(f"--allowlist 未解析出任何 id：{value!r}")
    return ids


def _load_report(path):
    """读取 --report 产出的诊断 JSON，返回 {protocol_id: entry}。"""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    out = {}
    for entry in data or []:
        try:
            out[int(entry.get('id'))] = entry
        except (TypeError, ValueError):
            continue
    return out


def _load_bio_overrides(path):
    """读取 Bio-protocol overrides JSON：{name: {objective, source_title, url}}。

    返回 {(name.strip()): entry}；空值/缺 objective 的条目跳过。
    """
    out = {}
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, list):
        data = {d.get('name', '').strip(): d for d in data if d.get('name')}
    for name, entry in data.items():
        name = (name or '').strip()
        if not name or not isinstance(entry, dict) or not entry.get('objective'):
            continue
        out[name] = entry
    return out


class Command(BaseCommand):
    help = "从 PubMed / Bio-protocol 外部抓取补齐 Protocol.objective 空缺口（取最匹配一条）。"

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='落库写入 objective（默认 --dry-run 只报告）')
        parser.add_argument('--only', default='all',
                            choices=['all', 'curated', 'bioprocorpus'],
                            help='处理范围：all / curated / bioprocorpus')
        parser.add_argument('--bio-protocol-file', default=None,
                            help='Bio-protocol overrides JSON 路径（WebFetch 离线路预取结果）')
        parser.add_argument('--pubmed-threshold', type=float,
                            default=eo.PUBMED_THRESHOLD,
                            help='PubMed 采纳门槛（协议名显著 token 在文章标题的覆盖率）')
        parser.add_argument('--bioprotocol-threshold', type=float,
                            default=eo.BIOPROTOCOL_THRESHOLD,
                            help='Bio-protocol 采纳门槛（协议名显著 token 在文章标题的覆盖率）')
        parser.add_argument('--epmc', action='store_true',
                            help='启用 Europe PMC 第三源（默认关）。一次请求内嵌摘要，'
                                 '且覆盖 PubMed 不索引的预印本平台；但错配率更高，'
                                 '落库务必配合 --from-report + --allowlist 人工收口')
        parser.add_argument('--epmc-threshold', type=float,
                            default=eo.EUROPEPMC_THRESHOLD,
                            help='Europe PMC 采纳门槛（口径同 PubMed）')
        parser.add_argument('--limit', type=int, default=0,
                            help='最多处理 N 个（调试用，0=不限制）')
        parser.add_argument('--force', action='store_true',
                            help='覆盖已有 objective（默认只填空值）')
        parser.add_argument('--record-source', action='store_true',
                            help='把来源 PMID/URL 追加进 references（可归因）')
        parser.add_argument('--report', default=None,
                            help='把逐协议匹配诊断写入该 JSON 路径（dry-run 审核用）')
        parser.add_argument('--semantic-report', default=None,
                            help='MiniLM 语义相似度预计算 JSON（{id: score}），'
                                 '由独立 emb3_venv 进程产出；对 token<门槛但有文本的边界项，'
                                 '语义>=SEMANTIC_THRESHOLD 仍采纳')
        parser.add_argument('--from-report', default=None,
                            help='零网络重放：从已审核的 --report 诊断 JSON 读取候选与 '
                                 'objective 文本，不再联网抓取（PubMed 间歇 502 会让联网'
                                 '重跑结果不可复现）。采纳门仍会重新判定。')
        parser.add_argument('--allowlist', default=None,
                            help='只写入这些 Protocol id（JSON 文件或逗号分隔串）。'
                                 '用于人工复核收口：自动门放行的候选里可能混有'
                                 '「正文点名了另一个方法」的错配，由白名单最终裁定。')

    def handle(self, *args, **options):
        apply = options['apply']
        only = options['only']
        bio_file = options['bio_protocol_file']
        p_thr = options['pubmed_threshold']
        b_thr = options['bioprotocol_threshold']
        use_epmc = options['epmc']
        e_thr = options['epmc_threshold']
        limit = options['limit']
        force = options['force']
        record_source = options['record_source']
        report_path = options['report']
        semantic_path = options['semantic_report']
        from_report_path = options['from_report']
        allowlist_opt = options['allowlist']

        bio_overrides = {}
        semantic_scores = {}
        replay = None
        allow_ids = None
        if from_report_path:
            if not os.path.isfile(from_report_path):
                raise CommandError(f"重放报告文件不存在：{from_report_path}")
            replay = _load_report(from_report_path)
            self.stdout.write(f"重放报告：{len(replay)} 条（零网络）")
        if allowlist_opt:
            allow_ids = _load_allowlist(allowlist_opt)
            self.stdout.write(f"白名单：{len(allow_ids)} 个 id")
        if semantic_path:
            if not os.path.isfile(semantic_path):
                raise CommandError(f"语义报告文件不存在：{semantic_path}")
            with open(semantic_path, encoding='utf-8') as f:
                raw = json.load(f)
            # 支持 {id: score} 或 {id: {"semantic": score}} 两种格式
            for k, v in raw.items():
                try:
                    pid = int(k)
                except (TypeError, ValueError):
                    continue
                if isinstance(v, dict):
                    v = v.get('semantic') or v.get('semantic_similarity')
                if isinstance(v, (int, float)):
                    semantic_scores[pid] = float(v)
            self.stdout.write(f"语义报告：{len(semantic_scores)} 条")
        if bio_file:
            if not os.path.isfile(bio_file):
                raise CommandError(f"Bio-protocol overrides 文件不存在：{bio_file}")
            bio_overrides = _load_bio_overrides(bio_file)
            self.stdout.write(f"Bio-protocol overrides：{len(bio_overrides)} 条")

        qs = Protocol.objects.all()
        if only == 'curated':
            qs = qs.filter(source=Protocol.Source.CURATED)
        elif only == 'bioprocorpus':
            qs = qs.filter(source=Protocol.Source.BIOPROCORPUS)
        if not force:
            qs = qs.filter(objective='')
        if allow_ids is not None:
            qs = qs.filter(id__in=allow_ids)
        qs = qs.order_by('id')
        if limit:
            qs = qs[:limit]
        qs = qs.only('id', 'name', 'objective', 'references', 'source')

        client = PubMedClient()
        # 只在真正需要联网抓 EPMC 时才建客户端；重放模式恒为 None（零网络）
        epmc_client = EuropePMCClient() if (use_epmc and replay is None) else None

        updated = 0
        skipped = 0          # 各源皆无合格匹配
        bio_wins = 0
        pub_wins = 0
        epmc_wins = 0
        rows = []
        diag = []            # 逐协议诊断（dry-run 审核 + --report）
        for proto in qs.iterator(chunk_size=BATCH):
            name = proto.name.strip()
            sem = semantic_scores.get(proto.id)
            if replay is not None:
                entry = replay.get(proto.id) or {}
                pm = eo.replay_candidate(entry.get('pubmed'), p_thr, semantic_sim=sem)
                bio = eo.replay_candidate(entry.get('bioprotocol'), b_thr)
                # 重放恒读报告里的 europepmc 段（报告没有该键则为 None），
                # 不受 --epmc 开关影响：开关只管「是否联网抓」。
                ep = eo.replay_candidate(entry.get('europepmc'), e_thr, semantic_sim=sem)
            else:
                pm = eo.pubmed_candidate(client, name, p_thr, semantic_sim=sem)
                bio = eo.bio_candidate(name, bio_overrides.get(name), b_thr)
                ep = (eo.epmc_candidate(epmc_client, name, e_thr, semantic_sim=sem)
                      if epmc_client else None)
            pm_g = pm if (pm and pm['accepted']) else None
            bio_g = bio if (bio and bio['accepted']) else None
            ep_g = ep if (ep and ep['accepted']) else None
            chosen = eo.choose_best_match(name, pm_g, bio_g, ep_g)
            chosen_source = chosen[1] if chosen else None
            if chosen:
                objective, source_label, source_ref, sim = chosen
                if proto.objective != objective or record_source:
                    updated += 1
                    if source_label == 'bioprotocol':
                        bio_wins += 1
                    elif source_label == 'europepmc':
                        epmc_wins += 1
                    else:
                        pub_wins += 1
                    rows.append((proto, objective, source_label, source_ref, sim))
            else:
                skipped += 1
            diag.append({
                'id': proto.id, 'name': proto.name, 'source': proto.source,
                'pubmed': pm, 'bioprotocol': bio, 'europepmc': ep,
                'chosen': chosen_source,
            })

        # 报告
        mode = '重放' if replay is not None else ('联网+EPMC' if use_epmc else '联网')
        self.stdout.write(
            f"\n范围 --only={only}（{mode}），处理 {updated + skipped} "
            f"（匹配 {updated}：pubmed {pub_wins} / europepmc {epmc_wins} / "
            f"bioprotocol {bio_wins}；跳过 {skipped}）"
        )
        if allow_ids is not None:
            hit = {d['id'] for d in diag}
            missing = sorted(allow_ids - hit)
            if missing:
                self.stdout.write(self.style.WARNING(
                    f"白名单中 {len(missing)} 个 id 未进入处理范围"
                    f"（objective 已非空 / 不在 --only 范围 / id 不存在）：{missing}"
                ))
        def _fmt(cand):
            if not cand:
                return '-'
            return f"{cand['similarity']:.2f}{'✓' if cand['accepted'] else '✗'}"

        for d in diag:
            decision = d['chosen'] or 'SKIP'
            self.stdout.write(
                f"  [{decision:>10}] pm={_fmt(d['pubmed']):>5} "
                f"ep={_fmt(d.get('europepmc')):>5} bio={_fmt(d['bioprotocol']):>5}"
                f"  {d['name'][:70]}"
            )

        if report_path:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(diag, f, ensure_ascii=False, indent=2)
            self.stdout.write(f"诊断报告已写入：{report_path}")

        if not apply:
            self.stdout.write(self.style.WARNING(
                f"[dry-run] 候选 {updated} 条，未落库。加 --apply 执行写入。"
            ))
            return

        # 落库（bulk_update objective；可选 references）
        buf = []
        for proto, objective, source_label, source_ref, sim in rows:
            proto.objective = objective
            if record_source and source_ref:
                refs = (proto.references or '').strip()
                # tag 形态按标识本身判定（PMID / DOI / PMCID / URL）：Europe PMC 的
                # 预印本源没有 PMID 只有 DOI，不能一律加 PMID: 前缀。
                tag = eo.reference_tag(source_label, source_ref)
                if tag and tag not in refs:
                    proto.references = (refs + '\n' + tag).strip() if refs else tag
            buf.append(proto)
            if len(buf) >= BATCH:
                Protocol.objects.bulk_update(
                    buf, ['objective'] + (['references'] if record_source else [])
                )
                buf = []
        if buf:
            Protocol.objects.bulk_update(
                buf, ['objective'] + (['references'] if record_source else [])
            )

        filled = Protocol.objects.exclude(objective='').count()
        self.stdout.write(self.style.SUCCESS(
            f"完成：写入 {updated} 条 Protocol.objective "
            f"（pubmed {pub_wins} / europepmc {epmc_wins} / bioprotocol {bio_wins}）；"
            f"当前非空 objective 总数 {filled}"
        ))
