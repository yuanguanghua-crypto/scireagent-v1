"""顶部链 AI 提取结果落库命令 — import_topchain_extractions。

把 T4 LLM 批量提取结果（research_goals / applications）落库到知识图谱：
- 实体 merge 优先：按 name.strip().casefold() 精确匹配（不分大小写），
  命中复用（不修改任何字段），未命中新建（origin=ai_extracted）。
- 关联幂等：RG.protocols / RG.application_collection 均为 M2M，add 天然幂等；
  Application.research_goal FK 一律不设置。
- 事务边界：按 --chunk-size 条协议一个 transaction.atomic()；
  某 chunk 抛异常 → 回滚该 chunk、记录错误到报告、继续后续 chunk。
- 默认 dry-run（只统计不写库）；加 --apply 才真正落库。

用法：
  python manage.py import_topchain_extractions --jsonl <path>
  python manage.py import_topchain_extractions --jsonl <path> --apply
  python manage.py import_topchain_extractions --jsonl <path> --report <abs-path>.json
"""
import json
import os
from contextlib import nullcontext

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.knowledge.models import Application, OriginChoices, Protocol, ResearchGoal


def _parse_element(elem):
    """解析 RG/AP 元素，返回 (name, confidence)。

    dict → 取 name / confidence；str → 字符串直接当 name；
    其它形态抛 ValueError（计入解析异常）。
    """
    if isinstance(elem, str):
        return elem, None
    if isinstance(elem, dict):
        return elem.get('name'), elem.get('confidence')
    raise ValueError(f'unsupported element type: {type(elem).__name__}')


