"""Validate multi-transcript evidence and compile it to the fixed SmartArt renderer.

Checks provenance and structure, not scientific truth or correct Arabic vowels.
No semantic deduplication or text generation is performed by this module.
"""
from __future__ import annotations
import copy
import hashlib
import json
import re
from pathlib import Path
from build_lesson import check_content
from check_lesson import load_source


def read_json(path):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    require(isinstance(data, dict), 'JSON root must be an object: ' + str(path))
    return data


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def indexed(items, label):
    require(isinstance(items, list), label + ': expected list')
    out = {}
    for item in items:
        require(isinstance(item, dict), label + ': list entries must be objects')
        ident = item.get('id', '')
        require(bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', ident)), label + ': invalid ID')
        require(ident not in out, label + ': duplicate ' + ident)
        out[ident] = item
    return out


def local_path(root, relative):
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()), 'Manifest path escapes run directory')
    return path


def evidence(span, text, label):
    lo, hi = span.get('start'), span.get('end')
    require(type(lo) is int and type(hi) is int and 0 <= lo < hi <= len(text), label + ': invalid offsets')
    require(bool(span.get('quote')) and span['quote'] == text[lo:hi], label + ': quote/offset mismatch')


def accounting(spans, text, units, label):
    require(bool(spans), label + ': missing source accounting')
    covered = bytearray(len(text))
    supported = set()
    for span in spans:
        require(isinstance(span, dict), label + ': source spans must be objects')
        lo, hi = span.get('start'), span.get('end')
        require(type(lo) is int and type(hi) is int and 0 <= lo < hi <= len(text), label + ': invalid accounting offsets')
        require(not any(covered[lo:hi]), label + ': overlapping accounting spans')
        covered[lo:hi] = b'\x01' * (hi-lo)
        kind = span.get('kind')
        require(kind in ('scientific', 'repetition', 'metadata', 'filler'), label + ': unknown span kind')
        if kind in ('scientific', 'repetition'):
            refs = span.get('units', [])
            require(bool(refs) and set(refs) <= units.keys(), label + ': invalid accounting units')
            supported.update(refs)
        else:
            require(bool(span.get('reason', '').strip()), label + ': excluded span requires reason')
    require(not any(not c.isspace() and not covered[i] for i, c in enumerate(text)), label + ': source characters not accounted for')
    require(supported == units.keys(), label + ': some extracted units have no scientific source span')
    for uid, unit in units.items():
        for quote in unit['evidence']:
            # Evidence may span adjacent scientific intervals; every character
            # must be attributed to this unit, not a separate filler interval.
            relevant = sorted((s['start'], s['end']) for s in spans if uid in s.get('units', []))
            position = quote['start']
            for lo, hi in relevant:
                if lo <= position < hi:
                    position = min(hi, quote['end'])
                if position == quote['end']:
                    break
            require(position == quote['end'], label + ': unit evidence is outside its scientific accounting spans ' + uid)


def validate_analysis(data, source, text, run_id):
    sid = source['id']
    require(data.get('schema_version') == 1 and data.get('run_id') == run_id, sid + ': wrong schema/run')
    require(data.get('source_id') == sid and data.get('source_sha256') == source['sha256'], sid + ': wrong source/hash')
    require(data.get('status') == 'complete', sid + ': worker is incomplete')
    require(bool(data.get('lesson', {}).get('title')), sid + ': lesson title missing')
    concepts = indexed(data.get('concepts'), sid + ' concepts')
    units = indexed(data.get('units'), sid + ' units')
    require(bool(units) and bool(concepts), sid + ': empty scientific analysis')
    for uid, unit in units.items():
        require(bool(unit.get('claim')) and bool(unit.get('kind')), sid + ': unit claim/kind missing ' + uid)
        require(bool(unit.get('concept_ids')) and set(unit['concept_ids']) <= concepts.keys(), sid + ': unknown unit concept ' + uid)
        require(isinstance(unit.get('qualifiers'), list) and 'attribution' in unit, sid + ': preserve qualifiers and attribution explicitly ' + uid)
        require(bool(unit.get('evidence')), sid + ': missing unit evidence ' + uid)
        for span in unit['evidence']:
            require(isinstance(span, dict), sid + ': evidence must be objects')
            evidence(span, text, sid + '::' + uid)
    for cid, concept in concepts.items():
        require(bool(concept.get('label')), sid + ': concept label missing ' + cid)
        require(any(cid in u['concept_ids'] for u in units.values()), sid + ': concept has no scientific unit ' + cid)
    relations = indexed(data.get('relations'), sid + ' relations')
    for rid, rel in relations.items():
        require(rel.get('from') in concepts and rel.get('to') in concepts and rel.get('kind') and rel.get('claim'), sid + ': invalid relation ' + rid)
        require(bool(rel.get('evidence')), sid + ': relation has no evidence ' + rid)
        for span in rel['evidence']:
            evidence(span, text, sid + '::' + rid)
    cross = indexed(data.get('cross_references'), sid + ' cross references')
    for rid, rel in cross.items():
        require(bool(rel.get('text')) and bool(rel.get('target_hint')) and bool(rel.get('evidence')), sid + ': incomplete cross reference ' + rid)
        for span in rel['evidence']:
            evidence(span, text, sid + '::' + rid)
    corrections = indexed(data.get('corrections'), sid + ' corrections')
    for rid, rel in corrections.items():
        require(rel.get('old_unit_id') in units and rel.get('new_unit_id') in units and rel['old_unit_id'] != rel['new_unit_id'], sid + ': invalid correction ' + rid)
        require(bool(rel.get('evidence')), sid + ': correction evidence missing')
        for span in rel['evidence']:
            evidence(span, text, sid + '::' + rid)
    require(not (relations.keys() & cross.keys() or relations.keys() & corrections.keys() or cross.keys() & corrections.keys()), sid + ': relation/cross/correction IDs must differ')
    accounting(data.get('source_accounting'), text, units, sid)
    return {'units': len(units), 'concepts': len(concepts), 'relations': len(relations), 'cross_references': len(cross), 'corrections': len(corrections)}


