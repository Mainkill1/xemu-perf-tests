"""Independent pixel/architectural oracles, never a captured xemu baseline."""
from pathlib import Path
import copy
import importlib.util
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module():
    spec = importlib.util.spec_from_file_location('x87_reference', ROOT / 'utils/x87_status_reference.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class ReferenceTests(unittest.TestCase):
    def test_fault_family_preserves_all_prior_oracles(self):
        m = module()
        existing = m.extend_reference(m.expected_records(), family='exception-status')
        before = copy.deepcopy(existing)
        try:
            extended = m.extend_reference(existing, family='fault')
        except ValueError:
            self.fail('The fault-checkpoint reference family is missing')
        self.assertEqual(existing, before)
        self.assertEqual(extended[:-1], before)
        record = extended[-1]
        self.assertEqual(record['id'], 'cpu_floating_point.x87_fault_checkpoint')
        self.assertEqual(record['metadata'], {'source_kat': '00000004',
                                            'result_checksum': '00000000', 'oracle_status': 'PASS'})
        self.assertEqual(record['framebuffer_fnv1a64'], m.solid_hash(0xff203040))
        with self.assertRaises(ValueError):
            m.extend_reference(extended, family='fault')

    def test_exception_status_family_appends_only_its_new_oracle(self):
        m = module()
        existing = m.expected_records()
        before = copy.deepcopy(existing)
        try:
            extended = m.extend_reference(existing, family='exception-status')
        except TypeError:
            self.fail('The exception-status reference family is missing')
        self.assertEqual(existing, before)
        self.assertEqual(extended[:3], before)
        self.assertEqual(len(extended), 4)
        record = extended[-1]
        self.assertEqual(record['id'], 'cpu_floating_point.x87_exception_status')
        self.assertEqual(record['revision'], 1)
        self.assertEqual(record['metadata'], {'source_kat': '00000180',
                                            'result_checksum': '00000000', 'oracle_status': 'PASS'})
        self.assertEqual(record['framebuffer_fnv1a64'], m.solid_hash(0xff403020))
        with self.assertRaises(ValueError):
            m.extend_reference(extended, family='exception-status')

    def test_pixel_byte_order_and_published_scalar_oracle(self):
        # Tiny explicit BGRA vector, plus the existing scalar reference color.
        m = module()
        self.assertEqual(m.pixel_bytes(0xff102030), bytes([0x30, 0x20, 0x10, 0xff]))
        self.assertEqual(m.solid_hash(0xff800000), '6962077c244da325')

    def test_empty_and_single_byte_fnv_vectors(self):
        m = module()
        self.assertEqual(m.fnv(b''), 'cbf29ce484222325')
        self.assertEqual(m.fnv(b'a'), 'af63dc4c8601ec8c')

    def test_work_oracles_and_reference_contract_are_literal(self):
        records = {r['id']: r for r in module().expected_records()}
        for suffix, revision, checksum, eax in [('x87_status_ax', 2, 'f1100000', 'a5a50000'),
                                              ('x87_compare_status_ax', 2, 'f0fb0000', 'a5a57000')]:
            r = records['cpu_floating_point.' + suffix]
            self.assertEqual(r['revision'], revision)
            self.assertEqual(r['metadata']['work_checksum'], checksum)
            self.assertEqual(r['metadata']['result_checksum'], eax)
            self.assertEqual(r['iterations'], 40)
            self.assertEqual(r['sample_count'], 10)
            self.assertEqual(r['warmup_iterations'], 3)
            self.assertEqual(r['measurement_iterations_multiplier'], 4)
            self.assertEqual(r['gpu_completion_mode'], 'per_iteration')

    def test_existing_oracles_are_preserved_without_mutation(self):
        existing = [{'id': 'other.leaf', 'framebuffer_fnv1a64': '1234567890abcdef', 'revision': 7}]
        before = copy.deepcopy(existing)
        extended = module().extend_reference(existing)
        self.assertEqual(existing, before)
        self.assertEqual(extended[:1], before)
        self.assertEqual(len(extended), 4)

    def test_duplicate_or_existing_x87_oracle_is_rejected(self):
        m = module()
        for records in [[{'id': 'cpu_floating_point.x87_status_ax'}],
                        [{'id': 'other.leaf'}, {'id': 'other.leaf'}]]:
            with self.assertRaises(ValueError):
                m.extend_reference(records)

    def test_cli_rejects_duplicate_json_fields_without_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base, output, manifest = (root / name for name in ['base.json', 'output.json', 'manifest.json'])
            raw = b'[{"id":"other.leaf","id":"changed.leaf"}]'
            base.write_bytes(raw)
            result = subprocess.run([sys.executable, str(ROOT / 'utils/x87_status_reference.py'),
                                     '--base', str(base), '--output', str(output), '--manifest', str(manifest)],
                                    capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(base.read_bytes(), raw)
            self.assertFalse(output.exists())
            self.assertFalse(manifest.exists())

    def test_cli_preserves_existing_output_and_manifest_bytes(self):
        for name in ['output.json', 'manifest.json']:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                base, output, manifest = (root / filename for filename in ['base.json', 'output.json', 'manifest.json'])
                base.write_bytes(b'[]')
                sentinel = root / name
                sentinel.write_bytes(b'existing reference evidence')
                result = subprocess.run([sys.executable, str(ROOT / 'utils/x87_status_reference.py'),
                                         '--base', str(base), '--output', str(output), '--manifest', str(manifest)],
                                        capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(sentinel.read_bytes(), b'existing reference evidence')
                self.assertEqual(base.read_bytes(), b'[]')
                self.assertFalse((manifest if sentinel == output else output).exists())


if __name__ == '__main__':
    unittest.main()
