import contextlib
import datetime as dt
import io
import json
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from fake import FakeAPI, client, repo, tarball

from reuse_first import cli, discover, examine, registry, yamlish
from reuse_first.github import github_slug
from reuse_first.store import Store, StoreError, card_filename

QUESTION = {
    "entities": ["reddit", "xiaohongshu|小红书|rednote", "twitter|x.com"],
    "mechanisms": ["logged-in browser", "chrome extension"],
    "forms": ["cli", "skill"],
    "problems": ["social media automation"],
}


def ago(months: float) -> str:
    return (dt.date.today() - dt.timedelta(days=int(months * 30.4))).isoformat() + "T00:00:00Z"


class YamlishTests(unittest.TestCase):
    def test_round_trip_keeps_values(self):
        data = {"id": "a/b", "summary": 'He said: "hi" # not a comment', "stars": 12, "date": "2026-10-15",
                "flag": True, "none": None, "tags": ["x", "y z", "小红书"], "empty": [],
                "uses": [{"project": "ops", "question": "q", "take": "use", "note": "a: b", "paths": ["s/*.ts"]}]}
        self.assertEqual(yamlish.parse(yamlish.dump(data)), data)

    def test_dates_and_numbers_like_strings_stay_strings(self):
        self.assertEqual(yamlish.parse(yamlish.dump({"d": "2026-10-15", "n": "123", "t": "true"})),
                         {"d": "2026-10-15", "n": "123", "t": "true"})

    def test_hand_written_variants(self):
        text = "a: plain text # comment\nb: 'it''s'\nc:\n  - one\n  - \"two\"\nd: [1, 'x, y']\n"
        self.assertEqual(yamlish.parse(text), {"a": "plain text", "b": "it's", "c": ["one", "two"], "d": [1, "x, y"]})

    def test_rejects_what_it_cannot_represent(self):
        for bad in ("a: |\n  x\n", "a:\n  b: 1\n", "a: {x: 1}\n", "a: 1\na: 2\n", "\tb: 1\n",
                    "u:\n  - k: v\n      deeper: 1\n"):
            with self.subTest(bad=bad), self.assertRaises(yamlish.FormatError):
                yamlish.parse(bad)


class SlugTests(unittest.TestCase):
    def test_slug_forms(self):
        for text, want in [("https://github.com/jackwener/opencli", "jackwener/opencli"),
                           ("git+https://github.com/a/b.git", "a/b"), ("github.com/a/b/tree/main/x", "a/b"),
                           ("git@github.com:a/b.git", "a/b"), ("a-b/c.d", "a-b/c.d"),
                           ("https://gitlab.com/a/b", None), ("https://github.com/topics/cli", None)]:
            self.assertEqual(github_slug(text), want, text)

    def test_slugs_in_text_dedupes_and_skips_non_repos(self):
        text = "see https://github.com/A/b and github.com/a/B#x, https://github.com/sponsors/me, github.com/c/d.git"
        self.assertEqual(discover.slugs_in_text(text), ["A/b", "c/d"])