def load_run(manifest_path, require_analyses=True):
    manifest_path = Path(manifest_path).resolve()
    root, manifest = manifest_path.parent, read_json(manifest_path)
    require(manifest.get('schema_version') == 1 and manifest.get('run_id'), 'Invalid manifest schema/run')
    sources = indexed(manifest.get('sources'), 'sources')
    require(bool(sources), 'No source files')
    require([s['order'] for s in sources.values()] == list(range(1, len(sources)+1)), 'Source order must be consecutive and explicit')
    analyses, texts, reports, hashes = {}, {}, {}, {}
    for sid, src in sources.items():
        raw = local_path(root, src['raw_path']).read_bytes()
        require(digest(raw) == src['raw_sha256'], sid + ': original snapshot changed')
        text = load_source(local_path(root, src['raw_path']))
        normalized = local_path(root, src['normalized_path']).read_bytes()
        require(normalized == text.encode('utf-8') and digest(normalized) == src['sha256'] and len(text) == src['characters'], sid + ': normalized source changed')
        texts[sid] = text
        if require_analyses:
            ap = local_path(root, src['analysis_path'])
            data = read_json(ap)
            reports[sid] = validate_analysis(data, src, text, manifest['run_id'])
            analyses[sid] = data
            hashes[sid] = digest(ap.read_bytes())
    return manifest, sources, analyses, texts, reports, hashes


def iter_nodes(node):
    yield node
    for child in node.get('children', []):
        yield from iter_nodes(child)


