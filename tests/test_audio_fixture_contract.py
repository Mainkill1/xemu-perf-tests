import hashlib
import importlib.util
import json
import sys
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIO_ROOT = ROOT / "resources" / "audio"


def load_generator():
    path = ROOT / "utils" / "generate_audio_fixtures.py"
    spec = importlib.util.spec_from_file_location("generate_audio_fixtures", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AudioFixtureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()
        cls.manifest = json.loads((AUDIO_ROOT / "manifest.json").read_text(encoding="utf-8"))
        cls.by_id = {item["id"]: item for item in cls.manifest["fixtures"]}

    def test_assets_are_fully_generated_and_public_domain(self):
        self.assertEqual(self.manifest["license"], "Unlicense (repository LICENSE)")
        self.assertIn("no third-party recordings", self.manifest["source"])
        expected, manifest_text, catalog_text = self.generator.generated_outputs()
        self.assertEqual(len(expected), 10)
        for relative_path, payload in expected.items():
            self.assertEqual((AUDIO_ROOT / relative_path).read_bytes(), payload)
        self.assertEqual((AUDIO_ROOT / "manifest.json").read_text(encoding="utf-8"), manifest_text)
        self.assertEqual(
            (ROOT / "src" / "generated" / "audio_fixture_catalog.inc").read_text(encoding="utf-8"),
            catalog_text,
        )

    def test_manifest_hashes_and_sizes_match_checked_in_bytes(self):
        ids = set()
        for fixture in self.manifest["fixtures"]:
            self.assertNotIn(fixture["id"], ids)
            ids.add(fixture["id"])
            payload = (AUDIO_ROOT / fixture["path"]).read_bytes()
            self.assertEqual(len(payload), fixture["bytes"], fixture["id"])
            self.assertEqual(hashlib.sha256(payload).hexdigest(), fixture["sha256"], fixture["id"])
            self.assertEqual(
                f"{self.generator.fnv1a64(payload):016x}",
                fixture["fnv1a64"],
                fixture["id"],
            )
        self.assertEqual(len(ids), 10)

    def test_audible_wavs_have_expected_pcm_contracts(self):
        expected = {
            "wav.multitone.s16.stereo.48k": (2, 48000, 1024),
            "wav.impulse.s16.mono.44k1": (1, 44100, 512),
            "wav.lfsr.s16.stereo.48k": (2, 48000, 512),
        }
        for fixture_id, (channels, rate, frames) in expected.items():
            fixture = self.by_id[fixture_id]
            with wave.open(str(AUDIO_ROOT / fixture["path"]), "rb") as value:
                self.assertEqual(value.getnchannels(), channels)
                self.assertEqual(value.getframerate(), rate)
                self.assertEqual(value.getnframes(), frames)
                self.assertEqual(value.getsampwidth(), 2)
                self.assertEqual(value.getcomptype(), "NONE")

    def test_raw_vp_formats_cover_every_decode_width(self):
        encodings = {fixture["encoding"] for fixture in self.manifest["fixtures"]}
        self.assertTrue(
            {"vp_pcm_s16", "vp_pcm_s24_b32", "vp_pcm_s32", "vp_ima_adpcm"}
            <= encodings
        )
        support = (
            ROOT / "src" / "tests" / "audio_torture_support.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("ConvertS16ToU8", support)

    def test_adpcm_blocks_have_independent_decode_goldens(self):
        mono = self.by_id["vp.adpcm.mono.block"]
        mono_golden = self.by_id["vp.adpcm.mono.expected_s16"]
        stereo = self.by_id["vp.adpcm.stereo.block"]
        stereo_golden = self.by_id["vp.adpcm.stereo.expected_s16"]
        self.assertEqual(mono["bytes"], 36)
        self.assertEqual(stereo["bytes"], 72)
        self.assertEqual(mono["frames"], mono_golden["frames"], 65)
        self.assertEqual(stereo["frames"], stereo_golden["frames"], 65)
        self.assertEqual(mono_golden["bytes"], 65 * 2)
        self.assertEqual(stereo_golden["bytes"], 65 * 2 * 2)
        self.assertIn("ADPCM_SAMPLES_PER_BLOCK=64", self.manifest["notes"]["adpcm"])

    def test_midi_is_intentionally_out_of_scope(self):
        self.assertIn("not included", self.manifest["notes"]["midi"].lower())
        self.assertFalse(any(path.suffix.lower() in {".mid", ".midi"} for path in AUDIO_ROOT.rglob("*")))


if __name__ == "__main__":
    unittest.main()