class PlanAndRankTests(unittest.TestCase):
    def test_plan_crosses_vocabularies_and_asks_only_for_maintained_repos(self):
        q = discover.plan(QUESTION)
        queries = [(x["lens"], x["query"]) for x in q]
        alive = f" pushed:>{discover.window(discover.HIDE)}"
        self.assertIn(("E", "小红书" + alive), queries)
        self.assertIn(("P", "reddit xiaohongshu in:readme" + alive), queries)
        self.assertIn(("M", '"logged-in browser" in:readme' + alive), queries)
        self.assertIn(("K", "reddit filename:SKILL.md"), queries)
        self.assertIn(("S", "xiaohongshu"), queries)
        self.assertNotIn("D", {lens for lens, _ in queries})          # forms has no mcp
        self.assertTrue(all(alive in s for lens, s in queries if lens in "EPMCQTR"))
        self.assertEqual(len(set(queries)), len(queries))

    def test_rising_lens_needs_no_vocabulary(self):
        alive = f" pushed:>{discover.window(discover.HIDE)}"
        rise = f"created:>{discover.window(discover.RISE_MONTHS)} stars:>{discover.RISE_STARS}"
        queries = [x["query"] for x in discover.plan(QUESTION) if x["lens"] == "H"]
        self.assertIn(f"topic:agent-skill {rise}" + alive, queries)
        self.assertIn(f"created:>{discover.window(discover.BREAKOUT_MONTHS)} stars:>{discover.BREAKOUT_STARS}" + alive,
                      queries)                                          # forms include cli: any breakout counts
        only_skill = [x["query"] for x in discover.plan({**QUESTION, "forms": ["skill"]}) if x["lens"] == "H"]
        self.assertTrue(only_skill and all(q.startswith("topic:") for q in only_skill))

    def test_fit_counts_own_text_not_readme(self):
        c = {"repo": "jackwener/opencli", "desc": "Make Any Website into CLI & Use your logged-in browser", "topics": ["cli"]}
        self.assertEqual(discover.fit(c, QUESTION), 1)
        c2 = {"repo": "x/rednote-tool", "desc": "Post to Reddit and 小红书 via a Chrome extension", "topics": []}
        self.assertEqual(discover.fit(c2, QUESTION), 3)

    def test_new_and_moving_beats_old_and_famous(self):
        old = {"repo": "a/old-reddit-bot", "desc": "Reddit bot", "stars": 40000, "created": ago(70)[:10],
               "pushed": ago(2)[:10], "license": "MIT", "lenses": ["E"], "topics": []}
        new = {"repo": "b/reddit-cli", "desc": "Reddit CLI", "stars": 900, "created": ago(3)[:10],
               "pushed": ago(0.2)[:10], "license": "MIT", "lenses": ["E"], "topics": []}
        self.assertGreater(discover.score(new, QUESTION), discover.score(old, QUESTION))

    def test_maintenance_rule(self):
        base = {"repo": "a/reddit-tool", "desc": "Reddit tool", "stars": 5000, "created": ago(8)[:10],
                "license": "MIT", "lenses": ["E"], "topics": []}
        fresh = discover.score({**base, "pushed": ago(1)[:10]}, QUESTION)
        slow = discover.score({**base, "pushed": ago(4)[:10]}, QUESTION)
        self.assertGreater(fresh - slow, 2.5, "over 3 months idle must fall far behind")
        scan = {"candidates": [{**base, "repo": "a/fresh", "pushed": ago(1)[:10]},
                               {**base, "repo": "a/stale", "pushed": ago(8)[:10]}]}
        self.assertEqual([c["repo"] for c in discover.visible(scan)], ["a/fresh"])
        self.assertEqual([c["repo"] for c in discover.visible(scan, show_all=True)], ["a/fresh", "a/stale"])
        sc = discover.Scan(None, client(FakeAPI()), {"project": "p", "id": "q", **QUESTION})
        sc._add(repo("a/dead", pushed=ago(13)), "E")
        sc._add(repo("a/alive", pushed=ago(2)), "E")
        out = sc.finish("E")
        self.assertEqual([c["repo"] for c in out["candidates"]], ["a/alive"])
        self.assertEqual(out["dropped"], 1)

    def test_lists_are_set_apart(self):
        self.assertTrue(discover.is_list({"repo": "public/apis", "desc": "A collective list of free APIs"}))
        self.assertTrue(discover.is_list({"repo": "x/awesome-mcp", "desc": ""}))
        self.assertFalse(discover.is_list({"repo": "a/xhs-cli", "desc": "Xiaohongshu CLI"}))


class Base(unittest.TestCase):
    lang = "en"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "reg"
        self.store = Store.init(self.root, "test", self.lang)
        registry.new_project(self.store, "ops", "Ops", "test project", "/src/ops")
        registry.new_question(self.store, "ops/browser-ops", "Drive our logged-in sites from scripts", "working")
        doc = self.store.question("ops/browser-ops")
        doc.data.update(QUESTION)
        self.store.save_question(doc)
        self.api = FakeAPI()
        self.old_factory = cli.make_client
        cli.make_client = lambda args, store=None: client(self.api)
        self.env = {k: os.environ.pop(k) for k in ["REUSE_FIRST_STORE"] if k in os.environ}

    def tearDown(self):
        cli.make_client = self.old_factory
        os.environ.update(self.env)
        self.tmp.cleanup()

    def run_cli(self, *argv) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--store", str(self.root), *argv])
        return code, out.getvalue(), err.getvalue()


