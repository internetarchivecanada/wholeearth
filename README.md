# Whole Earth People

An index of the writers, editors and staff of the Whole Earth publications (Whole Earth Catalog,
CoEvolution Quarterly, Whole Earth Software Review, Whole Earth Review, Whole Earth, 1968–2002),
built from the [Whole Earth Index](https://wholeearth.info/), its
[Whole Earth Redux](https://redux.wholeearth.info/) essays and the Internet Archive's OCR text of the scans.

Live: https://wayback-labs.sf.archive.org/wholeearth/ (Wayback Machine Labs studio, static tile `wholeearth`).

## How it is built

```
tools/harvest.sh        # raw/: Index pages, Redux essays, per-page OCR (hocr searchtext + page index) per issue
python3 -m we.parse     # data/index.json: issues, people, credits
python3 -m we.site      # public/: the static site (committed: the studio serves public/ from main as is)
```

Sources of names, in `we/parse.py`:

- **Contents** — the Index's tables of contents; "Title by Name", "edited by", "interview with", "photographs by"…
- **Editors** — the Index's `editor` field per issue.
- **Mastheads** — OCR pages with at least four staff-box job titles; names are read from the text that follows
  each job title on a line. A name seen on only one masthead (and nowhere else) is shown with a "?"; a close
  misspelling of a confirmed name (same first name and surname initial, difflib ratio ≥ 0.86) is merged into it.
- **Redux** — essay authors and the issue each essay is about.

Corrections: `data/aliases.tsv` (variant → canonical name) and `data/not_people.txt` (strings that are not people).
Rebuild after editing either.

## Deploying

The studio dir `/opt/services/wholeearth` is a checkout of this repo (remote `canada`). Push to `main`, then
`ssh wayback-labs.sf.archive.org sudo /opt/services/_scripts/deploy-tile deploy wholeearth --expect "$(git rev-parse HEAD)"`
(see DEPLOY.md in internetarchivecanada/waybacklabs). `public/` must be rebuilt and committed before pushing.
The landing-page tile lives in the waybacklabs repo (`tiles/wholeearth.menu`, `covers/wholeearth-cover.jpg`).
