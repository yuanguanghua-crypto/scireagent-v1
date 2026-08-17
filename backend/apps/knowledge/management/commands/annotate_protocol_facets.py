# -*- coding: utf-8 -*-
"""annotate_protocol_facets — 离线标注流水线（route B 加法，范围 A）。

基于 k=80 聚类（与 poc_cluster_vocab.py 完全一致的 KMeans 参数：
KMeans(n_clusters=80, random_state=42, n_init=4)）复现每协议簇号，经
「簇大小对齐闸门」fail-closed 校验后，按 poc_facet_taxonomy.json 把簇归并为
facet（technique / biological_context / study_type），并对协议文本做保守交叉检测
补 biological_context。幂等 upsert FacetValue + ProtocolFacet。

数据血缘（已核实）：
- poc_protocol_emb.npy：14065×384 L2 归一化嵌入，行序 == poc_topchain_data.json 的
  protocols 列表顺序；protocols[i]["id"] 即 DB Protocol 主键值。
- poc_vocab.json：by_k["80"]["clusters"] 给出每个 cluster_id 的参考 size；
  cluster_id 就是 KMeans 原始标签(0..79)，故同参数复现必得相同标签。
- poc_facet_taxonomy.json：CLF[cluster_id] -> (dimension, value, kind)；
  resolve_facet_spec 负责收口到 facet。

契约（见 apps/knowledge/tests/test_annotate_protocol_facets.py）：
- 数据文件默认在 workspace 根目录（--data-dir 可覆盖），文件名固定。
- --k 默认 80，须与 poc_vocab.json 的 by_k 键一致。
- 复现 KMeans 得每协议簇号（cluster_id）。
- 闸门：重跑簇大小分布必须 == poc_vocab.json 参考分布，否则 CommandError 中止（fail-closed）。
- 经 poc_topchain_data.json 的 protocols[i].id 把向量下标 i 映射到协议 PK。
- 逐协议：resolve_facet_spec(cluster_id) 主 facet（source=cluster_main；drop 跳过）；
          detect_biological_context(协议文本) 补 biological_context（source=cross_detect）。
- 幂等：FacetValue.get_or_create((facet_type,kind,value))；
        ProtocolFacet.get_or_create((protocol,facet))。
- --dry-run 只统计不落库；--limit N 只处理前 N 个（按嵌入顺序）；--clear 先清空再标。
- 不修改任何 Protocol / Method / Product；只写 FacetValue / ProtocolFacet。
"""
import json
import os

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.knowledge.models import Protocol, FacetValue, ProtocolFacet
from apps.knowledge.services.facet_annotation import (
    resolve_facet_spec,
    detect_biological_context,
    protocol_text,
    load_taxonomy,
    PROTOCOL_TEXT_FIELDS,
)

DEFAULT_K = 80
CROSS_SRC = ProtocolFacet.Source.CROSS_DETECT
CLUSTER_SRC = ProtocolFacet.Source.CLUSTER_MAIN
BIO_TYPE = FacetValue.FacetType.BIOLOGICAL_CONTEXT