class StoreTests(Base):
    def test_init_and_check_clean(self):
        self.assertEqual(json.loads((self.root / "reuse-first.json").read_text())["format"], 2)
        self.assertEqual(self.store.check()[0], [])

    def test_question_template_carries_the_stage(self):
        body = self.store.question("ops/browser-ops").body
        self.assertIn("Stage: working (it works: borrow techniques", body)
        self.assertIn("### Ideas worth taking", body)

    def test_check_reports_bad_cards_and_questions(self):
        (self.root / "repos" / "a__b.md").write_text("---\nid: a/c\nkind: cli\nuses:\n  - project: ops\n    take: love\n---\n")
        doc = self.store.question("ops/browser-ops")
        doc.data["stage"] = "someday"
        self.store.save_question(doc)
        text = "\n".join(self.store.check()[0])
        for needle in ("file name must be a__c.md", "kind must be", "take must be", "missing commit", "stage must be"):
            self.assertIn(needle, text)

    def test_locate_by_marker_in_parent(self):
        from reuse_first.store import locate
        cwd = os.getcwd()
        try:
            os.chdir(self.root / "projects" / "ops")
            with unittest.mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "nocfg")}):
                self.assertEqual(locate(None), self.root.resolve())
        finally:
            os.chdir(cwd)
        with self.assertRaises(StoreError):
            locate(str(Path(self.tmp.name)))


class ChineseStoreTests(Base):
    lang = "zh"

    def test_chinese_templates(self):
        body = self.store.question("ops/browser-ops").body
        self.assertIn("阶段：working（已经能用：借技巧", body)
        self.assertIn("### 值得借的思路", body)


