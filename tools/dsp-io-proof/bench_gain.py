#!/usr/bin/env python3
"""Balanced fixed-work DSP/native gain costs; original guest answers required."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import struct
import subprocess
import time

PROGRAM = '41a14ad0eff5ce00e45fb73c81f497d1d1056bf1ffc6301b91b1d78d5663778a'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def balanced_order(pairs):
    return [mode for cycle in range(pairs) for mode in
            (('dsp', 'native', 'native', 'dsp') if cycle % 2 == 0
             else ('native', 'dsp', 'dsp', 'native'))]


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def summarize(rows, iterations=None, warmup=None):
    if not rows or any(row.get('mode') not in ('dsp', 'native') for row in rows):
        raise ValueError('no samples')
    result = {}
    counts = set()
    for mode in ('dsp', 'native'):
        samples = [row for row in rows if row.get('mode') == mode]
        if not samples:
            raise ValueError('missing engine samples')
        for row in samples:
            blocks = row.get('blocks')
            if row.get('status') != 'MATCH' or type(blocks) is not int or blocks < 1:
                raise ValueError('failed or missing fixed work')
            counts.add(blocks)
            if (iterations is not None and blocks != iterations) or (warmup is not None and row.get('warmup') != warmup):
                raise ValueError('worker did not execute requested work')
            for key in ('wall_ns', 'cpu_ns', 'peak_rss_kib'):
                if type(row.get(key)) is not int or row[key] <= 0:
                    raise ValueError('missing resource measurement')
            if (row.get('output_words_checked') != blocks * 192 or
                    row.get('dma_words_checked') != blocks * 192 or
                    row.get('semantic_gain_results') != blocks * 192 or
                    row.get('exports') != blocks or row.get('exported_bytes') != blocks * 768 or
                    row.get('dsp_instructions_per_block') != (588 if mode == 'dsp' else 0) or
                    row.get('dsp_route_instructions') != ([193] * 3 if mode == 'dsp' else [0] * 3)):
                raise ValueError('incomplete correctness coverage')
        cpu = [row['cpu_ns'] / row['blocks'] for row in samples]
        wall = [row['wall_ns'] / row['blocks'] for row in samples]
        result[mode] = {'samples': len(samples), 'completed_blocks': sum(row['blocks'] for row in samples),
                        'median_cpu_ns_per_block': statistics.median(cpu),
                        'median_wall_ns_per_block': statistics.median(wall),
                        'p95_batch_wall_ns_per_block': percentile(wall, .95),
                        'p99_batch_wall_ns_per_block': percentile(wall, .99),
                        'min_cpu_ns_per_block': min(cpu), 'max_cpu_ns_per_block': max(cpu),
                        'median_cpu_ns_per_output_word': statistics.median(cpu) / 192,
                        'median_one_core_cpu_percent': statistics.median(
                            [100 * row['cpu_ns'] / row['wall_ns'] for row in samples]),
                        'median_peak_rss_kib': statistics.median([row['peak_rss_kib'] for row in samples])}
    if len(counts) != 1 or result['dsp']['samples'] != result['native']['samples']:
        raise ValueError('unmatched work or sample counts')
    for label in ('cpu', 'wall'):
        key = 'median_' + label + '_ns_per_block'
        result[label + '_improvement_percent'] = 100 * (result['dsp'][key] - result['native'][key]) / result['dsp'][key]
    return result


def prepare(report, header, output):
    if (report.get('status') != 'PASS' or report.get('program_matches') is not True or
            report.get('program_sha256') != PROGRAM or report.get('dma_matches') is not True or
            report.get('input_preserved') is not True):
        raise ValueError('admitted full guest GP/DMA proof required')
    words = [int(word, 16) for word in re.findall(r'0x([0-9a-fA-F]+)', header.read_text())]
    if not 1 <= len(words) <= 2048 or any(word > 0xffffff for word in words):
        raise ValueError('invalid program header')
    image = struct.pack('<4096I', *(words + [0] * (4096 - len(words))))
    if hashlib.sha256(image).hexdigest() != PROGRAM:
        raise ValueError('program identity mismatch')
    files = [output / name for name in ('program.bin', 'input.bin', 'expected.bin')]
    files[0].write_bytes(image)
    for key, count, file in zip(('input_words', 'output_words'), (64, 192), files[1:]):
        data = report[key]
        if not isinstance(data, list) or len(data) != count or any(type(v) is not int or not 0 <= v <= 0xffffff for v in data):
            raise ValueError('invalid admitted words')
        file.write_bytes(struct.pack('<' + str(count) + 'I', *data))
    return files


def campaign(args):
    args.output.mkdir(mode=0o700)
    report = json.loads(args.guest_report.read_text())
    files = prepare(report, args.program_header, args.output)
    manifest = {'status': 'INCOMPLETE', 'scope': 'isolated-public-gain-output-and-export-projection',
                'worker_sha256': digest(args.worker), 'guest_report_sha256': digest(args.guest_report),
                'worker_elf_sha256': digest(args.worker_binary or args.worker),
                'runner_sha256': digest(Path(__file__)), 'iso_sha256': report['iso_sha256'],
                'input_identities': {file.name: digest(file) for file in files},
                'iterations': args.iterations, 'warmup': args.warmup, 'cpu': args.cpu,
                'order': balanced_order(args.pairs), 'samples': [],
                'percentiles': 'nearest rank across batch cost/block; not individual block/frame tails',
                'timing_scope': 'warm fixed work including input feed, output materialization, export and validation; process startup/warmup excluded',
                'created_unix': time.time(), 'uname': list(os.uname())}
    repeat_image = bytearray(files[0].read_bytes())
    struct.pack_into('<I', repeat_image, 1238 * 4, 0)
    manifest['repeat_program_sha256'] = hashlib.sha256(repeat_image).hexdigest()
    for index, mode in enumerate(manifest['order']):
        command = [str(args.worker), mode, *(str(file) for file in files),
                   str(args.iterations), str(args.warmup)]
        if args.cpu is not None:
            command = ['taskset', '-c', str(args.cpu), *command]
        run = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout)
        try:
            sample = json.loads(run.stdout)
        except ValueError:
            sample = {'status': 'INVALID', 'stdout': run.stdout}
        sample.update(index=index, process_exit=run.returncode, stderr=run.stderr)
        manifest['samples'].append(sample)
        (args.output / 'report.json').write_text(json.dumps(manifest, indent=2) + '\n')
        if run.returncode or sample.get('status') != 'MATCH' or sample.get('mode') != mode:
            raise ValueError('failed sample; retained campaign incomplete')
    manifest['summary'] = summarize(manifest['samples'], args.iterations, args.warmup)
    manifest['status'] = 'MATCH'
    (args.output / 'report.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest['summary'], sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', type=Path, required=True)
    parser.add_argument('--worker-binary', type=Path, help='actual ELF when --worker is a loader wrapper')
    parser.add_argument('--guest-report', type=Path, required=True)
    parser.add_argument('--program-header', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--iterations', type=int, default=50000)
    parser.add_argument('--warmup', type=int, default=100)
    parser.add_argument('--pairs', type=int, default=16)
    parser.add_argument('--cpu', type=int)
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    if args.worker.read_bytes()[:4] != b'\x7fELF' and args.worker_binary is None:
        parser.error('a loader wrapper requires --worker-binary for exact evidence identity')
    if not (1 <= args.iterations <= 1000000 and 1 <= args.warmup <= 10000 and 1 <= args.pairs <= 64):
        parser.error('iteration, warmup or pair count outside bounds')
    campaign(args)
