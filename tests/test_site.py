import datetime as dt
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "github-scout" / "scripts"))

from github_scout import registry, site  # noqa: E402
from github_scout.store import Store  # noqa: E402

EVIL = '<script>alert("summary")</script>'
CARD_BODY = """
# widget

## {idea}

Sends mail **fast** through `<smtp>` pools, with *retries*.

<img src=x onerror=alert(1)>

[bad](javascript:alert(1)) [docs](https://example.com/a?b=1&c=2) [spec](../projects/shop/project.md)

## {read}

- `src/send.py`
  - nested `a|b`
"""
ANSWER = """
# {ask}

## {where}
{stage_line}

## {answer}

### {one}
Take **acme/widget** as the mailer; see https://github.com/acme/widget.

| we have | they do |
|---|:---:|
| a cron job | a queue |

```python
print("<b>not bold</b>")
```

1. first
2. second
"""


def ago(days: int) -> str:
    return (dt.date.today() - dt.timedelta(days=days)).isoformat()


def build(tmp: str, lang: str) -> tuple[Path, str, dict]:
    store = Store.init(Path(tmp) / "reg", name="Shop <registry>", lang=lang)
    zh = lang == "zh"
    registry.new_project(store, "shop", "Shop backend", "one line")
    registry.new_question(store, "shop/mail", "How do we send email?", "working")
    registry.new_question(store, "shop/blank", "Untouched question", "idea")
    q = store.question("shop/mail")
    q.data.update(status="answered", picked=["acme/widget"], scanned="2026-10-01")
    q.body = ANSWER.format(ask="How do we send email?", where="我们现在" if zh else "Where we are",
                           stage_line="阶段：working" if zh else "Stage: working", answer="答案" if zh else "Answer",
                           one="一段话结论" if zh else "In one paragraph")
    store.save_question(q)
    meta = {"repo": "acme/widget", "license": "MIT", "stars": 12345, "created": "2024-01-01", "pushed": ago(200),
            "branch": "main", "commit": "abcdef1234567"}
    card = registry.new_card(store, meta, "software", "library",
                             [{"project": "shop", "question": "mail", "take": "use", "note": "the mailer"}],
                             [], "read", summary=EVIL)
    card.body = CARD_BODY.format(idea="思路" if zh else "The idea", read="先读" if zh else "Read first")
    card.data["results"] = ["https://example.com/demo.mp4", "javascript:alert(1)"]
    card.data["adopted"] = [{"project": "shop", "question": "mail", "mode": "vendor", "into": ["src/mail/pool.py"],
                             "from": ["src/send.py"], "at": "abcdef1234567", "date": "2026-10-02"},
                            {"project": "shop", "question": "mail", "mode": "port", "into": ["src/old.py"],
                             "dropped": "2026-10-03"}]
    store.save_card(card)
    registry.new_card(store, {"repo": "acme/fresh", "license": "MIT", "stars": 5, "pushed": ago(3), "commit": "1234567"},
                      "skill", None, [{"project": "shop", "question": "mail", "take": "skip", "note": "too small"}], [],
                      "look", summary="fresh one")
    store.append_ledger([
        {"date": "2026-10-01", "repo": "acme/widget", "project": "shop", "question": "mail", "verdict": "card"},
        {"date": "2026-10-01", "repo": "old/thing", "project": "shop", "question": "mail", "verdict": "short"},
        {"date": "2026-10-02", "repo": "old/thing", "project": "shop", "question": "mail", "verdict": "skip",
         "reason": "no push since 2024"},
    ])
    out = site.build_site(store, Path(tmp) / "out" / "index.html")
    text = out.read_text(encoding="utf-8")
    m = re.search(r'<script type="application/json" id="data">(.*?)</script>', text, re.S)
    return out, text, json.loads(m.group(1))


