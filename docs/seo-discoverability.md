# Getting the agency discovered

What the repo already does for the public landing page (`frontend/public/home.html`, served at `/`):
canonical URL, title and description, Open Graph, JSON-LD (`SoftwareApplication`, `WebSite`,
`Organization`, `FAQPage`), `robots.txt` with named AI-crawler rules, `sitemap.xml`, `llms.txt`,
and an IndexNow key file. Rankings are not something code can guarantee; these are the steps that
need an account or a decision, in order of payoff.

1. **Custom domain (biggest lever).** `*.workers.dev` is a shared suffix with no authority of its own.
   Attach a domain in Cloudflare (Workers → Settings → Domains), then update `CANONICAL` in
   `tests/test_landing_page.py`, every URL in `home.html`, `robots.txt`, `sitemap.xml`, `llms.txt`,
   `HOST` in `scripts/indexnow_ping.py` and `PRIMARY_PRODUCTION_URL` in `wrangler.jsonc`, and 301 the old host.
2. **Google Search Console.** Add the property, verify (DNS TXT, or an HTML-tag token pasted into
   `home.html`), submit `/sitemap.xml`, then "Request indexing" for `/`.
3. **Bing Webmaster Tools.** Import the site from Search Console, submit the sitemap. Bing data also
   feeds ChatGPT search and Copilot answers.
4. **IndexNow.** After a deploy that changes the page: `python scripts/indexnow_ping.py`.
5. **Backlinks.** Set the GitHub repo "Website" to the landing URL and add topics (for example
   `ai-agents`, `self-hosted`, `openai-compatible`, `llm-proxy`); link it from the README top;
   post it where agent/self-hosting people look (Show HN, relevant subreddits, awesome-lists).
6. **Measure.** Re-run `python scripts/run_seo_audit.py --website-url <landing URL>` after each release.
