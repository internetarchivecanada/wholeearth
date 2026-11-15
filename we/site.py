"""Build the static site into public/ from data/index.json.

    python -m we.site
"""
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import date
from html import escape
from pathlib import Path

from .common import DATA, PUBLIC, page_numbers, slugify

TITLE = "Whole Earth People"
BASE_URL = "https://wayback-labs.sf.archive.org/wholeearth/"
CSS_V = "3"

ROLE_GROUPS = [
    ("Editors", ["Editor", "Editor-in-Chief", "Executive Editor", "Managing Editor", "Senior Editor", "Usual Editor",
                 "Guest Editor", "Associate Editor", "Assistant Editor", "Contributing Editor", "Software Editor",
                 "Review Editor", "Reviews Editor", "Book Review Editor", "Fiction Editor", "Poetry Editor",
                 "News Editor", "Art Editor", "Photo Editor", "Picture Editor", "Research Editor", "Technical Editor",
                 "Editorial Assistant", "Editorial Staff", "Editorial Director", "Copy Editor", "Assistant to the Editor"]),
    ("Art, design and production", ["Art Director", "Design Director", "Designer", "Design", "Production Manager",
                                    "Production Director", "Production Coordinator", "Production Assistant",
                                    "Production Staff", "Production", "Production & Layout", "Layout", "Paste-up",
                                    "Typesetting", "Typesetter", "Typography", "Proofreading", "Proofreader", "Indexing",
                                    "Camera", "Camera Work", "Darkroom", "Photography", "Photographer", "Illustration",
                                    "Illustrations", "Illustrator", "Cartoonist", "Cover Art", "Cover Design", "Logo",
                                    "Headlines", "Typing", "Word Processing", "Interview Transcriptions",
                                    "Transcriptions", "Transcription", "Transcribing"]),
    ("Business, office and readers", ["Publisher", "Associate Publisher", "Publishing", "Office Manager", "Office Staff",
                                      "Business Manager", "General Manager", "Financial Manager", "Bookkeeper",
                                      "Bookkeeping", "Accounting", "Accountant", "Circulation Manager",
                                      "Circulation Director", "Circulation", "Subscriptions",
                                      "Subscriptions & Back Issues", "Subscription Services", "Subscriber Services",
                                      "Customer Service", "Fulfillment", "Mail Order", "Mail Room", "Shipping",
                                      "Shipping & Receiving", "Shipping Clerk", "Traffic", "Distribution", "Advertising",
                                      "Advertising Sales", "Advertising Director", "Marketing", "Marketing Director",
                                      "Promotion", "Publicity", "Public Relations", "Receptionist", "Development",
                                      "Fundraising", "Executive Director", "Assistant to the Publisher", "Data Entry",
                                      "Computer Systems", "Systems Manager", "Truck Driver", "Janitor", "Gardener",
                                      "Cook"]),
    ("Research, library and projects", ["Research", "Researcher", "Research Assistant", "Library", "Librarian",
                                        "Projects", "Interns", "Intern"]),
    ("Point Foundation board", ["Point Board", "Board of Directors", "President"]),
    ("Other", ["Staff", "Columnists", "Correspondents", "Contributors", "Thanks", "Special Thanks"]),
]
ROLE_GROUP = {r: g for g, rs in ROLE_GROUPS for r in rs}
CONTENT_ROLE = {"wrote": "wrote", "edited": "edited", "compiled": "compiled", "photographs": "photographs",
                "illustrations": "illustrations", "interviewer": "interviewer", "interviewed": "interviewed"}


def e(s):
    return escape(str(s or ""), quote=True)


