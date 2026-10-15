# Workflow, with a worked example

The example is a real case. An operations project needed to read and post on Reddit, X and
Xiaohongshu through a logged-in browser, with no model in the loop. Agents searched for
"social media automation" and "自媒体 运营", found old bots and tutorials, and started writing
their own scraper. The right tool, a 30k-star project created that year, described itself as
"Make any website into CLI & use your logged-in browser by AI agent". None of the agents'
words appear in that sentence. A person found it while scrolling X.

## 1. The question

A weak question asks for a tool: "find a social media automation tool". It gets tools for
someone else's problem.

A strong question asks for a result, says where we stand, and what is not good enough:

```
reuse-first ask ops/browser-ops "Drive our logged-in accounts on Reddit, X and Xiaohongshu from scripts, no model clicking pages" --stage prototype
```

Then, in the file: what we have (`tools/reddit/chrome.ts` drives Chrome through a model; one run
costs 580k tokens and 16 subreddits get blocked), and the vocabulary:

```yaml
entities: ["reddit", "xiaohongshu|小红书|rednote", "twitter|x.com", "bilibili", "zhihu"]
mechanisms: ["logged-in browser", "chrome extension", "browser cookies", "CDP"]
forms: [cli, mcp, skill]
problems: ["social media automation", "自媒体 自动化", "website to cli"]
```

Why each part works:

- **Entity pairs** find multi-platform tools: a tool that supports both Reddit and Xiaohongshu
  names both in its README; a tutorial about one platform does not. `"reddit xiaohongshu"
  in:readme` put the target first.
- **Mechanisms** find a tool by how it works. `"logged-in browser"` also put it first.
- **Topics plus a 12-month window** find young projects that best-match search buries.
- **Other-language synonyms** (`小红书`) reach communities that do not write in English.
- **Problem phrases** find the least. Keep them short.

Writing mechanisms: picture the solution's README. What would it say it uses? "headless
Chrome", "Remotion", "an MCP server", "SQLite FTS5", "whisper.cpp". Write those words.

## 2. Reading the scan table

```
  #  score  stars created   pushed  repo  description  [lenses] fit
  1.  11.6  64.2k  26-01 26-10-13  mvanhorn/last30days-skill  AI agent skill that researches ...  [EPMCTRS] fit 1
  4.   9.5    282  26-10 26-10-14  aindeev/agent-chrome-relay  Let your AI agents use your Chrome ...  [T] fit 3
```

- `score` orders the table; it is not a verdict. Relevance counts most, then life: a 282-star
  repo created this month that matches three vocabulary groups ranks above a famous old one.
- `fit` is the number of vocabulary groups in the repo's own name, description and topics.
- Lens letters show why a row is there; several letters mean several independent routes found it.
- The header line says how many repos were dropped (no push in 12 months) or hidden (6 months).
- `seen:skip@other/question` means another question already judged it; read that reason first.
- The `rising` block under the table (`h1`, `h2`...) holds new repos growing fast that match no
  vocabulary. Words cannot find a tool whose description never names your use, so read these
  by what they make. They are counted in `pick --rest` like the table rows.

Pick about 5–10 rows. A wrong pick costs a 1.3k-token look; a right one skipped is the whole
reason this skill exists.

## 3. Widening the search

The API does not see repos without good metadata, projects announced on social media, or
projects hosted elsewhere. Do one pass outside GitHub search:

| source | query patterns |
|---|---|
| web | `site:github.com <entity> <mechanism>` · `site:github.com <entity> cli OR mcp OR skill` |
| other languages | the same with `小红书`, `自动化`, `开源`, Japanese, Korean terms |
| forums | `<problem> github` on Reddit, Hacker News, V2EX, Zhihu |
| X | posts that mention an entity and link github.com; builders in the field |
| the user | links they shared or bookmarked |

```bash
reuse-first scan ops/browser-ops --add notes.txt --note "web: site:github.com xiaohongshu cli"
pbpaste | reuse-first scan ops/browser-ops --add - --note "X: xiaohongshu github"
reuse-first scan ops/browser-ops --expand someone/awesome-browser-agents
```

## 4. Looking, reading, trying

- `look` shows activity next to the facts: commits in 30 days, releases in 90, the top
  contributor's share. A one-person repo pushing daily is normal now; a team repo gone quiet is
  a warning.
- `look --source` maps the code in tokens, so you read `clis/reddit/*.js` and skip the other
  100 adapters.
- Look for the idea before the code: what decision did they make that we would not have? For
  OpenCLI it was driving the browser through an extension that lives in the user's own profile,
  so it inherits every login and never needs the debugging port.

## 5. The answer

Write it in the question file. A good one, for a project at `prototype`:

> **In one paragraph.** Use OpenCLI for reads on Reddit and Xiaohongshu (pinned v1.8.8). Write
> our own Reddit comment adapter on its plugin API, because its `reddit read` drops comment ids.
> Keep posting where it is; nothing found posts without a model and survives rate limits.
>
> **Ideas worth taking.** (1) An extension inside the user's profile instead of a debugging port
> (OpenCLI `extension/manifest.json`): inherits logins, works with Chrome 136+. (2) Exit codes
> as a contract (`docs/guide/exit-codes.md`: 66 empty, 69 extension missing, 77 needs login):
> our scheduler can route "needs login" to a human without parsing text.
>
> **Against what we have.** | model-driven page reading, 580k tokens a run | one JSON request per subreddit | ... | take |

That tells the next agent what to run, what not to rebuild, and where the gap is.

## 6. Upkeep

- Before relying on a repo again: `updates --project <p>`.
- A `review` row means a watched path changed, a release came out, the repo was archived or
  relicensed, or it stopped being maintained. `updates --diff <repo>`, update the card, `updates --done <repo>`.
- Rescan a question with `scan`; `scan --show` merges all scans and hides what was decided.
