"""Turn the harvested Whole Earth Index pages, Redux essays and Internet Archive OCR
into data/index.json: issues, people and every credit that links them.

    python -m we.parse
"""
import html
import json
import re
from collections import Counter, defaultdict

from .common import DATA, RAW, clean_name, next_data, ocr_pages, page_numbers, slugify, sort_key

# ---------------------------------------------------------------- names

NOT_PEOPLE_WORDS = {
    "readers", "reader", "staff", "editors", "editor", "mail", "catalog", "catalogs", "magazine", "review",
    "quarterly", "whole", "earth", "coevolution", "cq", "wer", "foundation", "press", "inc", "co", "company",
    "services", "service", "printing", "mailing", "list", "lists", "san", "francisco", "california", "berkeley",
    "sausalito", "oakland", "menlo", "park", "valley", "mill", "street", "the", "of", "for", "our", "your",
    "various", "others", "anonymous", "everybody", "everyone", "people", "subscribers", "subscriptions",
    "university", "institute", "society", "association", "department", "office", "center", "centre", "council",
    "corporation", "corp", "ltd", "news", "times", "journal", "books", "book", "library", "point", "well",
    "software", "hardware", "computer", "computers", "systems", "network", "project", "projects", "group",
    "committee", "board", "directors", "trust", "fund", "agency", "bureau", "national", "american", "federal",
    "us", "u.s.", "usa", "panther", "party", "workshop", "collective", "commune", "lab", "laboratory",
    "photographs", "illustrations", "drawings", "photos", "cover", "back", "issue", "issues", "page", "pages",
    "supplement", "index", "letters", "gossip", "update", "updates", "reviews", "contents", "and", "&",
    "unknown", "et", "al", "assorted", "friends", "many", "several", "some", "this", "that", "these", "who",
    "what", "how", "why", "when", "where", "with", "from", "on", "in", "at", "to", "a", "an", "by",
    "typesetting", "proofreading", "production", "layout", "camera", "manager", "director", "design",
    "circulation", "bookkeeping", "accounting", "typing", "shipping", "receiving", "research", "interns",
    "assistant", "associate", "managing", "contributing", "publisher", "business", "advertising", "printer",
    "printed", "bindery", "envelopes", "halftones", "stats", "dept", "box", "suite", "road", "avenue",
    "ca", "ny", "ma", "or", "wa", "nm", "tx", "il", "co.", "inc.", "llc", "mailroom", "fulfillment",
    "telephone", "phone", "fax", "address", "copyright", "rights", "reserved", "printed", "usa.",
    "soft", "tech", "nomadics", "shelter", "learning", "communications", "community", "craft", "land", "use",
    "outline", "goudy", "distribution", "transcribing", "restaurant", "coop", "co-op", "food", "foods", "hills",
    "canada", "store", "shop", "bookstore", "books.", "market", "cafe", "gallery", "museum", "farm", "ranch",
    "politics", "understanding", "wholesome", "systems.", "gossip", "dept.", "editorial", "photo", "cartoon",
}

NAME_RE = re.compile(
    r"^(?:[A-Z][a-zA-Z'\-]*\.?|[A-Z]\.(?:[A-Z]\.)*|(?:de|van|von|der|di|da|du|le|la|Mc|Mac|O')\w*)"
    r"(?: (?:[A-Z][a-zA-Z'\-]*\.?|[A-Z]\.(?:[A-Z]\.)*|de|van|von|der|di|da|du|le|la|Jr\.?|Sr\.?|II|III|IV)){0,4}$"
)


def is_person(name, strict=False):
    if not name or len(name) < 4 or len(name) > 40:
        return False
    if re.search(r"\d|@|/|\\|\?|!|#|\$|%|=|\+|\|", name):
        return False
    words = name.split()
    if len(words) < 2 or len(words) > 5:
        return False
    if not NAME_RE.match(name):
        return False
    low = [w.lower().strip(".,'") for w in words]
    if any(w in NOT_PEOPLE_WORDS for w in low):
        return False
    if strict:
        # OCR mastheads: every word capitalised normally, surname at least 2 letters, no ALL-CAPS runs
        if any(len(w) > 3 and w.isupper() for w in words):
            return False
        if len(words[-1].strip(".")) < 2:
            return False
        if sum(1 for w in words if len(w.strip(".")) == 1) > 2:
            return False
    return True