class Site:
    def __init__(self):
        d = json.loads((DATA / "index.json").read_text())
        self.collections = d["collections"]
        self.issues = d["issues"]
        self.people = d["people"]
        self.redux = d["redux"]
        self.issue = {i["slug"]: i for i in self.issues}
        self.person = {p["name"]: p for p in self.people}
        self.leaf_of = {}  # (identifier, printed page) -> leaf
        for i in self.issues:
            pn = page_numbers(i["id"])
            m = {}
            for leaf, num in sorted(pn.items()):
                m.setdefault(num, leaf)
            self.leaf_of[i["id"]] = m
        self.urls = []

    # ------------------------------------------------------------ helpers
    def page_url(self, iss, page=None, leaf=None):
        base = f"https://archive.org/details/{iss['id']}"
        if leaf is not None:
            return f"{base}/page/n{leaf}/mode/1up"
        if page is not None:
            l = self.leaf_of.get(iss["id"], {}).get(str(page))
            if l is not None:
                return f"{base}/page/n{l}/mode/1up"
            return f"{base}/page/{page}/mode/1up"
        return base

    def thumb(self, iss, page=None, leaf=None):
        if leaf is None and page is not None:
            leaf = self.leaf_of.get(iss["id"], {}).get(str(page))
        if leaf is None:
            return None
        return f"https://archive.org/download/{iss['id']}/page/n{leaf}_w240.jpg"

    def plink(self, name, rel):
        p = self.person.get(name)
        if not p:
            return e(name)
        return f'<a href="{rel}people/{p["slug"]}.html">{e(name)}</a>'

    def ilabel(self, iss):
        return iss["title"]

    def write(self, path, html, priority=None):
        out = PUBLIC / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html)
        if path.endswith(".html") and path != "404.html":
            self.urls.append(path.replace("index.html", ""))

    def page(self, path, title, body, rel="", desc="", wide=False):
        t = f"{title} · {TITLE}" if title != TITLE else TITLE
        nav = [("people/", "People"), ("writers.html", "Writers"), ("staff.html", "Staff"),
               ("issues.html", "Issues"), ("redux.html", "Redux"), ("about.html", "About")]
        navh = "".join(f'<a href="{rel}{h}">{x}</a>' for h, x in nav)
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(t)}</title>
<meta name="description" content="{e(desc or 'Writers, editors and staff of the Whole Earth Catalog, CoEvolution Quarterly, Whole Earth Review and their sister publications, 1968–2002.')}">
<link rel="icon" href="{rel}img/favicon.png">
<link rel="stylesheet" href="{rel}style.css?v={CSS_V}">
</head><body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><a class="brand" href="{rel}./">{TITLE}</a><nav aria-label="Main">{navh}</nav></header>
<main id="main"{' class="wide"' if wide else ''}>
{body}
</main>
<footer>
<div class="foot-l"><a href="https://archive.org/"><img src="{rel}img/internet-archive.png" alt="Internet Archive" width="40" height="40"></a>
<p>A Wayback Machine Labs experiment, Internet Archive.<br>
Feedback? <a href="mailto:info@archive.org?subject=Whole%20Earth%20People">Email us</a></p></div>
<p class="foot-r">“access to tools, ideas, and practices”<br>Issues: <a href="https://wholeearth.info/">Whole Earth Index</a> · Scans: <a href="https://archive.org/details/wholeearth">Internet Archive</a></p>
</footer>
<script src="{rel}app.js?v={CSS_V}" defer></script>
</body></html>
"""

    def roles_line(self, p):
        bits = []
        if p["n_writing"]:
            bits.append(f'{p["n_writing"]} piece{"s" if p["n_writing"] != 1 else ""} in the contents')
        if p.get("n_signed"):
            bits.append(f'{p["n_signed"]} signed review{"s" if p["n_signed"] != 1 else ""}')
        if p["n_editor"]:
            bits.append(f'editor of {p["n_editor"]} issue{"s" if p["n_editor"] != 1 else ""}')
        mi = len({c["issue"] for c in p["credits"] if c["kind"] == "masthead"})
        if mi:
            bits.append(f"on the masthead of {mi} issue{'s' if mi != 1 else ''}")
        if p["n_redux"]:
            bits.append("Redux essay" + ("s" if p["n_redux"] > 1 else ""))
        return " · ".join(bits)

    def years(self, p):
        y = p["years"]
        if not y:
            return ""
        return str(y[0]) if y[0] == y[-1] else f"{y[0]}–{y[-1]}"

    # ------------------------------------------------------------ pages
    def build(self):
        if PUBLIC.exists():
            for sub in ("people", "issues", "collections"):
                shutil.rmtree(PUBLIC / sub, ignore_errors=True)
        PUBLIC.mkdir(exist_ok=True)
        self.static()
        self.home()
        self.people_index()
        self.writers()
        self.staff()
        self.issues_index()
        for c in self.collections:
            self.collection(c)
        for i in self.issues:
            self.issue_page(i)
        for p in self.people:
            self.person_page(p)
        self.redux_page()
        self.about()
        self.not_found()
        self.data_files()
        self.sitemap()
        print(f"built {len(self.urls)} pages into {PUBLIC}")

    def static(self):
        src = Path(__file__).parent / "static"
        for f in src.iterdir():
            shutil.copy(f, PUBLIC / f.name)

    def home(self):
        n_people = len(self.people)
        writers = [p for p in self.people if p["n_writing"] or p["n_signed"]]
        staff = [p for p in self.people if p["n_masthead"] or p["n_editor"]]
        top_w = sorted(writers, key=lambda p: (-(p["n_writing"] + p["n_signed"]), p["sort"]))[:30]
        top_s = sorted(staff, key=lambda p: (-len({c["issue"] for c in p["credits"] if c["kind"] in ("masthead", "editor")}),
                                             p["sort"]))[:30]
        def li(p, n, what):
            return (f'<li><a href="people/{p["slug"]}.html">{e(p["name"])}</a> '
                    f'<span class="m">{n} {what} · {self.years(p)}</span></li>')
        colls = []
        for k, c in enumerate(self.collections, 1):
            iss = [i for i in self.issues if i["collection"] == c["title"]]
            if not iss:
                continue
            ppl = {cr["name"] for i in iss for p in self.people for cr in p["credits"] if cr["issue"] == i["slug"]} if False else None
            colls.append(f'<li><span class="num">{k}</span> <a href="collections/{c["slug"]}.html">{e(c["title"])}</a> '
                         f'<span class="m">{len(iss)} issues · {min(i["year"] for i in iss)}–{max(i["year"] for i in iss)}</span></li>')
        letters = self.letter_links("people/")
        body = f"""
