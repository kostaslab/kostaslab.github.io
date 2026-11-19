#!/usr/bin/env python3
"""KOSTAS Lab static site builder.

Kullanım / Usage:
    pip install jinja2 pyyaml
    python3 src/build.py

src/data/*.yml dosyalarını okur, src/templates/ içindeki şablonlarla
İngilizce (kök dizin) ve Türkçe (/tr/) sayfaları, sitemap.xml ve robots.txt üretir.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import shutil
import unicodedata
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DATA = SRC / "data"
LANGS = ["en", "tr"]

# ---------------------------------------------------------------- data
def load(name):
    with open(DATA / f"{name}.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)

site = load("site")
people = load("people")
pubs = load("publications")
research = load("research")
projects = load("projects")
collaborators = load("collaborators")
news = load("news")
STR = load("strings")

def _validate():
    """Catch common YAML mistakes (unquoted ': ' or ',' in text) before rendering."""
    problems = []
    def walk(o, path):
        if isinstance(o, dict):
            if set(o) & {"en", "tr"} and not set(o) <= {"en", "tr", "value"}:
                problems.append(f"{path}: unexpected keys {sorted(o)}")
            for k, v in o.items():
                if v is None and k not in ("google_site_verification", "bing_site_verification"):
                    problems.append(f"{path}.{k}: empty value")
                walk(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, x in enumerate(o):
                if isinstance(x, dict) and path.split(".")[-1] in ("bio", "about", "en", "tr", "authors", "interests"):
                    problems.append(f"{path}[{i}]: text parsed as a mapping — wrap it in double quotes")
                walk(x, f"{path}[{i}]")
    for p in pubs:
        if p.get("origin") not in site.get("origins", {}):
            problems.append(f"publication {p.get('id')}: 'origin' must be one of {sorted(site.get('origins', {}))}")
    for pr in projects:
        if pr.get("origin") and pr["origin"] not in site.get("origins", {}):
            problems.append(f"project {pr.get('name')}: unknown origin '{pr['origin']}'")
    for name, obj in [("site", site), ("people", people), ("publications", pubs), ("research", research),
                      ("projects", projects), ("news", news), ("strings", STR), ("collaborators", collaborators)]:
        walk(obj, name)
    if problems:
        raise SystemExit("YAML problems found:\n  " + "\n  ".join(problems))


_validate()
BASE = site["url"].rstrip("/")
TODAY = dt.date.today().isoformat()

# URL paths per language. Keys are page ids.
ROUTES = {
    "home": {"en": "/", "tr": "/tr/"},
    "publications": {"en": "/publications/", "tr": "/tr/yayinlar/"},
}
for p in people:
    ROUTES[f"person:{p['id']}"] = {"en": f"/people/{p['slug']}/", "tr": f"/tr/ekip/{p['slug']}/"}

people_by_id = {p["id"]: p for p in people}

# Map author-name variants to lab members (for bolding + linking)
def _norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)

AUTHOR_MAP = {}
for p in people:
    for n in p.get("alternate_names", []) + [p["name"]["en"], p["name"]["tr"]]:
        AUTHOR_MAP[_norm(n)] = p["id"]

TYPE_ORDER = ["journal", "conference", "chapter", "abstract"]

# ---------------------------------------------------------------- helpers
def tr_(val, lang):
    """Pick language variant from {en:…, tr:…} or return value as-is."""
    if isinstance(val, dict) and ("en" in val or "tr" in val):
        return val.get(lang) or val.get("en")
    return val


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def bibtex(p):
    kind = {"journal": "article", "conference": "inproceedings", "chapter": "incollection", "abstract": "inproceedings"}[p["type"]]
    venue_key = {"article": "journal", "inproceedings": "booktitle", "incollection": "booktitle"}[kind]
    fields = [
        ("title", "{" + p["title"] + "}"),
        ("author", " and ".join(p["authors"])),
        (venue_key, p["venue"]),
        ("year", str(p["year"])),
    ]
    if p.get("doi"):
        fields.append(("doi", p["doi"]))
    elif p.get("links"):
        fields.append(("url", next(iter(p["links"].values()))))
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields)
    return f"@{kind}{{{p['id']},\n{body}\n}}"


for p in pubs:
    p["bibtex"] = bibtex(p)
    links = {}
    if p.get("doi"):
        links["DOI"] = f"https://doi.org/{p['doi']}"
    links.update(p.get("links") or {})
    p["all_links"] = links
    p["url"] = links.get("DOI") or next(iter(links.values()), None)

pubs.sort(key=lambda p: (-p["year"], TYPE_ORDER.index(p["type"])))

for r in research:
    r["count"] = sum(1 for p in pubs if r["topic"] in p.get("topics", []))


def stats():
    return {
        "pubs": len(pubs),
        "q1": sum(1 for p in pubs if p.get("q1")),
        "code": sum(1 for p in pubs if "Code" in (p.get("links") or {})),
        "founded": site["founded"],
        "lab_pubs": sum(1 for p in pubs if p.get("origin") == "lab"),
    }


# ---------------------------------------------------------------- jinja
env = Environment(
    loader=FileSystemLoader(SRC / "templates"),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def make_ctx(lang, page_id, **extra):
    def t(val):
        return tr_(val, lang)

    def s(key):
        return STR[key][lang]

    def url(pid, l=None):
        return ROUTES[pid][l or lang]

    def authors_html(names):
        out = []
        for n in names:
            pid = AUTHOR_MAP.get(_norm(n))
            if pid:
                out.append(f'<a class="me" href="{url("person:" + pid)}">{html.escape(n)}</a>')
            else:
                out.append(html.escape(n))
        return Markup(", ".join(out))

    def news_date(d):
        d = str(d)
        if len(d) == 4:
            return d
        y, m = d.split("-")
        return f"{STR['months'][lang][int(m) - 1]} {y}"

    alternates = {l: BASE + ROUTES[page_id][l] for l in LANGS}
    ctx = dict(
        lang=lang,
        other_lang="tr" if lang == "en" else "en",
        page_id=page_id,
        site=site,
        people=people,
        people_by_id=people_by_id,
        pubs=pubs,
        research=research,
        projects=projects,
        collaborators=collaborators,
        origins_used=[o for o in site["origins"] if any(p.get("origin") == o for p in pubs)],
        news=news,
        stats=stats(),
        t=t,
        s=s,
        url=url,
        authors_html=authors_html,
        news_date=news_date,
        canonical=alternates[lang],
        alternates=alternates,
        base=BASE,
        year=dt.date.today().year,
        json=lambda o: Markup(json.dumps(o, ensure_ascii=False, indent=1).replace("</", "<\\/")),
        type_label=lambda ty: STR["type_" + ty][lang],
    )
    ctx.update(extra)
    return ctx


def write(path, content):
    out = ROOT / path.lstrip("/")
    if path.endswith("/"):
        out = out / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    return out


# ---------------------------------------------------------------- structured data
def person_ld(p, lang):
    links = list((p.get("links") or {}).values())
    if p.get("website"):
        links.append(p["website"])
    return {
        "@type": "Person",
        "@id": f"{BASE}{ROUTES['person:' + p['id']]['en']}#person",
        "name": tr_(p["name"], lang),
        "alternateName": [n for n in p.get("alternate_names", []) if n != tr_(p["name"], lang)],
        "honorificPrefix": p.get("honorific"),
        "jobTitle": tr_(p["position"], lang),
        "url": BASE + ROUTES["person:" + p["id"]][lang],
        "image": f"{BASE}/assets/img/{p['slug']}.jpg",
        "email": "mailto:" + p["email"],
        "sameAs": links,
        "knowsAbout": tr_(p["interests"], "en"),
        "alumniOf": [{"@type": "CollegeOrUniversity", "name": n} for n in p.get("alumni_of", [])],
        "worksFor": [{"@type": "Organization", "name": n} for n in p.get("works_for", [])],
        "memberOf": {"@id": BASE + "/#org"},
    }


def article_ld(p):
    d = {
        "@type": "ScholarlyArticle",
        "headline": p["title"][:110],
        "name": p["title"],
        "author": [
            {"@id": f"{BASE}{ROUTES['person:' + AUTHOR_MAP[_norm(a)]]['en']}#person"} if _norm(a) in AUTHOR_MAP
            else {"@type": "Person", "name": a}
            for a in p["authors"]
        ],
        "datePublished": str(p["year"]),
        "isPartOf": {"@type": "Periodical" if p["type"] == "journal" else "CreativeWork", "name": p["venue"]},
    }
    if p.get("url"):
        d["url"] = p["url"]
    org = site["origins"].get(p.get("origin"), {})
    if org.get("org"):
        d["sourceOrganization"] = {"@type": "Organization", "name": org["org"]}
    elif p.get("origin") == "lab":
        d["sourceOrganization"] = {"@id": BASE + "/#org"}
    if p.get("doi"):
        d["identifier"] = {"@type": "PropertyValue", "propertyID": "DOI", "value": p["doi"]}
        d["sameAs"] = f"https://doi.org/{p['doi']}"
    return d


def org_ld(lang):
    return {
        "@type": "ResearchOrganization",
        "@id": BASE + "/#org",
        "name": "KOSTAS Lab",
        "alternateName": ["Knowledge-Oriented Systems for Technology, AI and Science", "KOSTAS Laboratuvarı", "Kostas Lab"],
        "url": BASE + "/",
        "logo": BASE + "/assets/img/icon-512.png",
        "image": BASE + "/assets/img/og-image.png",
        "description": tr_(site["description"], lang) + " " + tr_(site["independence"], lang),
        "foundingDate": str(site["founded"]),
        "email": site["email"],
        "address": {"@type": "PostalAddress", "addressLocality": "Gümüşhane", "addressCountry": "TR"},
        "founder": [{"@id": f"{BASE}{ROUTES['person:' + p['id']]['en']}#person"} for p in people],
        "member": [{"@id": f"{BASE}{ROUTES['person:' + p['id']]['en']}#person"} for p in people],
        "knowsAbout": [tr_(r["title"], "en") for r in research],
    }


def graph(*nodes):
    return {"@context": "https://schema.org", "@graph": [n for n in nodes if n]}


def breadcrumbs(lang, items):
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": BASE + u} for i, (n, u) in enumerate(items)
        ],
    }


# ---------------------------------------------------------------- build
def clean():
    for d in ["tr", "people", "publications"]:
        shutil.rmtree(ROOT / d, ignore_errors=True)


def build():
    clean()
    pages = []  # (page_id, priority)

    for lang in LANGS:
        home_name = STR["nav_home"][lang]

        # Home
        ld = graph(
            org_ld(lang),
            {"@type": "WebSite", "@id": BASE + "/#website", "url": BASE + "/", "name": "KOSTAS Lab",
             "inLanguage": ["en", "tr"], "publisher": {"@id": BASE + "/#org"}},
            *[person_ld(p, lang) for p in people],
        )
        ctx = make_ctx(lang, "home",
                       title=STR["home_title"][lang],
                       description=tr_(site["meta_description"], lang),
                       ld=ld)
        write(ROUTES["home"][lang], env.get_template("home.html").render(**ctx))

        # Publications
        ld = graph(
            {"@type": "CollectionPage", "name": STR["pubs_title"][lang], "url": BASE + ROUTES["publications"][lang],
             "isPartOf": {"@id": BASE + "/#website"}, "about": {"@id": BASE + "/#org"},
             "mainEntity": {"@type": "ItemList", "numberOfItems": len(pubs),
                            "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": article_ld(p)}
                                                for i, p in enumerate(pubs)]}},
            breadcrumbs(lang, [(home_name, ROUTES["home"][lang]), (STR["nav_pubs"][lang], ROUTES["publications"][lang])]),
        )
        ctx = make_ctx(lang, "publications",
                       title=STR["pubs_title"][lang] + " · KOSTAS Lab",
                       description=STR["pubs_desc"][lang].format(n=len(pubs)),
                       ld=ld,
                       years=sorted({p["year"] for p in pubs}, reverse=True),
                       types=[t for t in TYPE_ORDER if any(p["type"] == t for p in pubs)])
        write(ROUTES["publications"][lang], env.get_template("publications.html").render(**ctx))

        # People
        for p in people:
            pid = "person:" + p["id"]
            mine = [x for x in pubs if p["id"] in x.get("members", [])]
            pj = [x for x in projects if p["id"] in x.get("members", [])]
            name = tr_(p["name"], lang)
            ld = graph(
                {"@type": "ProfilePage", "url": BASE + ROUTES[pid][lang], "name": name,
                 "isPartOf": {"@id": BASE + "/#website"}, "dateModified": TODAY,
                 "mainEntity": person_ld(p, lang)},
                breadcrumbs(lang, [(home_name, ROUTES["home"][lang]), (STR["nav_people"][lang], ROUTES["home"][lang] + "#people"),
                                   (name, ROUTES[pid][lang])]),
            )
            ctx = make_ctx(lang, pid,
                           title=f"{p['honorific']} {name} · KOSTAS Lab",
                           description=f"{p['honorific']} {name}, KOSTAS Lab. {tr_(p['short'], lang)}",
                           ld=ld, person=p, my_pubs=mine, my_projects=pj,
                           og_image=f"/assets/img/{p['slug']}.jpg", og_type="profile")
            write(ROUTES[pid][lang], env.get_template("person.html").render(**ctx))

    # 404 (bilingual, outside language tree)
    ctx = make_ctx("en", "home", title="Page not found · KOSTAS Lab", description="", ld=None, noindex=True)
    (ROOT / "404.html").write_text(env.get_template("404.html").render(**ctx), encoding="utf-8")

    # sitemap
    prio = {"home": "1.0", "publications": "0.8"}
    urls = []
    for pid, langs in ROUTES.items():
        for l in LANGS:
            alts = "".join(
                f'\n    <xhtml:link rel="alternate" hreflang="{a}" href="{BASE}{langs[a]}"/>' for a in LANGS
            ) + f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{BASE}{langs["en"]}"/>'
            urls.append(
                f"  <url>\n    <loc>{BASE}{langs[l]}</loc>\n    <lastmod>{TODAY}</lastmod>\n"
                f"    <priority>{prio.get(pid, '0.9')}</priority>{alts}\n  </url>"
            )
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(urls) + "\n</urlset>\n", encoding="utf-8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /src/\n\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    print(f"Built {len(ROUTES) * len(LANGS)} pages, {len(pubs)} publications.")


if __name__ == "__main__":
    build()
