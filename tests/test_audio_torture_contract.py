import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "resources" / "audio_torture_matrix.json"


class AudioTortureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))

    def test_ground_truth_sources_are_revision_pinned(self):
        nxdk = self.matrix["ground_truth"]["nxdk_xaudio"]
        apu = self.matrix["ground_truth"]["mcpx_apu"]
        self.assertEqual(nxdk["repository"], "abaire/nxdk")
        self.assertEqual(nxdk["revision"], "73c95900965a16be3a3e34b8d4d5d41bc18498be")
        self.assertEqual(nxdk["path"], "lib/hal/audio.h")
        self.assertEqual(apu["repository"], "Mainkill1/xemu")
        self.assertEqual(apu["revision"], "b4d69b2440a33ad93987b269c2ecac97c45367bc")
        self.assertEqual(apu["path"], "hw/xbox/mcpx/apu/apu_regs.h")

    def test_ground_truth_limits_are_explicit(self):
        apu = self.matrix["ground_truth"]["mcpx_apu"]
        self.assertEqual(apu["max_voices"], 256)
        self.assertEqual(apu["max_3d_voices"], 64)
        self.assertEqual(apu["samples_per_frame"], 32)
        self.assertEqual(apu["mixbins"], 32)
        self.assertEqual(apu["max_mixbins_per_voice"], 8)
        self.assertEqual(set(apu["formats"]), {"u8", "s16", "s24", "s32", "adpcm"})

    def test_ac97_backend_does_not_overclaim_apu_coverage(self):
        ac97 = self.matrix["backends"]["ac97_dma"]
        self.assertEqual(
            ac97["supported_formats"],
            [{"sample_format": "s16", "channels": 2, "sample_rate_hz": 48000}],
        )
        self.assertEqual(
            set(ac97["legitimate_paths"]),
            {"ac97.descriptor", "ac97.irq", "ac97.underrun"},
        )
        for path in ac97["legitimate_paths"]:
            self.assertFalse(path.startswith(("apu.vp.", "apu.gp.", "apu.ep.")))

    def test_raw_backend_declares_required_format_channel_matrix(self):
        raw = self.matrix["backends"]["mcpx_apu_raw"]
        formats = {
            (entry["sample_format"], entry["channels"])
            for entry in raw["supported_formats"]
        }
        self.assertEqual(
            formats,
            {
                ("u8", 1), ("u8", 2),
                ("s16", 1), ("s16", 2),
                ("s24", 1), ("s24", 2),
                ("s32", 1), ("s32", 2),
                ("adpcm", 1), ("adpcm", 2),
            },
        )
        self.assertEqual(raw["discovery"], "guest-visible PCI BAR")
        self.assertTrue(raw["teardown_required"])
        self.assertFalse(raw["full_suite_registration_allowed"])
        self.assertFalse(
            self.matrix["backends"]["ac97_dma"]["full_suite_registration_allowed"]
        )
        self.assertIn(
            "no public deinit",
            self.matrix["backends"]["ac97_dma"]["registration_blocker"],
        )

    def test_stress_boundaries_are_not_reduced_to_powers_of_two(self):
        axes = self.matrix["axes"]
        voices = axes["voice_count_sweep"]
        for boundary in (31, 32, 33, 63, 64, 65, 127, 128, 129, 255, 256):
            self.assertIn(boundary, voices)
        self.assertEqual(axes["allocation_boundary_probe"], [255, 256, 257])
        self.assertEqual(
            axes["vp_buffer_samples"],
            [31, 32, 33, 63, 64, 65, 127, 128, 129],
        )
        self.assertEqual(axes["mixbin_fanout"], [1, 2, 4, 8])

    def test_source_rate_and_memory_axes_remain_broad(self):
        axes = self.matrix["axes"]
        self.assertEqual(
            axes["source_rates_hz"],
            [8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000],
        )
        self.assertEqual(
            axes["memory_layouts"],
            ["shared", "contiguous_unique", "scattered"],
        )
        self.assertIn("near_nyquist_045", axes["signals"])
        self.assertIn("near_nyquist_049", axes["signals"])

    def test_every_family_uses_a_known_backend_and_legitimate_paths(self):
        backends = self.matrix["backends"]
        family_ids = set()
        for family in self.matrix["families"]:
            self.assertNotIn(family["id"], family_ids)
            family_ids.add(family["id"])
            self.assertIn(family["backend"], backends)
            legitimate = set(backends[family["backend"]]["legitimate_paths"])
            self.assertTrue(set(family["required_paths"]).issubset(legitimate))
            for axis in family["stress_axes"]:
                self.assertIn(axis, self.matrix["axes"])

        self.assertTrue(set(self.matrix["fast_gate"]).issubset(family_ids))

    def test_planned_case_expansion_is_stable_and_valid(self):
        path = ROOT / "utils" / "audio_torture_cases.py"
        spec = importlib.util.spec_from_file_location("audio_torture_cases", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        cases = module.build_cases(self.matrix)
        module.validate(self.matrix, cases)
        self.assertEqual(len(cases), 138)
        self.assertEqual(len({case["id"] for case in cases}), 138)

        by_family = {}
        for case in cases:
            by_family[case["family"]] = by_family.get(case["family"], 0) + 1
        self.assertEqual(by_family["audio.vp_scaling"], 45)
        self.assertEqual(by_family["audio.format_rate"], 29)
        self.assertEqual(by_family["audio.hrtf_3d"], 4)
        self.assertEqual(by_family["audio.voice_modes"], 8)
        self.assertEqual(by_family["audio.voice_control"], 4)
        self.assertEqual(by_family["audio.everything_max"], 1)
        scaling = [case for case in cases if case["family"] == "audio.vp_scaling"]
        for channels in (1, 2):
            counts = {case["params"]["voice_count"] for case in scaling
                      if case["params"]["channels"] == channels}
            self.assertEqual(counts, set(self.matrix["axes"]["voice_count_sweep"]))
        allocation = [case for case in scaling if case["params"].get("expected_allocation_failure")]
        self.assertEqual(len(allocation), 1)
        self.assertEqual(allocation[0]["params"]["allocation_attempt_count"], 257)
        self.assertEqual(allocation[0]["params"]["voice_count"], 256)
        self.assertEqual(allocation[0]["required_paths"], ["apu.vp.voice", "apu.vp.mix"])

        gp_ep_paths = {
            case["params"]["pipeline_mode"]: set(case["required_paths"])
            for case in cases if case["family"] == "audio.gp_ep"
        }
        self.assertNotIn("apu.gp.frame", gp_ep_paths["vp_only"])
        self.assertNotIn("apu.ep.frame", gp_ep_paths["vp_only"])
        self.assertIn("apu.gp.frame", gp_ep_paths["vp_gp"])
        self.assertNotIn("apu.ep.frame", gp_ep_paths["vp_gp"])
        self.assertIn("apu.ep.frame", gp_ep_paths["vp_gp_ep_stereo"])

    def test_validator_rejects_cases_that_claim_executable_or_vp_coverage(self):
        path = ROOT / "utils" / "audio_torture_cases.py"
        spec = importlib.util.spec_from_file_location("audio_torture_cases", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(module)

        for field, value in (
            ("implementation_state", "implemented"),
            ("voice_count", 64),
            ("sample_rate_hz", 44100),
        ):
            with self.subTest(field=field):
                cases = copy.deepcopy(module.build_cases(self.matrix))
                target = cases[0]
                if field == "implementation_state":
                    target[field] = value
                else:
                    target["params"][field] = value
                with self.assertRaises(ValueError):
                    module.validate(self.matrix, cases)

    def test_validator_rejects_unsupported_raw_configurations_and_path_claims(self):
        path = ROOT / "utils" / "audio_torture_cases.py"
        spec = importlib.util.spec_from_file_location("audio_torture_cases", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(module)

        for changes in (
            {"sample_format": "s16", "channels": 3},
            {"mixbin_fanout": 9},
            {"allocation_attempt_count": 257},
        ):
            with self.subTest(changes=changes):
                cases = copy.deepcopy(module.build_cases(self.matrix))
                cases[11]["params"].update(changes)
                with self.assertRaises(ValueError):
                    module.validate(self.matrix, cases)

        cases = copy.deepcopy(module.build_cases(self.matrix))
        gp_only = next(case for case in cases if case["id"] == "audio.gp_ep.vp_only")
        gp_only["required_paths"].append("apu.gp.frame")
        with self.assertRaises(ValueError):
            module.validate(self.matrix, cases)

    def test_unhandled_voice_position_is_not_in_normal_gate(self):
        gap = self.matrix["known_gaps"]["get_voice_position"]
        self.assertEqual(gap["method"], "NV1BA0_PIO_GET_VOICE_POSITION")
        self.assertEqual(gap["implementation_state"], "xemu_unhandled_assert")
        self.assertFalse(gap["normal_gate_allowed"])
        self.assertNotIn("audio.voice_position", self.matrix["fast_gate"])

    def test_planned_framework_is_not_registered_as_fake_executable_coverage(self):
        states = {family["implementation_state"] for family in self.matrix["families"]}
        self.assertEqual(states, {"planned"})

        catalog = json.loads((ROOT / "resources" / "catalog.json").read_text(encoding="utf-8"))
        catalog_ids = {entry["id"] for entry in catalog["tests"]}
        self.assertEqual(
            {test_id for test_id in catalog_ids if test_id.startswith("audio.")},
            {"audio.vp_scaling.s16_mono.v001"},
        )

        main_source = (ROOT / "src" / "main.cpp").read_text(encoding="utf-8")
        self.assertNotIn("REG_TEST(AudioTortureTests)", main_source)


if __name__ == "__main__":
    unittest.main()
