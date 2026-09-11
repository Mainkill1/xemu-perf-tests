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
