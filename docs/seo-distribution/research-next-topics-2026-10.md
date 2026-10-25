# What to write next on serbyn.io (research run 2026-10-25)

Method: Google autocomplete (98 seeds + 156 letter-expansion queries), GitHub issue search via gh, WebSearch for 8 questions, page fetches of 11 pages. Raw files: scratchpad `seeds.json`, `le.txt`. Autocomplete shows what people type, not volume. Treat counts as a relative signal.

## 1. Autocomplete demand map

98 seeds (7 tools x 14 modifiers). 60 returned nothing, 38 returned something.

Seeds with zero suggestions, by tool:
- "ai coding agent" x all 14 modifiers except cost: 0 (13 of 14 empty).
- "cursor agent": 12 of 14 empty (only hooks, cost, observability return).
- "coding agent": 9 of 14 empty. "llm agent": 8 of 14 empty.
- "codex cli": 10 of 14 empty (empty: posttooluse, session logs, audit, verification, tests pass, says done, lying, reliability, evals).
- "copilot agent": 7 of 14 empty.
- "claude code": only "tests pass" and "says done" are empty. "lying" and "reliability" return only themselves (1 suggestion each, no expansions).
- Across every tool, "tests pass", "says done", "lying" have no demand as autocomplete phrases. Nobody types these queries the way the posts name them. The pain is searched as errors and "how do I" questions, not as "false green".

Strong seeds (letter expansion, a to z; unique suggestions): claude code hooks 195, claude code verification 109 (mostly login-code noise, see below), claude code audit 36, claude code stop hook 15 (13 of 26 letters empty), claude code posttooluse 5 (22 of 26 empty), codex cli hooks 4 (21 of 26 empty).

| Cluster | Example suggestions | Type |
|---|---|---|
| Hooks how-to and examples | "claude code hooks examples", "claude code hooks tutorial", "how to create claude code hooks", "claude code hooks best practices", "claude code hooks explained" | Learning (largest, about 45 of 195) |
| Hooks not working | "claude code hooks not working", "not firing", "not running", "claude code stop hook not working", "claude code stop hook error json validation failed" | Problem |
| Hook errors by event | "claude code posttooluse bash hook error", "posttooluse edit hook error", "stop hook error failed with non-blocking status code" | Problem |
| Stop hook specifics | "claude code stop hook example", "stop_hook_active", "subagent stop hook", "claude_code_stop_hook_block_cap" | Learning plus a few problems |
| Hooks comparisons | "claude code hooks vs skills", "hooks vs commands", "rules vs hooks", "claude code hooks codex" | Evaluation |
| Hooks "best/awesome" | "best claude code hooks reddit", "most useful claude code hooks", "claude code hooks awesome", "must have hooks" | Evaluation |
| Hooks as notification | "hooks notification sound", "ntfy", "telegram", "afplay", "macos notification" | Learning (utility, not our topic) |
| Hooks observability | "claude code hooks multi agent observability", "claude code observability dashboard", "observability github" | Evaluation / tools |
| Codex hooks | "does codex cli have hooks", "does codex cli support hooks", "hooks in codex cli" | Learning, yes/no question |
| Audit | "claude code audit logs", "audit logging", "audit trail", "enterprise audit logs" | Compliance. Also noise: "seo audit", "security audit", "code audit skill" |
| Verification | "claude code verification loop", "verification agent", "verification skill", "verification failed" | Learning. Most others are login noise ("claude verification code not working") |
| Evals / analytics / cost | "claude code evals skills", "claude code analytics dashboard", "claude code /cost command", "cost per million tokens", "codex cli cost", "cursor agent cost comparison" | Cost is the largest family (10 of 10 slots filled for claude code, codex cli, coding agent) |

Reading: hooks has real demand, and about one quarter of it is problems. Verification and "agent lies" have almost no autocomplete demand under those words. Cost has demand under almost every tool. "does codex cli have hooks" is a literal question that autocompletes.

## 2. GitHub issues as pain signal

Full-text counts are capped at 1000 by the API and noisy (body matches). Title-only counts are cleaner. Date range: oldest match Feb 2025 (claude-code) and Apr 2025 (codex), newest Oct 2026.

| Query | claude-code (full text / title) | codex (full text / title) |
|---|---|---|
| "tests pass" | 460 / 4 | 608 / 1 |
| "claims tests" | 18 / n.a. | 8 / n.a. |
| "said it ran", "didn't run tests" | 0 / n.a. | 0 and 1 / n.a. |
| "stop hook" | 1000+ / 283 | 128 / 26 |
| PostToolUse | 1000+ / 195 | 138 / 27 |
| "hook not working" | 23 / n.a. | 0 / n.a. |
| hooks | 1000+ / 1000+ | 1000+ / 188 |
| "false success" (title) | 6 | 0 |
| "without running" (title) | 8 | 5 |