def split_names(s):
    s = re.sub(r"\s*\((?:[^)]*)\)", "", s)
    s = re.sub(r",?\s+(?:and|&)\s+", ", ", s)
    s = s.replace(" with ", ", ")
    out = []
    for part in s.split(","):
        n = clean_name(part)
        n = re.sub(r"^(?:Dr|Mr|Mrs|Ms|Prof|Rev)\.?\s+", "", n)
        if n:
            out.append(n)
    return out


# ---------------------------------------------------------------- contents credits

CREDIT_RE = re.compile(
    r"^(?P<title>.*?)[,:]?\s+(?P<how>edited by|compiled by|photographs by|photos by|illustrated by|"
    r"drawings by|interviewed by|interview by|by|interview with|conversation with)\s+(?P<who>[^:]+)$",
    re.I,
)
HOW = {
    "by": "wrote", "edited by": "edited", "compiled by": "compiled", "photographs by": "photographs",
    "photos by": "photographs", "illustrated by": "illustrations", "drawings by": "illustrations",
    "interviewed by": "interviewer", "interview by": "interviewer", "interview with": "interviewed",
    "conversation with": "interviewed",
}


def parse_entry(text):
    m = CREDIT_RE.match(text.strip())
    if not m:
        return text.strip(), []
    title, how, who = m.group("title").strip(), HOW[m.group("how").lower()], m.group("who")
    names = [n for n in split_names(who) if is_person(n)]
    if not names:
        return text.strip(), []
    if how in ("interviewed",) and not title:
        title = text.strip()
    return (title or text.strip()), [(n, how) for n in names]


# ---------------------------------------------------------------- mastheads (OCR)

ROLES = [
    "Editor-in-Chief", "Editor in Chief", "Executive Editor", "Managing Editor", "Senior Editor", "Senior Editors",
    "Associate Editor", "Associate Editors", "Assistant Editor", "Assistant Editors", "Contributing Editor",
    "Contributing Editors", "Guest Editor", "Guest Editors", "Copy Editor", "Copy Editors", "Copyeditor", "Copyediting",
    "Software Editor", "Review Editor", "Reviews Editor", "Book Review Editor", "Fiction Editor", "Poetry Editor",
    "News Editor", "Art Editor", "Photo Editor", "Picture Editor", "Research Editor", "Technical Editor",
    "Editorial Assistant", "Editorial Assistants", "Editorial Staff", "Editorial Director", "Usual Editor",
    "Editors", "Editor", "Art Director", "Art Directors", "Design Director", "Designer", "Designers", "Design",
    "Production Manager", "Production Director", "Production Coordinator", "Production Assistant",
    "Production Staff", "Production", "Production & Layout", "Lay Out", "Layout", "Paste-up", "Pasteup",
    "Typesetting", "Typesetter", "Typography", "Proofreading", "Proofreader", "Proofreaders", "Indexing",
    "Camera", "Camera Work", "Darkroom", "Photography", "Photographer", "Photographers", "Illustration",
    "Illustrations", "Illustrator", "Illustrators", "Cartoonist", "Cover Art", "Cover Design",
    "Office Manager", "Office Staff", "Business Manager", "General Manager", "Financial Manager", "Bookkeeper",
    "Bookkeeping", "Accounting", "Accountant", "Circulation Manager", "Circulation Director", "Circulation",
    "Subscriptions", "Subscriptions & Back Issues", "Subscription Services", "Subscriber Services",
    "Customer Service", "Fulfillment", "Mail Order", "Mail Room", "Mailroom", "Shipping", "Shipping & Receiving",
    "Advertising", "Advertising Sales", "Advertising Director", "Marketing", "Marketing Director",
    "Promotion", "Publicity", "Public Relations", "Publisher", "Associate Publisher", "Publishing",
    "Research", "Researcher", "Researchers", "Research Assistant", "Interns", "Intern", "Receptionist",
    "Development", "Fundraising", "Executive Director", "President", "Board of Directors", "Point Board",
    "POINT Board", "Point Foundation Board", "Interview Transcriptions", "Transcriptions", "Transcription",
    "Projects", "Library", "Librarian", "Computer Systems", "Systems Manager", "Data Entry",
    "Columnists", "Correspondents", "Contributors", "Truck Driver", "Janitor", "Gardener", "Cook",
    "Logo", "Headlines", "Typing", "Word Processing", "Assistant to the Editor", "Assistant to the Publisher",
    "Staff", "Thanks", "Special Thanks", "Traffic", "Art Direction", "Art Department",
    "Subscriptions and Back Issues", "Soft Tech and Nomadics", "Soft Tech", "Nomadics", "Land Use", "Learning",
    "Film", "Medical", "Uncommon Courtesy", "Production Traffic", "Mailing Services", "Mailing List Services",
    "Printing", "Printer", "Bindery", "Color Separations", "Legal Counsel", "Attorney", "Auditor", "Banking", "Distribution", "Transcribing", "Shipping Clerk",
]
NOT_STAFF_ROLES = {"Thanks", "Special Thanks", "Contributors", "Correspondents", "Columnists"}
# job titles that end a run of names but whose "names" are firms, not staff
FIRM_ROLES = {"Mailing Services", "Mailing List Services", "Printing", "Printer", "Bindery", "Color Separations",
              "Legal Counsel", "Attorney", "Auditor", "Banking"}
