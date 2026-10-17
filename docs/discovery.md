# Public website and discovery

The website is https://glasgowm148.github.io/nvidia-MCP/. Edit its static HTML in `website/`.
The `Publish website` workflow deploys that directory and two explicitly selected public
documentation images. It does not publish the checkout, private output, filled configuration,
credentials, logs or recovery backups. No server version bump or TV connection is needed.

## Reader questions

| Page | Question answered |
| --- | --- |
| Landing page | What is this Kodi MCP server, and how do I start? |
| `ai-kodi-nvidia-shield/` | How can a local AI assistant connect to Kodi on Shield? |
| `nvidia-mcp-vs-adb-json-rpc/` | What does MCP add to direct ADB or Kodi API access? |
| `diagnose-kodi-playback/` | How do I gather evidence before attempting a repair? |

Maintain one useful page per question, with clear authorship, actual setup links and compatibility
limits. Avoid thin device-name variations, fabricated user stories, keyword stuffing or unsupported
claims that this works with every client/TV. Comparisons link to primary documentation and explain
when another interface is enough. The server is free; clients/models can cost separately.

## Publish and verify

Changes on `main` to the website, its selected images or publishing infrastructure run
`.github/workflows/pages.yml`. GitHub Settings → Pages uses GitHub Actions. Deployment has a separate
job with Pages/OIDC write permissions; the build only reads repository contents.

To reproduce locally, copy `website/` into an empty artifact directory, then copy
`docs/images/logo.svg` and `docs/images/manager-dashboard.png` into its `assets/` folder.
Run `python scripts/check_website.py ARTIFACT_DIRECTORY` to check local links, metadata,
canonicals, JSON-LD and the sitemap. Review mobile/desktop rendering and external links too.
Update a guide's reviewed date, JSON-LD `dateModified` and sitemap `lastmod` after substantive edits.

Pages are ordinary crawlable HTML with internal links and visible-fact structured data. There is
no client-side routing or content that requires executing JavaScript. Only the origin-root
`https://glasgowm148.github.io/robots.txt` can control crawlers, not a project-local robots file.
At publication the root file returned 404, leaving crawling unblocked. Recheck it if an account-level
site is added. The project does not set an AI-training preference on the shared origin.

Google's [AI search guidance](https://developers.google.com/search/docs/appearance/ai-features)
says there is no special AI markup or file requirement. OpenAI's
[crawler documentation](https://developers.openai.com/api/docs/bots) identifies OAI-SearchBot as
its search crawler. Do not block it if search visibility is desired. Neither guidance guarantees
indexing, citations or recommendations. Sitemap: https://glasgowm148.github.io/nvidia-MCP/sitemap.xml.

## Measurement and next evidence

The site uses no analytics scripts, project cookies or browser storage. Hosting follows
[GitHub Pages data collection](https://docs.github.com/en/pages/getting-started-with-github-pages/about-github-pages#data-collection).
Repository Traffic reports are a short rolling view of GitHub repository activity, not this site's
traffic or completed installations. Do not present downloads, visits or referrers as signups.

An owner can verify the exact Pages URL-prefix property in Google Search Console and submit the
sitemap. This is an account step, not something implied by successful deployment, and is not claimed
as completed. Inspect coverage/impressions after recrawling; compare the same windows when possible.

If site analytics are deliberately introduced later, OpenAI's
[publisher FAQ](https://help.openai.com/en/articles/12627856) documents ChatGPT referral UTM parameters.
Use aggregate landing-page/referrer data, never device IPs, tokens, diagnostic payloads, saved
settings or viewing histories. No recurring monitor is configured by the website workflow.
