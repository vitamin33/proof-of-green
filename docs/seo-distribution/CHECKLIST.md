# Distribution checklist (owner actions)

Prepared 2026-10-25. Nothing below has been published; each item is a decision for you.

## 1. Push the two README branches (links to serbyn.io)

Both are committed locally and not pushed. Review the diff, then push:

```
git -C ~/development/ascend-core push -u origin readme/serbyn-link
```

```
git -C ~/research/vitamin33-profile-readme push -u origin readme/serbyn-link
```

Then merge each into main on GitHub (or push to main directly, both are single-commit README changes). The profile README still says "serbyn.pro" was the portfolio; that domain no longer answers, so the branch replaces it with serbyn.io.

Already pushed: proof-of-green README links the post, /audit and serbyn.io (commit 165a639 on main). The old "team report" link pointed at serbyn.io/proof-of-green, which returns 404, and now points at /audit.

## 2. dev.to canonical reposts

For each file, open https://dev.to/new, paste the whole file (dev.to reads the front matter: title, tags, canonical_url, published: false), check the preview, then set `published: true` when you are happy.

- `docs/seo-distribution/devto-proof-of-green.md`, canonical https://serbyn.io/blog/proof-of-green-checks-every-done. The five SVG diagrams are replaced by one italic figure line each with the caption text; the live post has the drawings.
- `docs/seo-distribution/devto-enforced-checkpoint.md`, canonical https://serbyn.io/blog/enforced-checkpoint-0-of-40-silent-failures-vs-22-of-40. The chart image is loaded from serbyn.io.

Wait until Google has indexed the serbyn.io URL before publishing the repost, so the canonical is honoured (check with `site:serbyn.io/blog/<slug>`).

## 3. Comment on the dev.to post about 249 sessions

File: `docs/seo-distribution/comment-devto-249-sessions.md`. Paste under https://dev.to/sjh9714/i-audited-249-of-my-own-ai-coding-sessions-the-problem-wasnt-lying-4f42. Read the post first; the comment asks the author one question about their 117 "test ran first" claims.

## 4. LinkedIn

File: `docs/seo-distribution/linkedin-featured.md`. Pick one of the three Featured titles and set the Featured link on the profile to the post. The post text is 7 short lines and ends with the link.

## 5. Bing Webmaster Tools (feeds ChatGPT search and Copilot)

1. Open https://www.bing.com/webmasters and sign in with a Microsoft account.
2. Choose "Import from Google Search Console" and pick the `https://serbyn.io/` property. This verifies the site without a DNS change.
3. If import is not offered, add the site `https://serbyn.io` and verify with the DNS or meta-tag option.
4. Sitemaps, submit `https://serbyn.io/sitemap.xml`.
5. URL submission: paste the 13 post URLs and `/audit`, `/writing` (quota is 10 per day on a new site; do the rest the next day).

## 6. Google Search Console

Being handled in the main session: sitemap submission and index requests for the top URLs. The domain property `sc-domain:serbyn.io` is owned by another account; if you know which one, add serbyn.vitalii@gmail.com as a user there, or ignore it and keep using the `https://serbyn.io/` property.

## Status 2026-10-25 (evening)

Done from the owner's Chrome: Bing Webmaster Tools verified via meta tag, sitemap submitted (Processing); Vercel Web Analytics enabled (Hobby, data starts now); both dev.to reposts published with canonical to serbyn.io; comment posted under the 249-sessions post; both README PRs merged; seo/round1 deployed to production.

Open: IndexNow returns HTTP 403 for the key `3d40b1ad44886b9950c3fb0356cf6ebc` on both api.indexnow.org and bing.com, although the key file is served 200 text/plain. The first production build got 202. Check the IndexNow page in Bing Webmaster Tools in a day; if still 403, generate the key inside Webmaster Tools and replace the file. LinkedIn post text is in linkedin-post.txt (owner publishes). Google URL Inspection quota: request /about and the four new answer pages on 2026-10-26. PostHog: the only project this account can see is Crest (usecrest.io); serbyn.io events are not in it, so Vercel Analytics is the traffic source going forward.

## Status 2026-10-25 (late)

- Google: both long posts (proof-of-green, enforced-checkpoint) show "URL is on Google" in Search Console, so the dev.to canonical copies came after the originals were indexed. Nothing to undo.
- IndexNow: a key generated in Bing's own generator (9b2cc94f75734fdbad0f12e7cd94d7bd) still gets HTTP 403 from api.indexnow.org and bing.com, while Seznam accepts the same key with 200. The 403 is on Bing's side for this host. Workaround applied: all 28 site URLs submitted through Bing Webmaster Tools, URL Submission (quota 100 per day). The post-build ping stays in place and never fails the build.
- Google URL Inspection: quota for the day is used; /about and the four answer pages are in the submitted sitemap and get requested on 2026-10-26. The domain property cannot be verified from here: DNS is at Namecheap, not Vercel.

## Status 2026-10-26

Run at 10:07 EET (01:07 PDT) by the scheduled task.

- Google URL Inspection: /about, /blog/does-codex-cli-have-hooks and /blog/claude-code-stop-hook-test-after-last-edit already show "URL is on Google" (indexed), so no request was sent for them. /blog/what-is-a-false-green-ai-coding-agent is "URL is unknown to Google"; Request indexing ran the live test and then answered "Quota Exceeded". /blog/audit-claude-code-codex-session-logs-locally is also unknown to Google and was not requested. The quota had not reset after midnight Pacific, so it looks like a rolling 24-hour window: retry these two after 2026-10-26 evening EET.
- Sitemap: /sitemap.xml status Success, last read Oct 25, 26 discovered pages. URL Inspection still says "No referring sitemaps detected" for the two unknown pages, which should change on the next sitemap read.
- IndexNow: `node scripts/indexnow.mjs` printed `submitted 30 URLs: HTTP 403`. Same Bing-side 403 as yesterday; Bing Webmaster Tools URL Submission stays the workaround.
- 17:42 EET retry (scheduled task): /blog/what-is-a-false-green-ai-coding-agent is still "URL is not on Google"; Request indexing ran the live test and again answered "Quota Exceeded". /blog/audit-claude-code-codex-session-logs-locally was not tried. So the quota was still out about 24h40m after it ran out on 2026-10-25 ~17:00 EET, which does not fit a plain rolling 24-hour window either. Next try: 2026-10-27 morning, or ask the owner to request both from their own browser.
