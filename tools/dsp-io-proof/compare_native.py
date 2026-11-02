#!/usr/bin/env python3
"""Qualify three isolated native gain routes against an admitted XISO report."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys


def compare(report, worker, inject=False):
    if report.get('status') != 'PASS' or report.get('program_matches') is not True:
        return {'status': 'INCOMPLETE', 'reason': 'guest/program admission required'}
    source, expected = report.get('input_words'), report.get('output_words')
    if not isinstance(source, list) or len(source) != 64 or not isinstance(expected, list) or len(expected) != 192:
        return {'status': 'INVALID'}
    if any(type(v) is not int or not 0 <= v <= 0xffffff for v in source + expected):
        return {'status': 'INVALID'}
    result = subprocess.run([str(worker.resolve())], input=struct.pack('<64I', *source),
                            capture_output=True, timeout=5)
    if result.returncode or len(result.stdout) != 768:
        return {'status': 'CRASH' if result.returncode < 0 else 'INVALID', 'worker_exit': result.returncode}
    output = list(struct.unpack('<192I', result.stdout))
    if inject:
        output[0] ^= 1
    differences = [i for i, (a, b) in enumerate(zip(output, expected)) if a != b]
    verdict = {'status': 'MISMATCH' if differences else 'BASELINE_MATCH',
               'authority': 'EMULATOR_BASELINE', 'native_routes_executed': 3,
               'native_output_words': 192, 'injected_fault': inject,
               'worker_sha256': hashlib.sha256(worker.read_bytes()).hexdigest(),
               'program_sha256': report['program_sha256'], 'iso_sha256': report['iso_sha256'],
               'live_routing_enabled': False, 'timing_comparable': False}
    if differences:
        i = differences[0]
        verdict['first_difference'] = {'route': i // 64, 'sample': i % 64,
                                       'expected': expected[i], 'actual': output[i]}
    return verdict


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guest-report', type=Path, required=True)
    parser.add_argument('--worker', type=Path, required=True)
    parser.add_argument('--inject-fault', action='store_true')
    args = parser.parse_args()
    try:
        verdict = compare(json.loads(args.guest_report.read_text()), args.worker, args.inject_fault)
    except subprocess.TimeoutExpired:
        verdict = {'status': 'TIMEOUT'}
    except (OSError, ValueError, TypeError, KeyError, struct.error):
        verdict = {'status': 'INVALID'}
    print(json.dumps(verdict, sort_keys=True))
    sys.exit(0 if verdict['status'] == 'BASELINE_MATCH' else 1)