<section class="intro">
<p class="lede">The people who made the Whole Earth publications, 1968–2002: the writers credited in each issue’s contents, the reviewers who signed the catalog pages, the editors, and the staff named on the mastheads, from typesetters and paste-up artists to the subscription department.</p>
<p class="mono small">An index of {n_people:,} people across {len(self.issues)} issues of the Whole Earth Catalog, CoEvolution Quarterly, Whole Earth Review, Whole Earth Software Review and their sister publications. Every credit links to the page where it appears in the Internet Archive’s scan.</p>
<form class="find" action="people/" method="get" role="search"><label for="q">Find a person</label>
<input id="q" name="q" type="search" placeholder="Stewart Brand, Anne Herbert, J. Baldwin…" autocomplete="off"><button>Search</button></form>
<p class="letters" aria-label="People by surname">{letters}</p>
</section>
<section class="cols3">
<div><h2><a href="writers.html">Most-credited writers</a></h2><ol class="plist">{''.join(li(p, p['n_writing'] + p['n_signed'], 'pieces') for p in top_w)}</ol>
<p class="more"><a href="writers.html">All {len(writers):,} writers →</a></p></div>
<div><h2><a href="staff.html">Longest on the masthead</a></h2><ol class="plist">{''.join(li(p, len({c['issue'] for c in p['credits'] if c['kind'] in ('masthead','editor')}), 'issues') for p in top_s)}</ol>
<p class="more"><a href="staff.html">All {len(staff):,} editors and staff →</a></p></div>
<div><h2><a href="issues.html">The publications</a></h2><ul class="clist">{''.join(colls)}</ul>
<h2><a href="redux.html">Whole Earth Redux</a></h2>
<p>{len(self.redux)} new essays (2026), each built on one issue. <a href="redux.html">Essays and their authors →</a></p></div>
</section>"""
        self.write("index.html", self.page("index.html", TITLE, body))

    def letter_links(self, prefix):
        have = sorted({p["sort"][:1].upper() for p in self.people if p["sort"][:1].isalpha()})
        return " ".join(f'<a href="{prefix}#{l}">{l}</a>' for l in have)

    def people_index(self):
        groups = defaultdict(list)
        for p in self.people:
            l = p["sort"][:1].upper()
            groups[l if l.isalpha() else "#"].append(p)
        parts = []
        for l in sorted(groups):
            items = "".join(
                f'<li data-n="{e(p["name"].lower())}" data-k="{kinds(p)}"><a href="{p["slug"]}.html">{e(surname_first(p["name"]))}</a> '
                f'<span class="m">{self.years(p)} · {e(short_roles(p))}</span></li>' for p in groups[l])
            parts.append(f'<h2 id="{l}">{l}</h2><ul class="alist">{items}</ul>')
        body = f"""<h1>People</h1>
<p class="mono small">{len(self.people):,} people, by surname. A person is listed once for every spelling the publications used; known variants are merged.</p>
<form class="find" role="search" onsubmit="return false"><label for="q">Filter</label><input id="q" name="q" type="search" autocomplete="off" placeholder="Type a name">
<select id="k" aria-label="Show"><option value="">Everyone</option><option value="w">Writers</option><option value="s">Editors and staff</option><option value="r">Redux essayists</option></select></form>
<p class="letters">{self.letter_links('')}</p>
<p id="count" class="mono small" aria-live="polite"></p>
<div id="people">{''.join(parts)}</div>"""
        self.write("people/index.html", self.page("people/index.html", "People", body, rel="../", wide=True))

    def writers(self):
        ws = sorted([p for p in self.people if p["n_writing"] or p["n_signed"]], key=lambda p: p["sort"])
        by_n = sorted(ws, key=lambda p: (-(p["n_writing"] + p["n_signed"]), p["sort"]))
        wk = ("contents", "signed")
        rows = "".join(
            f'<tr><td><a href="people/{p["slug"]}.html">{e(p["name"])}</a></td><td class="r">{p["n_writing"]}</td>'
            f'<td class="r">{p["n_signed"]}</td>'
            f'<td class="r">{len({c["issue"] for c in p["credits"] if c["kind"] in wk})}</td><td>{self.years(p)}</td>'
            f'<td class="m">{e(", ".join(sorted({self.issue[c["issue"]]["collection"] for c in p["credits"] if c["kind"] in wk})))}</td></tr>'
            for p in by_n)
        body = f"""<h1>Writers</h1>