SECTION_ROLES = {"Art", "Soft Tech and Nomadics", "Soft Tech", "Nomadics", "Land Use", "Learning", "Film", "Medical"}
STRIP_WORDS = {"In-Chief", "Emeritus", "Founder", "Guest", "Asst", "Asst.", "Employee", "Acquisitions", "Consultant",
               "Consultants", "Dead", "Bullpen", "DC", "Orinda", "Infinite", "Games", "Senior", "Junior"}
ROLE_RE = re.compile(
    r"(?<![A-Za-z])(" + "|".join(re.escape(r) for r in sorted(ROLES, key=len, reverse=True))
    + r"|Art(?= (?!Kleiner|Spiegelman)[A-Z]))(?![a-z])"
)
ROLE_CANON = {
    "Editor in Chief": "Editor-in-Chief", "Lay Out": "Layout", "Pasteup": "Paste-up", "Copyeditor": "Copy Editor",
    "Copyediting": "Copy Editor", "Mailroom": "Mail Room", "POINT Board": "Point Board",
    "Point Foundation Board": "Point Board",
}
MASTHEAD_STRONG = re.compile(
    r"(?i)\b(managing editor|art director|production manager|typesetting|proofreading|office manager|"
    r"circulation|bookkeeping|paste-?up|business manager|editorial assistant|contributing editors?|"
    r"assistant editor|associate editor|subscriptions)\b"
)


def canon_role(r):
    r = ROLE_CANON.get(r, r)
    if r.endswith("s") and r[:-1] in ROLES and r not in ("Subscriptions", "Interns", "Contributors", "Columnists",
                                                          "Correspondents", "Illustrations", "Projects", "Headlines"):
        r = r[:-1]
    return r


def masthead_pages(pages):
    """Leaf indexes that look like a staff box: at least four different strong role words."""
    out = []
    for i, p in enumerate(pages):
        kinds = {m.group(1).lower().replace("-", "") for m in MASTHEAD_STRONG.finditer(p)}
        if len(kinds) >= 4:
            out.append(i)
    return out


def parse_masthead(text):
    """[(name, role)] from one OCR page. Only text following a role word, up to the next role word."""
    out = []
    # work line by line: column layouts keep role + names on one line most of the time
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        ms = list(ROLE_RE.finditer(line))
        if not ms:
            continue
        for k, m in enumerate(ms):
            role = canon_role(m.group(1))
            end = ms[k + 1].start() if k + 1 < len(ms) else len(line)
            if role in FIRM_ROLES:
                continue
            if role in SECTION_ROLES:
                role = "Section Editor (" + role + ")"
            seg = line[m.end():end].strip(" :—–-,.")
            if not seg:
                continue
            seg = re.sub(r"\s*\([^)]*\)", "", seg)
            # names separated by commas, "and", "&", or run together ("Anne Herbert Stewart Brand")
            for chunk in split_names(seg):
                for n in split_run(chunk):
                    w = n.split()
                    while w and w[0] in STRIP_WORDS:
                        w = w[1:]
                    while w and w[-1] in STRIP_WORDS:
                        w = w[:-1]
                    n = " ".join(w)
                    if is_person(n, strict=True):
                        out.append((n, role))
    return out


DASH_RE = re.compile(r"([A-Z][A-Za-z.'\- ]{2,32}?)\s*[-—–]{3,}[\s\-—–]*([a-z][a-z ,&/]{1,40}[a-z])")