class FlowTests(Base):
    def seed(self):
        opencli = self.api.add(repo("jackwener/OpenCLI", 30000, "Make Any Website into CLI & Use your logged-in browser by AI agent.",
                                    created=ago(7), pushed=ago(0.1), topics=["cli", "browser-automation"], license="Apache-2.0"))
        noise = self.api.add(repo("public-apis/public-apis", 480000, "A collective list of free APIs", created=ago(110), pushed=ago(0.5)))
        xhs = self.api.add(repo("xpzouying/xiaohongshu-mcp", 16000, "MCP for xiaohongshu.com", created=ago(14), pushed=ago(0.5)))
        old = self.api.add(repo("someone/xiaohongshu-old", 9000, "xiaohongshu bot", created=ago(60), pushed=ago(9)))
        self.api.add(repo("someone/reddit-skill", 50, "Reddit skill for agents", created=ago(4), pushed=ago(1)))
        alive = f" pushed:>{discover.window(discover.HIDE)}"
        self.api.search['reddit xiaohongshu in:readme' + alive] = [opencli, noise]
        self.api.search['"logged-in browser"' + alive] = [opencli]
        self.api.search['xiaohongshu' + alive] = [xhs, old]
        self.api.code['reddit filename:SKILL.md'] = ["someone/reddit-skill"]
        self.api.npm['reddit'] = ["git+https://github.com/someone/reddit-skill.git"]
        self.api.skills['reddit'] = [("someone/reddit-skill", 4200)]

    def seed_repo_files(self, slug="jackwener/OpenCLI"):
        sha = "b9213a15d63d" + "0" * 28
        self.api.paths[f"repos/{slug}/commits/main"] = {"sha": sha}
        self.api.paths[f"repos/{slug}/git/trees/{sha}"] = {"tree": [
            {"path": "package.json", "type": "blob", "size": 400}, {"path": "src/daemon.ts", "type": "blob", "size": 9000},
            {"path": "skills/opencli/SKILL.md", "type": "blob", "size": 800},
            *[{"path": f"src/x{i}.ts", "type": "blob", "size": 100} for i in range(45)]], "truncated": False}
        self.api.paths[f"repos/{slug}/contents/package.json"] = json.dumps({"name": "@jackwener/opencli", "bin": {"opencli": "dist/cli.js"}})
        self.api.paths[f"repos/{slug}/readme"] = "<p align=center><img src=x></p>\n# OpenCLI\n\nTurn websites into commands.\n"
        self.api.paths[f"repos/{slug}/commits"] = [{"sha": "x"}] * 37
        self.api.paths[f"repos/{slug}/contributors"] = [{"contributions": 80}, {"contributions": 20}]

    def rows(self, out):
        return [ln for ln in out.splitlines() if ln.strip()[:3].strip().rstrip(".").isdigit()]

    def test_full_loop(self):
        self.seed()
        code, out, _ = self.run_cli("scan", "ops/browser-ops", "--quiet")
        self.assertEqual(code, 0, out)
        rows = self.rows(out)
        names = [r.split()[5] for r in rows]
        self.assertIn("jackwener/OpenCLI", names)
        self.assertNotIn("public-apis/public-apis", names)            # a list, shown apart
        self.assertIn("lists (scan --expand", out)
        self.assertNotIn("someone/xiaohongshu-old", names)            # idle 9 months: hidden by default
        self.assertIn("1 hidden (no push in 6 months", out)
        skill_row = next(r for r in rows if "someone/reddit-skill" in r)
        self.assertIn("[KSN]", skill_row)
        self.assertIn("installs 4.2k", skill_row)
        self.assertEqual(self.store.question("ops/browser-ops").data["scanned"], discover.today())

        n = names.index("jackwener/OpenCLI") + 1
        code, out, _ = self.run_cli("pick", "ops/browser-ops", str(n), "--rest", "not a browser driver")
        self.assertEqual(code, 0, out)
        self.assertIn("look --q ops/browser-ops jackwener/OpenCLI", out)
        verdicts = {(e["repo"], e["verdict"]) for e in self.store.ledger()}
        self.assertIn(("jackwener/OpenCLI", "short"), verdicts)
        self.assertIn(("xpzouying/xiaohongshu-mcp", "skip"), verdicts)
        self.assertNotIn(("someone/xiaohongshu-old", "skip"), verdicts)   # never shown, never judged
        _, out, _ = self.run_cli("scan", "ops/browser-ops", "--show")
        self.assertNotIn("xpzouying/xiaohongshu-mcp", out)
        self.assertIn("jackwener/OpenCLI", out)

        self.seed_repo_files()
        code, out, _ = self.run_cli("look", "--q", "ops/browser-ops", "jackwener/OpenCLI")
        self.assertEqual(code, 0, out)
        self.assertIn("(software: cli?)", out)
        self.assertIn("maintenance: active · 37 commits in 30 days", out)
        self.assertIn("top one 80% of commits", out)

        code, out, _ = self.run_cli("note", "jackwener/OpenCLI", "--q", "ops/browser-ops", "--take", "use",
                                    "--where", "tools/opencli", "--watch", "clis/reddit/**")
        self.assertEqual(code, 0, out)
        card = self.store.card("jackwener/opencli")
        self.assertEqual(card.path.name, card_filename("jackwener/OpenCLI"))
        self.assertEqual((card.data["kind"], card.data["form"]), ("software", "cli"))
        self.assertEqual(card.data["uses"], [{"project": "ops", "question": "browser-ops", "take": "use", "where": "tools/opencli"}])
        self.assertIn("## The idea", card.body)

        registry.new_project(self.store, "other", "Other", "")
        registry.new_question(self.store, "other/exit-codes", "How should our CLI report failures", "idea")
        code, out, _ = self.run_cli("note", "jackwener/OpenCLI", "--q", "other/exit-codes", "--take", "learn",
                                    "--note", "exit codes 66/69/75/77")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.store.card("jackwener/OpenCLI").data["uses"]), 2)

        code, out, _ = self.run_cli("note", "z/nothing", "--q", "ops/browser-ops", "--take", "skip", "--note", "a demo")
        self.assertIn("recorded skip", out)
        self.assertIsNone(self.store.card("z/nothing"))

        _, out, _ = self.run_cli("find", "logged-in", "browser")
        self.assertIn("jackwener/OpenCLI [software/cli] use", out)
        _, out, _ = self.run_cli("find", "free", "APIs")
        self.assertIn("public-apis/public-apis skip", out)
        code, out, _ = self.run_cli("check")
        self.assertEqual(code, 0, out)
        index = (self.root / "INDEX.md").read_text()
        self.assertIn("[ops/browser-ops]", index)
        self.assertIn("| [jackwener/OpenCLI](repos/jackwener__opencli.md) | use |", index)
        _, out, _ = self.run_cli("show", "ops/browser-ops")
        self.assertIn("stage: it works", out)
        self.assertIn("cards:", out)

    def test_add_and_expand(self):
        self.seed()
        code, out, _ = self.run_cli("scan", "ops/browser-ops", "--add", "found https://github.com/xpzouying/xiaohongshu-mcp on X",
                                    "--note", "x.com post")
        self.assertEqual(code, 0, out)
        self.assertIn("xpzouying/xiaohongshu-mcp", out)
        self.assertIn("[W]", out)
        self.api.add(repo("someone/awesome-social", 2000, "A curated list of social tools", pushed=ago(1)))
        self.api.add(repo("z/unrelated", 9000, "A database", pushed=ago(1)))
        self.api.paths["repos/someone/awesome-social/readme"] = (
            "- [OpenCLI](https://github.com/jackwener/OpenCLI)\n- [db](https://github.com/z/unrelated)\n")
        code, out, _ = self.run_cli("scan", "ops/browser-ops", "--expand", "someone/awesome-social")
        self.assertEqual(code, 0, out)
        self.assertIn("jackwener/OpenCLI", out)
        self.assertNotIn("z/unrelated", out)

    def test_rising_repos_are_listed_apart(self):
        self.seed()
        anatomy = self.api.add(repo("wheresryan22/anatomy", 11000, "Interactive isometric illustrations of machines, in SVG",
                                    created=ago(0.25), pushed=ago(0.05), topics=["agent-skill", "svg"]))
        slow = self.api.add(repo("a/calm-skill", 120, "A diff viewer", created=ago(1.5), pushed=ago(0.5), topics=["agent-skill"]))
        near = self.api.add(repo("b/reddit-digest", 300, "Daily Reddit digest", created=ago(1), pushed=ago(0.2),
                                 topics=["agent-skill"]))
        alive = f" pushed:>{discover.window(discover.HIDE)}"
        rise = f"created:>{discover.window(discover.RISE_MONTHS)} stars:>{discover.RISE_STARS}"
        self.api.search[f"topic:agent-skill {rise}" + alive] = [anatomy, slow, near]
        code, out, _ = self.run_cli("scan", "ops/browser-ops", "--quiet")
        self.assertEqual(code, 0, out)
        names = [r.split()[5] for r in self.rows(out)]
        self.assertIn("b/reddit-digest", names)                       # matches the vocabulary: ranked with the rest
        self.assertNotIn("wheresryan22/anatomy", names)
        self.assertIn("rising: new in the last 2 months", out)
        h1 = next(ln for ln in out.splitlines() if ln.strip().startswith("h1."))
        self.assertIn("wheresryan22/anatomy", h1)                     # fastest growing first
        self.assertIn("stars/month", h1)
        code, out, _ = self.run_cli("pick", "ops/browser-ops", "h1=explainer figures an agent can film", "--rest", "no")
        self.assertEqual(code, 0, out)
        verdicts = {(e["repo"], e["verdict"]) for e in self.store.ledger()}
        self.assertIn(("wheresryan22/anatomy", "short"), verdicts)
        self.assertIn(("a/calm-skill", "skip"), verdicts)             # shown in the rising list, so judged
        code, out, _ = self.run_cli("pick", "ops/browser-ops", "h9")
        self.assertNotEqual(code, 0)

    def test_resurface_when_a_skipped_repo_grows(self):
        self.seed()
        self.run_cli("scan", "ops/browser-ops", "--quiet")
        self.run_cli("pick", "ops/browser-ops", "--skip", "xpzouying/xiaohongshu-mcp=x")
        led = self.store.ledger()
        led[-1]["stars"] = 1000
        (self.root / "ledger.jsonl").write_text("".join(json.dumps(e) + "\n" for e in led))
        _, out, _ = self.run_cli("scan", "ops/browser-ops", "--show")
        self.assertIn("grew, look again", out)

    def test_updates_diff_done(self):
        slug = "jackwener/OpenCLI"
        self.api.add(repo(slug, 31000, "x", pushed=ago(5)))
        meta = {"repo": slug, "desc": "x", "stars": 30000, "license": "Apache-2.0", "branch": "main", "commit": "aaaaaaaaaaaa"}
        registry.new_card(self.store, meta, "software", "cli", [{"project": "ops", "question": "browser-ops", "take": "use"}],
                          ["clis/reddit/**"], "read")
        self.api.paths[f"repos/{slug}/compare/aaaaaaaaaaaa...main"] = {
            "ahead_by": 3, "commits": [{"sha": "c" * 40, "commit": {"message": "fix reddit"}}],
            "files": [{"filename": "clis/reddit/read.js", "status": "modified", "additions": 2, "deletions": 1,
                       "patch": "@@ -1 +1 @@\n-old\n+new"}, {"filename": "README.md", "status": "modified", "patch": "x"}]}
        self.api.paths[f"repos/{slug}/releases"] = [{"tag_name": "v2", "published_at": "2999-01-01T00:00:00Z"}]
        code, out, _ = self.run_cli("updates")
        self.assertEqual(code, 0, out)
        self.assertIn("review", out)
        self.assertIn("watched: clis/reddit/read.js", out)
        self.assertIn("unmaintained: no push in 5 months", out)
        _, out, _ = self.run_cli("updates", "--diff", slug)
        self.assertIn("+new", out)
        self.assertNotIn("README.md (", out)
        self.api.paths[f"repos/{slug}/commits/main"] = {"sha": "c" * 40}
        self.run_cli("updates", "--done", slug)
        self.assertEqual(self.store.card(slug).data["commit"], "c" * 12)

    def test_look_source_extracts_safely(self):
        slug = "a/b"
        self.api.add(repo(slug, pushed=ago(1)))
        sha = "d" * 40
        self.api.paths[f"repos/{slug}/commits/main"] = {"sha": sha}
        self.api.paths[f"repos/{slug}/git/trees/{sha}"] = {"tree": [{"path": "src/main.py", "type": "blob", "size": 900}]}
        self.api.paths[f"repos/{slug}/tarball/{sha}"] = tarball({"README.md": "# b", "src/main.py": "print(1)\n" * 100,
                                                                 "../evil.txt": "x"})
        code, out, _ = self.run_cli("look", slug, "--source")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.root / "cache" / "a__b@ddddddd" / "src/main.py").is_file())
        self.assertFalse((self.root / "cache" / "evil.txt").exists())
        self.assertIn("entry points: README.md, src/main.py", out)