<p class="mono small">{len(ws):,} people, most credits first. <b>Contents</b>: pieces credited “… by Name” in an issue’s table of contents. <b>Signed</b>: reviews and short pieces signed “—Name” on the page, counted in the OCR text of the scans (a name needs at least three signatures, or two and another credit, to be listed; a few are quotations credited to their author rather than reviews). Click a column to sort.</p>
<div class="tablewrap"><table class="sortable"><thead><tr><th>Name</th><th class="r">Contents</th><th class="r">Signed</th><th class="r">Issues</th><th>Years</th><th>Publications</th></tr></thead>
<tbody>{rows}</tbody></table></div>"""
        self.write("writers.html", self.page("writers.html", "Writers", body, wide=True))

    def staff(self):
        by_group = defaultdict(lambda: defaultdict(set))  # group -> person -> roles
        tenure = defaultdict(set)
        for p in self.people:
            for c in p["credits"]:
                if c["kind"] in ("masthead", "editor"):
                    g = ROLE_GROUP.get(c["role"], "Other")
                    by_group[g][p["name"]].add(c["role"])
                    tenure[p["name"]].add(c["issue"])
        parts = []
        for g, _ in ROLE_GROUPS:
            if g not in by_group:
                continue
            ppl = sorted(by_group[g], key=lambda n: self.person[n]["sort"])
            items = "".join(
                f'<li><a href="people/{self.person[n]["slug"]}.html">{e(surname_first(n))}</a> '
                f'<span class="m">{e(", ".join(sorted(by_group[g][n])))} · {len(tenure[n])} issue{"s" if len(tenure[n])!=1 else ""} · {self.years(self.person[n])}</span></li>'
                for n in ppl)
            parts.append(f'<h2 id="{slugify(g)}">{e(g)} <span class="m">{len(ppl)}</span></h2><ul class="alist">{items}</ul>')
        toc = " · ".join(f'<a href="#{slugify(g)}">{e(g)}</a>' for g, _ in ROLE_GROUPS if g in by_group)
        n_mast = sum(1 for i in self.issues if i["masthead"])
        body = f"""<h1>Editors and staff</h1>
<p class="mono small">{len(tenure):,} people named as an issue’s editor on the Whole Earth Index, or found on an issue’s masthead (staff box) in the Internet Archive’s OCR text. Mastheads were found and read in {n_mast} of {len(self.issues)} issues. OCR can misread names: each person’s page links to the scanned masthead so you can check.</p>
<p class="mono small">{toc}</p>
{''.join(parts)}"""
        self.write("staff.html", self.page("staff.html", "Editors and staff", body, wide=True))

    def issues_index(self):
        parts = []
        for c in self.collections:
            iss = [i for i in self.issues if i["collection"] == c["title"]]
            if not iss:
                continue
            parts.append(f'<h2><a href="collections/{c["slug"]}.html">{e(c["title"])}</a></h2><ul class="ilist">'
                         + "".join(self.issue_li(i, "") for i in iss) + "</ul>")
        body = f'<h1>Issues</h1><p class="mono small">{len(self.issues)} issues, by publication.</p>' + "".join(parts)
        self.write("issues.html", self.page("issues.html", "Issues", body))

    def issue_people(self, i):
        return {c["name"] for p in self.people for c in p["credits"] if c["issue"] == i["slug"]}

    def issue_li(self, i, rel):
        n = len(self._ipeople.get(i["slug"], ())) if hasattr(self, "_ipeople") else 0
        return (f'<li><a href="{rel}issues/{i["slug"]}.html">{e(i["title"])}</a> '
                f'<span class="m">{n} people{(" · ed. " + e(i["editor"])) if i.get("editor") and not i["editor"].startswith("See") else ""}</span></li>')

    def collection(self, c):
        iss = [i for i in self.issues if i["collection"] == c["title"]]
        if not iss:
            return
        cnt = Counter()
        for i in iss:
            for n in self._ipeople.get(i["slug"], ()):
                cnt[n] += 1
        top = "".join(f'<li>{self.plink(n, "../")} <span class="m">{k} issue{"s" if k!=1 else ""}</span></li>'
                      for n, k in sorted(cnt.items(), key=lambda x: (-x[1], self.person[x[0]]["sort"]))[:60])
        body = f"""<p class="crumbs"><a href="../issues.html">Issues</a></p>
