"""Shared paths and helpers for the Whole Earth people index."""
import gzip, json, os, re, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = Path(os.environ.get("WE_RAW", ROOT / "raw"))
DATA = ROOT / "data"
PUBLIC = ROOT / "public"


def next_data(path):
    h = Path(path).read_text()
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    return json.loads(m.group(1))["props"]["pageProps"]


def ocr_pages(identifier):
    """Per-leaf OCR text for an Internet Archive item, or None."""
    t = RAW / "ocr" / f"{identifier}_hocr_searchtext.txt.gz"
    i = RAW / "ocr" / f"{identifier}_hocr_pageindex.json.gz"
    if not (t.exists() and i.exists()):
        return None
    try:
        text = gzip.open(t, "rt").read()
        idx = json.load(gzip.open(i, "rt"))
    except Exception:
        return None
    return [text[a:b] for a, b, *_ in idx]


def page_numbers(identifier):
    """leaf index -> printed page number (string), from page_numbers.json."""
    p = RAW / "ocr" / f"{identifier}_page_numbers.json"
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text())
    except Exception:
        return {}
    out = {}
    for row in d.get("pages", []):
        if row.get("pageNumber"):
            out[row["leafNum"]] = str(row["pageNumber"])
    return out


def clean_name(s):
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"\s+", " ", s).strip(" ,;:.-–—_~|\"'()[]*")
    if len(s) > 3 and s.isupper():
        s = " ".join(w if re.fullmatch(r"(?:[A-Z]\.)+|II|III|IV", w) else
                     re.sub(r"(^|[-'])([a-z])", lambda m: m.group(1) + m.group(2).upper(), w.lower())
                     for w in s.split())
        s = re.sub(r"\bMc([a-z])", lambda m: "Mc" + m.group(1).upper(), s)
    s = re.sub(r"\bO' (?=[A-Z])", "O'", s)
    s = re.sub(r"\b([A-Z])\.\s*(?=[A-Z]\.)", r"\1.", s)  # J. D. -> J.D.
    s = re.sub(r"\b([A-Z])\.(?=[A-Z][a-z])", r"\1. ", s)  # J.Baldwin -> J. Baldwin
    return s


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "x"


def sort_key(name):
    """Surname-first key: 'Stewart Brand' -> 'brand stewart'."""
    parts = name.split()
    suffixes = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}
    while len(parts) > 1 and parts[-1].lower().strip(",") in suffixes:
        parts = parts[:-1]
    if len(parts) == 1:
        return slugify(parts[0])
    i = len(parts) - 1
    while i > 1 and parts[i - 1].lower() in {"de", "van", "von", "der", "di", "da", "le", "la", "du"}:
        i -= 1
    return slugify(" ".join(parts[i:]) + " " + " ".join(parts[:i]))
