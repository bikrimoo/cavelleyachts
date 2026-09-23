#!/usr/bin/env python3
"""Build Cavelle blog pages from articles/*.json into public/blog/ and public/ar/blog/.

Uses only Python's standard library. No runtime API, database, client-side rendering,
or HTML supplied by article authors. Source JSON is the canonical article record.
"""
import argparse
from datetime import date
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

BASE = 'https://www.cavelleyachts.com'
# Keep in sync with the CSS version used by the hand-authored pages.
CSS_VERSION = '20260913'
# Match the existing site font systems: EN pages load Playfair Display + Jost,
# AR pages load Amiri + Noto Sans Arabic (see public/ar/*/index.html).
FONTS = {
    'en': 'https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;1,500&family=Jost:wght@300;400;500;600&display=swap',
    'ar': 'https://fonts.googleapis.com/css2?family=Amiri:ital,wght@0,400;0,700;1,400&family=Noto+Sans+Arabic:wght@300;400;500;600;700&display=swap',
}
SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
LANGS = {'en': '', 'ar': 'ar/'}
LABEL = {
    'en': {'home': 'Home', 'blog': 'Blog', 'empty': 'Articles are coming soon.',
           'latest': 'Latest articles', 'related': 'Related articles', 'read': 'Read article',
           'back': 'All articles', 'intro': 'Perspectives on floating living, hospitality and life on the water.',
           'index_title': 'Blog | Cavelle', 'index_description': 'Ideas and perspectives on floating living, waterfront hospitality and luxury floating assets from Cavelle.'},
    'ar': {'home': 'الرئيسية', 'blog': 'المدونة', 'empty': 'المقالات قادمة قريباً.',
           'latest': 'أحدث المقالات', 'related': 'مقالات ذات صلة', 'read': 'اقرأ المقال',
           'back': 'جميع المقالات', 'intro': 'رؤى حول الحياة العائمة والضيافة والحياة على الماء.',
           'index_title': 'المدونة | كافيل', 'index_description': 'أفكار ورؤى حول الحياة العائمة والضيافة على الواجهة البحرية والأصول العائمة الفاخرة من كافيل.'},
}


def e(value):
    return escape(str(value), quote=True)


def url(value, *, image=False):
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        raise ValueError('URL must be a nonempty printable string')
    parsed = urlsplit(value)
    # Absolute HTTPS covers a future custom R2 domain; root-relative covers site images.
    if parsed.scheme == 'https' and parsed.netloc and not parsed.username and not parsed.password:
        if not re.fullmatch(r'[A-Za-z0-9.-]+(?::443)?', parsed.netloc):
            raise ValueError(f'Invalid HTTPS host: {value}')
        return value
    if value.startswith('/') and not value.startswith('//') and not parsed.scheme and not parsed.netloc and not re.search(r'(^|/)\.\.?(/|$)', parsed.path) and '\\' not in value:
        return value
    raise ValueError(f'Only root-relative or HTTPS URLs are allowed: {value}')


def absolute(value):
    return value if value.startswith('https://') else BASE + value


def required_text(data, key):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{key} must be nonempty text')
    return value.strip()


def image_data(value):
    if not isinstance(value, dict):
        raise ValueError('featured_image must be an object')
    src = url(required_text(value, 'url'), image=True)
    alt = required_text(value, 'alt')
    width, height = value.get('width'), value.get('height')
    if not all(isinstance(n, int) and not isinstance(n, bool) and 0 < n <= 10000 for n in (width, height)):
        raise ValueError('featured_image width and height must be positive integers <= 10000')
    return {'url': src, 'alt': alt, 'width': width, 'height': height}