def _default_data_dir():
    # 从 BASE_DIR 向上搜索含 poc_protocol_emb.npy 的目录（稳健，不受 BASE_DIR 结构影响）。
    cur = os.path.abspath(str(settings.BASE_DIR))
    marker = 'poc_protocol_emb.npy'
    for _ in range(6):
        if os.path.isfile(os.path.join(cur, marker)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    # 回退启发式：backend 的上两级（workspace 根）
    return os.path.dirname(os.path.dirname(os.path.abspath(str(settings.BASE_DIR))))


class Command(BaseCommand):
    help = "基于 k=80 聚类离线标注 Protocol 受控词表 facet（route B 加法，范围 A）。"

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-dir', default=None,
            help='poc 数据文件目录（默认 workspace 根目录）',
        )
        parser.add_argument(
            '--k', type=int, default=DEFAULT_K,
            help='聚类数（默认 80，须与 poc_vocab.json 的 by_k 键一致）',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='只统计将要写入的量，不落库',
        )
        parser.add_argument(
            '--limit', type=int, default=0,
            help='只处理前 N 个协议（按嵌入顺序），0=全部',
        )
        parser.add_argument(
            '--clear', action='store_true',
            help='落库前先清空全部 FacetValue / ProtocolFacet（全量重标）',
        )
        parser.add_argument(
            '--application', action='store_true',
            help='application 模式：用 k=20 聚类标注研究域 facet（facet_type=application），'
                 '走 k=20 闸门，仅写 cluster_main，不做生物交叉检测',
        )

    # ---------- 数据加载 ----------
    def _load_embedding(self, path):
        if not os.path.isfile(path):
            raise CommandError(f"嵌入文件不存在：{path}")
        emb = np.load(path)
        if emb.ndim != 2:
            raise CommandError(f"嵌入文件形状异常（非 2D）：{emb.shape}")
        return emb

    def _reproduce_labels(self, emb, k):
        from sklearn.cluster import KMeans
        km = KMeans(n_clusters=k, random_state=42, n_init=4)
        return km.fit_predict(emb)

    def _gate_cluster_sizes(self, labels, k, vocab_path):
        """fail-closed：重跑簇大小分布必须 == 参考 poc_vocab.json。"""
        with open(vocab_path, encoding='utf-8') as f:
            vocab = json.load(f)
        ref_entry = vocab.get('by_k', {}).get(str(k))
        if not ref_entry:
            raise CommandError(f"poc_vocab.json 缺少 by_k['{k}'] 参考分布")
        ref_sizes = {c['cluster_id']: c['size'] for c in ref_entry['clusters']}
        my_sizes = {cid: int((labels == cid).sum()) for cid in range(k)}
        if my_sizes != ref_sizes:
            diffs = []
            for cid in sorted(set(ref_sizes) | set(range(k))):
                r = ref_sizes.get(cid)
                m = my_sizes.get(cid)
                if r != m:
                    diffs.append(f"cluster {cid}: ref={r} run={m}")
            raise CommandError(
                "簇大小对齐闸门 FAIL：复现 KMeans 与参考 poc_vocab.json 不一致，"
                "可能 sklearn 版本或嵌入文件漂移，已中止以防错标。\n  " + "; ".join(diffs[:20])
            )
        return my_sizes

    def _build_pk_to_cid(self, topchain_path, labels):
        with open(topchain_path, encoding='utf-8') as f:
            td = json.load(f)
        protocols = td.get('protocols', [])
        if len(protocols) != len(labels):
            raise CommandError(
                f"协议数({len(protocols)}) != 嵌入行数({len(labels)})，向量/协议对齐断裂"
            )
        pk_to_cid = []
        for i, p in enumerate(protocols):
            pk = p.get('id')
            if pk is None:
                raise CommandError(f"protocols[{i}] 缺少 id 字段")
            pk_to_cid.append((int(pk), int(labels[i])))
        return pk_to_cid

    # ---------- 主流程 ----------
    def handle(self, *args, **options):
        data_dir = options['data_dir'] or _default_data_dir()
        application_mode = bool(options.get('application'))
        if application_mode:
            # application 模式：固定 k=20，独立 taxonomy，仅增量追加，禁止 --clear
            k = 20
            taxonomy_path = os.path.join(data_dir, 'poc_application_taxonomy.json')
            if options['clear']:
                raise CommandError(
                    "application 模式不支持 --clear（仅增量追加 application facet，"
                    "避免误删既有的 method / biological_context facet）"
                )
        else:
            k = options['k']
            taxonomy_path = os.path.join(data_dir, 'poc_facet_taxonomy.json')
        dry_run = options['dry_run']
        limit = options['limit']
        clear = options['clear']
        if limit and limit < 0:
            limit = 0

        emb_path = os.path.join(data_dir, 'poc_protocol_emb.npy')
        topchain_path = os.path.join(data_dir, 'poc_topchain_data.json')
        vocab_path = os.path.join(data_dir, 'poc_vocab.json')
        for p in (emb_path, topchain_path, vocab_path, taxonomy_path):
            if not os.path.isfile(p):
                raise CommandError(f"数据文件不存在：{p}")

        self.stdout.write(f"数据目录：{data_dir}")
        self.stdout.write(f"k={k}  dry_run={dry_run}  limit={limit or '全部'}  clear={clear}")

        # 1) 复现聚类 + 闸门
        emb = self._load_embedding(emb_path)
        self.stdout.write(f"加载嵌入：{emb.shape}")
        labels = self._reproduce_labels(emb, k)
        self.stdout.write("复现 KMeans 完成，校验簇大小对齐闸门 ...")
        self._gate_cluster_sizes(labels, k, vocab_path)
        self.stdout.write(self.style.SUCCESS("簇大小对齐闸门 PASS"))

        # 2) 映射 PK -> cluster_id
        pk_to_cid = self._build_pk_to_cid(topchain_path, labels)
        if limit:
            pk_to_cid = pk_to_cid[:limit]
        total = len(pk_to_cid)
        self.stdout.write(f"待标注协议数：{total}")

        # 3) 对齐 DB：所有 PK 必须存在（fail-closed）
        pks = [pk for pk, _ in pk_to_cid]
        db_ids = set(Protocol.objects.filter(id__in=pks).values_list('id', flat=True))
        missing = [pk for pk in pks if pk not in db_ids]
        if missing:
            raise CommandError(
                f"对齐断裂：{len(missing)} 个 PK 不在 Protocol 表（示例 {missing[:5]}）"
            )

        # 4) taxonomy
        _, taxonomy_map = load_taxonomy(taxonomy_path)

        # 5) 收集待写 (pk, spec, source)
        wanted = []  # (pk, (facet_type, kind, value), source)
        # 5a) 聚类主标签：无需 DB 文本
        for pk, cid in pk_to_cid:
            spec = resolve_facet_spec(cid, taxonomy_map)
            if spec:
                wanted.append((pk, spec, CLUSTER_SRC))
        # 5b) 交叉检测补标：分块取协议文本（控内存）；application 模式只标研究域，跳过生物补标
        if not application_mode:
            CHUNK = 2000
            for start in range(0, total, CHUNK):
                chunk_pc = pk_to_cid[start:start + CHUNK]
                chunk_pks = [pk for pk, _ in chunk_pc]
                proto_map = {
                    p.id: p
                    for p in Protocol.objects.only('id', *PROTOCOL_TEXT_FIELDS)
                    .filter(id__in=chunk_pks)
                }
                for pk, _ in chunk_pc:
                    proto = proto_map.get(pk)
                    if not proto:
                        continue
                    text = protocol_text(proto)
                    for kind, value in detect_biological_context(text):
                        wanted.append((pk, (BIO_TYPE, kind, value), CROSS_SRC))

        # 6) 幂等 upsert FacetValue
        facet_cache = {}  # spec -> FacetValue（dry-run 时为 None）
        for pk, spec, src in wanted:
            if spec in facet_cache:
                continue
            ft, kind, value = spec
            if dry_run:
                facet_cache[spec] = None
                continue
            fv, _created = FacetValue.objects.get_or_create(
                facet_type=ft, kind=kind, value=value,
                defaults={'description': ''},
            )
            facet_cache[spec] = fv

        # 7) dry-run 报告
        if dry_run:
            distinct_facets = len({spec for _, spec, _ in wanted})
            distinct_links = len({(pk, spec) for pk, spec, _ in wanted})
            self.stdout.write(self.style.WARNING(
                f"[dry-run] 将写入 FacetValue 去重 {distinct_facets} 个；"
                f"ProtocolFacet 链接去重 {distinct_links} 条；未落库"
            ))
            return

        # 8) --clear：先清空再标（幂等重标）
        if clear:
            self.stdout.write("清空既有 FacetValue / ProtocolFacet ...")
            ProtocolFacet.objects.all().delete()
            FacetValue.objects.all().delete()
            facet_cache = {}
            for pk, spec, src in wanted:
                if spec in facet_cache:
                    continue
                ft, kind, value = spec
                fv, _created = FacetValue.objects.get_or_create(
                    facet_type=ft, kind=kind, value=value,
                    defaults={'description': ''},
                )
                facet_cache[spec] = fv

        # 9) 计算待写链接并去重 (pk, facet_id)
        link_specs = {}  # (pk, facet_id) -> source
        for pk, spec, src in wanted:
            fv = facet_cache.get(spec)
            if fv is None:
                continue
            link_specs[(pk, fv.id)] = src

        with transaction.atomic():
            existing = set(
                ProtocolFacet.objects.filter(protocol_id__in=pks)
                .values_list('protocol_id', 'facet_id')
            )
            to_create = [
                ProtocolFacet(protocol_id=pk, facet_id=fid, source=src)
                for (pk, fid), src in link_specs.items()
                if (pk, fid) not in existing
            ]
            created_n = len(to_create)
            if to_create:
                ProtocolFacet.objects.bulk_create(to_create, batch_size=2000)

        # 10) 统计
        total_fv = FacetValue.objects.count()
        total_pf = ProtocolFacet.objects.count()
        by_src = {
            src_val: ProtocolFacet.objects.filter(source=src_val).count()
            for src_val, _ in ProtocolFacet.Source.choices
        }
        self.stdout.write(self.style.SUCCESS(
            f"完成：新建/确认 ProtocolFacet 链接 {created_n} 条（累计 {total_pf}）；"
            f"FacetValue 累计 {total_fv}；"
            f"来源 cluster_main={by_src.get('cluster_main', 0)} "
            f"cross_detect={by_src.get('cross_detect', 0)}"
        ))