<h1>{e(c["title"])}</h1>
<div class="two"><div><p>{e(c.get("summary") or "")}</p>
<h2>Issues</h2><ul class="ilist">{''.join(self.issue_li(i, "../") for i in iss)}</ul></div>
<div><h2>People in the most issues</h2><ol class="plist">{top}</ol></div></div>"""
        self.write(f"collections/{c['slug']}.html", self.page("", c["title"], body, rel="../"))

    def issue_page(self, i):
        rel = "../"
        mast = defaultdict(list)
        for m in i["masthead"]:
            mast[m["role"]].append(m)
        order = {r: k for k, (g, rs) in enumerate(ROLE_GROUPS) for r in rs}
        mast_html = ""
        if i["masthead"]:
            leaf = i["masthead"][0]["leaf"]
            rows = "".join(
                f'<dt>{e(r)}</dt><dd>{", ".join(self.plink(m["name"], rel) + ("" if m["confirmed"] else "<sup title=\"Seen on one masthead only: check the scan\">?</sup>") for m in ms)}</dd>'
                for r, ms in sorted(mast.items(), key=lambda x: (order.get(x[0], 99), x[0])))
            mast_html = (f'<h2>Masthead</h2><p class="mono small">Read from the OCR text of the staff box '
                         f'(<a href="{self.page_url(i, leaf=leaf)}">see the scan</a>). '
                         f'<sup>?</sup> marks a name seen on only one masthead.</p><dl class="mast">{rows}</dl>')
        elif i["ocr"]:
            mast_html = '<h2>Masthead</h2><p class="mono small">No staff box was found in this issue’s OCR text.</p>'
        secs = []
        for s in i["sections"]:
            lis = []
            for en in s["entries"]:
                who = ", ".join(self.plink(n, rel) + (f' <span class="m">({how})</span>' if how not in ("wrote",) else "")
                                for n, how in en["who"])
                lis.append(f'<li><a class="pg" href="{self.page_url(i, page=en["p"])}">{e(en["p"])}</a> '
                           f'<span class="t">{e(en["t"])}{(" <span class=by>— " + who + "</span>") if who else ""}</span></li>')
            secs.append((f'<h3>{e(s["title"])}</h3>' if s["title"] else "") + f'<ul class="toc">{"".join(lis)}</ul>')
        sg = sorted((i.get("signed") or {}).items(), key=lambda x: (-x[1], self.person[x[0]]["sort"]))
        sig_html = ""
        if sg:
            sig_html = ("<h2>Signed reviews</h2><p class=\"mono small\">Reviews and pieces signed “—Name” on the page, counted in the OCR text.</p><p>"
                        + ", ".join(f'{self.plink(n, rel)} <span class="m">{k}</span>' for n, k in sg) + "</p>")
        reds = [r for r in self.redux if r["issue"] == i["slug"]]
        red_html = ""
        if reds:
            red_html = "<h2>Whole Earth Redux</h2><ul>" + "".join(
                f'<li><a href="{e(r["url"])}">{e(r["title"])}</a> by {", ".join(self.plink(a, rel) for a in r["authors"])} '
                f'<span class="m">{e(r["category"])}, {e(r["published"])}</span></li>' for r in reds) + "</ul>"
        ed = ""
        if i.get("editor") and not i["editor"].startswith("See"):
            eds = i.get("editors") or [n.strip() for n in re.split(r",\s*|\s+&\s+", i["editor"])]
            ed = "Editor: " + ", ".join(self.plink(n, rel) for n in eds) + "<br>"
        coll = next((c for c in self.collections if c["title"] == i["collection"]), None)
        n_people = len(self._ipeople.get(i["slug"], ()))
        body = f"""<p class="crumbs"><a href="../issues.html">Issues</a> / <a href="../collections/{i['collection_slug']}.html">{e(i['collection'])}</a></p>
