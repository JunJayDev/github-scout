import contextlib
import datetime as dt
import http.client
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from fake import FakeAPI, client, commit, repo, tarball

from github_scout import cli, discover, examine, registry, yamlish
from github_scout.github import Client, github_slug
from github_scout.store import PROJECT_ORDER, Store, StoreError, card_filename, today, write_doc

QUESTION = {
    "entities": ["reddit", "xiaohongshu|小红书|rednote", "twitter|x.com"],
    "mechanisms": ["logged-in browser", "chrome extension"],
    "forms": ["cli", "skill"],
    "problems": ["social media automation"],
}


# The answer as the question template wrote it on 2026-10-18 (a backbone and its gaps): such answers still brief.
OLD_ANSWER = {
    "en": "\n## Answer\n(The deliverable: one repo to follow as a whole.)\n\n### In one paragraph\n(Which repo.)\n\n"
          "### Backbone\n(The repo we follow.)\n\n### Gaps to fill\n| what the backbone lacks | filled from | why |\n|---|---|---|\n\n"
          "### Trial runs\n(Each repo tried.)\n\n### Against what we have\n| we have | the backbone does | difference | take it? |\n"
          "|---|---|---|---|\n\n### Next steps in our project\n\n### Not adopted\n(Ideas we did not take.)\n\n",
    "zh": "\n## 答案\n（交付物：整套照做的一个仓库。）\n\n### 一段话结论\n（照哪个仓库做。）\n\n### 主干\n（整套照做的那个仓库。）\n\n"
          "### 补什么\n| 主干缺什么 | 从哪补 | 为什么 |\n|---|---|---|\n\n### 试跑记录\n（每个试过的仓库。）\n\n"
          "### 和我们已有的对照\n| 我们已有 | 主干的做法 | 差在哪 | 拿不拿 |\n|---|---|---|---|\n\n### 我们接下来改什么\n\n"
          "### 没采用\n（别家的思路。）\n\n",
}


