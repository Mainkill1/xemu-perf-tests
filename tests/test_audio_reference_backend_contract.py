import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AudioReferenceBackendContractTests(unittest.TestCase):
    def test_nxdk_audio_dependency_is_pinned_and_examples_disabled(self):
        cmake = (ROOT / "src" / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("https://github.com/Ryzee119/nxdk-audio.git", cmake)
        self.assertIn("fc2deca2cc1e434805ac03ca7c2f500b3b028f36", cmake)
        self.assertIn("set(NXAUDIO_BUILD_EXAMPLES OFF", cmake)
        self.assertIn("nxaudio", cmake)

        notice = (ROOT / "third_party" / "nxdk-audio-NOTICE.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("SPDX-License-Identifier: MIT", notice)
        self.assertIn("2026 Ryzee119", notice)

    def test_reference_backend_is_not_overpromoted(self):
        matrix = json.loads(
            (ROOT / "resources" / "audio_torture_matrix.json").read_text(encoding="utf-8")
        )
        backend = matrix["backends"]["nxaudio_reference"]
        self.assertEqual(
            backend["implementation_state"],
            "static_reference_backend_implemented_unvalidated",
        )
        self.assertFalse(backend["full_suite_registration_allowed"])
        self.assertIn("static buffer", backend["implemented_workload_scope"])
        self.assertIn("streaming", backend["intentionally_rejected_for_now"])
        self.assertIn("HRTF", backend["intentionally_rejected_for_now"])
        self.assertIn("Release XISO compile", backend["registration_blocker"])

    def test_bootstrap_smoke_is_opt_in_and_not_cataloged(self):
        cmake = (ROOT / "src" / "CMakeLists.txt").read_text(encoding="utf-8")
        main = (ROOT / "src" / "main.cpp").read_text(encoding="utf-8")
        self.assertRegex(
            cmake,
            r"option\(\s*AUDIO_BOOTSTRAP_SMOKE[\s\S]*?OFF\s*\)",
        )
        self.assertIn("XEMU_PERF_TESTS_AUDIO_BOOTSTRAP_SMOKE=1", cmake)
        self.assertIn("#ifdef XEMU_PERF_TESTS_AUDIO_BOOTSTRAP_SMOKE", main)
        self.assertIn("RunAudioBootstrapSmoke", main)

        catalog = json.loads(
            (ROOT / "resources" / "catalog.json").read_text(encoding="utf-8")
        )
        self.assertFalse(
            any("audio" in test["id"] for test in catalog["tests"]),
            "development bootstrap must not become stable catalog coverage",
        )

    def test_bootstrap_uses_exact_s16_fixture_and_one_voice(self):
        source = (
            ROOT / "src" / "tests" / "audio_bootstrap_smoke.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn('FindAudioFixture("vp.s16.mono.48k.256")', source)
        self.assertIn("spec.format = SampleFormat::kS16", source)
        self.assertIn("spec.channels = 1", source)
        self.assertIn("spec.source_rate_hz = 48000", source)
        self.assertIn("spec.voice_count = 1", source)
        self.assertIn("backend.Shutdown()", source)

    def test_reference_backend_rejects_unvalidated_paths(self):
        source = (
            ROOT / "src" / "tests" / "audio_nxaudio_backend.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("kVoiceModeStream", source)
        self.assertIn("spec.enable_filter", source)
        self.assertIn("spec.mutate_voice_state", source)
        self.assertIn("spec.enable_hrtf", source)
        self.assertIn("spec.mixbin_fanout != 1", source)
        self.assertIn("nxAudioShutdown()", source)
        self.assertIn('extern "C"', source)


if __name__ == "__main__":
    unittest.main()