<h1>{e(i['title'])}</h1>
<div class="two"><div>
<p class="quote">{summary_html(i['summary'])}</p>
<p class="mono small">{ed}Published: {e(i.get('season') or '')} {i['year']} · {i['pages']} pages · {n_people} people credited here<br>
Read it: <a href="https://wholeearth.info/p/{i['slug']}">Whole Earth Index</a> · <a href="https://archive.org/details/{i['id']}">Internet Archive</a></p>
{mast_html}
{sig_html}
{red_html}
</div><div>
<h2>Contents</h2>
{''.join(secs) if secs else '<p class="mono small">The Whole Earth Index has no table of contents for this issue.</p>'}
</div></div>"""
        self.write(f"issues/{i['slug']}.html", self.page("", i["title"], body, rel=rel,
                                                         desc=f"Writers and staff of {i['title']}."))

    def person_page(self, p):
        rel = "../"
        by_issue = defaultdict(list)
        for c in p["credits"]:
            if c["kind"] != "redux":
                by_issue[c["issue"]].append(c)
        iss_order = sorted(by_issue, key=lambda s: (self.issue[s]["year"], self.issues.index(self.issue[s])))
        # timeline: one cell per year 1968..2002
        years = Counter(self.issue[s]["year"] for s in by_issue)
        kinds_by_year = defaultdict(set)
        for s, cs in by_issue.items():
            for c in cs:
                kinds_by_year[self.issue[s]["year"]].add("w" if c["kind"] in ("contents", "signed") else "s")
        tl = "".join(
            f'<span class="y{" " + " ".join(sorted(kinds_by_year[y])) if y in years else ""}" title="{y}: {years.get(y, 0)} issue(s)">'
            f'{str(y)[2:] if y % 5 == 0 or y in years else ""}</span>'
            for y in range(1968, 2003))
        blocks = []
        for s in iss_order:
            i = self.issue[s]
            items = []
            thumb = None
            for c in by_issue[s]:
                if c["kind"] == "contents":
                    how = "" if c["role"] == "wrote" else f' <span class="m">({e(c["role"])})</span>'
                    items.append(f'<li><a class="pg" href="{self.page_url(i, page=c["page"])}">p. {e(c["page"])}</a> '
                                 f'{e(c["title"])}{how}{(" <span class=m>· " + e(c["section"]) + "</span>") if c["section"] else ""}</li>')
                    thumb = thumb or self.thumb(i, page=c["page"])
                elif c["kind"] == "signed":
                    lv = c["leaves"]
                    links = ", ".join(f'<a href="{self.page_url(i, leaf=l)}">{e(pg) if pg else "leaf " + str(l)}</a>' for l, pg in lv[:15])
                    more = f" and {len(lv) - 15} more" if len(lv) > 15 else ""
                    items.append(f'<li><span class="role">Signed {len(lv)} review{"s" if len(lv) != 1 else ""}</span> '
                                 f'<span class="m">p. {links}{more}</span></li>')
                    thumb = thumb or self.thumb(i, leaf=lv[0][0])
                elif c["kind"] == "editor":
                    items.append('<li><span class="role">Editor of this issue</span></li>')
                elif c["kind"] == "masthead":
                    note = "" if c.get("confirmed") else ' <span class="m">(seen on one masthead only)</span>'
                    items.append(f'<li><a class="pg" href="{self.page_url(i, leaf=c.get("leaf"))}">masthead</a> '
                                 f'<span class="role">{e(c["role"])}</span>{note}</li>')
            img = (f'<a class="th" href="{self.page_url(i)}"><img loading="lazy" src="{thumb}" alt="" width="120"></a>'
                   if thumb else "")
            blocks.append(f'<li class="iss">{img}<div><h3><a href="../issues/{s}.html">{e(i["title"])}</a></h3>'
                          f'<ul>{"".join(items)}</ul></div></li>')
        reds = [c for c in p["credits"] if c["kind"] == "redux"]
        red_html = ""
        if reds:
            red_html = "<h2>Whole Earth Redux</h2><ul>" + "".join(
                f'<li><a href="{e(c["url"])}">{e(c["title"])}</a>'
                + (f' <span class="m">on <a href="../issues/{c["issue"]}.html">{e(self.issue[c["issue"]]["title"])}</a></span>' if c["issue"] in self.issue else "")
                + "</li>" for c in reds) + "</ul>"
        # people who shared issues with them most often
        co = Counter()
        for s in by_issue:
            for n in self._ipeople.get(s, ()):
                if n != p["name"]:
                    co[n] += 1
        co_html = ", ".join(f'{self.plink(n, rel)} <span class="m">{k}</span>'
                            for n, k in sorted(co.items(), key=lambda x: (-x[1], self.person[x[0]]["sort"]))[:24] if k > 1)
        roles = ", ".join(f"{e({'wrote': 'writer', 'signed reviews': 'reviewer'}.get(r, r))}"
                          for r, _ in p["roles"])
        q = p["name"].replace(" ", "+")
        body = f"""<p class="crumbs"><a href="./">People</a></p>