Representative issues (reactions, state):
- Stop hook, claude-code: #58192 "/goal Stop hook fails with Prompt is too long" (14, closed, May 2026); #38651 "Stop hook causes empty result in print mode" (11, closed, Mar 2026); #58558 "/goal Stop hook fails with JSON validation failed" (10, closed). https://github.com/anthropics/claude-code/issues/58192
- Stop hook, codex: #20783 "Blocking stop hook continuation can fail with invalid local message id" (4, open); #53574 "Interactive /review appears to bypass the root Stop hook" (0, open, Oct 2026). https://github.com/openai/codex/issues/20783
- PostToolUse, claude-code: #34692 hooks do not fire for subagent tool calls (7, closed); #19009 exit code 2 shows "blocking error" but does not block (opened Jan 2026, closed Feb 2026); #33656 "hook error" shown when the Bash command fails but the hook exits 0. https://github.com/anthropics/claude-code/issues/34692
- Hook not working: #12151 plugin hook output not captured (31 reactions, open); #10373 SessionStart hooks not working (19, open); #6305 Pre/PostToolUse hooks not executing (16, open, 41 comments). https://github.com/anthropics/claude-code/issues/6305
- Codex demand for hooks: #2109 "Event Hooks" (688 reactions, closed Aug 2025, since shipped); #21753 "Full Claude Code Hook Parity (29+)" (50, open, May 2026). https://github.com/openai/codex/issues/2109
- False claims, claude-code: #64329 "Opus 4.8 stated multiple unverified claims as fact" (7, closed); #47483 "Opus 4.6 quality regression, confident but unverified claims increasing" (3, closed); #53297 WebFetch fabricates confident claims (8, closed).

Findings:
- The "agent claims tests pass" pain is almost absent as a filed issue (4 and 1 title hits). It lives in blogs and Reddit, not in issue trackers. That means no authoritative public answer, and no complaint-driven search traffic yet.
- Hook pain is large and concrete: hooks not firing in subagents, exit-code semantics, "hook error" labels, Stop hook loops and JSON validation. Many are closed, so the answers are scattered across closed threads. No single page explains the exit-code and JSON rules across Stop and PostToolUse.
- Codex hooks are new (issue closed Aug 2025, feature behind a flag per third-party posts) and Stop-hook bugs are open. Few answers.
- Reaction counts on pure false-claim issues are low (3 to 8). The wider "model quality regression" threads have thousands, so the audience cares about reliability but frames it as model quality.

## 3. Answer-engine check (WebSearch top domains)

| Question | Top domains returned | Data present? |
|---|---|---|
| what is a false green in AI coding agents | docs.rs (falsegreen crate, 6 versions), rdworldonline, greenpt.com. The engine said it found no established definition. | None. The term is open. |
| does codex cli have hooks | codex.danielvaughan.com (2 posts), developers.openai.com (de, es docs), lilting.ch, skills.sh, pypi | Docs only. A comparison post says "no hooks", now outdated: conflicting answers. |
| claude code stop hook example run tests | dev.to, mintlify, wmedia.es, web-developpeur.com, datacamp, substack, claudefa.st, gumroad | No measurements. |
| how to audit claude code session logs | dev.to, pypi (ctxprof, cc-audit), tecmint, aident.ai, brycewatson.com, nylas, mcpmarket | Tools and how-tos. No audit results. |
| why does my ai coding agent say tests pass when they fail | neurips.cc, producthunt, pkg.go.dev, pypi (claimproof), github (groundtruth), dev.to x2, aident.ai | Mostly tools. One NeurIPS paper, one dev.to anecdote. |
| claude code posttooluse hook error | github issues, claudeissues.com (5 pages), datacamp, thepromptshelf.dev | Issue threads only. |
| ai coding agent verification loop | zartis, kenwalger.com, engineering.atspotify.com, substack, sonarsource (3 locales), regolo.ai | Spotify has process data; others opinion. |
| how to measure ai coding agent reliability | arxiv (4 papers), omniassist, dev.to, huggingface, normaltech | Papers with benchmarks; no field data from real sessions. |

Page checks (fetched, lengths are estimates):

