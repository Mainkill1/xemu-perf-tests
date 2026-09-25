import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class BundleTests(unittest.TestCase):
    def module(self):
        spec = importlib.util.spec_from_file_location('bundle', ROOT / 'utils/package_runner_suite.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def fixture(self):
        def leaf(id, suite):
            return {'id': id, 'kind': 'leaf', 'suite_id': suite, 'supported_targets': ['xemu'],
                    'execution': {'legacy_suite': suite, 'legacy_test': id}}
        return {'schema_version': 1, 'catalog_id': 'sha256:' + 'a' * 64,
                'leaf_count': 4, 'group_count': 1, 'tests': [
                    leaf('cpu.math', 'cpu_floating_point'), leaf('shader.pipeline', 'shader_lifecycle'),
                    leaf('surface.vulkan_memory_pressure.a', 'surface'), leaf('surface.vulkan_memory_pressure.b', 'surface'),
                    {'id': 'memory.group', 'kind': 'group', 'child_ids': ['surface.vulkan_memory_pressure.a', 'surface.vulkan_memory_pressure.b']}]}

    def test_categories_cover_each_leaf_once_and_include_shaders(self):
        m = self.module().manifest(b'iso', json.dumps(self.fixture()).encode(), 'b' * 40)
        selected = [id for c in m['categories'] for id in c['tests']]
        self.assertEqual(len(selected), len(set(selected)))
        self.assertEqual(len(selected), 4)
        self.assertEqual(next(c for c in m['categories'] if c['id'] == 'shaders')['tests'], ['shader.pipeline'])
        self.assertEqual(m['atomicGroups'], [['surface.vulkan_memory_pressure.a', 'surface.vulkan_memory_pressure.b']])

    def test_exact_iso_catalog_bytes_are_hashed(self):
        catalog = json.dumps(self.fixture()).encode()
        result = self.module().manifest(b'iso', catalog, 'b' * 40)
        self.assertEqual(result['isoSha256'], hashlib.sha256(b'iso').hexdigest())
        self.assertEqual(result['catalogSha256'], hashlib.sha256(catalog).hexdigest())
        self.assertEqual(result['qualification'], 'candidate')

    def test_invalid_counts_or_duplicate_ids_are_rejected(self):
        module = self.module()
        for bad in ('count', 'duplicate'):
            catalog = self.fixture()
            if bad == 'count': catalog['leaf_count'] = 5
            else: catalog['tests'][1]['id'] = 'cpu.math'
            with self.assertRaises(ValueError): module.manifest(b'iso', json.dumps(catalog).encode(), 'b' * 40)

    def test_unknown_subsystem_is_not_silently_hidden(self):
        catalog = self.fixture()
        catalog['tests'][0]['suite_id'] = 'unknown_core'
        with self.assertRaises(ValueError): self.module().manifest(b'iso', json.dumps(catalog).encode(), 'b' * 40)

    def test_packaging_does_not_change_iso_or_catalog(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            iso, catalog = root / 'input.iso', root / 'catalog.json'
            iso.write_bytes(b'immutable')
            raw = json.dumps(self.fixture()).encode()
            catalog.write_bytes(raw)
            module.package(iso, catalog, root / 'bundle', 'b' * 40)
            self.assertEqual((root / 'bundle/suite.iso').read_bytes(), b'immutable')
            self.assertEqual((root / 'bundle/catalog.json').read_bytes(), raw)
            self.assertEqual(iso.read_bytes(), b'immutable')

    def test_real_shader_catalog_has_complete_category_coverage(self):
        raw = (ROOT / 'resources/catalog.json').read_bytes()
        bundle = self.module().manifest(b'build-fixture', raw, 'b' * 40)
        shader_ids = next(c['tests'] for c in bundle['categories'] if c['id'] == 'shaders')
        self.assertTrue(any('shader_lifecycle' in id for id in shader_ids))
        self.assertEqual(sum(len(c['tests']) for c in bundle['categories']), json.loads(raw)['leaf_count'])

if __name__ == '__main__': unittest.main()