def old_answer(doc, lang: str = "en") -> None:
    """Put the 2026-10-18 answer sections in place of the report's."""
    start, end = ("\n## Answer\n", "\n## Searched\n") if lang == "en" else ("\n## 答案\n", "\n## 搜过哪些\n")
    doc.body = doc.body[:doc.body.index(start)] + OLD_ANSWER[lang] + doc.body[doc.body.index(end) + 1:]


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
        self.env = {k: os.environ.pop(k) for k in ["GITHUB_SCOUT_STORE", "REUSE_FIRST_STORE", "GITHUB_SCOUT_MIN_STARS",
                                                   "REUSE_FIRST_MIN_STARS"] if k in os.environ}

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
        self.assertEqual(json.loads((self.root / "github-scout.json").read_text(encoding="utf-8"))["format"], 2)
        self.assertEqual(self.store.check()[0], [])

    def test_question_template_carries_the_stage(self):
        body = self.store.question("ops/browser-ops").body
        self.assertIn("Stage: working (it works: borrow techniques", body)
        for heading in ("## What good looks like", "### In one paragraph", "### Candidates", "### Try first",
                        "### Not recommended", "### Trials and choice"):
            self.assertIn(heading, body)
        self.assertNotIn("### Backbone", body)                          # the coding agent chooses, after the report
        self.assertNotIn("### Ideas worth taking", body)
        self.assertIn("50+ stars", body)
        self.assertEqual((self.store.question("ops/browser-ops").data["backbone"], self.store.check()[0]), (None, []))

    def test_check_reports_bad_cards_and_questions(self):
        (self.root / "repos" / "a__b.md").write_text("---\nid: a/c\nkind: cli\nuses:\n  - project: ops\n    take: love\n---\n", encoding="utf-8")
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
        for heading in ("## 好的结果长什么样", "### 候选", "### 先试这几个", "### 不推荐", "### 试跑和选定"):
            self.assertIn(heading, body)
        self.assertIn("50 星以上", body)

    def test_chinese_brief_is_a_report(self):
        doc = self.store.question("ops/browser-ops")
        doc.body = doc.body.replace("### 一段话结论\n", "### 一段话结论\n读用 OpenCLI。\n")
        doc.data["picked"] = ["z/no-card"]
        self.store.save_question(doc)
        code, out, _ = self.run_cli("brief", "ops/browser-ops")
        self.assertEqual(code, 0, out)
        text = Path(out.splitlines()[0]).read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# GitHub scout 报告：Drive our logged-in sites from scripts\n"))
        self.assertIn("github-scout 负责找、筛、写报告；试跑和选定由开发 agent 来做", text)
        self.assertIn("## 给开发 agent：试跑、选定、落地", text)
        self.assertIn('github-scout note z/no-card --q ops/browser-ops --take <use|adapt|learn|later|skip> '
                      '--trial "<跑了什么、出来什么、花了多久>"', text)
        self.assertIn("\n## 落地和登记\n", text)
        self.assertIn("github-scout adopt z/no-card --q ops/browser-ops --mode <方式> --into <我们的路径> --from <他们的文件>", text)
        self.assertIn("## 搜过哪些\n\n没有扫描记录", text)

    def test_chinese_brief_follows_the_backbone(self):
        doc = self.store.question("ops/browser-ops")
        old_answer(doc, "zh")
        doc.body = doc.body.replace("### 主干\n", "### 主干\nd/tool：成片和目标最像，试跑 40 秒出片。\n")
        doc.body = doc.body.replace("### 补什么\n| 主干缺什么 | 从哪补 | 为什么 |\n|---|---|---|\n",
                                    "### 补什么\n| 主干缺什么 | 从哪补 | 为什么 |\n|---|---|---|\n| 字幕 | e/gap | 主干没有 |\n")
        doc.data.update(backbone="d/tool", picked=["d/tool", "e/gap"])
        self.store.save_question(doc)
        code, out, _ = self.run_cli("brief", "ops/browser-ops")
        self.assertEqual(code, 0, out)
        text = Path(out.splitlines()[0]).read_text(encoding="utf-8")
        self.assertIn("## 主干：整套照做\n\n照主干的做法从头做到尾；别的仓库只在「补什么」点名的地方进来。", text)
        self.assertIn("d/tool：成片和目标最像", text)
        self.assertIn("## 补什么\n\n| 主干缺什么 | 从哪补 | 为什么 |", text)
        self.assertIn("| [d/tool](https://github.com/d/tool) | 主干 | - | - | - | - | - | - |", text)
        self.assertIn("--mode <depend|skill|tool>", text)
        self.assertIn('--note "<补主干的哪个缺口>"', text)


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
        self.assertIn("verifiable effect: weak, only a text description", out)
        self.assertIn("--results <links>", out)
        self.assertIn("top one 80% of commits", out)

        code, _, err = self.run_cli("note", "jackwener/OpenCLI", "--q", "ops/browser-ops", "--take", "use",
                                    "--results", "https://github.com/jackwener/OpenCLI#demo")
        self.assertIn("jackwener/OpenCLI shows only text in its own repo", err)   # its README is a weak effect
        code, out, _ = self.run_cli("note", "jackwener/OpenCLI", "--q", "ops/browser-ops", "--take", "use",
                                    "--where", "tools/opencli", "--watch", "clis/reddit/**",
                                    "--results", "https://opencli.info/")
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
        index = (self.root / "INDEX.md").read_text(encoding="utf-8")
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
        (d / "notes-structure.json").write_text('{"repos": {}}', encoding="utf-8")
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
                          "Also see github.com/jackwener/OpenCLI.\n", encoding="utf-8")
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
        report.write_text("| repo | verdict |\n|---|---|\n| https://github.com/oldorg/voice | learn |\n", encoding="utf-8")
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
                          "| https://github.com/jackwener/OpenCLI | read the adapters | shortlist | one command per site |\n", encoding="utf-8")
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
                          "| https://github.com/xpzouying/xiaohongshu-mcp | mcp | D1 | zh | 登录态复用 | unknown | 9k | 1 |\n", encoding="utf-8")
        code, out, _ = self.run_cli("import", str(report), "--q", "ops/browser-ops")
        self.assertEqual(code, 0, out)
        self.assertIn("2 searches from its search log", out)
        scan = json.loads(sorted((self.root / "scans" / "ops" / "browser-ops").glob("*.json"))[-1].read_text(encoding="utf-8"))
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
                          "See https://github.com/xpzouying/xiaohongshu-mcp.\n", encoding="utf-8")
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
                          "https://github.com/xpzouying/xiaohongshu-mcp\n", encoding="utf-8")
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
                          "| repo | verdict |\n|---|---|\n| https://github.com/xpzouying/xiaohongshu-mcp | shortlist |\n", encoding="utf-8")
        code, out, _ = self.run_cli("import", str(report), "--q", "ops/xhs-read")
        self.assertEqual(code, 0, out)
        q = self.store.question("ops/xhs-read").data
        self.assertEqual((q["ask"], q["stage"]), ("Read Xiaohongshu notes from scripts", "prototype"))

    def test_brief_is_a_report_for_the_coding_agent(self):
        """Owner, 2026-10-19: github-scout finds, filters and reports; the coding agent tries and chooses."""
        self.seed()
        self.run_cli("scan", "ops/browser-ops", "--quiet")
        doc = self.store.question("ops/browser-ops")
        code, out, _ = self.run_cli("brief", "ops/browser-ops")
        self.assertNotEqual(code, 0)                                  # no answer yet
        self.seed_repo_files()
        code, _, err = self.run_cli("note", "jackwener/OpenCLI", "--q", "ops/browser-ops", "--take", "use",
                                    "--results", "https://opencli.info/", "--note", "one JSON command per site")
        self.assertEqual(code, 0, err)
        for heading, text in (("In one paragraph", "OpenCLI reads all three sites; posting is left to build."),
                              ("Candidates", "| repo | kind | stars |\n|---|---|---|\n| jackwener/OpenCLI | cli | 30k |"),
                              ("Try first", "1. jackwener/OpenCLI: run `opencli reddit hot`; look for JSON with ids."),
                              ("Not recommended", "- xpzouying/xiaohongshu-mcp: one site only.")):
            doc.body = re.sub(rf"(\n### {heading}\n)(?:\(.*\)\n|\|.*\|\n\|[-|]+\|\n)?",
                              lambda m, text=text: m.group(1) + text + "\n", doc.body, count=1)
        doc.data.update(status="answered", picked=["jackwener/OpenCLI"])
        self.store.save_question(doc)
        mine = [w for w in self.store.check()[1] if "questions/browser-ops.md" in w and "vocabulary" not in w]
        self.assertEqual(mine, [])                                    # no backbone and no trial asked of a report
        code, out, _ = self.run_cli("brief", "ops/browser-ops")
        self.assertEqual(code, 0, out)
        text = Path(out.splitlines()[0]).read_text(encoding="utf-8")
        order = ["# GitHub scout report: Drive our logged-in sites", "github-scout found the candidates, filtered them",
                 "## Goal and where we stand", "Project code: /src/ops", "## In one paragraph", "OpenCLI reads all three",
                 "## Candidates", "| jackwener/OpenCLI | cli | 30k |", "## Try first", "run `opencli reddit hot`",
                 "## Sources", "| [jackwener/OpenCLI](https://github.com/jackwener/OpenCLI) | try first | use | 30000 | "
                 "mid: [1](https://opencli.info/) |", "## For the coding agent: try, choose, adopt",
                 "github-scout note jackwener/OpenCLI --q ops/browser-ops --take <use|adapt|learn|later|skip> --trial",
                 "## Adopt and record", "## Not recommended (leave these out)", "- xpzouying/xiaohongshu-mcp: one site",
                 "## What was searched", "repos kept.", "Star threshold 50, relaxed where a direction had under 5"]
        self.assertEqual([text.index(x) for x in order], sorted(text.index(x) for x in order))
        self.assertNotIn("## Backbone", text)

    def test_resurface_when_a_skipped_repo_grows(self):
        self.seed()
        self.run_cli("scan", "ops/browser-ops", "--quiet")
        self.run_cli("pick", "ops/browser-ops", "--skip", "xpzouying/xiaohongshu-mcp=x")
        led = self.store.ledger()
        led[-1]["stars"] = 1000
        (self.root / "ledger.jsonl").write_text("".join(json.dumps(e) + "\n" for e in led), encoding="utf-8")
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
        (self.proj / "tools" / "read.ts").write_text("// port of jackwener/OpenCLI clis/reddit/read.js\n", encoding="utf-8")
        doc = self.store.project("ops")
        write_doc(doc.path, {**doc.data, "code": str(self.proj)}, doc.body, PROJECT_ORDER)
        registry.new_card(self.store, {"repo": self.slug, "desc": "x", "stars": 30000, "branch": "main",
                                       "commit": "aaaaaaaaaaaa"}, "software", "cli",
                          [{"project": "ops", "question": "browser-ops", "take": "use", "where": "tools"}], [], "read")
        self.api.paths[f"repos/{self.slug}/commits/aaaaaaaaaaaa"] = {"sha": "a" * 40}   # --from is checked upstream
        for path in ("clis/reddit/read.js", "src/daemon.ts", "src/broken.ts", "data/old.json"):
            self.api.paths[f"repos/{self.slug}/contents/{path}"] = "x"

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
        self.adopt("--mode", "port", "--into", "tools/read.ts", "--ours", "2345bcd")       # same paths: updated
        self.adopt("--mode", "tool", "--into", "tools/run.sh", "--ours", "1234abc")        # other paths: added
        adopted = self.store.card(self.slug).data["adopted"]
        self.assertEqual([(a["mode"], a["into"]) for a in adopted], [("port", ["tools/read.ts"]), ("tool", ["tools/run.sh"])])
        self.assertEqual((adopted[0]["from"], adopted[0]["note"], adopted[0]["ours"]),
                         (["clis/reddit/read.js"], "comment ids kept", "2345bcd"))      # what was left out is kept
        code, _, err = self.adopt("--mode", "vendor", "--into", "tools/x.ts", "--from", "clis/reddit/raed.js")
        self.assertEqual(code, 1)
        self.assertIn("not in jackwener/OpenCLI at aaaaaaa: clis/reddit/raed.js", err)
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

    def test_updates_reports_upstream_commits_on_the_files_we_took(self):
        self.api.add(repo(self.slug, 31000, "x", pushed=ago(0.1)))
        self.api.add(repo("other/tool", 50, "y", pushed=ago(0.1)))
        registry.new_card(self.store, {"repo": "other/tool", "desc": "y", "stars": 50, "branch": "main", "commit": "bbbbbbbbbbbb"},
                          "software", "cli", [{"project": "ops", "question": "browser-ops", "take": "learn", "note": "n"}], [],
                          "read")
        self.api.paths[f"repos/{self.slug}/compare/aaaaaaaaaaaa...main"] = {
            "ahead_by": 4, "commits": [{"sha": "c" * 40, "commit": {"message": "m"}}],
            "files": [{"filename": "clis/reddit/read.js", "status": "modified", "additions": 1, "deletions": 1,
                       "patch": "@@ -1 +1 @@\n-old\n+new"}, {"filename": "README.md", "status": "modified", "patch": "x"}]}
        self.api.paths["repos/other/tool/compare/bbbbbbbbbbbb...main"] = {"ahead_by": 0, "commits": [], "files": []}
        self.api.paths[f"repos/{self.slug}/commits/aaaaaaaaaaaa"] = {
            "sha": "a" * 40, "commit": {"committer": {"date": "2026-10-01T08:00:00Z"}}}
        self.api.history["clis/reddit/read.js"] = [commit("9f8e7d6" + "0" * 33, "2026-10-20", "fix reddit comments\n\nbody"),
                                                   commit("8" * 40, "2026-10-12"), commit("7" * 40, "2026-10-05"),
                                                   commit("a" * 40, "2026-10-01", "the commit we took")]
        self.api.history["src/broken.ts"] = 403
        self.adopt("--mode", "vendor", "--into", "tools/read.ts", "--from", "clis/reddit/read.js,src/daemon.ts", "--ours", "1234abc")
        self.adopt("--mode", "tool", "--into", "tools/run.sh", "--ours", "1234abc")
        self.adopt("--mode", "port", "--into", "tools/gone.ts", "--from", "src/broken.ts", "--ours", "1234abc")
        self.adopt("--mode", "data", "--into", "tools/old.json", "--from", "data/old.json", "--ours", "1234abc")
        self.adopt("--into", "tools/old.json", "--drop")
        code, out, err = self.run_cli("updates")
        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("jackwener/OpenCLI") and "review" in lines[0], out)     # adopted first
        self.assertIn('  adopted into ops (vendor tools/read.ts): upstream clis/reddit/read.js changed 3 times since '
                      'aaaaaaa — newest 9f8e7d6 2026-10-20 "fix reddit comments"', lines)
        self.assertIn("  adopted into ops (vendor tools/read.ts): upstream src/daemon.ts unchanged since aaaaaaa", lines)
        self.assertIn("  adopted into ops (port tools/gone.ts): upstream src/broken.ts: history unreachable", lines)
        self.assertIn("  adopted into ops (tool tools/run.sh): no upstream paths recorded (adopt --from), so only the line "
                      "above applies", lines)
        self.assertNotIn("old.json", out)                                    # dropped: no longer watched
        self.assertTrue(lines[5].startswith("other/tool") and "up to date" in lines[5], out)
        self.assertIn("files we took changed: update our copy", out)
        asked = [c for c in self.api.calls if "path=clis%2Freddit%2Fread.js" in c]
        self.assertEqual(len(asked), 1)
        self.assertIn("sha=main", asked[0])
        self.assertIn("since=2026-10-01T08%3A00%3A00Z", asked[0])
        _, out, _ = self.run_cli("updates", "--json", "--project", "ops")
        row = next(r for r in json.loads(out.split("\nnext:")[0]) if r["repo"] == self.slug)
        self.assertEqual(row["adopted"][0]["paths"][0]["newest"]["sha"], "9f8e7d6")
        _, out, _ = self.run_cli("updates", "--diff", self.slug)            # the card watches nothing; we took read.js
        self.assertIn("--- clis/reddit/read.js (modified, +1 -1)", out)
        self.assertNotIn("README.md (", out)

    def test_brief_ends_with_one_adopt_line_per_picked_repo(self):
        doc = self.store.question("ops/browser-ops")
        doc.body = doc.body.replace("### In one paragraph\n", "### In one paragraph\nUse OpenCLI for reads.\n")
        doc.data["picked"] = [self.slug, "z/no-card"]
        self.store.save_question(doc)
        code, out, _ = self.run_cli("brief", "ops/browser-ops")
        self.assertEqual(code, 0, out)
        text = Path(out.splitlines()[0]).read_text(encoding="utf-8")
        self.assertIn("the github-scout-dig skill, then github-scout-adopt", text)
        tail = text.split("\n## Adopt and record\n", 1)[1].split("\n## What was searched\n")[0]
        self.assertNotIn("\n## ", tail)
        self.assertEqual([ln for ln in tail.splitlines() if ln.startswith("github-scout adopt ")], [
            "github-scout adopt jackwener/OpenCLI --q ops/browser-ops --mode <mode> --into tools --from <their files>",
            "github-scout adopt z/no-card --q ops/browser-ops --mode <mode> --into <our paths> --from <their files>   "
            "# no card yet: github-scout note z/no-card --q ops/browser-ops first"])

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
                                    "--idea", "Judge pairs, not scores.", "--note", "judge design",
                                    "--results", "https://example.com/a-b/samples")
        self.assertEqual(code, 0, out)
        self.assertNotIn("LICENSE", out)                     # licences are not part of the research
        card = self.store.card(slug)
        self.assertNotIn("license", card.data)
        self.assertIn("## The idea\nJudge pairs, not scores.", card.body)
        code, out, _ = self.run_cli("ask", "ops/browser-ops", "A sharper question", "--stage", "prototype", "--update")
        self.assertEqual(code, 0, out)
        q = self.store.question("ops/browser-ops").data
        self.assertEqual((q["ask"], q["stage"]), ("A sharper question", "prototype"))

    def test_note_from_a_second_question_keeps_the_first_idea_first_and_merges_watch(self):
        slug = "a/b"
        self.api.add(repo(slug, pushed=ago(1), desc="A tool"))
        code, out, _ = self.run_cli("note", slug, "--q", "ops/browser-ops", "--take", "learn",
                                    "--idea", "First idea.", "--watch", "src/a.py", "--results", "https://example.com/demo")
        self.assertEqual(code, 0, out)
        registry.new_question(self.store, "ops/other", "Another question", "idea")
        code, out, _ = self.run_cli("note", slug, "--q", "ops/other", "--take", "adapt", "--idea", "Second idea.",
                                    "--watch", "src/b.py", "src/a.py", "--summary", "A sharper summary")
        self.assertEqual(code, 0, out)
        card = self.store.card(slug)
        self.assertLess(card.body.index("First idea."), card.body.index("Second idea."))
        self.assertIn("**ops/other:** Second idea.", card.body)
        self.assertEqual(card.data["watch"], ["src/a.py", "src/b.py"])
        self.assertEqual(card.data["summary"], "A sharper summary")

    def test_a_repo_without_a_description_still_gets_a_summary(self):
        slug = "c/d"
        self.api.add(repo(slug, pushed=ago(1), desc=""))
        code, out, _ = self.run_cli("note", slug, "--q", "ops/browser-ops", "--take", "learn",
                                    "--idea", "Writes letters in the order schools teach them. It also does more.",
                                    "--no-results", "a teaching method; its output is the order itself")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.store.card(slug).data["summary"], "Writes letters in the order schools teach them.")
        self.assertFalse([e for e in self.store.check()[0] if "summary" in e])


