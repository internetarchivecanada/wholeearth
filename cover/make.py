"""Render cover/cover.html (then screenshot it to cover/wholeearth-cover.jpg, 1200x630)."""
import json
from pathlib import Path
here = Path(__file__).parent
d = json.loads((here.parent / "data" / "index.json").read_text())
ppl = sorted(d["people"], key=lambda p: -(p["n_writing"] + 2 * p["n_masthead"] + 2 * p["n_editor"]))[:90]
names = " · ".join(p["name"].replace(" ", "&nbsp;") for p in ppl)
fonts = (here.parent / "public" / "fonts").resolve()
html = f"""<!doctype html><meta charset=utf-8><style>
@font-face{{font-family:M;src:url(file://{fonts}/WEMLMRoman8-Regular.woff2)}}
@font-face{{font-family:T;src:url(file://{fonts}/WEMLMMono10-Regular.woff2)}}
html,body{{margin:0;width:1200px;height:630px;background:#000;color:#fff;overflow:hidden}}
.n{{position:absolute;inset:150px 40px 40px 40px;font-family:M;font-size:25px;line-height:1.45;color:#9a9a9a;text-align:justify}}
.t{{position:absolute;left:40px;top:34px;font-family:M;font-size:64px;letter-spacing:-.5px}}
.s{{position:absolute;right:40px;top:58px;font-family:T;font-size:20px;text-align:right;line-height:1.4}}
.r{{position:absolute;left:40px;right:40px;top:130px;border-top:2px solid #fff}}
</style><div class=t>Whole Earth People</div><div class=s>{len(d['people']):,} writers, editors and staff<br>{len(d['issues'])} issues · 1968–2002</div><div class=r></div><div class=n>{names}</div>"""
(here / "cover.html").write_text(html)
