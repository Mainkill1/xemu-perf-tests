import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_generator():
    spec = importlib.util.spec_from_file_location("test_catalog_generator", ROOT / "utils/test_catalog.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CatalogPlanContractTests(unittest.TestCase):
 def test_generated_catalog_is_current_and_well_formed(self):
    module = load_generator()
    rendered = module.render()
    for path, expected in rendered.items():
        assert path.read_text(encoding="utf-8") == expected

    catalog = json.loads((ROOT / "resources/catalog.json").read_text(encoding="utf-8"))
    tests = catalog["tests"]
    self.assertEqual(catalog["leaf_count"], 156)
    self.assertEqual(catalog["group_count"], 5)
    self.assertEqual(len(tests), 161)
    self.assertEqual(len({test["id"] for test in tests}), len(tests))
    self.assertEqual(len({test["legacy_ids"][0] for test in tests}), len(tests))
    self.assertTrue(all(re.fullmatch(r"[a-z0-9_.]+", test["id"]) for test in tests))
    self.assertTrue(all(test["description"] and test["tags"] for test in tests))

    failure_guide = (ROOT / "docs/generated/test-failure-guide.md").read_text(encoding="utf-8")
    self.assertIn("# Test failure guide", failure_guide)
    self.assertIn("Reading a failure", failure_guide)
    for test in tests:
        self.assertEqual(failure_guide.count(f"`{test['id']}`"), 1, test["id"])


 def test_groups_are_outcomes_with_explicit_children_and_no_implicit_timing(self):
    catalog = json.loads((ROOT / "resources/catalog.json").read_text(encoding="utf-8"))
    groups = [test for test in catalog["tests"] if test["kind"] == "group"]
    assert {test["aggregation"] for test in groups} == {"none"}
    assert sorted(len(test["child_ids"]) for test in groups) == [5, 5, 6, 11, 12]
    source = (ROOT / "src/test_host.cpp").read_text(encoding="utf-8")
    assert "no group timing" in source
    assert "FinishGroup" in source
    assert "child_result_count" in source


 def test_sample_resolved_plan_uses_catalog_id_and_explicit_leaf_count(self):
    catalog = json.loads((ROOT / "resources/catalog.json").read_text(encoding="utf-8"))
    plan = json.loads((ROOT / "resources/plans/smoke.json").read_text(encoding="utf-8"))["resolved_plan"]
    ids = [test["id"] for test in plan["tests"]]
    by_id = {test["id"]: test for test in catalog["tests"]}
    assert plan["catalog_id"] == catalog["catalog_id"]
    assert plan["selected_leaf_count"] == len(ids) == len(set(ids))
    assert all(by_id[id]["kind"] == "leaf" for id in ids)


 def test_runtime_keeps_legacy_filter_adapter_but_plan_is_authoritative(self):
    source = (ROOT / "src/runtime_config.cpp").read_text(encoding="utf-8")
    assert "resolved_plan and legacy test_suites filtering cannot be combined" in source
    assert "configured_test_suites_" in source
    assert "selected_test_ids_" in source
    assert "memory-pressure plans must include all five checkpoint leaf ids" in source


if __name__ == "__main__":
    unittest.main()