| Page | Words | Format | Measured data |
|---|---|---|---|
| aident.ai verify-ai-coding-agent-tests-pass | 1,500-1,700 | H1 matches query, definition first, 7 steps, no FAQ, product promo | None (only product dashboard numbers) |
| dev.to elberacasa "Your AI agent is lying about its tests" | 500-550 | Anecdote opener, 3 headings, no FAQ | One anecdote: 14 claimed, 3 passed |
| wmedia.es Claude Code hooks guide | 2,000-2,200 | Personal opener, 27-entry TOC, 15 events table, no FAQ | None |
| claudefa.st stop hook enforcement | 900-1,000 | One-line summary, quick-win code block, 12 H2s, no FAQ | None |
| brycewatson.com session logs | 900 | Problem first, definition in para 3, no FAQ | One count (6 vs 58 entries) |
| developers.openai.com/codex/hooks | not read | Redirects to learn.chatgpt.com/docs/hooks (308) | n.a. |

Where answers exist without data: stop hook examples (8 pages, 0 measurements), "tests pass" explainers (0 first-party rates), session log auditing (tools but no results), Codex hooks (docs plus conflicting blogs). The only measured field data seen anywhere are the dev.to 249-session audit (below) and Vitalii's own posts.

## 4. Peer and competitor scan

| Page | Who | Claim | Own data | Sells | Structure |
|---|---|---|---|---|---|
| dev.to/sjh9714 (Aug 2026) | JinHyuk Sung, builds MergeWarden, tool "red-handed" | Problem is unreadable verification, not lying | Yes: 249 sessions, 124 "tests pass" claims, 117 had a test run, 7 had none; 0 confirmed, 7 suspicious; 5 false-accusation modes found | Nothing (MIT tool) | About 1,900 words, 8 sections, first person |
| specstory.com/learning/verification/coding-agent-done-claims (updated 2026-09-29) | SpecStory | "Done" is a claim from the same process; cites 65-69% unbacked from the dev.to-style audit (516 claims) and METR 7% | None, quotes others | RunStory (private alpha, independent runner) | About 1,800 words, question title, 4-question FAQ, about 15 internal links |
| scale100.co/false-floors/truth (v0.5, 2026-08-14) | Scale100 "False Floors" registers | 15 claim types: 9 detectable by diffing a committed artefact, 6 judgement-only | Own incidents (8 of 15), one codebase, internally inconsistent counts | Newsletter, trust-check tool, enterprise mapping | 6,000-7,000 words, reference register |
| paelladoc.com/blog/false-success-claims | PAELLADOC (@jlcases, Valencia) | Not lying, next-token prediction; verify outside the model | None; cites TestJack arXiv 34.4% | Mac app, free up to 3 projects | About 1,100 words, 4-question FAQ |
| regolo.ai build-verify loop | Regolo, EU inference provider | Gate in control flow, not prompt | Unsourced: 34% of agent PRs fail CI, 20-30% extra tokens | Inference API, trial | 2,500-3,000 words, 6-question FAQ, promo blocks |

The pattern: five publishers in 3 months target the same claim, "agent says done without proof". Only one has audited real sessions, and it has 12 sessions with claims. Vitalii's 948 claims in one week, plus hand-checking 46 flags, is the largest measured set I found. Nobody else reports the precision of their own detector (3 of 46) except the dev.to author's false-positive notes.

SpecStory hub: https://specstory.com/learning/verification/ exists. It is a hub with 25 article pages plus a glossary of 26 terms. Sections: start here (1), concepts (11), how-to (2), comparisons (2), common questions (6), failures (3). Titles are questions ("What is a false pass (false green test)?", "Why do coding agents say done when the code does not work?"), each with a one-sentence summary, and pages cross-link heavily. Pages are 9-minute reads, end with a short FAQ, and carry a product CTA. This is a topical cluster built for answer engines. They already own "false green test" at /false-pass.

## 5. Ranked next topics

Scores are 1-5 (demand / uniqueness / audit fit). Total in brackets.

1. **What is a false green in AI coding agents?** Format: short answer page, 400-700 words, definition in the first sentence, then the 948 / 315 / 46 / 3 numbers, then 4-question FAQ.
   - Queries: none in autocomplete (0 of 98 seeds). Win by being the definition page for the term. Search returned the falsegreen crate and no definition.
   - Unique data: yes, the weekly numbers and the "43 of 46 flags were wrong" precision result.
   - Competitors: specstory /false-pass.
   - Scores: 2 / 5 / 5 [12]. Low search demand, but owns the term for answer engines.