class SiteTests(unittest.TestCase):
    def test_page_is_self_contained_and_carries_the_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, text, data = build(tmp, "en")
            self.assertTrue(out.is_file())
            self.assertTrue(text.startswith("<!doctype html>"))
            self.assertEqual(data["counts"], {"questions": 2, "cards": 2, "verdicts": 3, "skipped": 2})
            self.assertEqual([c["id"] for c in data["cards"]], ["acme/widget", "acme/fresh"])
            self.assertIsNone(re.search(r"<(?:script|link|img|iframe)\b[^>]*\b(?:src|href)=", text))
            self.assertNotIn("@import", text)
            self.assertNotIn("url(", site.CSS)
            for call in ("fetch(", "XMLHttpRequest", "import("):
                self.assertNotIn(call, site.JS)

    def test_cards_carry_their_result_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, data = build(tmp, "en")
            self.assertEqual([c["results"] for c in data["cards"]], [["https://example.com/demo.mp4"], []])
            self.assertEqual(data["ui"]["results"], "Verifiable effect")

    def test_registry_text_cannot_inject_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, text, data = build(tmp, "en")
            self.assertNotIn("<script>alert", text)
            self.assertEqual(text.count("<script"), 2)              # the data and the page script
            self.assertNotIn("</script>", text.split('id="data">', 1)[1].split("</script>", 1)[0])
            self.assertNotIn("<registry>", text)
            widget = data["cards"][0]
            self.assertEqual(widget["summary"], EVIL)                # shown as written, as text
            body = widget["body"]
            self.assertIn("&lt;img src=x onerror=alert(1)&gt;", body)
            self.assertNotIn("<img", body)
            self.assertNotIn("javascript:", body.replace(">bad<", ""))
            self.assertIn("<code>&lt;smtp&gt;</code>", body)
            self.assertIn('href="https://example.com/a?b=1&amp;c=2"', body)
            self.assertIn('href="../reg/projects/shop/project.md"', body)

    def test_questions_answers_and_staleness(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, data = build(tmp, "en")
            mail, blank = data["questions"]
            self.assertEqual((mail["ref"], blank["ref"]), ("shop/mail", "shop/blank"))  # answered first
            self.assertEqual(mail["picked"], ["acme/widget"])
            self.assertEqual([(r["repo"], r["mark"]) for r in mail["looked"]],
                             [("acme/widget", "use"), ("acme/fresh", "skip"), ("old/thing", "skip")])
            self.assertEqual(mail["scanned"], "2026-10-01")
            self.assertIn("it works", mail["stageHelp"])
            answer = mail["answer"]
            self.assertTrue(answer.startswith("<h3>In one paragraph</h3>"))
            self.assertIn("<strong>acme/widget</strong>", answer)
            self.assertIn('<th style="text-align:center">they do</th>', answer)
            self.assertIn("&lt;b&gt;not bold&lt;/b&gt;", answer)
            self.assertIn("<ol><li>first</li><li>second</li></ol>", answer)
            self.assertIn('href="https://github.com/acme/widget"', answer)
            self.assertNotIn("Answer", answer)
            self.assertEqual(blank["answer"], "")                    # unfilled template: nothing to show
            self.assertNotIn("What we have", blank["context"])
            self.assertIn("Stage: idea", blank["context"])
            widget, fresh = data["cards"]
            self.assertTrue(widget["stale"])
            self.assertGreaterEqual(widget["age"], 6)
            self.assertFalse(fresh["stale"])
            self.assertTrue(widget["idea"].startswith("Sends mail fast through <smtp> pools"))
            self.assertNotIn("<h3>widget</h3>", widget["body"])       # the title is the row itself

    def test_cards_say_where_they_were_adopted(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, text, data = build(tmp, "en")
            widget, fresh = data["cards"]
            self.assertEqual(widget["adopted"], [{"project": "shop", "question": "mail", "mode": "vendor",
                                                  "into": ["src/mail/pool.py"]}])          # the dropped one is left out
            self.assertEqual(fresh["adopted"], [])
            self.assertEqual(data["ui"]["adoptedIn"], "adopted in {project} ({mode})")
            self.assertIn("c.adopted.map(", site.JS)
        with tempfile.TemporaryDirectory() as tmp:
            _, _, data = build(tmp, "zh")
            self.assertEqual((data["ui"]["adoptedIn"], data["ui"]["labels"]["mode"]["vendor"]), ("已引入 {project}（{mode}）", "复制"))

    def test_ui_follows_the_registry_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, text, data = build(tmp, "zh")
            self.assertIn('<html lang="zh-CN">', text)
            self.assertIn(">问题</a>", text)
            self.assertIn("2 个问题 · 2 张卡片 · 账本 3 条 · 跳过 2 个仓库", text)
            self.assertEqual(data["ui"]["labels"]["take"]["use"], "采用")
            self.assertTrue(data["questions"][0]["answer"].startswith("<h3>一段话结论</h3>"))
            self.assertEqual(data["questions"][1]["answer"], "")
        with tempfile.TemporaryDirectory() as tmp:
            _, text, data = build(tmp, "en")
            self.assertIn('<html lang="en">', text)
            self.assertIn(">Questions</a>", text)
            self.assertIn("2 questions · 2 cards · 3 verdicts in the ledger · 2 repos skipped", text)


class MarkdownTests(unittest.TestCase):
    def test_blocks(self):
        html = site.markdown("# T\n\nline one\nline two  \nbroken\n\n> quoted\n> more\n\n---\n\n"
                             "- [x] done\n- [ ] todo\n\n```\n<raw>\n```\n")
        self.assertIn("<h3>T</h3>", html)
        self.assertIn("<p>line one line two<br>broken</p>", html)
        self.assertIn("<blockquote><p>quoted more</p></blockquote>", html)
        self.assertIn("<hr>", html)
        self.assertIn('<li class="task"><input type="checkbox" disabled checked> done</li>', html)
        self.assertIn("<pre><code>&lt;raw&gt;</code></pre>", html)

    def test_nested_lists_and_cjk_lines(self):
        html = site.markdown("- a\n  - b\n    - c\n- d\n\n第一行\n第二行")
        self.assertIn("<ul><li>a\n<ul><li>b\n<ul><li>c</li></ul></li></ul></li><li>d</li></ul>", html)
        self.assertIn("<p>第一行第二行</p>", html)

    def test_inline(self):
        html = site.markdown("**b** *i* _u_ snake_case_name ~~s~~ `a<b` \\*lit\\* [x `y`](https://e.com) <https://f.com>")
        for want in ("<strong>b</strong>", "<em>i</em>", "<em>u</em>", "snake_case_name", "<del>s</del>",
                     "<code>a&lt;b</code>", "*lit*", '<a href="https://e.com" target="_blank" rel="noopener noreferrer">x <code>y</code></a>',
                     '<a href="https://f.com"'):
            self.assertIn(want, html)

    def test_unsafe_links_become_text(self):
        for url in ("javascript:alert(1)", "JAVASCRIPT:alert(1)", "data:text/html,x", "vbscript:x", "//evil.com/x"):
            html = site.markdown(f"[go]({url})")
            self.assertEqual(html, "<p>go</p>", url)
        self.assertEqual(site.markdown('[x](https://a.com/"onmouseover="y)'),
                         '<p><a href="https://a.com/&quot;onmouseover=&quot;y" target="_blank" rel="noopener noreferrer">x</a></p>')


if __name__ == "__main__":
    unittest.main()