<h1>{e(p['name'])}</h1>
<p class="mono">{self.roles_line(p)}{(' · ' + self.years(p)) if p['years'] else ''}</p>
<p class="mono small">Roles: {roles}</p>
<div class="timeline" aria-label="Years with credits, 1968 to 2002">{tl}</div>
<p class="legend mono small"><span class="y w"></span> wrote <span class="y s"></span> editor or masthead</p>
<ol class="issues">{''.join(blocks)}</ol>
{red_html}
{('<h2>Often in the same issues</h2><p>' + co_html + '</p>') if co_html else ''}
<p class="mono small">Search the full text of the scans for this name: <a href="https://archive.org/search?query=%22{e(q)}%22&amp;sin=TXT&amp;and%5B%5D=collection%3A%22wholeearth%22">Internet Archive full-text search</a></p>"""
        self.write(f"people/{p['slug']}.html", self.page("", p["name"], body, rel=rel,
                                                         desc=f"{p['name']} in the Whole Earth publications: {self.roles_line(p)}."))

    def redux_page(self):
        lis = "".join(
            f'<li><a href="{e(r["url"])}">{e(r["title"])}</a> by {", ".join(self.plink(a, "") for a in r["authors"])}'
            f' <span class="m">{e(r["category"])} · {e(r["published"])}'
            + (f' · on <a href="issues/{r["issue"]}.html">{e(self.issue[r["issue"]]["title"])}</a>' if r["issue"] in self.issue else "")
            + "</span></li>" for r in sorted(self.redux, key=lambda r: r["title"]))
        body = f"""<h1>Whole Earth Redux</h1>
<p>In 2026 the Whole Earth Index began publishing <a href="https://redux.wholeearth.info/">Whole Earth Redux</a>: new essays, each of which takes one artifact from the Index and follows its history forward. Here are the {len(self.redux)} essays so far, their authors, and the issue each one starts from.</p>
<ul class="rlist">{lis}</ul>"""
        self.write("redux.html", self.page("redux.html", "Whole Earth Redux", body))

    def about(self):
        n_ocr = sum(1 for i in self.issues if i["ocr"])
        n_mast = sum(1 for i in self.issues if i["masthead"])
        n_contents = sum(1 for i in self.issues if i["sections"])
        body = f"""<h1>About</h1>