class DogfoodFixTests(Base):
    """Fixes from the first two real runs (agent video, human-sounding writing)."""

    def test_every_synonym_is_searched(self):
        q = {"entities": ["xiaohongshu|小红书|rednote"], "mechanisms": ["去AI味|humanizer"], "forms": ["skill"]}
        queries = [x["query"] for x in discover.plan(q)]
        for term in ("小红书", "rednote", "去AI味", "humanizer"):
            self.assertTrue(any(term in s for s in queries if not s.startswith(("topic:",))), term)
        self.assertIn("humanizer filename:SKILL.md", queries)

    def test_fit_tolerates_word_forms_and_order(self):
        q = {"problems": ["agent video editing"], "mechanisms": ["programmatic video"]}
        self.assertEqual(discover.fit({"repo": "a/b", "desc": "Edit videos with coding agents", "topics": []}, q), 1)
        self.assertEqual(discover.fit({"repo": "a/b", "desc": "Programmatic videos in React", "topics": []}, q), 1)
        self.assertEqual(discover.fit({"repo": "a/b", "desc": "Agent for coding", "topics": []}, q), 0)

    def test_relevant_beats_popular_and_added_beats_found(self):
        popular = {"repo": "a/claude-stuff", "desc": "Everything for Claude Code and reddit", "stars": 200000,
                   "created": ago(5)[:10], "pushed": ago(0.1)[:10], "license": "MIT", "lenses": ["E", "M", "R"], "topics": []}
        relevant = {"repo": "b/xhs-reddit-cli", "desc": "Xiaohongshu and Reddit CLI with your logged-in browser",
                    "stars": 300, "created": ago(5)[:10], "pushed": ago(0.5)[:10], "license": "MIT", "lenses": ["P"], "topics": []}
        self.assertGreater(discover.score(relevant, QUESTION), discover.score(popular, QUESTION))
        added = {**relevant, "repo": "c/x", "desc": "Reddit tool", "lenses": ["W"]}
        found = {**relevant, "repo": "d/x", "desc": "Reddit tool", "lenses": ["E"]}
        self.assertGreater(discover.score(added, QUESTION), discover.score(found, QUESTION))

    def test_license_hint_catches_non_commercial(self):
        self.assertEqual(examine.license_hint("# PolyForm Noncommercial License 1.0.0\n..."), ("PolyForm-Noncommercial", True))
        self.assertEqual(examine.license_hint("MIT License\n\nCopyright"), ("MIT", False))
        self.assertIsNone(examine.license_hint("All rights reserved."))

    def test_note_idea_and_ask_update(self):
        slug = "a/b"
        self.api.add(repo(slug, pushed=ago(1)))
        sha = "e" * 40
        self.api.paths[f"repos/{slug}/commits/main"] = {"sha": sha}
        self.api.paths[f"repos/{slug}/git/trees/{sha}"] = {"tree": [{"path": "LICENSE", "type": "blob", "size": 10}]}
        self.api.paths[f"repos/{slug}/contents/LICENSE"] = "PolyForm Noncommercial License 1.0.0"
        self.api.repos[slug]["license"] = None
        code, out, _ = self.run_cli("note", slug, "--q", "ops/browser-ops", "--take", "learn",
                                    "--idea", "Judge pairs, not scores.", "--note", "judge design")
        self.assertEqual(code, 0, out)
        self.assertIn("LICENSE WARNING: PolyForm-Noncommercial", out)
        card = self.store.card(slug)
        self.assertEqual(card.data["license"], "PolyForm-Noncommercial")
        self.assertIn("## The idea\nJudge pairs, not scores.", card.body)
        code, out, _ = self.run_cli("ask", "ops/browser-ops", "A sharper question", "--stage", "prototype", "--update")
        self.assertEqual(code, 0, out)
        q = self.store.question("ops/browser-ops").data
        self.assertEqual((q["ask"], q["stage"]), ("A sharper question", "prototype"))