def validate(raw, path):
    if not isinstance(raw, dict) or raw.get('schema_version') != 1:
        raise ValueError('schema_version must be 1')
    if raw.get('status') not in ('draft', 'published'):
        raise ValueError('status must be draft or published')
    if raw.get('language') not in LANGS or not SLUG.fullmatch(str(raw.get('slug', ''))):
        raise ValueError('language must be en/ar and slug must use lowercase letters, digits and hyphens')
    if raw['slug'] in ('index', 'category', 'tag', 'page'):
        raise ValueError('reserved article slug')
    for key in ('title', 'seo_title', 'meta_description', 'excerpt', 'category'):
        required_text(raw, key)
    if len(raw['seo_title']) > 90 or len(raw['meta_description']) > 200:
        raise ValueError('seo_title max 90, meta_description max 200 characters')
    if not isinstance(raw.get('author'), dict):
        raise ValueError('author must be an object')
    required_text(raw['author'], 'name')
    if raw['author'].get('url'):
        url(raw['author']['url'])
    for key in ('date_published', 'date_modified'):
        if not isinstance(raw.get(key), str):
            raise ValueError(f'{key} is required as YYYY-MM-DD')
        try:
            parsed = date.fromisoformat(raw[key])
        except ValueError as exc:
            raise ValueError(f'{key} must be YYYY-MM-DD') from exc
        if parsed.isoformat() != raw[key]:
            raise ValueError(f'{key} must be YYYY-MM-DD')
    if raw['date_modified'] < raw['date_published']:
        raise ValueError('date_modified cannot precede date_published')
    image_data(raw.get('featured_image'))
    if not isinstance(raw.get('blocks'), list) or not raw['blocks']:
        raise ValueError('blocks must be a nonempty array')
    for block in raw['blocks']:
        if not isinstance(block, dict):
            raise ValueError('each block must be an object')
        kind = block.get('type')
        if kind in ('paragraph', 'quote'):
            required_text(block, 'text')
        elif kind == 'heading':
            required_text(block, 'text')
            if block.get('level') not in (2, 3):
                raise ValueError('article headings must be H2 or H3; H1 is the article title')
        elif kind == 'list':
            if not isinstance(block.get('items'), list) or not block['items']:
                raise ValueError('list.items must be a nonempty array')
            for item in block['items']:
                if not isinstance(item, str) or not item.strip():
                    raise ValueError('list items must be text')
        elif kind == 'link':
            required_text(block, 'text')
            url(required_text(block, 'href'))
        elif kind == 'image':
            image_data(block)
        else:
            raise ValueError(f'unknown article block type: {kind}')
    if 'related_slugs' in raw:
        if not isinstance(raw['related_slugs'], list) or not all(isinstance(s, str) and SLUG.fullmatch(s) for s in raw['related_slugs']):
            raise ValueError('related_slugs must be an array of slugs')
    return raw


def load_articles(source):
    results, seen = [], set()
    for path in sorted(source.glob('*.json')):
        try:
            article = validate(json.loads(path.read_text(encoding='utf-8')), path)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f'{path}: {exc}') from exc
        key = (article['language'], article['slug'])
        if key in seen:
            raise ValueError(f'Duplicate blog URL from {path}: {key}')
        seen.add(key)
        if article['status'] == 'published':
            results.append(article)
    return sorted(results, key=lambda a: (a['date_published'], a['slug']), reverse=True)


def route(lang, slug=None):
    return '/' + LANGS[lang] + 'blog/' + (slug + '/' if slug else '')


def element_image(image, *, eager=False):
    data = image_data(image)
    return (f'<img src="{e(data["url"])}" alt="{e(data["alt"])}" width="{data["width"]}" height="{data["height"]}" '
            f'loading="{"eager" if eager else "lazy"}" decoding="async">')


def card(article, label):
    href = route(article['language'], article['slug'])
    return (f'<article class="blog-card"><a class="blog-card-image" href="{e(href)}" aria-label="{e(article["title"])}">'
            f'{element_image(article["featured_image"])}</a><div class="blog-card-copy">'
            f'<time datetime="{e(article["date_published"])}">{e(article["date_published"])}</time>'
            f'<h3 class="h3"><a href="{e(href)}">{e(article["title"])}</a></h3>'
            f'<p>{e(article["excerpt"])}</p><a class="blog-card-link" href="{e(href)}">{e(label)} <span aria-hidden="true">→</span></a>'
            f'</div></article>')


def body_blocks(article):
    blocks = []
    for block in article['blocks']:
        kind = block['type']
        if kind == 'paragraph':
            blocks.append(f'<p>{e(block["text"])}</p>')
        elif kind == 'heading':
            level = block['level']
            blocks.append(f'<h{level}>{e(block["text"])}</h{level}>')
        elif kind == 'quote':
            blocks.append(f'<blockquote><p>{e(block["text"])}</p></blockquote>')
        elif kind == 'list':
            blocks.append('<ul>' + ''.join(f'<li>{e(item)}</li>' for item in block['items']) + '</ul>')
        elif kind == 'link':
            blocks.append(f'<p><a href="{e(url(block["href"]))}">{e(block["text"])}</a></p>')
        elif kind == 'image':
            blocks.append(f'<figure>{element_image(block)}</figure>')
    return '\n'.join(blocks)


def jsonld(data):
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False).replace('<', '\\u003c') + '</script>'


def breadcrumbs(lang, article=None):
    words = LABEL[lang]
    items = [(words['home'], '/ar/' if lang == 'ar' else '/'), (words['blog'], route(lang))]
    if article:
        items.append((article['title'], route(lang, article['slug'])))
    nav = ' <span class="sep" aria-hidden="true">/</span> '.join(
        f'<a href="{e(href)}">{e(name)}</a>' if n < len(items) - 1 else f'<span aria-current="page">{e(name)}</span>'
        for n, (name, href) in enumerate(items))
    schema = {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': n, 'name': name, 'item': BASE + href}
        for n, (name, href) in enumerate(items, 1)]}
    return f'<nav class="breadcrumbs" aria-label="{e(words["blog"])}">{nav}</nav>', schema