def parse_dash_credits(text):
    """Catalog-era credits: 'Stewart Brand---------editor', 'Lois Brand------food, corrections, bookkeeping'."""
    out = []
    for m in DASH_RE.finditer(text):
        name = clean_name(m.group(1))
        w = name.split()
        name = next((" ".join(w[-k:]) for k in (4, 3, 2) if len(w) >= k and is_person(" ".join(w[-k:]), strict=True)
                     and w[-k][:1].isupper()), None)
        role = m.group(2).strip()
        role = re.split(r"\s{2,}| (?:a|an|the|to|of|for) ", role)[0].strip(" ,")
        role = re.sub(r"(?:\s+[a-z]{1,2})+$", "", role)
        if not name or not role or len(role) < 3:
            continue
        out.append((name, role[:1].upper() + role[1:]))
    return out


def split_run(chunk):
    """'Anne Herbert Stewart Brand' -> ['Anne Herbert', 'Stewart Brand'] when it splits evenly into pairs."""
    w = chunk.split()
    if len(w) in (4, 6) and all(x[0].isupper() and len(x.strip(".")) > 1 for x in w) and not any(
        x.lower() in ("de", "van", "von", "der", "la", "le") for x in w
    ):
        return [" ".join(w[i:i + 2]) for i in range(0, len(w), 2)]
    return [chunk]


def near(name, pool):
    """A confirmed name one or two OCR slips away (same first word and initial of surname)."""
    import difflib
    first = name.split()[0]
    cands = [p for p in pool if p.split()[0] == first and p.split()[-1][:1] == name.split()[-1][:1]]
    best = difflib.get_close_matches(name, cands, n=1, cutoff=0.86)
    return best[0] if best else None


SIG_RE = re.compile(r"[—–]\s?([A-Z][A-Za-z.'\-]+(?: (?:[A-Z][A-Za-z.'\-]+|de|van|von)){1,3})(?=\s*(?:\n|$|\[|\())")


def signatures(pages):
    """[(name, leaf)] for every '—Name' that ends a line: how Whole Earth signed its reviews."""
    out = []
    for leaf, t in enumerate(pages):
        for m in SIG_RE.finditer(t):
            n = clean_name(m.group(1))
            if is_person(n, strict=True):
                out.append((n, leaf))
    return out


# ---------------------------------------------------------------- redux

def parse_redux():
    out = []
    for f in sorted((RAW / "redux").glob("*.html")):
        if f.name.startswith("_"):
            continue
        h = f.read_text()
        title = re.search(r"<title>Whole Earth Redux \| (.*?)</title>", h)
        body = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
        txt = html.unescape(re.sub(r"<[^>]+>", "\n", body))
        txt = re.sub(r"\n\s*\n+", "\n", txt)
        author = re.search(r"Author:\s*\n?\s*(.+)", txt)
        pub = re.search(r"Published:\s*\n?\s*(.+)", txt)
        cat = re.search(r"Category:\s*\n?\s*(.+)", txt)
        ref = re.search(r'href="https?://wholeearth\.info/p/([^"?#]+)', h)
        out.append({
            "slug": f.stem,
            "title": html.unescape(title.group(1)).strip() if title else f.stem,
            "url": f"https://redux.wholeearth.info/index/{f.stem}",
            "authors": [n for n in split_names(author.group(1))] if author else [],
            "published": pub.group(1).strip() if pub else "",
            "category": cat.group(1).strip() if cat else "",
            "issue": ref.group(1) if ref else None,
        })
    return out


# ---------------------------------------------------------------- aliases

def load_aliases():
    """data/aliases.tsv: variant<TAB>canonical name."""
    p = DATA / "aliases.tsv"
    out = {}
    if p.exists():
        for line in p.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                a, b = line.split("\t")[:2]
                out[clean_name(a)] = clean_name(b)
    return out


def load_not_people():
    p = DATA / "not_people.txt"
    return {clean_name(x) for x in p.read_text().splitlines() if x.strip() and not x.startswith("#")} if p.exists() else set()


# ---------------------------------------------------------------- main

