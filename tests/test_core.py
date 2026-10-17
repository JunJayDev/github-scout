import contextlib
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from fake import FakeAPI, client, repo, tarball

from github_scout import cli, discover, examine, registry, yamlish
from github_scout.github import github_slug
from github_scout.store import PROJECT_ORDER, Store, StoreError, card_filename, today, write_doc

QUESTION = {
    "entities": ["reddit", "xiaohongshu|小红书|rednote", "twitter|x.com"],
    "mechanisms": ["logged-in browser", "chrome extension"],
    "forms": ["cli", "skill"],
    "problems": ["social media automation"],
}


def ago(months: float) -> str:
    return (dt.date.today() - dt.timedelta(days=int(months * 30.4))).isoformat() + "T00:00:00Z"


@contextlib.contextmanager
def cwd(path: Path):
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


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

    def test_lures_and_farmed_installs_are_excluded(self):
        lures = [("imthegamer404-bot/KCD2-Forge-Mod-Suite", "Kingdom Come Deliverance 2 Trainer 2026 Companion Tool for Enhanced Gameplay"),
                 ("fiyinjj123-lang/Paralives-Mod-Forge", "Paralives Studio Suite 2026: Ultimate Mod Hub for Infinite Money and Building"),
                 ("c/Skewb-Mastery-Lab", "Skewb Skills Advanced Trainer 2026: Learn Layers, Algs and Speedcubing Fast")]
        for repo_, desc in lures:
            self.assertTrue(discover.is_lure({"repo": repo_, "desc": desc}), repo_)
        for repo_, desc in [("bmaltais/kohya_ss", "LoRA trainer for Stable Diffusion"), ("a/mod-tools", "Minecraft mod tools"),
                            ("b/hack-week", "Projects from our 2026 hack week")]:
            self.assertFalse(discover.is_lure({"repo": repo_, "desc": desc}), repo_)
        self.assertTrue(discover.is_farmed({"repo": "magentosh/superpowers", "stars": 2, "installs": 2773960}))
        self.assertFalse(discover.is_farmed({"repo": "obra/superpowers", "stars": 300000, "installs": 3501140}))
        self.assertFalse(discover.is_farmed({"repo": "larksuite/cli", "stars": 17705, "installs": 11732527}))
        base = {"desc": "Reddit skill", "created": ago(1)[:10], "pushed": ago(0.1)[:10], "license": "MIT", "lenses": ["S"],
                "topics": [], "fit": 1, "score": 5}
        scan = {"candidates": [{**base, "repo": "a/real", "stars": 900, "installs": 4000},
                               {**base, "repo": "b/copy", "stars": 1, "installs": 900000},
                               {**base, "repo": "c/Mod-Hub", "desc": "Ultimate Mod Hub for Infinite Money", "stars": 60}],
                "searches": [], "id": "x", "project": "p", "question": "q"}
        self.assertEqual([c["repo"] for c in discover.visible(scan)], ["a/real"])
        self.assertIn("excluded: 1 look like lures", discover.render(scan))
        self.assertLess(discover.score({**base, "repo": "b/copy", "stars": 1, "installs": 900000}),
                        discover.score({**base, "repo": "b/copy", "stars": 1, "installs": 0}) + 0.01)

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
        self.env = {k: os.environ.pop(k) for k in ["GITHUB_SCOUT_STORE", "REUSE_FIRST_STORE"] if k in os.environ}

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
        self.assertEqual(json.loads((self.root / "github-scout.json").read_text())["format"], 2)
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
        from github_scout.store import locate
        cwd = os.getcwd()
        try:
            os.chdir(self.root / "projects" / "ops")
            with unittest.mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "nocfg")}):
                self.assertEqual(locate(None), self.root.resolve())
        finally:
            os.chdir(cwd)
        with self.assertRaises(StoreError):
            locate(str(Path(self.tmp.name)))


