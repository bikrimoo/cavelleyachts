# Cavelle blog article source

GitHub is the source of truth. Each `*.json` in this folder is a single article record.
`status: "draft"` is validated but never deployed as a page or listed in indexes/sitemap.
`status: "published"` creates `/blog/<slug>/` for `language: "en"` and
`/ar/blog/<slug>/` for `language: "ar"`. No placeholder articles are published.

Copy `article.example.json.template` to `<slug>.json`, fill genuine approved details,
then run `python3 scripts/build_blog.py` followed by `python3 scripts/generate_sitemap.py`.
The deploy workflow runs both steps automatically on a future push to `main`.
Do not hand-edit generated pages under `public/blog/` or `public/ar/blog/`.

Article fields:
- `schema_version`: 1, `status`: `draft` or `published`, `language`: `en` or `ar`.
- `slug`: lowercase ASCII letters/digits/hyphens, unique within its language.
- `title`, `seo_title` (max 90), `meta_description` (max 200), `excerpt`, `category`.
- `author`: `{ "name": "verified name", "url": "/about/" }`; URL optional.
- `date_published` and `date_modified`: ISO calendar dates `YYYY-MM-DD`.
- `featured_image`: `{ "url": "https://YOUR-R2-CUSTOM-DOMAIN/...", "alt": "...", "width": 1200, "height": 630 }`.
  Root-relative image URLs are also supported. Public R2/CDN URLs must be HTTPS.
- `blocks`: nonempty array of typed content. Supported blocks: `paragraph` and `quote` with
  `text`; `heading` with `text` and `level` 2 or 3; `list` with an `items` array of strings;
  `link` with `text` and a root-relative or HTTPS `href`; `image` with the same fields as
  `featured_image`. Plain text is HTML-escaped. No arbitrary HTML, script, or MDX.
- `related_slugs`: optional array of same-language published article slugs. If omitted,
  related articles use the same category first, then latest other articles.

Posts can be updated by editing the same JSON file, changing `date_modified`, and
pushing normally. Deleting/unpublishing a JSON record removes its generated route
at the next build (plan redirects before retiring an indexed URL). **Do not store
unapproved drafts on a public branch if confidentiality matters:** draft JSON itself
may still be readable in GitHub even though no draft HTML is deployed.

The future n8n workflow may write these JSON files through the GitHub API and upload
approved images to R2, then let the ordinary GitHub deployment pipeline build pages.
No n8n or R2 credentials are needed by this generator. A production publish is not
complete until the build and Cloudflare deployment succeed.