class QualityGateTests(Base):
    """User, 2026-10-18: a reference shows results and has 50+ stars; the top 2-3 are tried; one backbone is followed
    as a whole and only its gaps are filled from elsewhere."""

    def scan_with_a_tiny_repo(self):
        alive = f" pushed:>{discover.window(discover.HIDE)}"
        big = self.api.add(repo("a/reddit-cli", 900, "Reddit CLI", created=ago(3), pushed=ago(0.2)))
        tiny = self.api.add(repo("b/reddit-tiny", 8, "Reddit CLI for agents", created=ago(1), pushed=ago(0.1)))
        lst = self.api.add(repo("c/awesome-reddit", 8, "A curated list of Reddit tools", pushed=ago(0.5)))
        self.api.search["reddit" + alive] = [big, tiny, lst]
        return self.run_cli("scan", "ops/browser-ops", "--quiet")

    def answered(self, body: dict, **data):
        doc = self.store.question("ops/browser-ops")
        for heading, text in body.items():
            doc.body = re.sub(rf"(\n#+ {re.escape(heading)}\n)(?:\(.*\)\n|\|.*\|\n\|[-|]+\|\n)?",
                              lambda m, text=text: m.group(1) + text + "\n", doc.body, count=1)
        doc.data.update(status="answered", **data)
        self.store.save_question(doc)

    def card(self, slug, stars, take="use", level="read", results=(), **use):
        registry.new_card(self.store, {"repo": slug, "desc": f"{slug} tool", "stars": stars, "branch": "main",
                                       "commit": "abcdef123456"}, "software", "cli",
                          [{"project": "ops", "question": "browser-ops", "take": take, "note": "n", **use}], [], level,
                          results=list(results))

    def test_rows_under_50_stars_leave_the_table_and_need_a_reason_to_shortlist(self):
        code, out, _ = self.scan_with_a_tiny_repo()
        self.assertEqual(code, 0, out)
        self.assertIn("a/reddit-cli", out)
        self.assertNotIn("b/reddit-tiny", out)
        self.assertIn("under 50 stars (or the relaxed floor): 1 hidden, no references", out)
        self.assertIn("lists (scan --expand <list>): c/awesome-reddit (8)", out)            # lists are only for finding
        _, out, _ = self.run_cli("scan", "ops/browser-ops", "--show", "--all")
        self.assertIn("under 10 stars", next(ln for ln in out.splitlines() if "b/reddit-tiny" in ln))   # never below 10
        code, _, err = self.run_cli("pick", "ops/browser-ops", "1", "b/reddit-tiny")
        self.assertEqual(code, 1)
        self.assertIn("no references: b/reddit-tiny (8). Shortlist one only with --low-stars", err)
        self.assertEqual(self.store.ledger(), [])                                          # nothing half-written
        code, out, _ = self.run_cli("pick", "ops/browser-ops", "--later", "b/reddit-tiny", "--list", "c/awesome-reddit")
        self.assertEqual(code, 0, out)
        code, out, _ = self.run_cli("pick", "ops/browser-ops", "b/reddit-tiny", "--low-stars", "official org, out this week")
        self.assertEqual(code, 0, out)
        e = self.store.ledger()[-1]
        self.assertEqual((e["repo"], e["verdict"], e["low_stars"]), ("b/reddit-tiny", "short", "official org, out this week"))
        self.assertIn("· low stars: official org, out this week", self.run_cli("show", "b/reddit-tiny")[1])
        code, out, _ = self.run_cli("pick", "ops/browser-ops", "z/never-scanned")
        self.assertEqual(code, 0, out)
        self.assertIn("warn  stars unknown (not in a scan): z/never-scanned. A reference needs 50+ stars", out)

    def test_the_threshold_comes_from_the_environment(self):
        self.scan_with_a_tiny_repo()
        with unittest.mock.patch.dict(os.environ, {"GITHUB_SCOUT_MIN_STARS": "5"}):
            _, out, _ = self.run_cli("scan", "ops/browser-ops", "--show")
            self.assertIn("b/reddit-tiny", out)
            code, out, _ = self.run_cli("pick", "ops/browser-ops", "b/reddit-tiny")
            self.assertEqual(code, 0, out)
            self.assertNotIn("relaxed", out)                              # the floors are above a threshold of 5
        with unittest.mock.patch.dict(os.environ, {"GITHUB_SCOUT_MIN_STARS": "lots"}):
            code, _, err = self.run_cli("pick", "ops/browser-ops", "b/reddit-tiny")
            self.assertEqual(code, 1)
            self.assertIn("GITHUB_SCOUT_MIN_STARS must be a whole number", err)

    def test_note_needs_results_and_stars_for_a_reference(self):
        self.api.add(repo("b/tiny", 12, "Tiny tool", pushed=ago(0.1)))
        code, _, err = self.run_cli("note", "b/tiny", "--q", "ops/browser-ops", "--take", "learn", "--note", "x")
        self.assertEqual(code, 1)
        self.assertIn("b/tiny has 12 stars, under 50: no reference. Say why it is an exception with --low-stars", err)
        self.assertIn("b/tiny shows no verifiable effect on its card. Give --results", err)
        self.assertIsNone(self.store.card("b/tiny"))
        self.assertEqual(self.store.ledger(), [])
        code, _, err = self.run_cli("note", "b/tiny", "--q", "ops/browser-ops", "--take", "learn", "--results", "demo.mp4",
                                    "--low-stars", "x")
        self.assertIn("--results takes links (http or https) to its verifiable effect: demo.mp4", err)
        code, out, err = self.run_cli("note", "b/tiny", "--q", "ops/browser-ops", "--take", "learn",
                                      "--results", "https://example.com/tiny/demo.mp4", "--low-stars", "official org")
        self.assertEqual(code, 0, err)
        card = self.store.card("b/tiny")
        self.assertEqual(card.data["results"], ["https://example.com/tiny/demo.mp4"])
        self.assertEqual(card.data["uses"][0]["low_stars"], "official org")
        self.assertEqual(self.store.ledger()[-1]["low_stars"], "official org")
        self.assertIn("verifiable effect: mid\n  mid    https://example.com/tiny/demo.mp4", self.run_cli("show", "b/tiny")[1])

        self.api.add(repo("c/plain", 400, "Plain tool", pushed=ago(0.1)))
        code, out, err = self.run_cli("note", "c/plain", "--q", "ops/browser-ops", "--take", "later", "--note", "no results yet")
        self.assertEqual(code, 0, err)                                    # later and skip need neither
        self.assertEqual(self.store.card("c/plain").data["results"], [])
        self.assertIn("verifiable effect: none recorded", self.run_cli("show", "c/plain")[1])
        code, _, err = self.run_cli("note", "c/plain", "--q", "ops/browser-ops", "--take", "adapt")
        self.assertEqual(code, 1)
        self.assertIn("no verifiable effect", err)
        self.assertNotIn("stars", err)
        code, _, err = self.run_cli("note", "c/plain", "--q", "ops/browser-ops", "--take", "adapt",
                                    "--no-results", "a library: its tests are the result")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.store.card("c/plain").data["uses"][0]["no_results"], "a library: its tests are the result")
        registry.new_question(self.store, "ops/other", "Another question", "idea")
        code, _, err = self.run_cli("note", "b/tiny", "--q", "ops/other", "--take", "use")
        self.assertIn("b/tiny has 12 stars on its card (updates --done refreshes the count), under 50", err)
        code, _, err = self.run_cli("note", "b/tiny", "--q", "ops/other", "--take", "use", "--low-stars", "same org")
        self.assertEqual(code, 0, err)                                    # the card has results already
        self.assertEqual(self.store.check()[0], [])

    def test_a_trial_goes_into_the_card(self):
        self.api.add(repo("d/tool", 300, "Video tool", pushed=ago(0.1)))
        code, out, err = self.run_cli("note", "d/tool", "--q", "ops/browser-ops", "--take", "use", "--kind", "software",
                                      "--results", "https://example.com/d/gallery", "--trial", "ran examples/basic:\n 40 s")
        self.assertEqual(code, 0, err)
        card = self.store.card("d/tool")
        self.assertEqual(card.data["level"], "trial")
        self.assertIn(f"## Verifiable effect and trial\n\n- {today()}, ops/browser-ops: ran examples/basic: 40 s\n\n## Quality", card.body)
        registry.new_question(self.store, "ops/other", "Another question", "idea")
        self.run_cli("note", "d/tool", "--q", "ops/other", "--take", "learn", "--trial", "second run")
        body = self.store.card("d/tool").body
        self.assertIn(f"40 s\n- {today()}, ops/other: second run\n\n## Quality", body)
        old = self.store.card("d/tool")                                   # a card from before the section
        old.body = "\n# d/tool\n\n## The idea\nRenders frames.\n\n## Read first\n"
        self.store.save_card(old)
        self.run_cli("note", "d/tool", "--q", "ops/other", "--take", "skip", "--trial", "fails on arm64")
        self.assertIn(f"Renders frames.\n\n## Verifiable effect and trial\n\n- {today()}, ops/other: fails on arm64\n\n## Read first",
                      self.store.card("d/tool").body)
        code, out, _ = self.run_cli("note", "z/gone", "--q", "ops/other", "--take", "skip", "--trial", "no install")
        self.assertEqual(self.store.ledger()[-1]["reason"], "trial: no install")   # no card: the trial goes in the ledger

    def test_check_holds_the_backbone_to_the_gates(self):
        """A backbone is set by the coding agent after trying; check then holds it to the gates."""
        doc = self.store.question("ops/browser-ops")
        old_answer(doc)
        self.store.save_question(doc)
        self.card("d/tool", 300)                                          # read, no results
        self.card("e/gap", 12, take="learn", results=["https://example.com/e"])
        self.card("f/alt", 900, level="trial", results=["https://example.com/f"])
        self.answered({"Backbone": "d/tool, because its films match."}, backbone="d/tool", alternate="f/alt",
                      picked=["d/tool", "e/gap"])
        errors, warns = self.store.check()
        self.assertEqual(errors, [])
        mine = [w.split(": ", 1)[1] for w in warns if "questions/browser-ops.md" in w and "vocabulary" not in w]
        self.assertEqual(mine, ["backbone d/tool was not tried (level read): run its own example, then note --trial",
                                "backbone d/tool shows no verifiable effect (note --results <a live site, screenshots, "
                                "videos or posts>)",
                                "picked e/gap has 12 stars, under 50, and no reason (note --low-stars)"])
        doc = self.store.question("ops/browser-ops")
        doc.data.update(backbone="not a repo", alternate=["a/b"])
        self.store.save_question(doc)
        errors = self.store.check()[0]
        self.assertIn("projects/ops/questions/browser-ops.md: backbone must be one repository, owner/repo", errors)
        self.assertIn("projects/ops/questions/browser-ops.md: alternate must be one repository, owner/repo", errors)
        registry.new_question(self.store, "ops/empty", "Answered with nothing under Try first", "idea")
        doc = self.store.question("ops/empty")
        doc.data["status"] = "answered"
        self.store.save_question(doc)
        self.assertIn("projects/ops/questions/empty.md: answered without repos to try first: name 2-3 under Try first "
                      "and in picked:, or say there why none qualifies", self.store.check()[1])
        card = self.store.card("f/alt")
        card.data["results"] = ["javascript:alert(1)"]
        self.store.save_card(card)
        self.assertIn("repos/f__alt.md: results are links (http or https): javascript:alert(1)", self.store.check()[0])

    def test_brief_follows_the_backbone_and_leaves_the_rest_in_an_appendix(self):
        doc = self.store.question("ops/browser-ops")                    # an answer written on 2026-10-18
        old_answer(doc)
        self.store.save_question(doc)
        self.card("d/tool", 300, level="trial", results=["https://example.com/d/gallery"], where="tools/video")
        self.card("e/gap", 12, take="learn", results=["https://example.com/e"], low_stars="official org")
        self.answered({"What good looks like": "The three films at https://example.com/target.",
                       "In one paragraph": "Follow d/tool; fill captions from e/gap.",
                       "Backbone": "d/tool: its gallery matches the target; 300 stars; the trial rendered in 40 s.",
                       "Gaps to fill": "| what the backbone lacks | filled from | why |\n|---|---|---|\n"
                                       "| captions | e/gap `src/caption.ts` | d/tool has none |",
                       "Trial runs": "- d/tool: examples/basic rendered in 40 s.",
                       "Next steps in our project": "1. Install d/tool 2.1.",
                       "Not adopted": "- x/y: shot lists by hand; d/tool plans its own."},
                      backbone="d/tool", alternate="f/alt", picked=["d/tool", "e/gap"])
        code, out, _ = self.run_cli("brief", "ops/browser-ops")
        self.assertEqual(code, 0, out)
        text = Path(out.splitlines()[0]).read_text(encoding="utf-8")
        order = ["## Goal and where we stand", "### What good looks like", "Follow d/tool; fill captions",
                 "## Backbone: follow it as a whole", "Do it the backbone's way, end to end", "## Gaps to fill",
                 "## Trial runs", "## What to change, in order", "## Sources", "## Adopt and record",
                 "## Not adopted (leave these out)", "- x/y: shot lists by hand"]
        self.assertEqual([text.index(x) for x in order], sorted(text.index(x) for x in order))
        self.assertNotIn("## Why: the ideas behind it", text)
        self.assertNotIn("## Against what we have", text)                  # left empty: no section
        self.assertIn("| [d/tool](https://github.com/d/tool) | backbone | use | 300 | mid: [1](https://example.com/d/gallery) | "
                      "trial | abcdef123456 | n |", text)
        self.assertIn("| [f/alt](https://github.com/f/alt) | alternate | - | - | - | - | - | - |", text)
        self.assertIn("| [e/gap](https://github.com/e/gap) | fills a gap | learn | 12 (official org) |", text)
        adopt = [ln for ln in text.splitlines() if ln.startswith("github-scout adopt ")]
        self.assertEqual(adopt, [
            "github-scout adopt d/tool --q ops/browser-ops --mode <depend|skill|tool> --into tools/video --from <their files>",
            "github-scout adopt e/gap --q ops/browser-ops --mode <mode> --into <our paths> --from <their files> "
            "--note \"<the gap in the backbone it fills>\""])                 # no line for the alternate

    def test_answers_written_before_the_backbone_still_brief_and_check(self):
        old = ("\n# Drive our logged-in sites\n\n## Where we are\nStage: working (it works)\n- What we have: tools/reddit\n\n"
               "## Answer\n(The deliverable. Ideas first: code is cheap for an agent, an idea it never had is not.)\n\n"
               "### In one paragraph\nUse OpenCLI for reads.\n\n### Ideas worth taking\n(One per line: the idea ...)\n\n"
               "1. Exit codes as a contract.\n\n### Practices and components\n(Only what our stage needs.)\n\n"
               "### Against what we have\n| we have | they do | difference | take it? |\n|---|---|---|---|\n\n"
               "### Next steps in our project\n1. Pin OpenCLI 1.8.\n\n## Searched\n(Scans are in scans/ops/browser-ops/.)\n")
        doc = self.store.question("ops/browser-ops")
        data = {k: v for k, v in doc.data.items() if k not in ("backbone", "alternate")}
        write_doc(doc.path, {**data, "status": "answered", "picked": []}, old, list(data))
        self.assertNotIn("backbone", doc.path.read_text(encoding="utf-8"))
        errors, warns = self.store.check()
        self.assertEqual(errors, [])
        self.assertFalse([w for w in warns if "backbone" in w], warns)
        code, out, _ = self.run_cli("brief", "ops/browser-ops")
        self.assertEqual(code, 0, out)
        text = Path(out.splitlines()[0]).read_text(encoding="utf-8")
        self.assertIn("## Why: the ideas behind it\n\n1. Exit codes as a contract.", text)
        self.assertIn("## What to change, in order\n\n1. Pin OpenCLI 1.8.", text)
        self.assertNotIn("(One per line", text)
        self.assertNotIn("## Backbone", text)
        self.assertNotIn("| we have | they do |", text)                    # a header-only table is no content

    def test_import_keeps_a_shortlist_under_50_stars_for_later(self):
        self.api.add(repo("a/big", 900, "Reddit CLI", pushed=ago(0.2)))
        self.api.add(repo("b/tiny", 8, "Reddit CLI", pushed=ago(0.2)))
        report = Path(self.tmp.name) / "cloud.md"
        report.write_text("## 3. Triage\n\n| repo | kind | results | route | verdict | reason |\n|---|---|---|---|---|---|\n"
                          "| https://github.com/a/big | cli | https://example.com/big.mp4 | read cli/ | shortlist | one command |\n"
                          "| https://github.com/b/tiny | cli | none | read all | shortlist | small |\n", encoding="utf-8")
        code, out, _ = self.run_cli("import", str(report), "--q", "ops/browser-ops")
        self.assertEqual(code, 0, out)
        self.assertIn("under 50 stars (or the relaxed floor), recorded as later, not shortlisted (1): b/tiny", out)
        verdicts = {e["repo"]: (e["verdict"], e["reason"]) for e in self.store.ledger()}
        self.assertEqual(verdicts["a/big"], ("short", "cloud.md: shortlist: one command"))
        self.assertEqual(verdicts["b/tiny"], ("later", "under 10 stars; cloud.md: shortlist: small"))


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


