"""Static contract checks for the PR71 native qualification runner."""

from __future__ import annotations

import ast
import math
import pathlib
import py_compile


ROOT = pathlib.Path(__file__).parents[1]
RUNNER = (
    ROOT
    / "docs/evidence/pr71-native-qualification-20260911/tooling/run-suite-pr71.py"
)
CAMPAIGN = ROOT / "docs/evidence/pr71-native-qualification-20260911/campaign-r1"
REVISED_CAMPAIGN = ROOT / "docs/evidence/pr71-native-qualification-20260911/campaign-r2"


def test_pr71_revised_campaign_keeps_controls_and_pins_repaired_head():
    """The rerun must preserve r1 while identifying the new product binary."""

    original = (CAMPAIGN / "campaign-config.ps1").read_text(encoding="utf-8")
    revised = (REVISED_CAMPAIGN / "campaign-config.ps1").read_text(
        encoding="utf-8"
    )
    for value in (
        "9f618d6d8c4c446ef023955f3d4de22f661f61a4",
        "5edff26383c6440da35bc92b9fca35f4a404b03b",
        "a8f07817b9f1b22ef93ea54497ddfc9f06d34147d734e4ed26a8bcb69c7e8687",
    ):
        assert value in original and value in revised
    assert "pr71-native-qualification-20260911-r1" in original
    assert "pr71-native-qualification-20260911-r2" in revised
    for value in (
        "d21072b39fd3a84b06943977f5f441116f229b2e",
        "5280daf18730ffd57441bcc80ddbea3d33e84ee9",
        "e161c4cfe6b7b6af9d91fc7f28afde52efa43e6d899db24f1b0d2a2324e0d2c5",
        "pr71-282909-release-r1\\xemu.exe",
    ):
        assert value in revised
    assert "e6048469f7f461ea8f0c91a4efe98f8331c9b8ce" in original
    assert "e6048469f7f461ea8f0c91a4efe98f8331c9b8ce" not in revised


def test_pr71_runner_is_syntax_valid_and_declares_qualification_contract():
    """The deployable runner must expose every required PR71 control."""

    assert RUNNER.is_file()
    py_compile.compile(str(RUNNER), doraise=True)
    source = RUNNER.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(RUNNER))

    required_literals = (
        "9f618d6d8c4c446ef023955f3d4de22f661f61a4",
        "5edff26383c6440da35bc92b9fca35f4a404b03b",
        "vk_hybrid_ubershaders",
        "cache_shaders",
        "full-xiso",
        "pgr2_snapshot",
        "pgr2_full_start",
        "morrowind_snapshot",
        "Improvement %",
        "+good",
        "+bad",
        "vulkan_validation",
        "cleanup",
        "run_order",
    )
    for literal in required_literals:
        assert literal in source, literal

    option_strings = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "--hybrid-ubershaders" in option_strings
    assert "--shader-cache" in option_strings
    assert "--comparison-baseline-commit" in option_strings
    assert "--comparison-previous-main-commit" in option_strings

    matrix_namespace: dict[str, object] = {}
    exec(
        compile(
            ast.Module(
                body=[
                    node
                    for node in tree.body
                    if isinstance(node, ast.Assign)
                    and any(
                        isinstance(target, ast.Name)
                        and target.id == "PR71_CAMPAIGN_MATRIX"
                        for target in node.targets
                    )
                ],
                type_ignores=[],
            ),
            str(RUNNER),
            "exec",
        ),
        matrix_namespace,
    )
    campaign_matrix = matrix_namespace["PR71_CAMPAIGN_MATRIX"]
    for workload in campaign_matrix.values():
        assert workload["candidate_hybrid_values"]["opengl"] == ("off",)
        assert workload["candidate_hybrid_values"]["vulkan"] == (
            "off",
            "on",
        )


def test_pr71_improvement_formula_preserves_positive_good_semantics():
    """The runner's shared formula must agree with the published convention."""

    source = RUNNER.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(RUNNER))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "improvement_percent"
    )
    namespace: dict[str, object] = {}
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), str(RUNNER), "exec"),
        namespace,
    )
    calculate = namespace["improvement_percent"]
    assert math.isclose(calculate(110.0, 100.0, "+good"), 10.0)
    assert math.isclose(calculate(90.0, 100.0, "+bad"), 10.0)
    assert calculate(0.0, 0.0, "+good") is None


