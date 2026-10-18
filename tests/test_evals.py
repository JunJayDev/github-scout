"""The recall eval (evals/run.py) searches GitHub for real; here its bookkeeping runs against the fake API."""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from fake import FakeAPI, client, repo

from github_scout import discover
from github_scout.github import github_slug

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("eval_run", ROOT / "evals" / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


class EvalCaseFileTests(unittest.TestCase):
    def test_every_case_carries_a_fixed_vocabulary(self):
        cases = run.load()
        self.assertEqual(len({c["id"] for c in cases}), len(cases))
        for c in cases:
            self.assertTrue(set(c["vocabulary"]) <= set(run.VOCAB), c["id"])
            self.assertTrue(c["vocabulary"].get("entities") or c["vocabulary"].get("mechanisms"), c["id"])
            for slug in c["must_find"]:
                self.assertEqual(github_slug(slug), slug, c["id"])
        self.assertIn("user-w-ui/search-before-build", {s for c in cases for s in c["must_find"]})


class EvalRunTests(unittest.TestCase):
    def test_reports_where_each_repo_sits_and_shares_a_scan(self):
        alive = f" pushed:>{discover.window(discover.HIDE)}"
        api = FakeAPI()
        hit = api.add(repo("a/reddit-cli", 900, "Reddit CLI", pushed="2026-10-01T00:00:00Z"))
        small = api.add(repo("b/reddit-mini", 12, "Reddit CLI, tiny", pushed="2026-10-01T00:00:00Z"))
        api.search["reddit" + alive] = [hit, small]
        vocab = {"entities": ["reddit"], "mechanisms": ["logged-in browser"], "forms": ["cli"]}
        cases = [{"id": "one", "prompt": "Drive Reddit", "must_find": ["a/reddit-cli", "b/reddit-mini", "c/nowhere"],
                  "vocabulary": vocab},
                 {"id": "two", "prompt": "Same words", "must_find": ["a/reddit-cli"], "vocabulary": dict(vocab)}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evals.json"
            path.write_text(json.dumps({"evals": cases}), encoding="utf-8")
            out = io.StringIO()
            with unittest.mock.patch.object(run, "Client", lambda verbose=False: client(api)), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = run.main(["--cases", str(path), "--json", str(Path(tmp) / "r.json")])
            result = json.loads((Path(tmp) / "r.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 1)                                         # a miss fails the run
        text = out.getvalue()
        self.assertIn("one: 2 of 3 found · ", text)
        self.assertIn("  found  a/reddit-cli  row 1  [E]", text)
        self.assertIn("  found  b/reddit-mini  under 50 stars", text)
        self.assertIn("  MISSED c/nowhere  not returned by any search", text)
        self.assertIn("two: 1 of 1 found (scan shared with one)", text)
        self.assertIn("recall: 3 of 4 repos in 2 cases", text)
        self.assertEqual(len([c for c in api.calls if "search/repositories" in c and "q=reddit+pushed" in c]), 1)
        self.assertEqual((result["found"], result["of"], result["cases"][1]["shared"]), (3, 4, "one"))
        with self.assertRaises(SystemExit):
            run.main(["--case", "nope"])


if __name__ == "__main__":
    unittest.main()
