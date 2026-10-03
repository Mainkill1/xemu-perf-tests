"""Execute the production fixture's emitted IA-32 code on an x86 Linux host.

Only as/ld and the host C++ compiler are needed; the IA-32 harness uses Linux
syscalls and no 32-bit C runtime. These are execution/KAT tests, not xemu timing.
"""
import pathlib
import struct
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def reference(operations, count):
    value = 0x12345678
    for i in range(operations):
        value ^= i ^ (((i % count) + 1) * 0x9E3779B9 & 0xFFFFFFFF)
        value = ((value << 7) | (value >> 25)) & 0xFFFFFFFF
        value = (value + 0x7F4A7C15) & 0xFFFFFFFF
    return value


class JumpCacheCollisionContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = pathlib.Path(cls.directory.name)
        source = cls.path / 'emit.cpp'
        source.write_text('''#include <cstdio>
#include <cstdlib>
#include "src/tests/cpu_jump_cache_workload.h"
int main(int argc, char **argv) {
    alignas(4096) unsigned char code[4096];
    if (argc != 3 && argc != 4) return 2;
    if (!CpuJumpCache::Initialize(code, std::atoi(argv[1]), std::atoi(argv[2]))) return 3;
    if (argc == 4) {
        uintptr_t base = std::strtoull(argv[3], nullptr, 10);
        for (unsigned i = 0; i < unsigned(std::atoi(argv[1])); ++i) {
            uint32_t slot = CpuJumpCache::Slot(base + CpuJumpCache::Offset(i, std::atoi(argv[2])));
            if (std::fwrite(&slot, 1, sizeof(slot), stdout) != sizeof(slot)) return 4;
        }
        return 0;
    }
    return std::fwrite(code, 1, sizeof(code), stdout) == sizeof(code) ? 0 : 4;
}
''')
        cls.emitter = cls.path / 'emit'
        subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT),
                        str(source), '-o', str(cls.emitter)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def emitted(self, count, collide):
        result = subprocess.run([str(self.emitter), str(count), str(int(collide))], capture_output=True)
        self.assertEqual(result.returncode, 0, 'valid generated workload must initialize')
        self.assertEqual(len(result.stdout), 4096)
        return result.stdout

    def test_geometry_for_every_page_alignment(self):
        for count in (2, 8, 10):
            for collide in (False, True):
                code = self.emitted(count, collide)
                offsets = [i * (65 if collide else 64) for i in range(count)]
                for base in (0x1000, 0x10000000, 0x80001000, 0xFFFFF000):
                    # Independent bit extraction of Mainkill1/xemu@76c23c7d's
                    # 4K-page, 4096-slot hash: six page bits and six offset bits.
                    slots = [((((base + o) >> 12) ^ ((base + o) >> 18)) & 63) * 64 +
                             (((base + o) ^ ((base + o) >> 6)) & 63) for o in offsets]
                    actual = subprocess.check_output([str(self.emitter), str(count),
                                                      str(int(collide)), str(base)])
                    self.assertEqual(list(struct.unpack('<' + 'I' * count, actual)), slots)
                    self.assertEqual(len(set(slots)), 1 if collide else count)
                for offset in offsets:
                    self.assertEqual(code[offset:offset + 4], b'\x8b\x44\x24\x04')
                    self.assertEqual(code[offset + 17], 0xC3)

    def test_generated_code_executes_independent_checksums(self):
        for count, collide in ((2, True), (8, True), (10, True), (8, False)):
            data = self.emitted(count, collide)
            for operations in (0, 1, 12347):
                with self.subTest(count=count, collide=collide, operations=operations):
                    actual = self.execute(data, count, collide, operations)
                    self.assertEqual(actual, reference(operations, count))

    def test_full_declared_budgets_match_known_answers(self):
        for count, collide, expected in ((2, True, 0x4F71ED44), (8, True, 0x52F08FDA),
                                         (10, True, 0x9D8149E6), (8, False, 0x52F08FDA)):
            with self.subTest(count=count, collide=collide):
                self.assertEqual(reference(8000000, count), expected)
                self.assertEqual(self.execute(self.emitted(count, collide), count, collide, 8000000), expected)

    def test_catalog_exposes_four_distinct_fixed_work_leaves(self):
        import json
        catalog = json.loads((ROOT / 'resources/catalog.json').read_text())
        entries = [x for x in catalog['tests'] if x['id'].startswith('cpu_translation_blocks.jump_cache_')]
        self.assertEqual({x['execution']['legacy_test'] for x in entries},
                         {'JumpCacheCollision2', 'JumpCacheCollision8', 'JumpCacheCollision10',
                          'JumpCacheNoncollision8'})
        self.assertTrue(all(x['kind'] == 'leaf' and x['revision'] == 1 and
                            x['timeout_ms'] == 120000 for x in entries))

    def test_source_reference_qualifies_work_without_observed_output(self):
        # Catches missing leaves, incorrect work hashes/KATs, and copied
        # framebuffer or timing output. Expectations were independently
        # established by the emitted-code execution tests above.
        from utils.cpu_jump_cache_reference import records
        expected = {'jump_cache_collision2': (2, True, '25d77da1', '4f71ed44'),
                    'jump_cache_collision8': (8, True, '8526a9d7', '52f08fda'),
                    'jump_cache_collision10': (10, True, '80931474', '9d8149e6'),
                    'jump_cache_noncollision8': (8, False, 'd9b2a53b', '52f08fda')}
        actual = records()
        self.assertEqual({x['id'].split('.')[-1] for x in actual}, set(expected))
        for item in actual:
            count, collide, work, result = expected[item['id'].split('.')[-1]]
            self.assertNotIn('framebuffer_fnv1a64', item)
            self.assertNotIn('raw_results', item)
            self.assertEqual(item['sample_count'], 10)
            self.assertEqual(item['metadata']['oracle_status'], 'PASS')
            self.assertEqual(item['metadata']['work_checksum'], work)
            self.assertEqual(item['metadata']['result_checksum'], result)
            self.assertEqual(item['metadata']['operations'], 8000000)
            data = self.emitted(count, collide)
            fnv = 2166136261
            for byte in data:
                fnv = ((fnv ^ byte) * 16777619) & 0xFFFFFFFF
            self.assertEqual(fnv, int(work, 16))

    def test_invalid_target_counts_fail(self):
        for count in (-1, 0, 11):
            result = subprocess.run([str(self.emitter), str(count), '1'], capture_output=True)
            self.assertEqual(result.returncode, 3)
            self.assertEqual(result.stdout, b'')

    def execute(self, code, count, collide, operations):
        blob = self.path / 'code.bin'
        blob.write_bytes(code)
        source = self.path / 'run.S'
        source.write_text(f'''.global _start
.section .text
_start:
 mov $0x12345678,%esi
 xor %edi,%edi
1:
 cmp ${operations},%edi
 jae 2f
 mov %edi,%eax
 xor %edx,%edx
 mov ${count},%ecx
 div %ecx
 imul ${65 if collide else 64},%edx,%edx
 lea code(%edx),%ebx
 mov %esi,%eax
 xor %edi,%eax
 push %eax
 call *%ebx
 add $4,%esp
 mov %eax,%esi
 inc %edi
 jmp 1b
2:
 mov %esi,result
 mov $4,%eax
 mov $1,%ebx
 mov $result,%ecx
 mov $4,%edx
 int $0x80
 mov $1,%eax
 xor %ebx,%ebx
 int $0x80
.balign 4096
code:
.incbin "{blob}"
.section .data
result: .long 0
''')
        obj = self.path / 'run.o'
        exe = self.path / 'run'
        subprocess.run(['as', '--32', str(source), '-o', str(obj)], check=True, capture_output=True)
        subprocess.run(['ld', '-m', 'elf_i386', str(obj), '-o', str(exe)], check=True, capture_output=True)
        result = subprocess.run([str(exe)], check=True, capture_output=True)
        self.assertEqual(len(result.stdout), 4)
        return struct.unpack('<I', result.stdout)[0]


if __name__ == '__main__':
    unittest.main()
