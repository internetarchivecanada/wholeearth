"""Render cover/cover.html, then screenshot it to cover/wholeearth-cover.jpg (1200x630, like the other tiles)."""
import json
from pathlib import Path
here = Path(__file__).parent
root = here.parent
d = json.loads((root / "data" / "index.json").read_text())
ppl = sorted(d["people"], key=lambda p: -(p["n_writing"] + p.get("n_signed", 0) // 4 + 2 * p["n_masthead"] + 2 * p["n_editor"]))[:44]
names = " · ".join(p["name"].replace(" ", "&nbsp;") for p in ppl)
pub = (root / "public").resolve()
roles = [("Writers", "#a63f24"), ("Reviewers", "#2e6a4c"), ("Editors", "#1f4f7a"), ("Artists", "#8a5300"),
         ("Staff", "#6a3d73"), ("Board", "#46621a"), ("Interviewed", "#97305a"), ("Redux", "#0e6570")]
pills = "".join(f'<span style="background:{c}">{r}</span>' for r, c in roles)
html = f"""<!doctype html><meta charset=utf-8><style>
@font-face{{font-family:M;src:url(file://{pub}/fonts/WEMLMRoman8-Italic.woff2)}}
@font-face{{font-family:R;src:url(file://{pub}/fonts/WEMLMRoman8-Regular.woff2)}}
@font-face{{font-family:T;src:url(file://{pub}/fonts/WEMLMMono10-Regular.woff2)}}
html,body{{margin:0;width:1200px;height:630px;overflow:hidden;background:#2f3b2b;color:#f4ede0}}
.logo{{position:absolute;left:60px;top:70px;display:flex;align-items:baseline;gap:22px}}
.logo img{{height:96px}}
.logo b{{font:italic 400 92px/1 M}}
.sub{{position:absolute;left:62px;top:196px;font:22px/1.4 T;opacity:.9}}
.pills{{position:absolute;left:60px;top:258px;display:flex;gap:10px;flex-wrap:wrap;width:1080px}}
.pills span{{font:20px/1 T;color:#fff;padding:9px 16px;border-radius:999px}}
.paper{{position:absolute;left:0;right:0;bottom:0;height:270px;background:#f4ede0;color:#5e564a;padding:30px 60px;box-sizing:border-box;font:24px/1.55 R;text-align:justify}}
</style>
<div class=logo><img src="file://{pub}/img/whole-earth-paper.png"><b>People</b></div>
<div class=sub>{len(d['people']):,} writers, reviewers, editors &amp; staff · {len(d['issues'])} issues · 1968–2002</div>
<div class=pills>{pills}</div>
<div class=paper>{names}</div>"""
(here / "cover.html").write_text(html)