<div class="prose">
<p><strong>{TITLE}</strong> is an index of the people who wrote, edited and produced the Whole Earth publications: the Whole Earth Catalog and its supplements (1968–1998), CoEvolution Quarterly (1974–1985), the Whole Earth Software Catalog and Review (1984–1985), Whole Earth Review and Whole Earth (1985–2002), and the books published alongside them. It lists every person it could find, and for each one, every issue they appear in and what they did there.</p>
<h2>Where the names come from</h2>
<ul>
<li><strong>Tables of contents.</strong> The <a href="https://wholeearth.info/">Whole Earth Index</a> transcribed the contents of {n_contents} of its {len(self.issues)} issues. Entries written “Title by Name” give the writers; “edited by”, “interview with”, “photographs by” and the like give other roles. Most catalog reviews have no byline in the contents, so they are not counted here.</li>
<li><strong>Signed reviews.</strong> Whole Earth reviews end with the reviewer’s name after a dash (“—J. Baldwin”). Those signatures were counted in the OCR text of every page. A name is kept if it is signed at least three times, or twice and also credited another way, which drops most OCR misreadings and one-off headings; a few names are quotations credited to their author rather than reviews. The earliest catalogs signed with initials (“—SB”), which are not counted.</li>
<li><strong>Editors.</strong> The Whole Earth Index names the editor of {sum(1 for i in self.issues if i.get('editor'))} issues.</li>
<li><strong>Mastheads.</strong> The staff box of each issue was found in the Internet Archive’s OCR (optical character recognition) text of the scans, and names were read from the lines that follow a job title (“Typesetting”, “Paste-up”, “Subscriptions & Back Issues”…). Staff boxes were found in {n_mast} of the {n_ocr} issues with OCR text. OCR misreads letters and mixes up columns, so a name seen on only one masthead is marked with a question mark, and close misspellings of a name seen elsewhere were merged into it. Every masthead credit links to the scanned page.</li>
<li><strong>Whole Earth Redux.</strong> The authors of the {len(self.redux)} essays published so far at <a href="https://redux.wholeearth.info/">redux.wholeearth.info</a>, linked to the issue each essay is about.</li>
</ul>
<p>A person who appears under more than one spelling (“Patty Phelan” and “Patricia Phelan”, “Evelyn Eldridge” and “Evelyn Eldridge-Diaz”) is merged where the match is clear. Others may remain separate. Corrections are welcome: <a href="mailto:info@archive.org?subject=Whole%20Earth%20People">info@archive.org</a>.</p>
<h2>Reading the issues</h2>
<p>The issues themselves are on the <a href="https://wholeearth.info/">Whole Earth Index</a>, made by Barry Threw with Gray Area, with design and development by Jon Gacnik and Mindy Seu. The scans are in the Internet Archive’s <a href="https://archive.org/details/wholeearth">Whole Earth collection</a>, digitized from copies donated by Fred Collopy, Kevin Kelly, Danica Remy, Howard Rheingold and the Long Now Foundation. This site links to both and copies none of the publications’ text. The typefaces are the Whole Earth Index’s versions of Latin Modern (GUST Font License).</p>
<p>Stewart Brand on the people behind the publications, and their photographs: <a href="https://www.wholeearth50th.com/photos">wholeearth50th.com</a>.</p>
<h2>Accessibility</h2>
<p>The site is plain HTML that works without JavaScript; the name filter on the People page is the only script. It is meant to meet WCAG 2.1 AA (Web Content Accessibility Guidelines). If something does not work for you, please write to <a href="mailto:info@archive.org?subject=Whole%20Earth%20People">info@archive.org</a>.</p>
<h2>Web archives</h2>
<p>Web archives are welcome to capture this site. If your crawler has trouble capturing it, contact info@archive.org. There is a <a href="sitemap.xml">sitemap</a>.</p>
<h2>Who made this</h2>
<p>This site was made by Claude, an AI model made by Anthropic, working in Claude Code at the direction of Mark Graham (Internet Archive). Mark Graham decided what it should be and what it should cover; Claude did the research and wrote the code. Built {date.today():%-d %B %Y}.</p>
</div>"""
        self.write("about.html", self.page("about.html", "About", body))

    def not_found(self):
        body = '<h1>Not found</h1><p>There is no page at this address. Try <a href="/wholeearth/people/">People</a> or the <a href="/wholeearth/">front page</a>.</p>'
        self.write("404.html", self.page("", "Not found", body, rel="/wholeearth/"))

    def data_files(self):
        slim = [{"n": p["name"], "s": p["slug"], "y": self.years(p), "k": kinds(p)} for p in self.people]
        (PUBLIC / "people.json").write_text(json.dumps(slim, ensure_ascii=False, separators=(",", ":")))
        rows = ["name\trole\tkind\tissue\tyear\ttitle\tpage"]
        for p in self.people:
            for c in p["credits"]:
                yr = self.issue[c["issue"]]["year"] if c["issue"] in self.issue else ""
                rows.append("\t".join(str(x if x is not None else "").replace("\t", " ") for x in
                                      (p["name"], c["role"], c["kind"], c["issue"] or "", yr, c.get("title") or (str(c["count"]) + " signed" if c.get("count") else ""), c.get("page") or "")))
        (PUBLIC / "credits.tsv").write_text("\n".join(rows) + "\n")

    def sitemap(self):
        xs = "".join(f"<url><loc>{BASE_URL}{u}</loc></url>" for u in sorted(set(self.urls)))
        (PUBLIC / "sitemap.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{xs}</urlset>\n')


def summary_html(s):
    """The Index's summaries are short quotes with *emphasis* or <em>; keep only that markup."""
    s = escape(s or "")
    s = re.sub(r"&lt;(/?)em&gt;", r"<\1em>", s)
    s = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", s)
    return s


def kinds(p):
    k = ""
    if p["n_writing"] or p.get("n_signed"):
        k += "w"
    if p["n_masthead"] or p["n_editor"]:
        k += "s"
    if p["n_redux"]:
        k += "r"
    return k


def short_roles(p):
    return ", ".join({"wrote": "writer"}.get(r, r) for r, _ in p["roles"][:3])


def surname_first(name):
    from .common import sort_key  # noqa
    parts = name.split()
    if len(parts) < 2:
        return name
    suffix = ""
    if parts[-1].strip(",").lower() in ("jr.", "jr", "sr.", "ii", "iii"):
        suffix = " " + parts[-1]
        parts = parts[:-1]
    i = len(parts) - 1
    while i > 1 and parts[i - 1].lower() in {"de", "van", "von", "der", "di", "da", "le", "la", "du"}:
        i -= 1
    return " ".join(parts[i:]) + ", " + " ".join(parts[:i]) + suffix


def main():
    s = Site()
    s._ipeople = defaultdict(set)
    for p in s.people:
        for c in p["credits"]:
            if c["issue"] and c["kind"] != "redux":
                s._ipeople[c["issue"]].add(p["name"])
    s.build()


if __name__ == "__main__":
    main()
