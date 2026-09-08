#!/usr/bin/env python3
"""Revalidate sealed XISO reports offline without editing inputs or rerunning xemu."""
import argparse
from pathlib import Path
import oracle_validation as oracle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, nargs='+', required=True,
                        help='At least two sealed reports from the same baseline/backend.')
    parser.add_argument('--candidate', type=Path, nargs='+', required=True,
                        help='Sealed candidate reports for the same workload/backend.')
    parser.add_argument('--output', type=Path, required=True,
                        help='New output directory; refuses to overwrite existing evidence.')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; choose a new directory')
    paths = args.baseline + args.candidate
    before = [oracle.file_sha256(path) for path in paths]
    reports = [oracle.load_report(path) for path in paths]
    baseline = reports[:len(args.baseline)]
    candidate = reports[len(args.baseline):]
    consensus = oracle.build_consensus(baseline)
    outcomes = [oracle.validate_against_oracle(report, consensus) for report in candidate]
    audit = []
    for report, digest in zip(reports, before):
        changes = []
        for raw, projected in zip(report['records'], oracle.comparison_records(report['records'])):
            if raw != projected:
                changes.append({'test_id': raw['test_id'],
                                'comparison_only_exclusion': 'internal_oracle.failure_count',
                                'retained_raw_value': raw['internal_oracle']['failure_count'],
                                'reason': raw['comparison_policy']['reason']})
        audit.append({'report_id': report['report_id'], 'file_sha256': digest,
                      'record_count': len(report['records']), 'exclusions': changes})
    if before != [oracle.file_sha256(path) for path in paths]:
        raise oracle.OracleValidationError('an input changed during revalidation')
    args.output.mkdir(parents=True, exist_ok=False)
    oracle.write_json(args.output / 'consensus.json', consensus)
    oracle.write_json(args.output / 'revalidation.json', {
        'status': 'PASSED', 'backend': baseline[0]['source_backend'],
        'validator_sha256': oracle.file_sha256(Path(oracle.__file__)),
        'guest_image_sha256': baseline[0]['guest_image_sha256'],
        'inputs_unchanged': True, 'inputs': audit, 'candidates': outcomes,
        'scope': 'Offline output comparison only; no new runtime/performance qualification.',
    })
    print(f"PASSED: {len(baseline)} baseline and {len(candidate)} candidate reports; inputs unchanged")


if __name__ == '__main__':
    main()
