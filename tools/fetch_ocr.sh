#!/bin/bash
# Fetch per-page OCR text (hocr searchtext + page index + page numbers) for every issue, 6 at a time.
cd "$(dirname "$0")/.."
python3 -I -c "
import re,json,glob
for f in sorted(glob.glob('raw/p/*.html')):
    h=open(f).read(); p=json.loads(re.search(r'id=\"__NEXT_DATA__\"[^>]*>(.*?)</script>',h,re.S).group(1))['props']['pageProps']['publication']; print(p['identifier'])
" > raw/identifiers.txt
one(){
  id=$1; suf=$2; out=raw/ocr/${id}_$suf
  [ -s "$out" ] && return
  for try in 1 2 3 4; do
    code=$(curl -sS -L --max-time 300 -o "$out.part" -w "%{http_code}" "https://archive.org/download/$id/${id}_$suf")
    [ "$code" = 200 ] && { mv "$out.part" "$out"; return; }
    rm -f "$out.part"; [ "$code" = 404 ] && break; sleep $((try*10))
  done
  echo "FAIL $id $suf $code"
}
export -f one
for id in $(cat raw/identifiers.txt); do for s in hocr_searchtext.txt.gz hocr_pageindex.json.gz page_numbers.json; do echo "$id $s"; done; done \
  | xargs -P 6 -n 2 bash -c 'one "$0" "$1"'
echo DONE