class ExamineTests(unittest.TestCase):
    def test_guess_form_and_kind(self):
        g = examine.guess_kind
        self.assertEqual(g(["skills/x/SKILL.md", "README.md"], {}, "x", "")[0], "skill")
        self.assertEqual(g(["a/SKILL.md", "b/SKILL.md"], {}, "x", "")[0], "skill-pack")
        big = ["SKILL.md"] + [f"examples/e{i}.tsx" for i in range(200)]
        self.assertEqual(g(big, {}, "x", "", "AI video skill for Claude Code")[0], "skill")
        self.assertEqual(g(["src/index.ts"], {"package.json": '{"dependencies":{"@modelcontextprotocol/sdk":"1"}}'}, "x", "")[0], "mcp")
        self.assertEqual(g(["manifest.json"], {"manifest.json": '{"manifest_version":3}'}, "x", "")[0], "extension")
        self.assertEqual(g(["README.md"], {}, "awesome-things", "")[0], "list")
        self.assertEqual(g(["pyproject.toml", "pkg/a.py"], {"pyproject.toml": "[project.scripts]\nx='a:b'"}, "x", "")[0], "cli")
        self.assertEqual([examine.kind_of(f) for f in ("skill-pack", "mcp", "list", "example")],
                         ["skill", "software", "list", "other"])

    def test_watched_globs(self):
        files = ["clis/reddit/read.js", "src/daemon.ts", "docs/a.md", "skills/x/SKILL.md"]
        self.assertEqual(examine.watched(files, ["clis/reddit/**", "src/daemon.ts", "skills/"]),
                         ["clis/reddit/read.js", "src/daemon.ts", "skills/x/SKILL.md"])

    def test_clean_readme_drops_badges_and_html(self):
        out = examine.clean_readme('<p align="center"><img src="x"></p>\n# T\n[![b](u)](v)\n\n\n\nBody\n```\n<keep>\n```\n', 1000)
        self.assertNotIn("img", out)
        self.assertIn("<keep>", out)


if __name__ == "__main__":
    unittest.main()
