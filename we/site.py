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
CSS_V = "6"

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


ART_ROLES = {"Art Director", "Art Direction", "Art Department", "Design Director", "Designer", "Design", "Photography",
             "Photographer", "Illustration", "Illustrations", "Illustrator", "Cartoonist", "Cover Art", "Cover Design",
             "Logo", "Headlines", "Section Editor (Art)"}
BOARD_ROLES = {"Point Board", "Board of Directors", "President"}

# slug, page, label, short label, colour class, what is counted, description
CATS = [
    ("writers", "writers.html", "Writers", "Writers", "Pieces credited “Title by Name” in an issue’s table of contents."),
    ("reviewers", "reviewers.html", "Reviewers", "Reviewers", "Reviews and short pieces signed “—Name” on the catalog pages."),
    ("editors", "editors.html", "Editors", "Editors", "Issue editors, managing, assistant, contributing and section editors."),
    ("artists", "artists.html", "Artists & photographers", "Artists", "Illustrators, photographers, designers and art directors."),
    ("staff", "staff.html", "Production & office staff", "Staff", "Typesetting, paste-up, camera, proofreading, subscriptions, the office, research and the library."),
    ("board", "board.html", "Point Foundation board", "Board", "Board members of the Point Foundation, the publisher."),
    ("interviewed", "interviewed.html", "Interviewed", "Interviewed", "People interviewed or in conversation in the contents."),
    ("essayists", "essayists.html", "Redux essayists", "Redux", "Authors of the 2026 Whole Earth Redux essays."),
]
CAT = {c[0]: c for c in CATS}