class RecallTests(Base):
    """A test scan on 2026-10-18 missed the two closest competitors: broad words sorted by stars returned only giants,
    the vocabulary said each idea one way, rising rows in other forms buried the list, and the star gate hid 16 rivals."""

    alive = f" pushed:>{discover.window(discover.HIDE)}"

    def vocab(self, **data):
        doc = self.store.question("ops/browser-ops")
        doc.data.update(data)
        self.store.save_question(doc)

    def last_scan(self) -> dict:
        return json.loads(self.store.scans("ops", "browser-ops")[-1].read_text(encoding="utf-8"))

    def best_calls(self) -> list[str]:
        return [c for c in self.api.calls if "search/repositories" in c and "sort=" not in c]

    def test_broad_single_terms_are_read_again_in_best_match_order(self):
        self.vocab(entities=QUESTION["entities"] + ["github|开源"])
        q = '"logged-in browser"' + self.alive
        giant = self.api.add(repo("big/browser", 90000, "Browser automation framework", pushed=ago(0.1)))
        small = self.api.add(repo("s/relay", 131, "Let agents drive your logged-in browser", created=ago(3), pushed=ago(0.1)))
        self.api.search[q], self.api.best[q], self.api.totals[q] = [giant], [small], 8176
        self.api.search["github" + self.alive] = [giant]
        self.api.best["github" + self.alive] = [self.api.add(repo("x/github-stats", 300, "GitHub stats", pushed=ago(0.1)))]
        self.api.totals["github" + self.alive] = 2_182_917
        code, out, _ = self.run_cli("scan", "ops/browser-ops", "--quiet")
        self.assertEqual(code, 0, out)
        self.assertIn("s/relay", out)                                   # 131 stars: never in the first 30 by stars
        self.assertNotIn("x/github-stats", out)                         # a generic word is not read again
        self.assertEqual(len(self.best_calls()), 1, self.best_calls())
        self.assertIn("per_page=100", self.best_calls()[0])
        e = next(s for s in self.last_scan()["searches"] if s["query"] == q)
        self.assertEqual((e["total"], e["best"], e["hits"]), (8176, 1, 2))
        self.assertIn("broad words (alone, only their most-starred repos came back; scan --plan says what to do): "
                      "github 2.2M", out)

    def test_best_match_reads_are_capped(self):
        for term, total in (('"logged-in browser"', 5000), ('"chrome extension"', 300000), ("reddit", 2000),
                            ('"logged-in browser" in:readme', 3000)):
            self.api.totals[term + self.alive] = total
        with unittest.mock.patch.object(discover, "BEST_MAX", 2):
            code, out, _ = self.run_cli("scan", "ops/browser-ops", "--quiet")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.best_calls()), 2)                     # mechanisms before entities, narrowest first
        self.assertEqual([s["query"] for s in self.last_scan()["searches"] if s.get("best") is not None],
                         ['"logged-in browser"' + self.alive, '"logged-in browser" in:readme' + self.alive])
        calls = self.api.calls
        first_best = min(i for i, c in enumerate(calls) if c in self.best_calls())
        self.assertGreater(first_best, max(i for i, c in enumerate(calls) if "registry.npmjs.org" in c))   # read last

    def test_a_topic_read_whole_is_not_searched_again_for_the_last_year(self):
        self.api.search["topic:reddit" + self.alive] = [self.api.add(repo("a/reddit-cli", 900, "Reddit CLI", pushed=ago(0.1)))]
        self.api.totals["topic:xiaohongshu" + self.alive] = 500
        code, out, _ = self.run_cli("scan", "ops/browser-ops", "--quiet")
        self.assertEqual(code, 0, out)
        searched = " ".join(self.api.calls)
        self.assertNotIn("topic%3Areddit+created", searched)
        self.assertIn("topic%3Axiaohongshu+created", searched)
        e = next(s for s in self.last_scan()["searches"] if s["query"].startswith("topic:reddit created"))
        self.assertEqual((e["hits"], e["skipped"]), (0, "topic:reddit has 1 repos, all read"))

    def test_generic_words_take_no_capped_slot(self):
        q = {"entities": ["github|开源|open source", "reddit|红迪"], "mechanisms": ["prior art|现成方案"], "forms": ["skill"]}
        p = discover.plan(q)

        def by(lens):
            return [words(x["query"]) for x in p if x["lens"] == lens]
        self.assertTrue({"github", "开源", "open source"} <= set(by("E")))    # searched once, as written
        for lens in "KSNR":
            self.assertEqual({"github", "开源", "open source"} & set(by(lens)), set(), lens)
            self.assertIn("prior art", by(lens), lens)                   # the slot goes to a word that narrows
        self.assertFalse(any(x["query"].startswith(("topic:github", "topic:open-source")) for x in p))
        mixed = discover.plan({"entities": ["github search|GitHub 搜索", "去 AI 味"], "forms": ["skill"]})
        self.assertEqual(sorted({x["query"].split()[0] for x in mixed if x["lens"] == "T"}), ["topic:github-search"])
        self.assertTrue(discover.is_generic("Open  Source") and not discover.is_generic("open source alternative"))

    def test_capped_lenses_reach_more_mechanisms_when_entities_are_few(self):
        mechs = ["search first|先搜索", "reinvent the wheel|重复造轮子", "prior art|现成方案", "repo research|开源调研",
                 "build vs buy|技术选型"]
        few = discover.plan({"entities": ["github|开源", "claude code|AI 编程"], "mechanisms": mechs, "forms": ["skill"]})
        s = [x["query"] for x in few if x["lens"] == "S"]
        self.assertEqual(s, ["claude code", "AI 编程", "search first", "先搜索", "reinvent the wheel", "重复造轮子",
                             "prior art", "现成方案", "repo research", "开源调研"])   # heads of five groups, no synonym
        many = discover.plan(BILINGUAL)
        self.assertNotIn("browser cookies", [x["query"] for x in many if x["lens"] == "S"])   # four entities: two mechanisms

    def test_plan_warns_about_broad_words_and_groups_said_one_way(self):
        self.vocab(entities=QUESTION["entities"] + ["github|开源"],
                   mechanisms=["logged-in browser", "chrome extension|浏览器插件|Chrome 插件", "CDP",
                               "search first|search-first|先搜索", "reuse first|reuse before build|不要重复造轮子|重复造轮子"])
        code, out, _ = self.run_cli("scan", "ops/browser-ops", "--plan")
        self.assertEqual(code, 0, out)
        self.assertIn("warn  broad: github, 开源. Alone each brings back only the most-starred repos", out)
        once = next(ln for ln in out.splitlines() if ln.startswith("warn  said one way only: "))
        self.assertIn("logged-in browser (en), chrome extension (en), search first (en, zh), reuse first (zh).", once)
        self.assertNotIn("CDP", once)                                    # a one-word name needs no synonym
        self.assertFalse(discover.said_once(["CDP", "cdp"], "en"))
        self.assertTrue(discover.said_once(["logged-in browser", "logged in browser"], "en"))
        self.api.totals["reddit" + self.alive] = 12719                  # a scan learns how broad each word is
        self.run_cli("scan", "ops/browser-ops", "--quiet")
        _, out, _ = self.run_cli("scan", "ops/browser-ops", "--plan")
        self.assertIn("warn  broad: github, 开源, reddit (12.7k repos).", out)
        self.assertEqual(self.store.check()[0], [])

    def test_rising_list_keeps_only_the_questions_forms(self):
        rise = f"created:>{discover.window(discover.RISE_MONTHS)} stars:>{discover.RISE_STARS}"
        skill = self.api.add(repo("a/anatomy", 11000, "Isometric illustrations of machines", created=ago(0.3),
                                  pushed=ago(0.05), topics=["agent-skill"]))
        cli_ = self.api.add(repo("b/fast-thing", 4000, "命令行工具：一键整理照片", created=ago(0.5), pushed=ago(0.1)))
        car = self.api.add(repo("c/DiPlay", 9000, "Independent CarPlay receiver for Android head units", created=ago(0.5),
                                pushed=ago(0.1)))
        self.api.search[f"topic:agent-skill {rise}" + self.alive] = [skill]
        breakout = f"created:>{discover.window(discover.BREAKOUT_MONTHS)} stars:>{discover.BREAKOUT_STARS}" + self.alive
        self.api.search[breakout] = [cli_, car]
        code, out, _ = self.run_cli("scan", "ops/browser-ops", "--quiet")
        self.assertEqual(code, 0, out)
        hs = [ln for ln in out.splitlines() if re.match(r"\s*h\d+\.", ln)]
        self.assertEqual([ln.split()[5] for ln in hs], ["a/anatomy", "b/fast-thing"])   # forms: cli, skill
        self.assertIn("(2; 1 more not in the question's forms, --all shows them)", out)
        _, out, _ = self.run_cli("scan", "ops/browser-ops", "--show", "--all")
        self.assertIn("c/DiPlay", out)
        self.run_cli("scan", "ops/browser-ops", "--show")                    # pick numbers refer to the last table
        code, out, _ = self.run_cli("pick", "ops/browser-ops", "h2", "--rest", "no")
        self.assertEqual(code, 0, out)
        verdicts = {e["repo"]: e["verdict"] for e in self.store.ledger()}
        self.assertEqual(verdicts, {"b/fast-thing": "short", "a/anatomy": "skip"})       # c/DiPlay was not shown
        self.vocab(forms=[])
        _, out, _ = self.run_cli("scan", "ops/browser-ops", "--show")
        self.assertIn("c/DiPlay", out)                                  # no forms: every rising row counts

    def test_rows_past_the_keep_limit_stay_when_their_own_words_fit(self):
        sc = discover.Scan(None, client(FakeAPI()), {"project": "p", "id": "q", **QUESTION})
        for i in range(3):
            sc._add(repo(f"big/reddit-tool-{i}", 90000, "Reddit tool", pushed=ago(0.1)), "E")
        sc._add(repo("s/rednote-skill", 53, "A skill for rednote", created=ago(3), pushed=ago(0.2)), "M")
        sc._add(repo("n/noise", 60, "Unrelated thing", created=ago(3), pushed=ago(0.2)), "M")
        sc._add(repo("l/awesome-notes", 9, "A curated list", created=ago(30), pushed=ago(2)), "S")
        with unittest.mock.patch.multiple(discover, KEEP=3, KEEP_FIT=5):
            kept = [c["repo"] for c in sc.finish("EM")["candidates"]]
        self.assertEqual(kept[3:], ["s/rednote-skill", "l/awesome-notes"])   # fit 1, and a list, past the first three
        self.assertNotIn("n/noise", kept)                               # no vocabulary in its own words

    def test_shows_form_reads_name_description_and_topics(self):
        cases = [({"repo": "a/x-cli", "desc": ""}, ["cli"], True), ({"repo": "a/x", "desc": "一个命令行工具"}, ["cli"], True),
                 ({"repo": "a/x", "desc": "", "topics": ["mcp-server"]}, ["mcp"], True),
                 ({"repo": "a/x", "desc": "", "topics": ["claude-skills"]}, ["skill"], True),
                 ({"repo": "a/clicker", "desc": "Auto clicker"}, ["cli"], False),
                 ({"repo": "a/x", "desc": "Steam Play for macOS"}, ["skill", "cli", "mcp"], False),
                 ({"repo": "a/x", "desc": "Starter for Next.js"}, ["template"], True)]
        for c, forms, want in cases:
            self.assertEqual(discover.shows_form(c, forms), want, (c, forms))

    def test_header_names_rows_under_the_star_threshold_that_fit_well(self):
        self.api.search["reddit" + self.alive] = [
            self.api.add(repo("a/reddit-cli", 900, "Reddit CLI", pushed=ago(0.1))),
            self.api.add(repo("b/rival", 9, "Reddit, Xiaohongshu and Twitter through your logged-in browser",
                              pushed=ago(0.1))),
            self.api.add(repo("c/one", 1, "Reddit, X.com, rednote via a chrome extension and your logged-in browser",
                              pushed=ago(0.1))),
            self.api.add(repo("d/tiny", 3, "Reddit notes", pushed=ago(0.1)))]
        code, out, _ = self.run_cli("scan", "ops/browser-ops", "--quiet")
        self.assertEqual(code, 0, out)
        self.assertIn("under 50 stars (or the relaxed floor): 3 hidden", out)
        line = next(ln for ln in out.splitlines() if ln.startswith("  of them on topic"))
        self.assertEqual(line, "  of them on topic (fit 4+), for a question about who else does this: "
                               "b/rival (9 stars, fit 4), c/one (1 star, fit 5)")   # in table order
        self.assertNotIn("d/tiny", out)