2. **Does Codex CLI have hooks, and can they stop a false "done"?** Short answer page, 500 words.
   - Queries: "does codex cli have hooks" (4 suggestions), "openai codex cli hooks". Search answers conflict (one says no hooks), Stop-hook issues are open (#20783, #53574).
   - Unique data: plugin works on Codex (release 0.2.1 Codex patches); data on exit-code-less runs. Say what a Stop hook can and cannot see in Codex.
   - Competitors: danielvaughan.com, OpenAI docs, lilting.ch.
   - Scores: 4 / 4 / 4 [12].

3. **How do I make a Claude Code Stop hook run tests before it says done?** Long post with a working script, about 1,200 words, plus the enforced-checkpoint result.
   - Queries: "claude code stop hook example", "stop_hook_active", "stop hook not working", "stop hook error json validation failed" (13 of 26 letters empty, so a narrow family; hooks overall 195).
   - Unique data: "0 of 40 silent failures enforced vs 22 of 40 optional" fits exactly.
   - Competitors: wmedia.es, claudefa.st, web-developpeur, datacamp. None measure.
   - Scores: 5 / 4 / 4 [13].

4. **Why does my AI coding agent say tests pass when they did not run?** Long post, about 1,500 words, question title, definition first.
   - Queries: no autocomplete ("tests pass" empty everywhere), but the 8 WebSearch results show active publishing (7 pages). Issue pain: low.
   - Unique data: 948 claims, 315 unverified, 3 of 46 held up. Strongest first-party set seen.
   - Competitors: aident, specstory, dev.to x2, paelladoc, regolo.
   - Scores: 2 / 5 / 5 [12]. Lowest search demand, highest authority; cited by answer engines, not by Google autocomplete.

5. **How do I audit my Claude Code session logs?** Long how-to, about 1,200 words, with `analysis/audit.py`.
   - Queries: "claude code audit logs", "audit trail", "enterprise audit logs" (36 audit suggestions, many noise). Search returns tools only.
   - Unique data: week of logs and claim counts; the local audit shows only shareable counts.
   - Competitors: cc-audit, ctxprof, ccusage, aident, nylas.
   - Scores: 3 / 4 / 5 [12]. Best lead into the paid audit.

6. **Claude Code hooks not firing: the five causes.** Short answer page, 600 words, one table (subagents, matcher, exit code 2 vs 1, JSON, plugin hooks).
   - Queries: "claude code hooks not working / not firing / not running", "posttooluse hook error", "stop hook error". Issues: 283 stop hook titles, 195 PostToolUse titles, #6305 (16 reactions, open).
   - Unique data: none beyond experience. Cite issue numbers.
   - Competitors: claudeissues.com mirrors, datacamp.
   - Scores: 5 / 2 / 2 [9]. Traffic play; risk of off-topic audience.

7. **What is a verification loop for an AI coding agent, and what does it cost?** Long post, 1,500 words.
   - Queries: "claude code verification loop", "verification agent". Search shows zartis, sonar, spotify, regolo.
   - Unique data: self-verification 1.64x cost and caught nothing; "0% vs 100% false greens" over 12-step tasks.
   - Competitors: Spotify engineering, sonar, regolo (unsourced numbers).
   - Scores: 3 / 5 / 4 [12].

8. **How do I measure whether my AI coding agent is reliable?** Long post, 1,500 words, with the 58-run calibration ledger.
   - Queries: "llm agent reliability" (2 suggestions), "claude code evals" (6), "coding agent evals" (2). Arxiv papers dominate.
   - Unique data: 58 runs, about 93% autonomous pass, small n; 9 times the eval lied.
   - Competitors: arxiv 2602.16666, 2608.14711, normaltech.
   - Scores: 2 / 4 / 3 [9].

Cost is the biggest autocomplete family but Vitalii has only per-check cost data (1.64x), so a "cost of verification" angle sits inside topic 7 rather than a general cost page.

Suggested order: 3, 2, 5, then 1, then 4, 7. Write 1 as a short hub-style entry and link the rest to it, copying the SpecStory hub pattern (question titles, one-sentence summaries, 400-700 word pages), since Google indexes only the home page and a hub gives crawlers a link path.

Caveats: autocomplete is US-English and personalized by nothing; suggestion counts cap at 10 per query; WebSearch is one engine, not Perplexity or ChatGPT; word counts come from a fetch-and-summarize model and are estimates; GitHub counts cap at 1000.

## 6. Repeat monthly

```
# ac.py (98-seed loop) is in the session scratchpad; copy it into analysis/ before reuse
curl -s "https://suggestqueries.google.com/complete/search?client=firefox&q=claude+code+stop+hook+a"
gh search issues '"stop hook"' --repo anthropics/claude-code --match title --limit 1000 --json number | jq length
gh search issues 'PostToolUse' --repo openai/codex --match title --limit 1000 --json number | jq length
gh search issues '"tests pass"' --repo anthropics/claude-code --sort reactions --limit 5 --json number,title,commentsCount
curl -s https://specstory.com/learning/verification/ | grep -o 'learning/verification/[a-z-]*' | sort -u | wc -l
```

Then re-run WebSearch for the 8 questions and diff the domains against this file. Keep the seed list and the 6 letter-expansion seeds fixed so month-on-month changes are comparable; log the counts in one table per month.
