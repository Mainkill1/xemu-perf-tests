#!/usr/bin/env python3
"""Package the exact compiled XISO and catalog for Xemu-Test-Runner.

Build-time only: no ISO edits, test starts or automatic qualification claims.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

CATEGORIES = {
    'cpu': 'CPU and translation',
    'command': 'Command submission and reports',
    'geometry': 'Geometry and vertex data',
    'textures': 'Textures and compression',
    'surfaces': 'Surfaces, framebuffer and memory',
    'scenarios': 'Game-like scenarios',
    'shaders': 'Shaders and pipelines',
}


def category(test: dict) -> str:
    suite, identity = test['suite_id'].lower(), test['id'].lower()
    if 'shader' in suite or suite in ('uniform_thrash', 'pipeline_texture_switch'):
        return 'shaders'
    if suite.startswith('cpu'):
        return 'cpu'
    if any(s in suite for s in ('pfifo', 'report_query')):
        return 'command'
    if suite in ('high_vertex_count', 'primitive_type', 'tiny_draw', 'vertex_buffer_allocation'):
        return 'geometry'
    if 'texture' in suite or 's3tc_sync_factor' in identity:
        return 'textures'
    if suite in ('surface', 'surface_rendering', 'fill_rate'):
        return 'surfaces'
    if suite == 'game_load' or suite.startswith('game_load_'):
        return 'scenarios'
    raise ValueError('Unclassified suite: ' + suite + '; extend the category map before packaging.')


def manifest(iso: bytes, catalog_bytes: bytes, source_commit: str) -> dict:
    if not iso or len(catalog_bytes) > 1024 * 1024:
        raise ValueError('Nonempty ISO and catalog up to 1 MiB required.')
    if not re.fullmatch(r'[0-9a-f]{40}', source_commit):
        raise ValueError('Supply the exact 40-character source commit.')
    catalog = json.loads(catalog_bytes)
    if catalog.get('schema_version') != 1 or not re.fullmatch(r'sha256:[0-9a-f]{64}', catalog.get('catalog_id', '')):
        raise ValueError('Unsupported catalog identity/schema.')
    tests = catalog['tests']
    ids = [test['id'] for test in tests]
    if len(ids) != len(set(ids)) or not all(re.fullmatch(r'[a-z0-9_.-]+', id) for id in ids):
        raise ValueError('Duplicate or invalid test IDs.')
    leaves = [test for test in tests if test['kind'] == 'leaf']
    groups = [test for test in tests if test['kind'] == 'group']
    if len(leaves) != catalog['leaf_count'] or len(groups) != catalog['group_count'] or len(tests) != len(leaves) + len(groups):
        raise ValueError('Catalog counts do not match its records.')
    partitions = {key: [] for key in CATEGORIES}
    for test in leaves:
        partitions[category(test)].append(test['id'])
    atomic = []
    for group in groups:
        children = group.get('child_ids', [])
        # Five checkpoints belong to one memory-pressure lifetime. Other
        # composite masks remain individually selectable; the host keeps their
        # selected shared execution route together without inventing siblings.
        if children and all('vulkan_memory_pressure' in child for child in children):
            atomic.append(children)
    known = {test['id'] for test in leaves}
    smoke = [id for id in ('busy_pfifo.pgraph_pattern_polling', 'surface.cpu_read_clean_surface',
                           'game_load.s3tc_sync_factor.dxt1_dirty_once_redraw') if id in known]
    if not smoke and leaves:
        smoke = [leaves[0]['id']]
    return {
        'schemaVersion': 1, 'sourceCommit': source_commit, 'qualification': 'candidate',
        'isoSha256': hashlib.sha256(iso).hexdigest(),
        'catalogSha256': hashlib.sha256(catalog_bytes).hexdigest(), 'catalogId': catalog['catalog_id'],
        'categories': [{'id': key, 'name': CATEGORIES[key], 'tests': values} for key, values in partitions.items() if values],
        'atomicGroups': atomic, 'smoke': smoke,
    }


def package(iso: Path, catalog: Path, output: Path, source_commit: str) -> dict:
    if iso.is_symlink() or catalog.is_symlink():
        raise ValueError('Package inputs must be regular files, not links.')
    data, raw = iso.read_bytes(), catalog.read_bytes()
    value = manifest(data, raw, source_commit)
    output.mkdir(parents=True, exist_ok=False)
    try:
        (output / 'suite.iso').write_bytes(data)
        (output / 'catalog.json').write_bytes(raw)
        (output / 'suite.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    except BaseException:
        shutil.rmtree(output)
        raise
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iso', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, default=Path('resources/catalog.json'))
    parser.add_argument('--output', type=Path, default=Path('build/runner-suite'))
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    value = package(args.iso, args.catalog, args.output, args.source_commit)
    print(json.dumps({'directory': str(args.output), 'isoSha256': value['isoSha256'],
                      'catalogId': value['catalogId'], 'qualification': value['qualification']}, separators=(',', ':')))

if __name__ == '__main__':
    main()
