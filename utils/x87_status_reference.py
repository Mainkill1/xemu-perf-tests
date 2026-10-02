#!/usr/bin/env python3
"""Derive CPU-only x87 oracles from instruction literals and solid pixels.

Never consume actual xemu results or replace an existing oracle. Retain the
input reference and output provenance alongside emulator evidence, in xemu.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def fnv(data):
    value = 0xcbf29ce484222325
    for byte in data:
        value = ((value ^ byte) * 0x100000001b3) & 0xffffffffffffffff
    return f'{value:016x}'


def pixel_bytes(argb):
    return argb.to_bytes(4, 'little')


def solid_hash(argb):
    # The declared 640x480 A8R8G8B8 surface is fully cleared before hashing.
    # Rows exclude pitch padding; FinishDraw hashes before drawing any text.
    return fnv(pixel_bytes(argb) * (640 * 480))


def expected_records():
    operations = 1048573 * 16
    records = []
    for suffix, name, revision, eax in [
        ('x87_status_vectors', 'X87StatusVectors', 2, None),
        ('x87_status_ax', 'X87StatusAX', 2, 0xa5a50000),
        ('x87_compare_status_ax', 'X87CompareStatusAX', 2, 0xa5a57000),
    ]:
        if eax is None:
            color = 0xff102030
            metadata = {'source_kat': '00001809', 'result_checksum': '00000000', 'oracle_status': 'PASS'}
        else:
            checksum = (operations * eax) & 0xffffffff
            color = 0xff000000 | (checksum & 0xffffff)
            metadata = {'work_checksum': f'{checksum:08x}', 'result_checksum': f'{eax:08x}',
                        'oracle_status': 'PASS'}
        records.append({'schema_version': 1, 'id': 'cpu_floating_point.' + suffix,
                        'revision': revision, 'kind': 'leaf', 'name': 'CpuFloatingPoint::' + name,
                        'outcome': 'PASS', 'iterations': 40, 'sample_count': 10,
                        'measurement_iterations_multiplier': 4, 'warmup_iterations': 3,
                        'gpu_completion_mode': 'per_iteration', 'unit': 'us',
                        'direction': 'lower_is_better', 'framebuffer_fnv1a64': solid_hash(color),
                        'metadata': metadata})
    return records


def extend_reference(existing):
    if not isinstance(existing, list) or not all(isinstance(r, dict) and isinstance(r.get('id'), str)
                                              for r in existing):
        raise ValueError('Reference must contain records with stable IDs')
    ids = {r['id'] for r in existing}
    new = expected_records()
    if len(ids) != len(existing) or ids & {r['id'] for r in new}:
        raise ValueError('Duplicate ID or existing x87 oracle; never replace existing expected output')
    return copy.deepcopy(existing) + new


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field: ' + key)
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True, help='Existing pinned reference, unchanged input')
    parser.add_argument('--output', type=Path, required=True, help='New reference file; must not exist')
    parser.add_argument('--manifest', type=Path, required=True, help='New provenance file; must not exist')
    args = parser.parse_args()
    if args.output.exists() or args.manifest.exists() or args.output == args.manifest:
        parser.error('Outputs must be distinct new files')
    raw = args.base.read_bytes()
    reference = extend_reference(json.loads(raw, object_pairs_hook=unique_object))
    output = (json.dumps(reference, indent=2) + '\n').encode()
    provenance = {'schema': 1, 'baseSha256': hashlib.sha256(raw).hexdigest(),
                  'outputSha256': hashlib.sha256(output).hexdigest(),
                  'origin': 'Independent architectural literals and solid-color framebuffer bytes',
                  'hardwareConformanceClaim': False, 'capturedXemuHashUsed': False,
                  'surface': '640x480 A8R8G8B8, little-endian BGRA, row bytes only, before overlay',
                  'operationsPerBody': 16777168, 'records': expected_records()}
    with args.output.open('xb') as file:
        file.write(output)
    with args.manifest.open('x') as file:
        json.dump(provenance, file, indent=2)
        file.write('\n')
    print(json.dumps({'output': str(args.output), 'sha256': provenance['outputSha256'], 'added': 3}))


if __name__ == '__main__':
    main()
