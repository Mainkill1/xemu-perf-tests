import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/tests/test_suite.cpp").read_text()


def function_body(signature: str) -> str:
    start = SOURCE.index(signature)
    brace = SOURCE.index("{", start)
    depth = 0
    for index in range(brace, len(SOURCE)):
        if SOURCE[index] == "{":
            depth += 1
        elif SOURCE[index] == "}":
            depth -= 1
            if depth == 0:
                return SOURCE[brace : index + 1]
    raise AssertionError(f"unterminated function: {signature}")


class ProgressStateIsolationContract(unittest.TestCase):
    def test_progress_is_drawn_before_workload_setup(self):
        body = function_body("void TestSuite::Run(")
        progress = body.index("host_.ShowResultProgress")
        setup = body.index("SetupTest()")
        dispatch = body.index("it->second()")
        self.assertLess(progress, setup)
        self.assertLess(progress, dispatch)

    def test_profile_does_not_render_ui_after_workload_setup(self):
        body = function_body("TestHost::ProfileResults TestSuite::Profile(")
        self.assertNotIn("ShowResultProgress", body)


if __name__ == "__main__":
    unittest.main()