class ReviewFixTests(Base):
    """Fixes from a code review on 2026-10-19, each reproduced first."""

    slug = "o/tool"

    def tool_card(self, take="learn", commit="a" * 12, branch="main"):
        registry.new_card(self.store, {"repo": self.slug, "desc": "x", "stars": 500, "branch": branch, "commit": commit},
                          "software", "cli", [{"project": "ops", "question": "browser-ops", "take": take, "note": "n"}],
                          [], "read")

    def test_ledger_keeps_entries_with_unicode_line_breaks(self):
        reason = "dead demo\u2028see issue 4\u2029and\x85more"
        code, _, err = self.run_cli("note", "z/nothing", "--q", "ops/browser-ops", "--take", "skip", "--note", reason)
        self.assertEqual(code, 0, err)
        [e] = self.store.ledger()
        self.assertEqual(e["reason"], reason)
        self.assertEqual(len((self.root / "ledger.jsonl").read_text(encoding="utf-8").splitlines()), 1)
        self.assertEqual(self.store.check()[0], [])
        old = json.dumps({"repo": "a/b", "verdict": "skip", "reason": "x\u2028y"}, ensure_ascii=False) + "\n"
        (self.root / "ledger.jsonl").write_text(old, encoding="utf-8")         # written raw by an earlier version
        self.assertEqual(self.store.ledger(), [{"repo": "a/b", "verdict": "skip", "reason": "x\u2028y"}])

    def test_ledger_survives_a_missing_newline_and_lines_that_are_not_objects(self):
        p = self.root / "ledger.jsonl"
        p.write_text('{"repo": "a/one", "verdict": "skip"}', encoding="utf-8")     # an editor dropped the final newline
        self.store.append_ledger([{"repo": "b/two", "verdict": "skip"}])
        self.assertEqual([e["repo"] for e in self.store.ledger()], ["a/one", "b/two"])
        with p.open("a", encoding="utf-8") as f:
            f.write('["a"]\n5\n{"repo": 5, "verdict": "skip"}\n')
        errors = self.store.check()[0]
        self.assertEqual(errors[-3:], ["ledger.jsonl:3: not a JSON object", "ledger.jsonl:4: not a JSON object",
                                       "ledger.jsonl:5: needs repo and a verdict in peeked, short, list, later, skip, card"])
        for argv in (["check"], ["show", "a/one"], ["find", "one"], ["site"], ["show", "ops/browser-ops"]):
            code, out, err = self.run_cli(*argv)                                   # no traceback
            self.assertIn(code, (0, 1), argv)

    def test_two_scans_in_one_second_keep_both(self):
        for s in ("a/reddit-one", "b/reddit-two"):
            self.api.add(repo(s, 500, "reddit cli", pushed=ago(0.2)))
        with unittest.mock.patch("github_scout.discover.now_stamp", return_value="20261019-120000"):
            for s in ("a/reddit-one", "b/reddit-two"):
                code, _, err = self.run_cli("scan", "ops/browser-ops", "--add", f"github.com/{s}", "--quiet")
                self.assertEqual(code, 0, err)
        d = self.root / "scans" / "ops" / "browser-ops"
        self.assertEqual([p.name for p in self.store.scans("ops", "browser-ops")],
                         ["20261019-120000.json", "20261019-120000-2.json"])
        self.assertEqual(json.loads((d / "20261019-120000-2.json").read_text(encoding="utf-8"))["id"], "20261019-120000-2")
        _, out, _ = self.run_cli("scan", "ops/browser-ops", "--show")
        self.assertIn("a/reddit-one", out)
        self.assertIn("b/reddit-two", out)
        for name in ("20261019-120000-10", "20261019-115959"):
            (d / f"{name}.json").write_text("{}", encoding="utf-8")
        self.assertEqual([p.stem for p in self.store.scans("ops", "browser-ops")],
                         ["20261019-115959", "20261019-120000", "20261019-120000-2", "20261019-120000-10"])

    def test_a_card_given_as_a_url_is_found(self):
        self.api.add(repo(self.slug, 500, "reddit cli", pushed=ago(0.1)))
        self.api.paths[f"repos/{self.slug}/commits/main"] = {"sha": "b" * 40}
        self.tool_card()
        url = "https://github.com/o/tool"
        code, out, err = self.run_cli("note", url, "--q", "ops/browser-ops", "--take", "skip", "--note", "not for us")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.store.card(self.slug).data["uses"][0]["take"], "skip")
        self.assertEqual(self.store.ledger()[-1]["verdict"], "card")
        self.assertIn("card: ", self.run_cli("show", url)[1])
        self.assertIn("o/tool", self.run_cli("updates", url + "/tree/main")[1].splitlines()[0])
        with cwd(Path(self.tmp.name)):
            code, _, err = self.run_cli("adopt", url, "--q", "ops/browser-ops", "--mode", "tool", "--into", "run.sh",
                                        "--ours", "1234abc")
        self.assertEqual(code, 0, err)
        code, _, err = self.run_cli("updates", "--done", url)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.store.card(self.slug).data["commit"], "b" * 12)


    def test_pick_reads_numbers_from_the_table_last_shown(self):
        self.api.add(repo("a/reddit-old", 900, "reddit logged-in browser cli", pushed=ago(8)))   # stale: hidden by default
        self.api.add(repo("b/reddit-cli", 300, "reddit cli", pushed=ago(0.2)))
        self.run_cli("scan", "ops/browser-ops", "--add", "github.com/b/reddit-cli github.com/a/reddit-old", "--quiet")
        out = self.run_cli("scan", "ops/browser-ops", "--show", "--all")[1]
        self.assertIn("2.", next(ln for ln in out.splitlines() if "a/reddit-old" in ln))
        code, _, err = self.run_cli("pick", "ops/browser-ops", "--skip", "2=too old")
        self.assertEqual((code, self.store.ledger()[-1]["repo"]), (0, "a/reddit-old"), err)
        self.run_cli("scan", "ops/browser-ops", "--show")
        code, _, err = self.run_cli("pick", "ops/browser-ops", "2")
        self.assertEqual(code, 1)
        self.assertIn("#2 is not in the last table (1-1", err)

    def test_ask_names_the_project_after_the_folder_as_an_id(self):
        repo_dir = Path(self.tmp.name) / "My App"
        (repo_dir / ".git").mkdir(parents=True)
        with cwd(repo_dir):
            code, out, err = self.run_cli("ask", "video", "Make promo videos", "--stage", "idea")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.store.project("my-app").data["code"], str(repo_dir.resolve()))
        self.assertEqual(self.store.check()[0], [])

    def test_a_reply_that_is_not_json_fails_only_its_search(self):
        def transport(method, url, headers, body):
            if "skills.sh" in url:
                return 200, {}, b"<!doctype html><title>Just a moment...</title>"
            if "npmjs" in url:
                raise http.client.IncompleteRead(b"{")
            return self.api(method, url, headers, body)
        cli.make_client = lambda args, store=None: Client(token="t", transport=transport, verbose=False)
        code, out, err = self.run_cli("scan", "ops/browser-ops", "--quiet")
        self.assertEqual(code, 0, err)
        self.assertIn("reply is not JSON: <!doctype html>", out)
        self.assertEqual(len(self.store.scans("ops", "browser-ops")), 1)

    def test_a_scan_reports_progress_on_stderr(self):
        code, out, err = self.run_cli("scan", "ops/browser-ops")
        self.assertEqual(code, 0, err)
        self.assertRegex(err, r"scan: \d+ of \d+ searches, 2\d API calls, \d+s so far, about \d+s left")
        self.assertNotIn("so far", out)
        self.assertNotIn("so far", self.run_cli("scan", "ops/browser-ops", "--quiet")[2])


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

    def test_the_readme_shows_media_and_demo_links_but_not_badges(self):
        readme = ("[![CI](https://github.com/a/b/actions/workflows/ci.yml/badge.svg)](https://github.com/a/b/actions)\n"
                  "# b\n\n![logo](docs/logo.png)\n<img src=\"docs/shot.png\" alt=\"main window\">\n![join](assets/wechat-group.jpg)\n"
                  "<img src=\"https://x.dev/tiny.png\" width=\"24\">\n\nhttps://github.com/user-attachments/assets/1234-abcd\n\n"
                  "Try the [live demo](https://b.dev/play) and [examples](./examples/basic). [Docs](https://b.dev/docs)\n"
                  "[![app](https://b.dev/hero.webp)](https://app.b.dev)\n"
                  '<video src="https://cdn.b.dev/demo.mp4"></video>\n[演示视频](https://www.bilibili.com/video/BV1xx)\n')
        media, sites = examine.readme_effect(readme, "a/b", "main")
        self.assertEqual([m["url"] for m in media], [
            "https://b.dev/hero.webp", "https://github.com/a/b/blob/main/docs/shot.png", "https://cdn.b.dev/demo.mp4",
            "https://www.bilibili.com/video/BV1xx", "https://github.com/user-attachments/assets/1234-abcd"])
        self.assertEqual(sites, ["https://app.b.dev", "https://b.dev/play"])   # docs and in-repo links are no site

    def test_clean_readme_drops_badges_and_html(self):
        out = examine.clean_readme('<p align="center"><img src="x"></p>\n# T\n[![b](u)](v)\n\n\n\nBody\n```\n<keep>\n```\n', 1000)
        self.assertNotIn("img", out)
        self.assertIn("<keep>", out)