def main():
    home = next_data(RAW / "home.html")
    collections = home["collections"]
    coll_slug = {c["title"]: c["slug"] for c in collections}
    order = {p["slug"]: i for i, p in enumerate(home["publications"])}
    aliases = load_aliases()
    not_people = load_not_people()

    def canon(n):
        n = clean_name(n)
        return aliases.get(n, n)

    issues = []
    credits = []  # (name, role, kind, issue_slug, title, page, section)
    masthead_report = {}
    for f in sorted((RAW / "p").glob("*.html"), key=lambda f: order.get(f.stem, 999)):
        p = next_data(f)["publication"]
        slug = p["slug"]
        iss = {
            "slug": slug, "id": p["identifier"], "title": p["title"], "collection": p["collection"],
            "collection_slug": coll_slug.get(p["collection"], slugify(p["collection"])),
            "year": p["year"], "season": p.get("season"), "pages": p["pages"], "summary": p.get("summary") or "",
            "editor": p.get("editor"), "sections": [],
        }
        # contents
        for c in p.get("contents") or []:
            sec = {"title": c["title"] or "", "entries": []}
            for c2 in c["content"]:
                if not isinstance(c2.get("content"), dict):
                    continue
                for text, page in c2["content"].items():
                    title, people = parse_entry(text)
                    people = [(canon(n), how) for n, how in people if canon(n) not in not_people]
                    sec["entries"].append({"t": title, "p": page, "who": people, "sub": c2.get("title") or ""})
                    for n, how in people:
                        credits.append({"name": n, "role": how, "kind": "contents", "issue": slug, "title": title,
                                        "page": page, "section": c["title"] or ""})
            if sec["entries"]:
                iss["sections"].append(sec)
        # editor(s)
        ed = p.get("editor") or ""
        iss["editors"] = [canon(n) for n in split_names(ed)] if ed and not ed.startswith("See ") else []
        if ed and not ed.startswith("See ") and ed != "Black Panther Party":
            for n in split_names(ed):
                n = canon(n)
                if is_person(n):
                    credits.append({"name": n, "role": "Editor", "kind": "editor", "issue": slug, "title": "",
                                    "page": None, "section": ""})
        # masthead from OCR
        pages = ocr_pages(p["identifier"])
        iss["ocr"] = pages is not None
        iss["masthead"] = []
        if pages:
            pn = page_numbers(p["identifier"])
            seen = set()
            found = [(leaf, parse_masthead(pages[leaf])) for leaf in masthead_pages(pages)]
            for leaf, txt in enumerate(pages):
                dc = parse_dash_credits(txt)
                if len(dc) >= 4:
                    found.append((leaf, dc))
            for leaf, rows in found:
                if len({n for n, _ in rows}) < 3:  # a photo credit or a stray line, not a staff box
                    continue
                for n, role in rows:
                    n = canon(n)
                    if n in not_people or (n, role) in seen:
                        continue
                    seen.add((n, role))
                    iss["masthead"].append({"name": n, "role": role, "leaf": leaf, "page": pn.get(leaf)})
            masthead_report[slug] = len(iss["masthead"])
            iss["_sigs"] = [(canon(n), leaf, pn.get(leaf)) for n, leaf in signatures(pages)]
        issues.append(iss)

    redux = parse_redux()

    # masthead names: keep those seen in 2+ issues, or also credited elsewhere, or with a real staff role
    mast_issues = defaultdict(set)
    for iss in issues:
        for m in iss["masthead"]:
            mast_issues[m["name"]].add(iss["slug"])
    other_names = {c["name"] for c in credits}
    confirmed_names = {n for n, v in mast_issues.items() if len(v) >= 2} | other_names
    fixes = {}
    for n in mast_issues:
        if n in confirmed_names:
            continue
        m = near(n, confirmed_names)
        if not m:
            m = next((c for c in sorted(confirmed_names, key=len, reverse=True)
                      if len(c.split()) >= 2 and (n.startswith(c + " ") or n.endswith(" " + c))), None)
        if m:
            fixes[n] = m
    for iss in issues:
        for m in iss["masthead"]:
            if m["name"] in fixes:
                m["ocr_name"], m["name"] = m["name"], fixes[m["name"]]
                mast_issues[m["name"]].add(iss["slug"])
        # one name per role per issue after fixes
        seen, uniq = set(), []
        for m in iss["masthead"]:
            if (m["name"], m["role"]) not in seen:
                seen.add((m["name"], m["role"]))
                uniq.append(m)
        iss["masthead"] = uniq
    for iss in issues:
        kept = []
        for m in iss["masthead"]:
            m["confirmed"] = len(mast_issues[m["name"]]) >= 2 or m["name"] in other_names
            if m["confirmed"] or (m["role"] not in NOT_STAFF_ROLES and m["role"] != "Library"):
                kept.append(m)
        iss["masthead"] = kept
        for m in kept:
            credits.append({"name": m["name"], "role": m["role"], "kind": "masthead", "issue": iss["slug"],
                            "title": "", "page": m["page"], "leaf": m["leaf"], "section": "",
                            "confirmed": m["confirmed"]})
    # signed reviews: keep names signed 3+ times, or 2+ and credited some other way
    sig_count = Counter(n for iss in issues for n, _, _ in iss.get("_sigs", []))
    known = {c["name"] for c in credits}
    for iss in issues:
        per = defaultdict(list)
        for n, leaf, page in iss.pop("_sigs", []):
            if n in not_people:
                continue
            if sig_count[n] >= 3 or (sig_count[n] >= 2 and n in known):
                per[n].append((leaf, page))
        iss["signed"] = {n: len(v) for n, v in per.items()}
        for n, v in per.items():
            credits.append({"name": n, "role": "signed reviews", "kind": "signed", "issue": iss["slug"], "title": "",
                            "page": None, "leaves": [[l, p] for l, p in v], "count": len(v), "section": ""})
    for r in redux:
        r["authors"] = [canon(a) for a in r["authors"]]
        for a in r["authors"]:
            credits.append({"name": a, "role": "Redux essay", "kind": "redux", "issue": r["issue"],
                            "title": r["title"], "page": None, "url": r["url"], "section": ""})

    # "Paul R. Ehrlich" / "Gary Paul Nabhan" -> "Paul Ehrlich" / "Gary Nabhan" when the short form is also used
    names = {c["name"] for c in credits}
    short = {}
    for n in names:
        w = n.split()
        if len(w) == 3 and w[2] not in ("Jr.", "Sr.", "II", "III") and w[1].lower() not in ("de", "van", "von", "der", "la", "le"):
            s2 = f"{w[0]} {w[2]}"
            if s2 in names:
                short[n] = s2
    for c in credits:
        c["name"] = short.get(c["name"], c["name"])
    for iss in issues:
        for m in iss["masthead"]:
            m["name"] = short.get(m["name"], m["name"])
        sg = Counter()
        for n, k in (iss.get("signed") or {}).items():
            sg[short.get(n, n)] += k
        iss["signed"] = dict(sg)
        iss["editors"] = [short.get(n, n) for n in iss.get("editors", [])]
        for sec in iss["sections"]:
            for en in sec["entries"]:
                en["who"] = [(short.get(n, n), how) for n, how in en["who"]]

    people = defaultdict(lambda: {"credits": []})
    for c in credits:
        people[c["name"]]["credits"].append(c)
    slugs = {}
    out_people = []
    for name, d in people.items():
        s = slugify(name)
        if s in slugs.values():
            s = s + "-2"
        slugs[name] = s
        kinds = Counter(c["kind"] for c in d["credits"])
        years = sorted({next(i["year"] for i in issues if i["slug"] == c["issue"]) for c in d["credits"]
                        if c["issue"] and c["kind"] != "redux"})
        out_people.append({
            "name": name, "slug": s, "sort": sort_key(name), "credits": d["credits"],
            "n_writing": kinds["contents"], "n_editor": kinds["editor"], "n_masthead": kinds["masthead"],
            "n_redux": kinds["redux"],
            "n_signed": sum(c.get("count", 0) for c in d["credits"] if c["kind"] == "signed"),
            "n_issues": len({c["issue"] for c in d["credits"] if c["kind"] != "redux"}),
            "years": years,
            "roles": Counter(c["role"] for c in d["credits"]).most_common(),
        })
    out_people.sort(key=lambda p: p["sort"])
    DATA.mkdir(exist_ok=True)
    (DATA / "index.json").write_text(json.dumps({
        "collections": collections, "issues": issues, "people": out_people, "redux": redux,
        "info": next_data(RAW / "information.html").get("about_credits", ""),
    }, ensure_ascii=False, indent=0))
    print(f"issues {len(issues)}  with OCR {sum(i['ocr'] for i in issues)}  people {len(out_people)}  "
          f"credits {len(credits)}  writers {sum(1 for p in out_people if p['n_writing'])}  "
          f"staff {sum(1 for p in out_people if p['n_masthead'] or p['n_editor'])}  "
          f"signers {sum(1 for p in out_people if p['n_signed'])} ({sum(p['n_signed'] for p in out_people)} signed)  redux {len(redux)}")


if __name__ == "__main__":
    main()
