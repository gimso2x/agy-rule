import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import check_rules  # noqa: E402

CASES = {
    "valid model_decision": ('---\ntrigger: model_decision\ndescription: "Use when X."\n---\n# t\n', True),
    "valid manual no description": ("---\ntrigger: manual\n---\nbody\n", True),
    "valid single quoted": ("---\ntrigger: model_decision\ndescription: 'it''s fine'\n---\n", True),
    "valid glob quoted star": ('---\ntrigger: glob\nglobs: "*.ts, *.tsx"\n---\n', True),
    "valid always_on": ("---\ntrigger: always_on\n---\n", True),
    "no frontmatter": ("# title\n", False),
    "missing closing": ("---\ntrigger: manual\n# title\n", False),
    "camelCase trigger": ("---\ntrigger: alwaysOn\n---\n", False),
    "missing trigger": ('---\ndescription: "x"\n---\n', False),
    "empty description": ('---\ntrigger: model_decision\ndescription: ""\n---\n', False),
    "model_decision no description": ("---\ntrigger: model_decision\n---\n", False),
    "glob without globs": ("---\ntrigger: glob\n---\n", False),
    "glob empty globs": ('---\ntrigger: glob\nglobs: ""\n---\n', False),
    "unquoted star glob": ("---\ntrigger: glob\nglobs: *.ts\n---\n", False),
    "unbalanced quote": ('---\ntrigger: model_decision\ndescription: "oops\n---\n', False),
    "oversize": ("---\ntrigger: manual\n---\n" + "a" * 24001, False),
}


class CheckRules(unittest.TestCase):
    def test_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, (text, ok) in CASES.items():
                path = Path(tmp) / "r.md"
                path.write_text(text, encoding="utf-8")
                self.assertEqual(not check_rules.check(path), ok, name)

    def test_repo_rules_pass(self):
        rules = Path(__file__).resolve().parent.parent.parent / "rules"
        for path in sorted(rules.glob("*.md")):
            self.assertEqual(check_rules.check(path), [], str(path))


if __name__ == "__main__":
    unittest.main()