def validate_course(data, manifest_path):
    manifest, sources, analyses, texts, reports, hashes = load_run(manifest_path)
    require(data.get('schema_version') == 1 and data.get('run_id') == manifest['run_id'], 'Merged course has wrong schema/run')
    check_content(data)
    content_ids = [t['id'] for t in data['topics']] + [b['id'] for t in data['topics'] for b in t['blocks']] + [s['id'] for s in data['summary']]
    bookmarks = ['lm_'+re.sub('[^a-zA-Z0-9_]', '_', x) for x in content_ids]
    require(len(set(bookmarks)) == len(bookmarks) and all(len(x) <= 40 for x in bookmarks), 'Content IDs produce colliding or too-long Word bookmarks')
    integ = data.get('integration', {})
    require(isinstance(integ, dict), 'integration must be an object')
    locks = integ.get('source_analyses', [])
    require(len(locks) == len(sources) and {x['source_id']: x['sha256'] for x in locks} == hashes, 'Missing, duplicate or stale worker results in integration')
    topics = {t['id']: t for t in data['topics']}
    blocks = {b['id']: b for t in data['topics'] for b in t['blocks']}
    visuals = {i for i, b in blocks.items() if b['type'] in ('diagram', 'table')}
    summaries = {x['id'] for x in data['summary'] if x.get('kind') != 'heading'}
    concepts = indexed(integ.get('concepts'), 'canonical concepts')
    facts = indexed(integ.get('facts'), 'canonical facts')
    relations = indexed(integ.get('relations'), 'canonical relations')
    corrections = indexed(integ.get('corrections'), 'canonical corrections')
    all_units = {sid+'::'+u['id']: u for sid, a in analyses.items() for u in a['units']}
    all_concepts = {sid+'::'+c['id'] for sid, a in analyses.items() for c in a['concepts']}
    candidates = {sid+'::'+r['id']: category for sid, a in analyses.items() for category in ('relations', 'cross_references', 'corrections') for r in a[category]}
    def global_evidence(items, label):
        require(bool(items), label + ': missing global evidence')
        for item in items:
            require(item.get('source_id') in sources, label + ': invalid evidence source')
            evidence(item, texts[item['source_id']], label)
    mapped_concepts = []
    for cid, c in concepts.items():
        require(c.get('label') and c.get('source_concepts'), 'Canonical concept requires label and source concepts ' + cid)
        require(c.get('topic_refs') and set(c['topic_refs']) <= topics.keys(), 'Canonical concept topic missing ' + cid)
        mapped_concepts.extend(c['source_concepts'])
    require(len(mapped_concepts) == len(set(mapped_concepts)) and set(mapped_concepts) == all_concepts, 'Every worker concept needs exactly one canonical identity')
    for cid, c in corrections.items():
        old, new = c.get('replaced_units', []), c.get('replacement_units', [])
        require(old and new and set(old+new) <= all_units.keys() and not set(old) & set(new), 'Invalid canonical correction ' + cid)
        global_evidence(c.get('evidence'), cid)
    mapped, member_details = {}, {}
    for fid, fact in facts.items():
        require(fact.get('claim') and fact.get('members'), 'Canonical fact has no claim/members ' + fid)
        require(fact.get('visual_refs') and set(fact['visual_refs']) <= visuals, 'Fact has no real visual ' + fid)
        require(fact.get('summary_refs') and set(fact['summary_refs']) <= summaries, 'Fact missing from final summary ' + fid)
        require(any(m.get('role') == 'primary' for m in fact['members']), 'Fact needs a primary source unit ' + fid)
        for member in fact['members']:
            ref, role = member.get('unit'), member.get('role')
            require(ref in all_units and ref not in mapped, 'Missing/duplicate worker unit mapping ' + str(ref))
            require(role in ('primary', 'duplicate', 'corrected'), 'Unknown unit merge role ' + str(ref))
            if role != 'primary':
                require(bool(member.get('reason')), 'Non-primary mapping requires reason ' + ref)
            if role == 'corrected':
                correction = corrections.get(member.get('correction_id'), {})
                require(ref in correction.get('replaced_units', []), 'Correction has no explicit support ' + ref)
                primary = {m['unit'] for m in fact['members'] if m['role'] == 'primary'}
                require(set(correction['replacement_units']) <= primary, 'Corrected fact does not contain its replacement units ' + ref)
            mapped[ref] = fid
            member_details[ref] = member
    require(mapped.keys() == all_units.keys(), 'Some source units were silently dropped')
    for cid, correction in corrections.items():
        for ref in correction['replaced_units']:
            member = member_details[ref]
            require(member.get('role') == 'corrected' and member.get('correction_id') == cid, 'Explicitly replaced unit remains an active claim ' + ref)
    for rid, rel in relations.items():
        require(rel.get('from') in concepts and rel.get('to') in concepts and rel.get('kind') and rel.get('claim'), 'Invalid integrated relation ' + rid)
        global_evidence(rel.get('evidence'), rid)
        require(rel.get('visual_refs') and set(rel['visual_refs']) <= visuals, 'Relation has no visual ' + rid)
        require(rel.get('summary_refs') and set(rel['summary_refs']) <= summaries, 'Relation missing from summary ' + rid)
    decisions = integ.get('decisions', [])
    seen = set()
    for decision in decisions:
        ref = decision.get('input_ref')
        require(ref in candidates and ref not in seen, 'Unknown or duplicate relationship decision ' + str(ref))
        seen.add(ref)
        target = corrections if candidates[ref] == 'corrections' else relations
        if decision.get('action') == 'mapped':
            require(decision.get('target_ref') in target, 'Decision points to missing integrated relation/correction ' + ref)
            if candidates[ref] == 'corrections':
                sid, local = ref.split('::')
                worker_correction = next(x for x in analyses[sid]['corrections'] if x['id'] == local)
                central = target[decision['target_ref']]
                require(sid+'::'+worker_correction['old_unit_id'] in central['replaced_units'] and sid+'::'+worker_correction['new_unit_id'] in central['replacement_units'], 'Mapped correction changed its old/new units ' + ref)
        else:
            require(decision.get('action') == 'excluded' and decision.get('reason'), 'Excluded relationship requires explicit reason ' + ref)
    require(seen == candidates.keys(), 'Unreviewed worker relationships or cross references')
    overview = integ.get('overview_block')
    require(overview in blocks and blocks[overview]['type'] == 'diagram' and blocks[overview].get('kind') == 'tree', 'A native hierarchy overview is required')
    require(data['topics'][0]['blocks'][0]['id'] == overview, 'Overview must be the first content block')
    overview_nodes = list(iter_nodes(blocks[overview]['root']))
    detailed_topics = topics.keys() - {data['topics'][0]['id']}
    require(bool(detailed_topics), 'Course needs detailed topic maps after overview')
    linked = {n['topic_ref'] for n in overview_nodes if n.get('topic_ref')}
    require(linked == detailed_topics, 'Overview must reference every detailed topic, with no stale targets')
    annotated = set()
    for block in blocks.values():
        if block['type'] != 'diagram':
            continue
        nodes = iter_nodes(block['root']) if 'root' in block else iter(block['nodes'])
        for node in nodes:
            if 'concept_id' in node:
                cid = node['concept_id']
                require(cid in concepts and node['label'] == concepts[cid]['label'], 'Diagram concept label differs from canonical terminology')
                annotated.add(cid)
    require(annotated == concepts.keys(), 'Canonical concepts missing from native SmartArt nodes')
    return {'sources': len(sources), 'worker_units': len(all_units), 'integrated_facts': len(facts), 'concepts': len(concepts), 'relations': len(relations), 'worker_checks': reports}, (sources, analyses, texts, mapped, facts)


