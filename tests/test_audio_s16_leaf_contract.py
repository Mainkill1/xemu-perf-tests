import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from utils.audio_torture_cases import build_cases


ROOT = Path(__file__).resolve().parents[1]
LEAF = "audio.vp_scaling.s16_mono.v001"


class AudioS16LeafContractTests(unittest.TestCase):
    def test_only_scaling_family_is_cataloged_and_explicitly_selected(self):
        catalog = json.loads((ROOT / "resources/catalog.json").read_text())
        audio_cases = build_cases(json.loads((ROOT / "resources/audio_torture_matrix.json").read_text()))
        catalog_ids = {test["id"] for test in catalog["tests"]}
        self.assertEqual(len(audio_cases), 138)
        scaling_ids = {case["id"] for case in audio_cases if case["family"] == "audio.vp_scaling"}
        self.assertEqual(len(scaling_ids), 45)
        self.assertEqual(catalog_ids & {case["id"] for case in audio_cases}, scaling_ids)
        routes = set()
        for case in audio_cases:
            if case["id"] not in scaling_ids:
                continue
            entry = next(test for test in catalog["tests"] if test["id"] == case["id"])
            name = ("S16MonoAllocationV257" if "allocation_v257" in case["id"] else
                    f"S16{'Mono' if case['params']['channels'] == 1 else 'Stereo'}V{case['params']['voice_count']:03d}")
            self.assertEqual(entry["execution"], {"legacy_suite": "AudioVpScaling", "legacy_test": name})
            self.assertEqual(entry["measurement_class"], "correctness")
            routes.add(name)
        self.assertEqual(len(routes), 45)
        leaf = next(test for test in catalog["tests"] if test["id"] == LEAF)
        self.assertEqual(leaf["suite_id"], "audio.vp_scaling")
        self.assertEqual(leaf["execution"], {"legacy_suite": "AudioVpScaling", "legacy_test": "S16MonoV001"})
        self.assertEqual(leaf["measurement_class"], "correctness")
        self.assertEqual(leaf["supported_targets"], ["xemu", "xbox"])
        self.assertIn({"name": "apu.mix", "kind": "structured", "scope_version": 1}, leaf["observations"])

        smoke = json.loads((ROOT / "resources/plans/smoke.json").read_text())["resolved_plan"]
        self.assertFalse(scaling_ids & {test["id"] for test in smoke["tests"]})
        family_plan = json.loads((ROOT / "resources/audio-vp-scaling.json").read_text())
        self.assertEqual({test["id"] for test in family_plan["resolved_plan"]["tests"]}, scaling_ids)
        selected = json.loads((ROOT / "resources/audio-vp-scaling-s16-mono-v001.json").read_text())
        self.assertEqual([test["id"] for test in selected["resolved_plan"]["tests"]], [LEAF])
        self.assertTrue(selected["settings"]["enable_xemu_only_tests"])
        self.assertTrue(selected["settings"]["skip_tests_by_default"])

    def test_suite_registration_and_result_path_are_explicit(self):
        source = (ROOT / "src/tests/audio_vp_scaling_tests.cpp").read_text()
        main = (ROOT / "src/main.cpp").read_text()
        runtime = (ROOT / "src/runtime_config.cpp").read_text()
        self.assertIn('"AudioVpScaling"', source)
        self.assertIn('AudioFamily::kVpScaling', source)
        self.assertIn('ScalingLegacyName(descriptor)', source)
        self.assertIn('RunCase(descriptor, name)', source)
        self.assertIn('BuildS16ScalingSource(', source)
        self.assertIn('McpxRawBackend', source)
        self.assertEqual(source.count('host_.FinishDraw(suite_name_, legacy_name'), 1)
        self.assertNotIn("ASSERT(", source)
        self.assertNotIn("McpxVoiceTests", source)
        self.assertIn('REG_TEST(AudioVpScalingTests)', main)
        self.assertIn('legacy_suite == "AudioVpScaling"', runtime)

    def test_failure_metadata_for_setup_output_and_teardown(self):
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / "probe"
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "src/tests"),
                            str(ROOT / "tests/audio_vp_scaling_result_probe.cpp"),
                            "-o", str(binary)], check=True, capture_output=True, text=True)
            subprocess.run([str(binary)], check=True, capture_output=True, text=True)

    def test_runner_bundle_categorizes_family_suite_as_audio(self):
        spec = importlib.util.spec_from_file_location("bundle", ROOT / "utils/package_runner_suite.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.category({"suite_id": "audio.vp_scaling", "id": LEAF}), "audio")


if __name__ == "__main__":
    unittest.main()
