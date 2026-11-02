import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AudioMcpxProbeContractTests(unittest.TestCase):
    def test_probe_matches_pinned_xemu_pci_identity_and_bar_size(self):
        header = (ROOT / "src" / "tests" / "audio_mcpx_apu_device.h").read_text(encoding="utf-8")
        source = (ROOT / "src" / "tests" / "audio_mcpx_apu_device.cpp").read_text(encoding="utf-8")
        matrix = json.loads((ROOT / "resources" / "audio_torture_matrix.json").read_text(encoding="utf-8"))
        apu = matrix["ground_truth"]["mcpx_apu"]

        self.assertIn("kVendorId = 0x10DE", header)
        self.assertIn("kDeviceId = 0x01B0", header)
        self.assertIn("kMmioBytes = 0x80000", header)
        self.assertEqual(apu["pci_vendor_id"], "0x10de")
        self.assertEqual(apu["pci_device_id"], "0x01b0")
        self.assertEqual(apu["bar0_mmio_bytes"], 0x80000)
        self.assertIn("MmMapIoSpace", source)
        self.assertIn("PAGE_NOCACHE", source)

    def test_probe_scans_pci_instead_of_hardcoding_apu_slot(self):
        source = (ROOT / "src" / "tests" / "audio_mcpx_apu_device.cpp").read_text(encoding="utf-8")
        self.assertIn("device < 32", source)
        self.assertIn("function < 8", source)
        self.assertIn("(device & 0x1FU) | ((function & 0x07U) << 5U)", source)
        self.assertNotRegex(source, r"slot\s*=\s*(?:0x)?a0\b")

    def test_probe_is_read_only(self):
        header = (ROOT / "src" / "tests" / "audio_mcpx_apu_device.h").read_text(encoding="utf-8")
        source = (ROOT / "src" / "tests" / "audio_mcpx_apu_device.cpp").read_text(encoding="utf-8")
        self.assertNotIn("Write32", header)
        self.assertNotIn("Write32", source)
        calls = re.findall(r"HalReadWritePCISpace\((.*?)\);", source, flags=re.S)
        self.assertGreaterEqual(len(calls), 3)
        self.assertTrue(all(re.search(r"FALSE\s*$", call.strip()) for call in calls))

    def test_snapshot_only_reads_known_registers(self):
        source = (ROOT / "src" / "tests" / "audio_mcpx_apu_device.cpp").read_text(encoding="utf-8")
        for token in (
            "kNvPapuFectl = 0x00001100",
            "kNvPapuSectl = 0x00002000",
            "kNvPapuXgscnt = 0x0000200C",
            "kNvPapuVpvaddr = 0x0000202C",
            "kNvPapuVpsgeaddr = 0x00002030",
            "kNvPapuVpssladdr = 0x00002034",
            "kNvPapuGpsaddr = 0x00002040",
            "kNvPapuEpsaddr = 0x00002048",
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