class ReportFirstTests(Base):
    """Owner, 2026-10-19: stars relaxed per direction when it has few references; results become a verifiable effect
    in tiers (strong, mid, weak)."""

    def test_a_direction_with_few_references_shows_its_rows_down_to_20_then_10(self):
        rows = [("a/reddit-cli", 900, "Reddit CLI"), ("b/reddit-mini", 12, "Reddit CLI"), ("c/reddit-mid", 25, "Reddit app")]
        rows += [(f"t/twitter-{i}", 60, "Twitter tool") for i in range(4)] + [("t/twitter-30", 30, "Twitter tool"),
                                                                                ("t/twitter-12", 12, "Twitter tool")]
        rows += [(f"x/xhs-{i}", 100, "Xiaohongshu tool") for i in range(5)] + [("x/xhs-15", 15, "Xiaohongshu tool")]
        self.api.search[f"reddit pushed:>{discover.window(discover.HIDE)}"] = [
            self.api.add(repo(slug, n, desc, pushed=ago(0.1))) for slug, n, desc in rows]
        code, out, _ = self.run_cli("scan", "ops/browser-ops", "--quiet")
        self.assertEqual(code, 0, out)
        self.assertIn("relaxed (a direction with under 5 repos at 50+ stars shows its own rows down to 20 then 10): "
                      "reddit to 10 stars (only 1 at 50+, 2 at 20+); twitter to 20 stars (only 4 at 50+); "
                      "no repo at 10+ stars names logged-in browser, chrome extension", out)
        shown = {ln.split()[5] for ln in out.splitlines() if re.match(r"\s*\d+\.", ln)}
        self.assertTrue({"b/reddit-mini", "c/reddit-mid", "t/twitter-30"} <= shown)
        self.assertFalse({"t/twitter-12", "x/xhs-15"} & shown)                  # under 20 for twitter; xhs not relaxed
        self.assertIn("relaxed: reddit", next(ln for ln in out.splitlines() if "b/reddit-mini" in ln))
        saved = json.loads(self.store.scans("ops", "browser-ops")[-1].read_text(encoding="utf-8"))
        self.assertEqual([r["group"] for r in saved["relaxed"]][:2], ["reddit", "twitter"])
        code, out, err = self.run_cli("pick", "ops/browser-ops", "b/reddit-mini")          # no --low-stars needed
        self.assertEqual(code, 0, err)
        self.assertEqual(self.store.ledger()[-1]["low_stars"], "relaxed: reddit had under 5 repos at 50+ stars (floor 10)")
        code, _, err = self.run_cli("pick", "ops/browser-ops", "t/twitter-12")
        self.assertIn("no references: t/twitter-12 (12)", err)
        code, _, err = self.run_cli("note", "b/reddit-mini", "--q", "ops/browser-ops", "--take", "use",
                                    "--results", "https://x.com/someone/status/1")
        self.assertEqual(code, 0, err)
        self.assertIn("relaxed: reddit", self.store.card("b/reddit-mini").data["uses"][0]["low_stars"])
        self.assertFalse([w for w in self.store.check()[1] if "b/reddit-mini" in w and "stars" in w])

    def test_links_are_graded_and_the_gate_needs_mid_or_strong(self):
        from github_scout.store import best_tier, link_tier
        cases = [("https://b.dev/", "mid"), ("https://www.npmjs.com/package/b", "strong"),
                 ("https://github.com/a/b/blob/main/shot.png", "mid"), ("https://x.com/a/status/1", "mid"),
                 ("https://www.bilibili.com/video/BV1", "mid"), ("https://github.com/other/user-of-b", "mid"),
                 ("https://github.com/a/b#demo", "weak"), ("https://github.com/a/b/tree/main/examples", "weak")]
        self.assertEqual([link_tier(u, "a/b") for u, _ in cases], [t for _, t in cases])
        self.assertEqual((best_tier([], "a/b"), best_tier([], "a/b", installs=4200)), ("weak", "strong"))
        self.api.add(repo("a/b", 300, "Tool", pushed=ago(0.1)))
        for take in ("use", "adapt", "learn"):
            code, _, err = self.run_cli("note", "a/b", "--q", "ops/browser-ops", "--take", take,
                                        "--results", "https://github.com/a/b#demo")
            self.assertIn("a/b shows only text in its own repo", err)
        code, _, err = self.run_cli("note", "a/b", "--q", "ops/browser-ops", "--take", "later")
        self.assertEqual(code, 0, err)                                          # weak: later or skip only
        code, _, err = self.run_cli("note", "a/b", "--q", "ops/browser-ops", "--take", "learn",
                                    "--results", "https://www.bilibili.com/video/BV1")
        self.assertEqual(code, 0, err)

    def test_look_grades_the_verifiable_effect(self):
        sha = "c" * 40
        self.api.add({**repo("a/b", 300, "Tool", pushed=ago(0.1)), "homepage": "https://b.dev"})
        self.api.paths["repos/a/b/commits/main"] = {"sha": sha}
        self.api.paths[f"repos/a/b/git/trees/{sha}"] = {"tree": [{"path": "package.json", "type": "blob", "size": 9}]}
        self.api.paths["repos/a/b/contents/package.json"] = json.dumps({"name": "b-cli"})
        self.api.paths["repos/a/b/readme"] = "# b\n![shot](docs/shot.png)\n[Live demo](https://old.b.dev)\n"
        self.api.sites["https://b.dev"] = 200
        self.api.downloads["b-cli"] = 5400
        code, out, _ = self.run_cli("look", "a/b")
        self.assertEqual(code, 0, out)
        self.assertIn("verifiable effect: strong · live site (homepage) https://b.dev · npm b-cli: 5.4k downloads last "
                      "month https://www.npmjs.com/package/b-cli", out)
        self.assertIn("  mid: 1 image in the README: https://github.com/a/b/blob/main/docs/shot.png", out)
        self.assertIn("  did not answer: https://old.b.dev", out)
        self.assertEqual(self.api.token_hosts, {"api.github.com"})            # sites and npm never get the token
        self.api.sites["https://b.dev"] = 404
        self.api.downloads["b-cli"] = 3
        self.assertIn("verifiable effect: mid", self.run_cli("look", "a/b")[1])
        self.api.paths["repos/a/b/readme"] = "# b\nA tool. ![logo](logo.png)\n"
        self.assertIn("verifiable effect: weak, only a text description", self.run_cli("look", "a/b")[1])

if __name__ == "__main__":
    unittest.main()