class FirstRunTests(unittest.TestCase):
    def test_ask_creates_the_registry_and_the_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            repo = Path(tmp) / "myapp"
            (repo / ".git").mkdir(parents=True)
            cwd = os.getcwd()
            env = {"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"), "GITHUB_SCOUT_STORE": "", "REUSE_FIRST_STORE": ""}
            try:
                os.chdir(repo)
                with unittest.mock.patch.dict(os.environ, env), \
                        unittest.mock.patch("github_scout.store.DEFAULT_STORE", home / ".github-scout"):
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                        code = cli.main(["ask", "video", "让 agent 做出像剪辑师做的宣传片", "--stage", "working"])
                    self.assertEqual(code, 0, out.getvalue())
                    store = Store(home / ".github-scout")
                    self.assertEqual(store.lang, "zh")                       # the goal was written in Chinese
                    self.assertEqual(store.project("myapp").data["code"], str(repo.resolve()))
                    self.assertTrue(store.question_path("myapp", "video").is_file())
            finally:
                os.chdir(cwd)

    def test_ask_creates_a_named_registry_that_does_not_exist_yet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "team-registry"
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = cli.main(["--store", str(root), "ask", "web/payments", "Take card payments", "--stage", "idea"])
            self.assertEqual(code, 0, out.getvalue())
            self.assertEqual(Store(root).lang, "en")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertNotEqual(cli.main(["--store", str(Path(tmp) / "nothing"), "find", "x"]), 0)   # reads never create

    def test_registries_made_before_the_rename_still_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "old"
            Store.init(root, "old", "en")
            (root / "github-scout.json").rename(root / "reuse-first.json")
            self.assertEqual(Store(root).settings["name"], "old")
            from github_scout.store import locate
            self.assertEqual(locate(str(root)), root.resolve())


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

    def test_other_files_beside_scans_are_ignored(self):
        self.seed()
        self.run_cli("scan", "ops/browser-ops", "--quiet")
        d = self.root / "scans" / "ops" / "browser-ops"
        (d / "notes-structure.json").write_text('{"repos": {}}')
        code, out, _ = self.run_cli("scan", "ops/browser-ops", "--show")
        self.assertEqual(code, 0, out)
        self.assertIn("jackwener/OpenCLI", out)

    def test_import_checks_links_and_keeps_table_notes(self):
        self.seed()
        self.run_cli("scan", "ops/browser-ops", "--quiet")
        report = Path(self.tmp.name) / "cloud.md"
        report.write_text("# report\n\n| 仓库 | 类型 | 结论 | 能借什么 |\n|---|---|---|---|\n"
                          "| https://github.com/xpzouying/xiaohongshu-mcp | mcp | 学思路 | 登录态复用 |\n"
                          "| https://github.com/nobody/invented-repo | cli | 直接用 | 编的 |\n\n"
                          "Also see github.com/jackwener/OpenCLI.\n")
        code, out, _ = self.run_cli("import", str(report), "--q", "ops/browser-ops", "--note", "ChatGPT Pro")
        self.assertEqual(code, 0, out)
        self.assertIn("3 repos linked; 2 exist on GitHub", out)
        self.assertIn("possibly invented by the report's author: nobody/invented-repo", out)
        e = [x for x in self.store.ledger() if x["repo"] == "xpzouying/xiaohongshu-mcp"][-1]
        self.assertEqual((e["verdict"], e["reason"]), ("short", "ChatGPT Pro: learn: 登录态复用"))

    def test_import_follows_renamed_repos(self):
        self.seed()
        self.api.add(repo("qwen/voice", 2400, "Multi-lingual voice generation", pushed=ago(1)))
        self.api.paths["repos/oldorg/voice"] = repo("qwen/voice", 2400, "Multi-lingual voice generation", pushed=ago(1))
        report = Path(self.tmp.name) / "r.md"
        report.write_text("| repo | verdict |\n|---|---|\n| https://github.com/oldorg/voice | learn |\n")
        code, out, _ = self.run_cli("import", str(report), "--q", "ops/browser-ops")
        self.assertEqual(code, 0, out)
        self.assertIn("moved (1), added under the new name: oldorg/voice -> qwen/voice", out)
        self.assertNotIn("possibly invented", out)
        self.assertIn(("qwen/voice", "short"), {(e["repo"], e["verdict"]) for e in self.store.ledger()})

    def test_import_takes_verdicts_from_triage_not_candidates(self):
        self.seed()
        self.run_cli("scan", "ops/browser-ops", "--quiet")
        report = Path(self.tmp.name) / "cloud.md"
        report.write_text("## 2. Candidates\n\n| repo | kind | verdict |\n|---|---|---|\n"
                          "| https://github.com/xpzouying/xiaohongshu-mcp | mcp | learn |\n"
                          "| https://github.com/jackwener/OpenCLI | cli | learn |\n\n"
                          "### Other sources\n\n| repo | verdict |\n|---|---|\n| https://github.com/jackwener/OpenCLI | use |\n\n"
                          "## 3. Triage\n\n| repo | route | verdict | reason |\n|---|---|---|---|\n"
                          "| https://github.com/jackwener/OpenCLI | read the adapters | shortlist | one command per site |\n")
        code, out, _ = self.run_cli("import", str(report), "--q", "ops/browser-ops")
        self.assertEqual(code, 0, out)
        self.assertIn("1 verdicts from the report's table", out)
        mine = {e["repo"]: e["verdict"] for e in self.store.ledger() if e.get("by") != "seed"}
        self.assertEqual(mine.get("jackwener/OpenCLI"), "short")
        self.assertNotIn("xpzouying/xiaohongshu-mcp", mine)

    def test_import_keeps_the_search_log(self):
        self.seed()
        report = Path(self.tmp.name) / "cloud.md"
        report.write_text("## 2. Search and candidates\n\n### Access\n| entry point | worked | fallback used |\n|---|---|---|\n"
                          "| GitHub search page | yes | |\n\n### Search log\n"
                          "| # | lens | direction | lang | query or URL | looked at | kept |\n|---|---|---|---|---|---|---|\n"
                          "| 1 | words | D1 | zh | `小红书 登录态` | 30 | xpzouying/xiaohongshu-mcp |\n"
                          "| 2 | list | D1 | en | https://github.com/jackwener/OpenCLI | 12 | |\n\n### Candidates\n"
                          "| repo | kind | direction | lang | why it may help | last commit | stars | found by |\n"
                          "|---|---|---|---|---|---|---|---|\n"
                          "| https://github.com/xpzouying/xiaohongshu-mcp | mcp | D1 | zh | 登录态复用 | unknown | 9k | 1 |\n")
        code, out, _ = self.run_cli("import", str(report), "--q", "ops/browser-ops")
        self.assertEqual(code, 0, out)
        self.assertIn("2 searches from its search log", out)
        scan = json.loads(sorted((self.root / "scans" / "ops" / "browser-ops").glob("*.json"))[-1].read_text())
        logged = [s for s in scan["searches"] if s["kind"].startswith("cloud")]
        self.assertEqual([(s["kind"], s["query"], s["hits"]) for s in logged],
                         [("cloud words", "D1 · zh · 小红书 登录态", 1),
                          ("cloud list", "D1 · en · https://github.com/jackwener/OpenCLI", 12)])
        cand = {c["repo"]: c for c in scan["candidates"]}
        self.assertEqual(cand["xpzouying/xiaohongshu-mcp"].get("said"), "登录态复用")

    def test_import_reads_the_directions_for_a_local_scan(self):
        self.seed()
        report = Path(self.tmp.name) / "cloud.md"
        report.write_text("# GitHub scout report: product videos\n\n## 1. Directions\n\n"
                          "| direction | entities (en / zh) | mechanisms (en / zh) | forms |\n|---|---|---|---|\n"
                          "| D1 | remotion / 宣传片, 产品视频 | `video understanding` / 视频理解 | skill, cli, whatever |\n"
                          "| D2 | Remotion、剪映, Claude Code, skill, 技能 | 审片, SKILL.md | mcp |\n\n"
                          "See https://github.com/xpzouying/xiaohongshu-mcp.\n")
        code, out, _ = self.run_cli("import", str(report), "--q", "ops/videos")
        self.assertEqual(code, 0, out)
        self.assertIn("directions read into the question: 4 entities, 3 mechanisms, 3 forms", out)
        self.assertIn("rows without W are repos the report did not list", out)
        q = self.store.question("ops/videos").data
        self.assertEqual(q["entities"], ["remotion", "宣传片", "剪映", "产品视频"])   # directions take turns
        self.assertEqual(q["mechanisms"], ["video understanding", "审片", "视频理解"])
        self.assertEqual(q["forms"], ["skill", "mcp", "cli"])
        doc = self.store.question("ops/videos")                       # a local plan is never overwritten
        doc.data["entities"] = ["product video|宣传片"]
        self.store.save_question(doc)
        self.run_cli("import", str(report), "--q", "ops/videos")
        self.assertEqual(self.store.question("ops/videos").data["entities"], ["product video|宣传片"])

    def test_import_without_directions_uses_the_logged_queries(self):
        self.seed()
        report = Path(self.tmp.name) / "cloud.md"
        report.write_text("| # | lens | lang | query |\n|---|---|---|---|\n"
                          "| 1 | connector search | en | Claude Code video |\n"
                          "| 2 | web | en | site:github.com/heygen-com/hyperframes agent video HTML |\n"
                          "| 3 | connector search | zh | 视频字幕 翻译 配音 开源 |\n"
                          "| 4 | connector search | en | claude code video |\n\n"
                          "https://github.com/xpzouying/xiaohongshu-mcp\n")
        code, out, _ = self.run_cli("import", str(report), "--q", "ops/v2")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.store.question("ops/v2").data["entities"],
                         ["Claude Code video", "视频字幕 翻译 配音 开源", "agent video HTML"])

    def test_show_names_the_rows_the_report_missed(self):
        base = {"desc": "Video skill", "created": ago(1)[:10], "pushed": ago(0.1)[:10], "topics": [], "fit": 1, "score": 5,
                "stars": 900}
        scan = {"candidates": [{**base, "repo": "a/listed", "lenses": ["W", "E"]},
                               {**base, "repo": "b/missed", "lenses": ["E", "H"]}],
                "searches": [], "id": "x", "project": "p", "question": "q"}
        self.assertIn("not in the report or web links: 1 of 2 rows came only from GitHub's API (no W): b/missed",
                      discover.render(scan))

    def test_import_creates_the_question_from_the_report(self):
        self.seed()
        report = Path(self.tmp.name) / "cloud.md"
        report.write_text("# GitHub scout report: Read Xiaohongshu notes from scripts\n\n- Stage: prototype\n\n"
                          "| repo | verdict |\n|---|---|\n| https://github.com/xpzouying/xiaohongshu-mcp | shortlist |\n")
        code, out, _ = self.run_cli("import", str(report), "--q", "ops/xhs-read")
        self.assertEqual(code, 0, out)
        q = self.store.question("ops/xhs-read").data
        self.assertEqual((q["ask"], q["stage"]), ("Read Xiaohongshu notes from scripts", "prototype"))

    def test_brief_packs_the_answer_for_the_coding_agent(self):
        doc = self.store.question("ops/browser-ops")
        code, out, _ = self.run_cli("brief", "ops/browser-ops")
        self.assertNotEqual(code, 0)                                  # no answer yet
        doc.body = doc.body.replace("### In one paragraph\n", "### In one paragraph\nUse OpenCLI for reads.\n")
        doc.body = doc.body.replace("### Next steps in our project\n", "### Next steps in our project\n1. Pin OpenCLI 1.8.\n")
        doc.data["picked"] = ["jackwener/OpenCLI"]
        self.store.save_question(doc)
        code, out, _ = self.run_cli("brief", "ops/browser-ops")
        self.assertEqual(code, 0, out)
        text = Path(out.splitlines()[0]).read_text()
        self.assertIn("# Brief for the coding agent:", text)
        self.assertIn("1. Pin OpenCLI 1.8.", text)
        self.assertIn("Project code: /src/ops", text)
        self.assertIn("[jackwener/OpenCLI](https://github.com/jackwener/OpenCLI)", text)

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