def person_cats(p):
    """{category: {"n": credits, "issues": set, "roles": set}} for one person."""
    out = defaultdict(lambda: {"n": 0, "issues": set(), "roles": set()})

    def add(cat, c, n=1, role=None):
        out[cat]["n"] += n
        if c.get("issue"):
            out[cat]["issues"].add(c["issue"])
        if role:
            out[cat]["roles"].add(role)
    for c in p["credits"]:
        k, r = c["kind"], c["role"]
        if k == "contents":
            if r in ("wrote", "edited", "compiled", "interviewer"):
                add("writers", c, role={"wrote": "writer", "interviewer": "interviewer"}.get(r, r))
            elif r in ("photographs", "illustrations"):
                add("artists", c, role=r)
            elif r == "interviewed":
                add("interviewed", c)
        elif k == "signed":
            add("reviewers", c, n=c.get("count", 1))
        elif k == "editor":
            add("editors", c, role="Editor of the issue")
        elif k == "masthead":
            if r in ART_ROLES:
                add("artists", c, role=r)
            elif r in BOARD_ROLES:
                add("board", c, role=r)
            elif ROLE_GROUP.get(r) == "Editors" or r.startswith("Section Editor"):
                add("editors", c, role=r)
            else:
                add("staff", c, role=r)
        elif k == "redux":
            add("essayists", c)
    return out


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
        nav = [("issues.html", "Issues"), ("redux.html", "Redux essays"), ("about.html", "About")]
        navh = "".join(f'<a href="{rel}{h}"{" aria-current=page" if h == path else ""}>{x}</a>' for h, x in nav)
        pills = [f'<a class="pill all" href="{rel}people/"{" aria-current=page" if path == "people/index.html" else ""}>'
                 f'Everyone <span>{len(self.people):,}</span></a>']
        for slug, href, label, short, _ in CATS:
            cur = " aria-current=page" if path == href else ""
            pills.append(f'<a class="pill c-{slug}" href="{rel}{href}"{cur}>{e(label)} <span>{self.cat_count[slug]:,}</span></a>')
        rolebar = f'<nav class="rolebar" aria-label="Browse people by role"><span class="rb-l">Browse people</span>{"".join(pills)}</nav>' 
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(t)}</title>
<meta name="description" content="{e(desc or 'Writers, editors and staff of the Whole Earth Catalog, CoEvolution Quarterly, Whole Earth Review and their sister publications, 1968–2002.')}">
<link rel="icon" href="{rel}img/favicon.png">
<link rel="stylesheet" href="{rel}style.css?v={CSS_V}">
</head><body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="top-in"><a class="brand" href="{rel}./"><img src="{rel}img/whole-earth-paper.png" alt="Whole Earth" width="190" height="24"><span>People</span></a><span class="tag">writers, editors &amp; staff of the Whole Earth publications, 1968–2002</span><nav class="sitenav" aria-label="Site">{navh}</nav></div>
{rolebar}</header>
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
        for c in CATS:
            self.category_page(c)
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
        cards = []
        for slug, href, label, short, desc in CATS:
            members = self.cat_members[slug]
            top = sorted(members, key=lambda n: (-self.cats[n][slug]["n"], self.person[n]["sort"]))[:8]
            unit = {"reviewers": "reviews", "writers": "pieces", "essayists": "essays", "interviewed": "interviews"}.get(slug, "issues")
            def val(n):
                d = self.cats[n][slug]
                return d["n"] if unit in ("reviews", "pieces", "essays", "interviews") else len(d["issues"])
            lis = "".join(f'<li><a href="people/{self.person[n]["slug"]}.html">{e(n)}</a> <span class="m">{val(n)}</span></li>' for n in top)
            cards.append(f'''<section class="card c-{slug}"><h2><a href="{href}">{e(label)}</a></h2>
<p class="big">{len(members):,} <span>people</span></p><p class="desc">{e(desc)}</p>
<ol class="plist">{lis}</ol><p class="more"><a href="{href}">All {e(short.lower()) if short != "Redux" else "Redux essayists"} →</a></p></section>''')
        colls = []
        for k, c in enumerate(self.collections, 1):
            iss = [i for i in self.issues if i["collection"] == c["title"]]
            if iss:
                colls.append(f'<li><a href="collections/{c["slug"]}.html">{e(c["title"])}</a> '
                             f'<span class="m">{len(iss)} issues · {min(i["year"] for i in iss)}–{max(i["year"] for i in iss)}</span></li>')
        body = f"""
<section class="intro">
<p class="lede">Everyone who made the Whole Earth publications, 1968–2002: the writers, the reviewers who signed the catalog pages, the editors, the artists and photographers, the people who set the type, pasted up the pages and answered the mail, and the Point Foundation board.</p>
<form class="find" action="people/" method="get" role="search"><label for="q">Find a person</label>
<input id="q" name="q" type="search" placeholder="Stewart Brand, Anne Herbert, J. Baldwin…" autocomplete="off"><button>Search</button></form>
<p class="mono small">{len(self.people):,} people across {len(self.issues)} issues of the Whole Earth Catalog, CoEvolution Quarterly, Whole Earth Software Review, Whole Earth Review and Whole Earth. Many people appear under more than one role. Every credit links to its page in the Internet Archive’s scan.</p>
</section>
<div class="cards">{''.join(cards)}</div>
<section class="pubs"><h2><a href="issues.html">The publications</a></h2><ul class="clist">{''.join(colls)}</ul>
<p class="more"><a href="people/">Everyone, A to Z →</a> · <a href="redux.html">The Redux essays →</a></p></section>"""
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
                f'<li data-n="{e(p["name"].lower())}" data-k="{" ".join(self.cat_order(p["name"]))}"><a href="{p["slug"]}.html">{e(surname_first(p["name"]))}</a> '
                f'<span class="m">{self.years(p)} · {e(", ".join(CAT[c][3] for c in self.cat_order(p["name"])))}</span></li>' for p in groups[l])
            parts.append(f'<h2 id="{l}">{l}</h2><ul class="alist">{items}</ul>')
        body = f"""<h1>People</h1>
<p class="mono small">{len(self.people):,} people, by surname, in every role. Known spelling variants are merged. Choose a role in the bar above, or narrow this list:</p>
<form class="find" role="search" onsubmit="return false"><label for="q">Filter</label><input id="q" name="q" type="search" autocomplete="off" placeholder="Type a name">
<select id="k" aria-label="Show"><option value="">Everyone</option>{"".join(f'<option value="{c[0]}">{e(c[2])}</option>' for c in CATS)}</select></form>
<p class="letters">{self.letter_links('')}</p>
<p id="count" class="mono small" aria-live="polite"></p>
<div id="people">{''.join(parts)}</div>"""
        self.write("people/index.html", self.page("people/index.html", "People", body, rel="../", wide=True))

    def category_page(self, cat):
        slug, href, label, short, desc = cat
        members = self.cat_members[slug]
        counted = slug in ("writers", "reviewers", "interviewed", "essayists")
        unit = {"writers": "Pieces", "reviewers": "Signed reviews", "interviewed": "Interviews", "essayists": "Essays"}.get(slug)
        rows = []
        for n in sorted(members, key=lambda n: (-(self.cats[n][slug]["n"] if counted else len(self.cats[n][slug]["issues"])), self.person[n]["sort"])):
            d = self.cats[n][slug]
            p = self.person[n]
            iss = [self.issue[x] for x in d["issues"] if x in self.issue]
            yrs = sorted(i["year"] for i in iss)
            yr = "" if not yrs else (str(yrs[0]) if yrs[0] == yrs[-1] else f"{yrs[0]}–{yrs[-1]}")
            other = ", ".join(CAT[c][3] for c in self.cat_order(n) if c != slug)
            roles = ", ".join(sorted(d["roles"]))
            rows.append(f'<tr data-n="{e(n.lower())}"><td><a href="people/{p["slug"]}.html">{e(n)}</a></td>'
                        + (f'<td class="r">{d["n"]}</td>' if counted else "")
                        + f'<td class="r">{len(iss)}</td><td>{yr}</td>'
                        + (f'<td class="m">{e(roles)}</td>' if slug not in ("reviewers", "essayists", "interviewed") else "")
                        + f'<td class="m">{e(other)}</td></tr>')
        head = ("<th>Name</th>" + (f'<th class="r">{unit}</th>' if counted else "") + '<th class="r">Issues</th><th>Years</th>'
                + ("<th>Roles</th>" if slug not in ("reviewers", "essayists", "interviewed") else "") + "<th>Also</th>")
        notes = {
            "reviewers": "Counted in the OCR text of the scans: a name needs at least three signatures, or two and another credit. A few are quotations credited to their author. The earliest catalogs signed with initials (“—SB”), which are not counted.",
            "editors": "From the Whole Earth Index’s editor of each issue and from the mastheads read in the OCR text (mastheads were found in %d of %d issues)." % (sum(1 for i in self.issues if i["masthead"]), len(self.issues)),
            "artists": "From the mastheads, and from “photographs by” and “illustrated by” in the contents.",
            "staff": "From the mastheads read in the OCR text (found in %d of %d issues). OCR can misread names; each person’s page links to the scanned masthead." % (sum(1 for i in self.issues if i["masthead"]), len(self.issues)),
            "board": "From the mastheads read in the OCR text.",
            "writers": "Pieces with no byline in the contents, which includes most catalog reviews, are under Reviewers.",
            "interviewed": "From the tables of contents (“interview with”, “conversation with”).",
            "essayists": "Each essay starts from one issue; see <a href=\"redux.html\">the essays</a>.",
        }
        body = f"""<div class="cat-head c-{slug}"><h1>{e(label)}</h1><p class="big">{len(members):,} <span>people</span></p></div>
<p class="desc">{e(desc)}</p>
<p class="mono small">{notes[slug]} Click a column heading to sort.</p>
<form class="find" role="search" onsubmit="return false"><label for="tq">Filter</label><input id="tq" type="search" autocomplete="off" placeholder="Type a name" data-table="t"></form>
<p id="tcount" class="mono small" aria-live="polite"></p>
<div class="tablewrap"><table class="sortable c-{slug}" id="t"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>"""
        self.write(href, self.page(href, label, body, wide=True, desc=f"{label} of the Whole Earth publications, 1968–2002: {len(members):,} people."))

    def cat_order(self, n):
        return [c[0] for c in CATS if c[0] in self.cats[n]]

    def chips(self, n, rel):
        return "".join(f'<a class="chip c-{c}" href="{rel}{CAT[c][1]}">{e(CAT[c][2])}</a>' for c in self.cat_order(n))

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
                    links = ", ".join(f'<a href="{self.page_url(i, leaf=l)}">{e(pg) if pg else "scan " + str(l)}</a>' for l, pg in lv[:15])
                    more = f" and {len(lv) - 15} more" if len(lv) > 15 else ""
                    items.append(f'<li><span class="role">Signed {len(lv)} review{"s" if len(lv) != 1 else ""}</span> '
                                 f'<span class="m">pages {links}{more}</span></li>')
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
<p class="chips">{self.chips(p["name"], rel)}</p>
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
<p>The issues themselves are on the <a href="https://wholeearth.info/">Whole Earth Index</a>, made by Barry Threw with Gray Area, with design and development by Jon Gacnik and Mindy Seu. The scans are in the Internet Archive’s <a href="https://archive.org/details/wholeearth">Whole Earth collection</a>, digitized from copies donated by Fred Collopy, Kevin Kelly, Danica Remy, Howard Rheingold and the Long Now Foundation. This site links to both and copies none of the publications’ text. The “Whole Earth” wordmark in the header is the Whole Earth Catalog’s, taken from the logo the Whole Earth Index uses. The typefaces are the Whole Earth Index’s versions of Latin Modern (GUST Font License).</p>
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
    s.cats = {p["name"]: person_cats(p) for p in s.people}
    s.cat_members = {c[0]: [n for n, d in s.cats.items() if c[0] in d] for c in CATS}
    s.cat_count = {k: len(v) for k, v in s.cat_members.items()}
    s.build()


if __name__ == "__main__":
    main()
