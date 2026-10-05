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
import struct

CATEGORIES = {
    'cpu': 'CPU and translation',
    'commands': 'Command submission and reports',
    'geometry': 'Geometry and vertex data',
    'textures': 'Textures and compression',
    'surfaces': 'Surfaces, framebuffer and memory',
    'scenarios': 'Game-like scenarios',
    'shaders': 'Shaders and pipelines',
    'audio': 'MCPX voice input and mixing',
}


def category(test: dict) -> str:
    suite, identity = test['suite_id'].lower(), test['id'].lower()
    if suite == 'mcpx_voice':
        return 'audio'
    if 'shader' in suite or suite in ('uniform_thrash', 'pipeline_texture_switch'):
        return 'shaders'
    if suite.startswith('cpu'):
        return 'cpu'
    if any(s in suite for s in ('pfifo', 'report_query')):
        return 'commands'
    if suite in ('high_vertex_count', 'primitive_type', 'tiny_draw', 'vertex_buffer_allocation'):
        return 'geometry'
    if 'texture' in suite or 's3tc_sync_factor' in identity:
        return 'textures'
    if suite in ('surface', 'surface_rendering', 'fill_rate'):
        return 'surfaces'
    if suite == 'game_load' or suite.startswith('game_load_'):
        return 'scenarios'
    raise ValueError('Unclassified suite: ' + suite + '; extend the category map before packaging.')


def embedded_catalog(iso: bytes) -> bytes:
    """Read the bounded root catalog from the XDVDFS directory in the actual ISO."""
    def span(offset: int, size: int) -> bytes:
        if offset < 0 or size < 0 or offset + size > len(iso):
            raise ValueError('XISO embedded catalog points outside the image.')
        return iso[offset:offset + size]

    volume = span(32 * 2048, 2048)
    magic = b'MICROSOFT*XBOX*MEDIA'
    if volume[:20] != magic or volume[2028:2048] != magic:
        raise ValueError('Expected a self-contained XISO with an embedded catalog.')
    root_sector, root_size = struct.unpack_from('<II', volume, 20)
    if not 14 <= root_size <= 1024 * 1024:
        raise ValueError('XISO root directory exceeds the embedded catalog reader limit.')
    directory = span(root_sector * 2048, root_size)
    pending, visited, catalog = [0], set(), None
    while pending:
        offset = pending.pop()
        if offset in visited or len(visited) >= 65536 or offset < 0 or offset + 14 > len(directory):
            raise ValueError('Invalid XISO embedded catalog directory graph.')
        visited.add(offset)
        left, right, sector, size, flags, name_size = struct.unpack_from('<HHIIBB', directory, offset)
        if not name_size or offset + 14 + name_size > len(directory):
            raise ValueError('Invalid XISO embedded catalog entry.')
        name = directory[offset + 14:offset + 14 + name_size].lower()
        if name == b'catalog.json':
            if catalog is not None or flags & 0x10 or not 2 <= size <= 1024 * 1024:
                raise ValueError('Ambiguous or invalid XISO embedded catalog.')
            catalog = span(sector * 2048, size)
        for child in (left, right):
            if child:
                pending.append(child * 4)
    if catalog is None:
        raise ValueError('XISO has no embedded root catalog.json.')
    return catalog


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
    if embedded_catalog(data) != raw:
        raise ValueError('Selected catalog bytes differ from the ISO embedded catalog.')
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