def compile_course(data, manifest_path):
    report, (sources, analyses, texts, mapped, facts) = validate_course(data, manifest_path)
    # Concatenate only the normalized evidence stream for the existing validator.
    # Document structure/content are authored semantically by the main agent.
    offsets, combined = {}, ''
    for sid in sources:
        offsets[sid] = len(combined)
        combined += texts[sid] + '\n\n'
    out = copy.deepcopy(data)
    used_ids = {t['id'] for t in out['topics']} | {b['id'] for t in out['topics'] for b in t['blocks']} | {s['id'] for s in out['summary']}
    used_bookmarks = {re.sub('[^a-zA-Z0-9_]', '_', x) for x in used_ids}
    def navigation_id():
        for i in range(1, len(used_ids)+2):
            ident = 'course_nav_' + str(i)
            if ident not in used_bookmarks:
                used_ids.add(ident)
                used_bookmarks.add(ident)
                return ident
        raise ValueError('Could not allocate navigation bookmark')
    units, spans = [], []
    unit_ids = {}
    for sid, analysis in analyses.items():
        for unit in analysis['units']:
            ref = sid+'::'+unit['id']
            ident = sid+'_'+unit['id']
            unit_ids[ref] = ident
            fact = facts[mapped[ref]]
            units.append({'id': ident, 'claim': fact['claim'], 'source_quotes': [e['quote'] for e in unit['evidence']], 'visual_refs': fact['visual_refs'], 'summary_refs': fact['summary_refs']})
    for sid, analysis in analyses.items():
        for span in analysis['source_accounting']:
            s = copy.deepcopy(span)
            s['start'] += offsets[sid]
            s['end'] += offsets[sid]
            if 'units' in s:
                s['units'] = [unit_ids[sid+'::'+u] for u in s['units']]
            spans.append(s)
    out['coverage'] = {'units': units, 'source_accounting': spans}
    # Visible navigation is deterministic from reviewed overview labels.
    links = [{'text': 'لِلتَّفْصِيلِ: '}]
    for node in iter_nodes(out['topics'][0]['blocks'][0]['root']):
        if node.get('topic_ref'):
            if len(links) > 1:
                links.append({'text': ' ؛ '})
            links.append({'text': node['label'], 'anchor': node['topic_ref']})
    if len(links) > 1:
        out['topics'][0]['blocks'].append({'id': navigation_id(), 'type': 'paragraph', 'text': links})
    for topic in out['topics'][1:]:
        topic['blocks'].append({'id': navigation_id(), 'type': 'paragraph', 'text': [{'text': 'الْعَوْدَةُ إِلَى الْخَرِيطَةِ الْعَامَّةِ', 'anchor': out['topics'][0]['id']}]})
    check_content(out)
    return out, combined, report
