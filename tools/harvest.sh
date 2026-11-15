#!/bin/bash
# Fetch everything the index is built from into raw/ (about 60 MB):
#   the Whole Earth Index front page, Info page and 147 issue pages (1 s apart),
#   the Whole Earth Redux essays, and each issue's per-page OCR text from the Internet Archive.
set -u
cd "$(dirname "$0")/.."
mkdir -p raw/p raw/redux raw/ocr
UA="Mozilla/5.0 (compatible; Internet Archive Wayback Machine Labs)"
curl -sS -A "$UA" -o raw/home.html https://wholeearth.info/
curl -sS -A "$UA" -o raw/information.html https://wholeearth.info/information
grep -o 'href="/p/[^"]*"' raw/home.html | sed 's/href="\/p\///;s/"//' | sort -u > raw/slugs.txt
while read s; do
  [ -s raw/p/$s.html ] || { curl -sS -A "$UA" -o raw/p/$s.html https://wholeearth.info/p/$s; sleep 1; }
done < raw/slugs.txt
curl -sS -A "$UA" -o raw/redux/_index.html https://redux.wholeearth.info/
for s in $(grep -o 'redux.wholeearth.info/index/[a-z0-9-]*' raw/redux/_index.html | sort -u | sed 's#.*/##'); do
  [ -s raw/redux/$s.html ] || { curl -sS -A "$UA" -o raw/redux/$s.html https://redux.wholeearth.info/index/$s; sleep 1; }
done
./tools/fetch_ocr.sh