def test_pr71_campaign_package_contract_is_complete_without_running_cells():
    """The Windows package is statically checked; benchmark execution is deployment-only."""

    required = {
        "campaign-config.ps1",
        "campaign-common.ps1",
        "run-all-session1.ps1",
        "run-full-xiso-session1.ps1",
        "run-retail-session1.ps1",
        "capture-pgr2-native-pr71.ps1",
        "run-morrowind-qualification-cell-exact-isolated.ps1",
        "morrowind-control-exact-isolated.ps1",
        "write-results.ps1",
    }
    assert required <= {path.name for path in CAMPAIGN.iterdir()}
    config = (CAMPAIGN / "campaign-config.ps1").read_text(encoding="utf-8")
    for identity in (
        "e6048469f7f461ea8f0c91a4efe98f8331c9b8ce",
        "9f618d6d8c4c446ef023955f3d4de22f661f61a4",
        "5edff26383c6440da35bc92b9fca35f4a404b03b",
        "e298704f3704887127965a4d03ac087f0df06b0f",
        "4df007150dcd5f25436a701c47bba76afb5c43d5a3613de9bd49980f909698dc",
        "a08c4d92916554f55f09231f525cda1f93b55129",
        "11981a736703553349357cd89926b443901cadb9",
        "91ca72bddb6ec21441ffbbf3ef5bdddeda84ab3b7768d1f29081dca07136c4b3",
        "0bb7618aec5ea73355a03bcb176a922ea8b3ec2e",
        "d0dfbf18f5fccafd3fc06b2401bbe1c17affdda4",
        "a8f07817b9f1b22ef93ea54497ddfc9f06d34147d734e4ed26a8bcb69c7e8687",
    ):
        assert identity in config
    assert "pr71-e604846-release-r1\\xemu.exe" in config
    assert "pr76-cross-gpu-a08c4d9291-r2\\xemu.exe" in config
    for path in CAMPAIGN.glob("*.ps1"):
        text = path.read_text(encoding="utf-8")
        assert "run-suite-pr70" not in text
    retail = (CAMPAIGN / "run-retail-session1.ps1").read_text(encoding="utf-8")
    xiso = (CAMPAIGN / "run-full-xiso-session1.ps1").read_text(encoding="utf-8")
    assert "HybridUbershaders" in retail and "'On'" in retail and "'Off'" in retail
    assert "vk_hybrid_ubershaders" in (CAMPAIGN / "capture-pgr2-native-pr71.ps1").read_text(encoding="utf-8")
    assert "ShaderCache" in retail and "cache_shaders" in (CAMPAIGN / "campaign-common.ps1").read_text(encoding="utf-8")
    assert "candidate-vulkan-on-cold" in retail and "candidate-vulkan-on-warm" in retail
    assert "guest-source-commit" in xiso and "guest-source-tree" in xiso
    assert "'--allow-dirty-build'" in xiso
    assert "$Build.Role -eq 'previous_main'" in xiso
    assert "Get-PortableBuild" in xiso
    assert "$matrixIndex = @($receipt.cells).Count" in xiso
    assert "baseline-candidate" in retail and "candidate-baseline" in retail
    assert "Get-HostAdmission" in (CAMPAIGN / "run-all-session1.ps1").read_text(encoding="utf-8")
    controller = (CAMPAIGN / "run-all-session1.ps1").read_text(encoding="utf-8")
    assert "resume_started_utc" in controller
    assert "completedPhases" in controller
    assert "host_admission" in controller
    writer = (CAMPAIGN / "write-results.ps1").read_text(encoding="utf-8")
    assert "tables_only = $true" in writer
    assert "$phase -eq 'cold'" in writer
    assert "$warmProof.Count -ge 6" in writer


def test_pr71_telemetry_diagnostic_isolated_and_sanitized():
    wrapper = CAMPAIGN / "run-pgr2-vk-telemetry-diagnostic.ps1"
    analyzer = CAMPAIGN / "compare-pgr2-vk-telemetry.py"
    dispatch = CAMPAIGN / "dispatch-pgr2-vk-telemetry-diagnostic.ps1"
    assert wrapper.is_file() and analyzer.is_file() and dispatch.is_file()
    wrapper_text = wrapper.read_text(encoding="utf-8")
    analyzer_text = analyzer.read_text(encoding="utf-8")
    dispatch_text = dispatch.read_text(encoding="utf-8")
    for literal in (
        "XEMU_VK_PERF_LOG",
        "VkTelemetry Enabled",
        "HybridUbershaders $hybrid",
        "Pgr2SnapshotSeed",
        "pipeline_prepare",
        "Invoke-CampaignCleanup",
        "outside the active qualification ResultsRoot",
        "campaign-manifest.json",
        "defer this diagnostic",
        "raw_paths",
        "BuildOverrideRoot",
        "SOURCE_STATE",
        "diagnostic",
        "release-qualified",
    ):
        assert literal in wrapper_text, literal
    for literal in ("BuildOverrideRoot", "run-pgr2-vk-telemetry-diagnostic.ps1", "GuiTestConsole"):
        assert literal in dispatch_text, literal
    for literal in (
        "pipeline_prepare_cpu_us_per_guest_frame",
        "flip_stall_wait_us_per_guest_frame",
        "on_minus_off",
        "summary_file",
    ):
        assert literal in analyzer_text, literal
    py_compile.compile(str(analyzer), doraise=True)