def fragment(html, start, end):
    first = html.index(start)
    last = html.index(end, first) + len(end)
    return html[first:last]


def site_chrome(public, lang, is_article, alternate):
    source = (public / ('ar/' if lang == 'ar' else '') / 'about/index.html').read_text(encoding='utf-8')
    header = fragment(source, '<header class="site-header"', '</header>')
    menu = fragment(source, '<div class="mobile-menu">', '</div>')
    footer = fragment(source, '<footer class="site-footer">', '</footer>')
    # Blog is the one addition to the existing navigation; source chrome already includes it.
    header = header.replace('href="/ar/about/" class="active"' if lang == 'ar' else 'href="/about/" class="active"',
                            'href="/ar/about/" class=""' if lang == 'ar' else 'href="/about/" class=""')
    if lang == 'en':
        header = header.replace('href="/blog/" class=""', 'href="/blog/" class="active"')
        header = header.replace('href="/ar/about/" class="lang-toggle" data-lang-toggle', f'href="{e(alternate)}" class="lang-toggle"')
        menu = menu.replace('href="/ar/about/" class="lang-toggle" data-lang-toggle', f'href="{e(alternate)}" class="lang-toggle"')
    else:
        header = header.replace('href="/ar/blog/" class=""', 'href="/ar/blog/" class="active"')
        header = header.replace('href="/about/" class="lang-toggle" data-lang-toggle', f'href="{e(alternate)}" class="lang-toggle"')
        menu = menu.replace('href="/about/" class="lang-toggle" data-lang-toggle', f'href="{e(alternate)}" class="lang-toggle"')
    return header + '\n' + menu, footer


def shell(public, lang, path, title, description, image, contents, schema, *, article=None, alternate=None):
    if alternate is None:
        alternate = route('ar' if lang == 'en' else 'en')
    chrome, footer = site_chrome(public, lang, article is not None, alternate)
    absolute_path = BASE + path
    meta = image_data(image) if image else None
    social = (f'<meta property="og:image" content="{e(absolute(meta["url"]))}">\n'
              f'<meta name="twitter:image" content="{e(absolute(meta["url"]))}">\n') if meta else ''
    # Never claim a translation exists unless it is actually generated.
    alternates = ''
    if article is None or alternate != route('ar' if lang == 'en' else 'en'):
        other = 'ar' if lang == 'en' else 'en'
        if article is None or alternate.endswith('/' + article['slug'] + '/'):
            alternates = (f'<link rel="alternate" hreflang="{lang}" href="{e(absolute_path)}">\n'
                          f'<link rel="alternate" hreflang="{other}" href="{e(BASE + alternate)}">\n')
    lang_dir = ' dir="rtl"' if lang == 'ar' else ''
    rtl = '<link rel="stylesheet" href="/css/rtl.css">\n' if lang == 'ar' else ''
    breadcrumb_html, breadcrumb_schema = breadcrumbs(lang, article)
    structured = jsonld(breadcrumb_schema) + (jsonld(schema) if schema else '')
    return (f'<!DOCTYPE html>\n<html lang="{lang}"{lang_dir}>\n<head>\n<meta charset="UTF-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f'<title>{e(title)}</title>\n<meta name="description" content="{e(description)}">\n'
            f'<link rel="canonical" href="{e(absolute_path)}">\n{alternates}'
            f'<meta name="robots" content="index, follow">\n<meta property="og:type" content="{"article" if article else "website"}">\n'
            f'<meta property="og:site_name" content="Cavelle">\n<meta property="og:title" content="{e(title)}">\n'
            f'<meta property="og:description" content="{e(description)}">\n<meta property="og:url" content="{e(absolute_path)}">\n'
            f'<meta name="twitter:card" content="summary_large_image">\n<meta name="twitter:title" content="{e(title)}">\n'
            f'<meta name="twitter:description" content="{e(description)}">\n{social}'
            f'<link rel="icon" href="/favicon.svg" type="image/svg+xml">\n'
            f'<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            f'<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            f'<link rel="stylesheet" href="{FONTS[lang]}">\n'
            f'<link rel="stylesheet" href="/css/style.min.css?v={CSS_VERSION}">\n{rtl}'
            f'<link rel="stylesheet" href="/css/blog.css">\n{structured}\n'
            f'<script src="/js/i18n.js" defer></script>\n</head>\n<body>\n'
            f'<a class="skip-link" href="#main">{e("تخطي إلى المحتوى" if lang == "ar" else "Skip to content")}</a>\n'
            f'{chrome}\n<main id="main" class="blog-main">\n{breadcrumb_html}\n{contents}\n</main>\n{footer}\n'
            f'<script src="/js/main.min.js" defer></script>\n'
            f'<script>document.getElementById("year").textContent = new Date().getFullYear();</script>\n'
            f'</body>\n</html>\n')


