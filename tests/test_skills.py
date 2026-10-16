"""The skills themselves: format, names, and the generated cloud file."""

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted((ROOT / "skills").glob("*/SKILL.md"))


class SkillFormatTests(unittest.TestCase):
    def test_every_skill_has_name_description_and_licence(self):
        self.assertEqual([p.parent.name for p in SKILLS], ["github-scout", "github-scout-brief", "github-scout-dig",
                                                          "github-scout-plan", "github-scout-search", "github-scout-triage"])
        for path in SKILLS:
            text = path.read_text(encoding="utf-8")
            m = re.match(r"---\n(.*?)\n---\n", text, re.S)
            self.assertIsNotNone(m, path)
            fields = dict(re.findall(r"^(\w[\w-]*): (.*)$", m.group(1), re.M))
            self.assertEqual(fields.get("name"), path.parent.name, path)
            self.assertTrue(20 <= len(fields.get("description", "")) <= 160, path)   # short: called on purpose
            self.assertEqual(fields.get("license"), "MIT", path)
            self.assertLess(text.count("\n"), 500, path)

    def test_stage_skills_work_with_and_without_the_command_line(self):
        for path in SKILLS:
            if path.parent.name == "github-scout":
                continue
            text = path.read_text(encoding="utf-8")
            self.assertIn("## With the command line", text, path)
            self.assertIn("## Without the command line", text, path)

    def test_cloud_file_is_up_to_date(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "build-cloud.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_evals_name_real_repositories(self):
        import json
        data = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
        for case in data["evals"]:
            self.assertTrue(case["prompt"] and case["must_find"], case["id"])
            for slug in case["must_find"]:
                self.assertRegex(slug, r"^[\w.-]+/[\w.-]+$")