class AdoptTests(Base):
    """Stage 6: what came into our project from which repo, and what upstream did to those files since."""

    slug = "jackwener/OpenCLI"

    def setUp(self):
        super().setUp()
        self.proj = Path(self.tmp.name) / "ops"
        (self.proj / "tools").mkdir(parents=True)
        (self.proj / "tools" / "read.ts").write_text("// port of jackwener/OpenCLI clis/reddit/read.js\n")
        doc = self.store.project("ops")
        write_doc(doc.path, {**doc.data, "code": str(self.proj)}, doc.body, PROJECT_ORDER)
        registry.new_card(self.store, {"repo": self.slug, "desc": "x", "stars": 30000, "branch": "main",
                                       "commit": "aaaaaaaaaaaa"}, "software", "cli",
                          [{"project": "ops", "question": "browser-ops", "take": "use", "where": "tools"}], [], "read")

    def adopt(self, *argv):
        with cwd(self.proj):
            return self.run_cli("adopt", self.slug, "--q", "ops/browser-ops", *argv)

    def test_adopt_writes_the_card_and_the_ledger_and_replaces_on_repeat(self):
        code, out, err = self.adopt("--mode", "vendor", "--into", "tools/read.ts", "--from", "clis/reddit/read.js",
                                    "--ours", "1234abc", "--note", "comment ids kept")
        self.assertEqual(code, 0, err)
        self.assertIn("next: github-scout updates jackwener/OpenCLI", out)
        self.assertEqual(self.store.card(self.slug).data["adopted"], [
            {"project": "ops", "question": "browser-ops", "mode": "vendor", "into": ["tools/read.ts"],
             "from": ["clis/reddit/read.js"], "at": "aaaaaaaaaaaa", "ours": "1234abc", "date": today(),
             "note": "comment ids kept"}])
        e = self.store.ledger()[-1]
        self.assertEqual((e["repo"], e["verdict"], e["project"], e["question"]), (self.slug, "card", "ops", "browser-ops"))
        self.assertTrue(e["reason"].startswith("adopted: vendor: tools/read.ts <- clis/reddit/read.js @aaaaaaaaaaaa"), e)
        self.adopt("--mode", "port", "--into", "tools/read.ts", "--ours", "1234abc")       # same paths: replaced
        self.adopt("--mode", "tool", "--into", "tools/run.sh", "--ours", "1234abc")        # other paths: added
        adopted = self.store.card(self.slug).data["adopted"]
        self.assertEqual([(a["mode"], a["into"]) for a in adopted], [("port", ["tools/read.ts"]), ("tool", ["tools/run.sh"])])
        self.assertNotIn("note", adopted[0])
        self.assertEqual(len([x for x in self.store.ledger() if x.get("reason", "").startswith("adopted")]), 3)

    def test_drop_marks_the_entry_and_keeps_it(self):
        self.adopt("--mode", "vendor", "--into", "tools/read.ts", "--from", "clis/reddit/read.js", "--ours", "1234abc")
        code, out, err = self.adopt("--into", "tools/read.ts", "--drop", "--note", "our own parser now")
        self.assertEqual(code, 0, err)
        self.assertIn("updates no longer reports it", out)
        [a] = self.store.card(self.slug).data["adopted"]
        self.assertEqual((a["mode"], a["dropped"], a["note"]), ("vendor", today(), "our own parser now"))
        self.assertTrue(self.store.ledger()[-1]["reason"].startswith("dropped adoption: vendor: tools/read.ts"))
        code, _, err = self.adopt("--into", "tools/other.ts", "--drop")
        self.assertEqual(code, 1)
        self.assertIn("no adoption into tools/other.ts under ops/browser-ops (recorded: tools/read.ts)", err)
        self.adopt("--mode", "vendor", "--into", "tools/read.ts", "--ours", "1234abc")     # adopted again: live
        self.assertNotIn("dropped", self.store.card(self.slug).data["adopted"][0])

    def test_unknown_repo_question_or_mode_is_refused(self):
        code, _, err = self.run_cli("adopt", "z/nothing", "--q", "ops/browser-ops", "--mode", "vendor", "--into", "x")
        self.assertEqual(code, 1)
        self.assertIn("z/nothing has no card. Look at it and note what we take first: github-scout look --q "
                      "ops/browser-ops z/nothing, then github-scout note z/nothing", err)
        for argv, needle in [(["--q", "ops/nope", "--mode", "vendor"], "no question ops/nope"),
                             (["--q", "ops/browser-ops"], "--mode is required"),
                             (["--q", "ops/browser-ops", "--mode", "vendor", "--from", "src/*.ts"], "not globs"),
                             (["--q", "ops/browser-ops", "--mode", "vendor", "--at", "v1.8"], "--at takes their commit sha")]:
            with cwd(self.proj):
                code, _, err = self.run_cli("adopt", self.slug, "--into", "tools/read.ts", *argv)
            self.assertEqual(code, 1, argv)
            self.assertIn(needle, err)
        self.assertNotIn("adopted", self.store.card(self.slug).data)
        self.assertFalse([e for e in self.store.ledger() if "adopt" in e.get("reason", "")])

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_paths_come_from_the_project_and_our_commit_from_git(self):
        git = ["git", "-C", str(self.proj)]
        subprocess.run(git + ["init", "-q"], check=True)
        subprocess.run(git + ["add", "."], check=True)
        subprocess.run(git + ["-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", "commit",
                              "--no-verify", "-qm", "port reddit read"], check=True)
        head = subprocess.run(git + ["rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        elsewhere = Path(self.tmp.name) / "elsewhere"
        elsewhere.mkdir()
        with cwd(elsewhere):                       # outside the project: read from its code path
            code, out, err = self.run_cli("adopt", self.slug, "--q", "ops/browser-ops", "--mode", "port", "--into", "tools/read.ts")
        self.assertEqual(code, 0, err)
        self.assertNotIn("warn", out)
        a = self.store.card(self.slug).data["adopted"][0]
        self.assertEqual((a["into"], a["ours"]), (["tools/read.ts"], head))
        with cwd(self.proj / "tools"):             # inside: read from here, stored from the repository's root
            code, out, err = self.run_cli("adopt", self.slug, "--q", "ops/browser-ops", "--mode", "data",
                                          "--into", "read.ts,../NOTICE")
        self.assertEqual(code, 0, err)
        self.assertIn("warn  NOTICE: not found", out)
        self.assertEqual(self.store.card(self.slug).data["adopted"][1]["into"], ["tools/read.ts", "NOTICE"])

    def test_show_lists_adoptions(self):
        self.adopt("--mode", "vendor", "--into", "tools/read.ts", "--from", "clis/reddit/read.js", "--ours", "1234abc")
        _, out, _ = self.run_cli("show", self.slug)
        self.assertIn("adopted:\n  ops/browser-ops vendor: tools/read.ts <- clis/reddit/read.js @aaaaaaaaaaaa, "
                      f"ours 1234abc, {today()}", out)
        lines = self.run_cli("show", "ops/browser-ops")[1].splitlines()
        i = next(n for n, ln in enumerate(lines) if ln.startswith("picked:"))
        self.assertEqual(lines[i + 1], "adopted: jackwener/OpenCLI (vendor tools/read.ts)")

    def test_check_accepts_cards_with_and_without_adoptions(self):
        self.assertEqual(self.store.check()[0], [])                          # a card from before stage 6
        self.adopt("--mode", "vendor", "--into", "tools/read.ts", "--from", "clis/reddit/read.js", "--ours", "1234abc")
        self.adopt("--into", "tools/read.ts", "--drop")
        self.assertEqual(self.store.check()[0], [])
        card = self.store.card(self.slug)
        card.data["adopted"][0].update(mode="borrow", at="v1.8", dropped="soon")
        card.data["adopted"].append({"project": "ops", "question": "browser-ops", "mode": "data", "into": "tools/x.json"})
        self.store.save_card(card)
        errors = "\n".join(self.store.check()[0])
        for needle in ("adopted mode must be one of depend, vendor, port, skill, tool, data", "adopted at must be a hex sha",
                       "adopted dropped must be YYYY-MM-DD", "adopted into must be a list of our paths"):
            self.assertIn(needle, errors)


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

    def test_note_idea_and_ask_update(self):
        slug = "a/b"
        self.api.add(repo(slug, pushed=ago(1)))
        sha = "e" * 40
        self.api.paths[f"repos/{slug}/commits/main"] = {"sha": sha}
        self.api.paths[f"repos/{slug}/git/trees/{sha}"] = {"tree": [{"path": "LICENSE", "type": "blob", "size": 10}]}
        self.api.paths[f"repos/{slug}/contents/LICENSE"] = "PolyForm Noncommercial License 1.0.0"
        code, out, _ = self.run_cli("note", slug, "--q", "ops/browser-ops", "--take", "learn",
                                    "--idea", "Judge pairs, not scores.", "--note", "judge design")
        self.assertEqual(code, 0, out)
        self.assertNotIn("LICENSE", out)                     # licences are not part of the research
        card = self.store.card(slug)
        self.assertNotIn("license", card.data)
        self.assertIn("## The idea\nJudge pairs, not scores.", card.body)
        code, out, _ = self.run_cli("ask", "ops/browser-ops", "A sharper question", "--stage", "prototype", "--update")
        self.assertEqual(code, 0, out)
        q = self.store.question("ops/browser-ops").data
        self.assertEqual((q["ask"], q["stage"]), ("A sharper question", "prototype"))


BILINGUAL = {
    "entities": ["reddit|红迪", "xiaohongshu|小红书|xhs|红书", "bilibili|B站|哔哩哔哩", "zhihu|知乎", "douyin|抖音",
                 "weibo|微博", "wechat|公众号", "twitter|推特"],
    "mechanisms": ["logged-in browser|登录态", "chrome extension|浏览器插件|浏览器扩展", "browser cookies|cookie 登录",
                   "browser automation|浏览器自动化", "website to cli|网站变命令行", "cdp|调试协议"],
    "forms": ["cli", "skill", "mcp"],
    "problems": ["social media automation", "自媒体 自动化"],
}


def words(query: str) -> str:
    """A query without its operators."""
    return " ".join(w for w in query.split() if ":" not in w or w.startswith('"')).replace('"', "")


class LanguageTests(Base):
    """Chinese projects supplied half the repos picked in real runs; the plan must search Chinese as much as English."""

    def test_language_of_a_term(self):
        from github_scout.store import lang_of
        for term, lang in [("小红书", "zh"), ("AIGC检测", "zh"), ("写作 skill", "zh"), ("ノート", "ja"),
                           ("日本語のテスト", "ja"), ("한국어", "ko"), ("note.com", "en"), ("résumé", "en")]:
            self.assertEqual(lang_of(term), lang, term)

    def test_pairs_and_combos_per_language_within_bounds(self):
        q = discover.plan(BILINGUAL)
        lang = discover.lang_of
        pairs = [x["query"] for x in q if x["lens"] == "P"]
        combos = [x["query"] for x in q if x["lens"] == "C"]
        self.assertEqual(len(pairs), 15)                                 # the same total as one language
        self.assertEqual(len(combos), 9)
        for query in pairs + combos:                                     # never mixes languages
            terms = words(query).split()
            self.assertEqual(len({lang(t) for t in terms}), 1, query)
        zh_combos = [c for c in combos if lang(c) == "zh"]
        self.assertIn(4, (len(zh_combos), len(combos) - len(zh_combos)))  # 5 + 4: combos take turns
        self.assertTrue(any(c.startswith("登录态 红迪 in:readme") for c in combos))   # first term in that language
        # pairs give English its full share; Chinese pairs replayed as noise, so they only fill what is left
        self.assertEqual({lang(p) for p in pairs}, {"en"})
        few = {**BILINGUAL, "entities": ["reddit|红迪", "xiaohongshu|小红书", "bilibili|B站"]}
        few_pairs = [x["query"] for x in discover.plan(few) if x["lens"] == "P"]
        self.assertEqual([lang(p) for p in few_pairs], ["en"] * 3 + ["zh"] * 3)
        self.assertTrue(any(p.startswith("红迪 小红书 in:readme") for p in few_pairs))
        self.assertTrue(any(c.startswith('"logged-in browser" reddit in:readme') for c in combos))

    def test_capped_lenses_share_slots_fairly(self):
        q = discover.plan(BILINGUAL)
        recent = [x["query"] for x in q if x["lens"] == "R"]                # English first, Chinese fills the rest
        self.assertEqual((len(recent), {discover.lang_of(s) for s in recent}), (12, {"en"}))
        for lens, cap in (("K", 10), ("S", 10), ("N", 8)):
            got = [x["query"] for x in q if x["lens"] == lens]
            zh = sum(discover.lang_of(s) == "zh" for s in got)
            self.assertEqual(len(got), cap, lens)
            self.assertEqual(zh, cap // 2, f"{lens}: {got}")
        mcp = [x["query"] for x in q if x["lens"] == "D"]           # the MCP registry matches ASCII names only
        self.assertEqual((len(mcp), {discover.lang_of(s) for s in mcp}), (7, {"en"}))   # every English lead term
        readme = [x["query"] for x in q if x["lens"] == "M" and "in:readme" in x["query"]]
        self.assertEqual(sum(discover.lang_of(s) == "zh" for s in readme), 5)
        # a language that runs out leaves its slots to the others
        one_zh = {**BILINGUAL, "entities": ["reddit", "xiaohongshu|小红书", "bilibili", "zhihu"], "mechanisms": ["cdp"]}
        k = [x["query"] for x in discover.plan(one_zh) if x["lens"] == "K"]
        self.assertEqual([discover.lang_of(s) for s in k].count("zh"), 1)
        self.assertEqual(len(k), 6)

    def test_invariants_hold_in_two_languages(self):
        q = discover.plan(BILINGUAL)
        queries = [(x["lens"], x["query"]) for x in q]
        alive = f" pushed:>{discover.window(discover.HIDE)}"
        self.assertEqual(len(set(queries)), len(queries))
        self.assertTrue(all(s.endswith(alive) for x, (lens, s) in zip(q, queries) if x["kind"] == "repos"))
        single = {words(s) for lens, s in queries if lens in "EM"}
        for key in ("entities", "mechanisms"):
            for g in discover.groups(BILINGUAL[key]):
                for term in g:
                    self.assertIn(term, single, term)                    # every synonym, in either language
        self.assertEqual([words(s) for lens, s in queries if lens == "Q"], ["social media automation", "自媒体 自动化"])

    def test_langs_order_the_turns(self):
        first = [x["query"] for x in discover.plan({**BILINGUAL, "langs": ["zh", "en"]}) if x["lens"] == "E"][0]
        self.assertTrue(first.startswith("红迪 "), first)
        en_only = {"entities": ["reddit", "bilibili"], "mechanisms": ["cdp"], "langs": ["en"]}
        self.assertEqual(set(discover.search_langs(discover.plan(en_only))), {"en"})

    def test_warnings_for_groups_missing_a_language(self):
        doc = self.store.question("ops/browser-ops")
        self.assertEqual(doc.data["langs"], ["en", "zh"])               # every new question
        _, warns = self.store.check()
        gap = [w for w in warns if "have no zh term" in w]
        self.assertEqual(len(gap), 1, warns)
        self.assertIn("4 of 5 vocabulary groups have no zh term: reddit, twitter, logged-in browser, chrome extension", gap[0])
        code, out, _ = self.run_cli("scan", "ops/browser-ops", "--plan")
        self.assertEqual(code, 0, out)
        self.assertIn("warn  4 of 5 vocabulary groups have no zh term", out)
        code, out, _ = self.run_cli("ask", "ops/browser-ops", "Drive our sites", "--stage", "working", "--update", "--langs", "en")
        self.assertEqual(code, 0, out)
        self.assertNotIn("warn", out)
        self.assertEqual(self.store.question("ops/browser-ops").data["langs"], ["en"])
        code, out, _ = self.run_cli("ask", "ops/browser-ops", "Drive our sites", "--stage", "working", "--update",
                                    "--langs", "en,zh")
        self.assertIn("warn  4 of 5 vocabulary groups have no zh term", out)
        self.assertEqual(self.store.check()[0], [])                     # a warning, never an error
        code, out, err = self.run_cli("ask", "ops/other", "x", "--stage", "idea", "--langs", "en,es")
        self.assertEqual(code, 1)
        self.assertIn("Latin-script languages count as en", err)
        code, out, _ = self.run_cli("ask", "ops/jp", "x", "--stage", "idea", "--langs", "en,ja")
        self.assertEqual(code, 0, out)
        self.assertIn("every language of langs (en, ja)", out)
        self.assertEqual(self.store.question("ops/jp").data["langs"], ["en", "ja"])
        doc = self.store.question("ops/jp")
        doc.data["langs"] = ["en", "es"]
        self.store.save_question(doc)
        self.assertTrue(any("langs must be codes from en, zh, ja, ko" in e for e in self.store.check()[0]))

    def test_header_counts_languages_and_chinese_descriptions(self):
        alive = f" pushed:>{discover.window(discover.HIDE)}"
        self.api.search["小红书" + alive] = [repo("a/xhs-cli", 900, "小红书命令行工具：用浏览器登录态发帖", pushed=ago(0.2)),
                                           repo("b/rednote", 300, "Xiaohongshu CLI", pushed=ago(0.2))]
        code, out, _ = self.run_cli("scan", "ops/browser-ops", "--quiet")
        self.assertEqual(code, 0, out)
        plan = discover.plan(self.store.question("ops/browser-ops").data)
        n = discover.search_langs(plan)
        line = next(ln for ln in out.splitlines() if ln.startswith("languages: "))
        self.assertEqual(line, f"languages: en {n['en']}, zh {n['zh']} searches with words; "
                               "1 of 2 rows shown have a Chinese description")


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