class Command(BaseCommand):
    help = '把 T4 LLM 提取结果（research_goals/applications）落库到知识图谱（默认 dry-run）'

    def add_arguments(self, parser):
        parser.add_argument('--jsonl', required=True, help='输入 jsonl 文件路径')
        parser.add_argument('--apply', action='store_true', default=False,
                            help='真正落库（缺省为 dry-run，只统计不写库）')
        parser.add_argument('--chunk-size', type=int, default=500,
                            help='每个事务提交的协议条数（默认 500）')
        parser.add_argument('--report', type=str, default='',
                            help='报告 JSON 输出路径（缺省仅打印到 stdout）')

    # ------------------------------------------------------------------ #
    # handle 主流程
    # ------------------------------------------------------------------ #
    def handle(self, *args, **options):
        self.apply = options['apply']
        chunk_size = options['chunk_size']
        report_path = options['report']
        if chunk_size < 1:
            raise CommandError('--chunk-size 必须 >= 1')

        # 1) 读取去重：按 protocol_id 保留最后一条，跳过 error 非空记录
        records, total_lines, skipped_errors, json_corrupt = self._load_records(options['jsonl'])
        protocol_ids = list(records.keys())
        self.stdout.write(
            f'读取完成：总行 {total_lines}，跳过 error 记录 {skipped_errors}，'
            f'JSON 损坏 {json_corrupt}，去重后协议 {len(protocol_ids)}')

        # 2) 预载库中现有实体映射（name.casefold() → 对象，同名取 id 最小）
        self.rg_by_key, dup_rg = self._preload_name_map(ResearchGoal)
        self.ap_by_key, dup_ap = self._preload_name_map(Application)
        self.dup_name_warnings = dup_rg + dup_ap

        # 3) 全量解析（Phase 1）：构建实体 registry 与关联对集合（只读内存）
        parsed, self.rg_registry, self.ap_registry, per_rg_aps, phase1 = self._scan_all(records)

        # 4) 逐 chunk 落库/统计（Phase 2）
        self.rg_cache = {}
        self.ap_cache = {}
        chunk_failures = []
        totals = {
            'new_rg': 0, 'reuse_rg': 0, 'new_ap': 0, 'reuse_ap': 0,
        }
        for start in range(0, len(protocol_ids), chunk_size):
            chunk_ids = protocol_ids[start:start + chunk_size]
            created_keys = {'rg': [], 'ap': []}
            local = None
            try:
                ctx = transaction.atomic() if self.apply else nullcontext()
                with ctx:
                    local = self._process_chunk(chunk_ids, parsed, created_keys)
            except Exception as exc:  # noqa: BLE001 —— 单 chunk 失败回滚后继续
                for k in created_keys['rg']:
                    self.rg_cache.pop(k, None)
                for k in created_keys['ap']:
                    self.ap_cache.pop(k, None)
                chunk_failures.append({
                    'chunk': start // chunk_size + 1,
                    'protocols': chunk_ids,
                    'error': str(exc),
                })
                self.stderr.write(
                    f'[chunk {start // chunk_size + 1}] 处理失败，已回滚 '
                    f'（协议 {chunk_ids[0]}..{chunk_ids[-1]}，共 {len(chunk_ids)} 条）: {exc}')
                continue
            for k in totals:
                totals[k] += local[k]

        # 5) 汇总报告
        stats = {
            'mode': 'apply' if self.apply else 'dry-run',
            'total_lines': total_lines,
            'unique_protocols': len(protocol_ids),
            'skipped_error_records': skipped_errors,
            'success_records': len(protocol_ids),
            'empty_rg_protocols': phase1['empty_rg'],
            'empty_ap_protocols': phase1['empty_ap'],
            'empty_both_protocols': phase1['empty_both'],
            'parse_errors': json_corrupt + phase1['element_errors'],
            'empty_name_skipped': phase1['empty_name'],
            'name_truncated': phase1['truncated'],
            'duplicate_name_warnings': self.dup_name_warnings,
            'new_research_goals': totals['new_rg'],
            'reused_research_goals': totals['reuse_rg'],
            'new_applications': totals['new_ap'],
            'reused_applications': totals['reuse_ap'],
            # 关联数 = 去重后的唯一关联对数（Phase 1 全量集合），
            # 即 apply 后 M2M 表中由本次命令写入的最终行数。
            'protocol_links_added': sum(len(reg['protocols']) for reg in self.rg_registry.values()),
            'application_links_added': sum(len(s) for s in per_rg_aps.values()),
        }
        report = {'stats': stats, 'chunk_failures': chunk_failures}

        self._write_report(report, report_path)

    # ------------------------------------------------------------------ #
    # 读取与去重
    # ------------------------------------------------------------------ #
    def _load_records(self, jsonl_path):
        """逐行读 jsonl；按 protocol_id 去重保留最后一条；跳过 error 非空记录。

        返回 (records: dict[pid→record], total_lines, skipped_errors, json_corrupt)。
        """
        records = {}
        total_lines = 0
        skipped_errors = 0
        json_corrupt = 0
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total_lines += 1
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    json_corrupt += 1
                    continue
                if rec.get('error'):
                    skipped_errors += 1
                    continue
                pid = rec.get('protocol_id')
                if pid is None:
                    json_corrupt += 1
                    continue
                records[pid] = rec
        return records, total_lines, skipped_errors, json_corrupt

    # ------------------------------------------------------------------ #
    # 预载映射
    # ------------------------------------------------------------------ #
    def _preload_name_map(self, model):
        """构建 name.casefold() → 对象 的映射；同名多实例取 id 最小者，其余记 warning。

        返回 (mapping, duplicate_count)。
        """
        mapping = {}
        duplicates = 0
        for obj in model.objects.all().order_by('id'):
            key = obj.name.strip().casefold()
            if not key:
                continue
            if key in mapping:
                duplicates += 1
                self.stderr.write(
                    f'[warning] {model.__name__} 同名多实例："{obj.name}" '
                    f'（id={obj.id}）被忽略，复用 id={mapping[key].id}')
            else:
                mapping[key] = obj
        return mapping, duplicates

    # ------------------------------------------------------------------ #
    # Phase 1 全量解析
    # ------------------------------------------------------------------ #
    def _scan_all(self, records):
        """只读扫描全部记录，构建：
        - parsed: pid → 解析结果（rg/ap 三元组与 key 列表），供 Phase 2 复用
        - rg_registry / ap_registry: key → {name, protocols:set, max_conf}
        - per_rg_aps: rg_key → set(ap_key)（RG.application_collection 关联对）
        - phase1 stats: empty_rg / empty_ap / empty_both / element_errors / empty_name / truncated
        """
        parsed = {}
        rg_registry = {}
        ap_registry = {}
        per_rg_aps = {}
        empty_rg = empty_ap = empty_both = element_errors = empty_name = truncated = 0

        for pid, rec in records.items():
            rg_triples, rg_keys, e1, en1, tr1 = self._parse_list(
                rec.get('research_goals'), rg_registry, pid)
            ap_triples, ap_keys, e2, en2, tr2 = self._parse_list(
                rec.get('applications'), ap_registry, pid)
            element_errors += e1 + e2
            empty_name += en1 + en2
            truncated += tr1 + tr2
            parsed[pid] = {
                'rg_triples': rg_triples,
                'ap_triples': ap_triples,
                'rg_keys': rg_keys,
                'ap_keys': ap_keys,
            }
            for rk in rg_keys:
                per_rg_aps.setdefault(rk, set()).update(ap_keys)
            if not rg_keys:
                empty_rg += 1
            if not ap_keys:
                empty_ap += 1
            if not rg_keys and not ap_keys:
                empty_both += 1

        phase1 = {
            'empty_rg': empty_rg,
            'empty_ap': empty_ap,
            'empty_both': empty_both,
            'element_errors': element_errors,
            'empty_name': empty_name,
            'truncated': truncated,
        }
        return parsed, rg_registry, ap_registry, per_rg_aps, phase1

    def _parse_list(self, raw, registry, pid):
        """解析一个字段（research_goals / applications），返回
        (triples, keys, element_errors, empty_name, truncated)。

        triple = (casefold_key, raw_name, confidence)；raw_name 已 strip / 截断。
        """
        triples = []
        keys = []
        element_errors = 0
        empty_name = 0
        truncated = 0
        if not isinstance(raw, list):
            if raw not in (None, '', []):
                element_errors += 1
            raw = []
        for elem in raw:
            try:
                name, conf = _parse_element(elem)
            except ValueError:
                element_errors += 1
                continue
            if name is None:
                name = ''
            name = name.strip()
            if not name:
                empty_name += 1
                continue
            if len(name) > 255:
                name = name[:255]
                truncated += 1
            key = name.casefold()
            reg = registry.setdefault(key, {'name': name, 'protocols': set(), 'max_conf': None})
            reg['protocols'].add(pid)
            if conf is not None and (reg['max_conf'] is None or conf > reg['max_conf']):
                reg['max_conf'] = conf
            triples.append((key, name, conf))
            keys.append(key)
        return triples, keys, element_errors, empty_name, truncated

    # ------------------------------------------------------------------ #
    # Phase 2 chunk 处理
    # ------------------------------------------------------------------ #
    def _process_chunk(self, chunk_ids, parsed, created_keys):
        """处理一个 chunk（apply 时在调用方 atomic 事务内执行）。

        返回 local 统计 dict：{new_rg, reuse_rg, new_ap, reuse_ap}。
        """
        local = {'new_rg': 0, 'reuse_rg': 0, 'new_ap': 0, 'reuse_ap': 0}
        chunk_rg_protocols = {}   # rg_key -> set(pid)
        chunk_rg_aps = {}         # rg_key -> set(ap_key)

        for pid in chunk_ids:
            info = parsed[pid]
            for key, _name, _conf in info['rg_triples']:
                if key not in self.rg_cache:
                    _obj, is_new = self._resolve_entity(
                        key, self.rg_by_key, self.rg_registry,
                        self.rg_cache, ResearchGoal, created_keys['rg'])
                    if is_new:
                        local['new_rg'] += 1
                    else:
                        local['reuse_rg'] += 1
                chunk_rg_protocols.setdefault(key, set()).add(pid)
            for key, _name, _conf in info['ap_triples']:
                if key not in self.ap_cache:
                    _obj, is_new = self._resolve_entity(
                        key, self.ap_by_key, self.ap_registry,
                        self.ap_cache, Application, created_keys['ap'])
                    if is_new:
                        local['new_ap'] += 1
                    else:
                        local['reuse_ap'] += 1
            for rk in info['rg_keys']:
                chunk_rg_aps.setdefault(rk, set()).update(info['ap_keys'])

        if self.apply:
            protocols_by_id = Protocol.objects.in_bulk(chunk_ids)
            for rk, pids in chunk_rg_protocols.items():
                rg = self.rg_cache[rk]
                rg.protocols.add(*[protocols_by_id[p] for p in pids])
            for rk, ap_keys in chunk_rg_aps.items():
                rg = self.rg_cache[rk]
                rg.application_collection.add(*[self.ap_cache[k] for k in ap_keys])
        return local

    def _resolve_entity(self, key, by_key, registry, cache, model, created_keys):
        """调用前提：key 不在 cache。

        - 预载映射命中 → 复用（不修改任何字段），入缓存。
        - 未命中 → 新建（apply 才真正落库），origin=ai_extracted，
          origin_detail 按 extractor_v0.1|protocols_count:<N>|max_conf:<conf> 格式。
        返回 (obj, is_new)。
        """
        if key in by_key:
            obj = by_key[key]
            cache[key] = obj
            return obj, False
        reg = registry[key]
        obj = None
        if self.apply:
            obj = model.objects.create(
                name=reg['name'],
                summary='',
                origin=OriginChoices.AI_EXTRACTED,
                origin_detail=self._build_origin_detail(reg),
            )
        cache[key] = obj
        created_keys.append(key)
        return obj, True

    def _build_origin_detail(self, reg):
        """extractor_v0.1|protocols_count:<协议数>|max_conf:<最大confidence>

        旧实现把全部协议 id 逗号拼接进 origin_detail（protocols:<id列表>），
        RG 关联几百上千协议时会突破字段 max_length=500；改为只记计数。
        """
        parts = ['extractor_v0.1', f'protocols_count:{len(reg["protocols"])}']
        if reg['max_conf'] is not None:
            parts.append(f'max_conf:{reg["max_conf"]}')
        return '|'.join(parts)

    # ------------------------------------------------------------------ #
    # 报告
    # ------------------------------------------------------------------ #
    def _write_report(self, report, path):
        stats = report['stats']
        s = stats
        self.stdout.write('=' * 64)
        self.stdout.write(f"模式：{s['mode']}  "
                          f"总行数：{s['total_lines']}  去重后协议数：{s['unique_protocols']}")
        self.stdout.write(f"成功记录：{s['success_records']}  "
                          f"跳过(error)：{s['skipped_error_records']}  "
                          f"解析异常：{s['parse_errors']}")
        self.stdout.write(f"空RG协议：{s['empty_rg_protocols']}  "
                          f"空AP协议：{s['empty_ap_protocols']}  "
                          f"两者皆空：{s['empty_both_protocols']}")
        self.stdout.write(f"空name跳过：{s['empty_name_skipped']}  "
                          f"name截断：{s['name_truncated']}  "
                          f"同名多实例warning：{s['duplicate_name_warnings']}")
        self.stdout.write(f"新建RG：{s['new_research_goals']}  "
                          f"复用RG：{s['reused_research_goals']}  "
                          f"新建AP：{s['new_applications']}  "
                          f"复用AP：{s['reused_applications']}")
        self.stdout.write(f"RG.protocols 关联数：{s['protocol_links_added']}  "
                          f"RG.application_collection 关联数：{s['application_links_added']}")
        failures = report['chunk_failures']
        if failures:
            self.stdout.write(f"失败 chunk 数：{len(failures)}")
            for f in failures:
                self.stdout.write(f"  [chunk {f['chunk']}] 协议 {len(f['protocols'])} 条: {f['error']}")
        else:
            self.stdout.write('失败 chunk 数：0')
        self.stdout.write('=' * 64)

        if path:
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            self.stdout.write(f'报告已写入 {path}')
