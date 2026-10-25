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