def index_page(public, lang, articles):
    label = LABEL[lang]
    cards = ('<div class="blog-grid">' + ''.join(card(a, label['read']) for a in articles) + '</div>'
             if articles else f'<p class="blog-empty">{e(label["empty"])}</p>')
    contents = (f'<section class="section-pad"><div class="container"><div class="blog-intro">'
                f'<span class="eyebrow">Cavelle</span><h1 class="h1">{e(label["blog"])}</h1>'
                f'<p class="lead">{e(label["intro"])}</p></div>'
                f'<h2 class="h2 blog-list-heading">{e(label["latest"])}</h2>{cards}</div></section>')
    return shell(public, lang, route(lang), label['index_title'], label['index_description'], None, contents, None)


def article_page(public, article, articles):
    lang = article['language']
    label = LABEL[lang]
    others = [a for a in articles if a['language'] == lang and a['slug'] != article['slug']]
    by_slug = {a['slug']: a for a in others}
    chosen = [by_slug[s] for s in article.get('related_slugs', []) if s in by_slug]
    chosen += [a for a in others if a not in chosen and a['category'] == article['category']]
    chosen += [a for a in others if a not in chosen]
    chosen = chosen[:3]
    related = (f'<section class="blog-related" aria-labelledby="related-heading"><h2 class="h2" id="related-heading">{e(label["related"])}</h2>'
               + '<div class="blog-grid">' + ''.join(card(a, label['read']) for a in chosen) + '</div></section>' if chosen else '')
    author = article['author']
    author_name = e(author['name'])
    if author.get('url'):
        author_name = f'<a href="{e(url(author["url"]))}">{author_name}</a>'
    contents = (f'<article class="section-pad blog-article"><div class="container">'
                f'<header class="blog-article-header"><span class="eyebrow">{e(article["category"])}</span>'
                f'<h1 class="h1">{e(article["title"])}</h1><div class="blog-byline"><span>{author_name}</span>'
                f'<time datetime="{e(article["date_published"])}">{e(article["date_published"])}</time></div></header>'
                f'<figure class="blog-featured">{element_image(article["featured_image"], eager=True)}</figure>'
                f'<div class="blog-prose">{body_blocks(article)}</div>'
                f'<p class="blog-back"><a href="{e(route(lang))}">← {e(label["back"])}</a></p>'
                f'{related}</div></article>')
    image = article['featured_image']
    canonical = BASE + route(lang, article['slug'])
    schema = {'@context': 'https://schema.org', '@type': 'BlogPosting', 'mainEntityOfPage': canonical,
              'headline': article['title'], 'description': article['meta_description'],
              'image': [absolute(image['url'])], 'datePublished': article['date_published'],
              'dateModified': article['date_modified'], 'author': {'@type': 'Person', 'name': author['name']},
              'publisher': {'@type': 'Organization', 'name': 'Cavelle', 'url': BASE}}
    counterpart = next((a for a in articles if a['language'] != lang and a['slug'] == article['slug']), None)
    alternate = route(counterpart['language'], counterpart['slug']) if counterpart else route('ar' if lang == 'en' else 'en')
    return shell(public, lang, route(lang, article['slug']), article['seo_title'], article['meta_description'], image, contents, schema,
                 article=article, alternate=alternate)


def build(source, public):
    articles = load_articles(source)
    outputs = {}
    for lang in LANGS:
        outputs[public / LANGS[lang] / 'blog/index.html'] = index_page(public, lang, [a for a in articles if a['language'] == lang])
    for article in articles:
        outputs[public / LANGS[article['language']] / 'blog' / article['slug'] / 'index.html'] = article_page(public, article, articles)
    # Fail without writing if a page would collide with a non-generated file.
    marker = '<!-- Generated by scripts/build_blog.py; do not edit this HTML. -->\n'
    for path in outputs:
        if path.exists() and not path.read_text(encoding='utf-8').startswith(marker):
            raise ValueError(f'Refusing to overwrite non-generated file: {path}')
    # Prune only generated files from prior builds; never delete a hand-authored page.
    for lang in LANGS:
        blog_dir = public / LANGS[lang] / 'blog'
        if blog_dir.exists():
            for old in blog_dir.rglob('index.html'):
                if old not in outputs and old.read_text(encoding='utf-8').startswith(marker):
                    old.unlink()
    for path, html in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(marker + html, encoding='utf-8')
    print(f'Blog: generated {len(articles)} published article(s) and 2 indexes from {source}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=Path('articles'))
    ap.add_argument('--public', type=Path, default=Path('public'))
    args = ap.parse_args()
    build(args.source, args.public)
