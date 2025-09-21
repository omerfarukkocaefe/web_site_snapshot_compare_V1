#!/usr/bin/env python3
#\"\"\"capture_snapshot_v3.py

#Birleştirilmiş araç: hem özet (snapshot) alma hem de iki özet dosyasını karşılaştırma işlevlerini içerir.
#Özellikler:
# - Tek URL için snapshot al (JSON + optional PNG): --capture --url ... --out ...
# + python3 capture_snapshot.py capture --url https://example.com --out snapshots/example.json

# - Dosyadan birden fazla URL al ve hepsini kaydet: --capture-file --file urls.txt --out-dir snapshots/
# + python3 capture_snapshot.py capture --file urls.txt --out-dir snaps/base

# + Karşılaştırma için iki farklı json dosyası oluşturulur. Yani "capture_snapshots.py" python dosyası iki kez farklı çıktılarla çalıştılır.
# + Daha sonra bu iki script çıktısı "compare_snapshots.py" ile kıyaslanır.

#\"\"\"

import argparse
import json
import os
import sys
import hashlib
import requests
from requests.exceptions import RequestException
from dataclasses import asdict
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from collections import Counter
import re

def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def slugify(url: str) -> str:
    """
    URL'yi güvenli bir slug string'e çevirir.
    - Harf ve rakamları korur
    - Diğer karakterleri '-' ile değiştirir
    - Baştaki/sondaki '-' işaretlerini temizler
    - Maksimum 120 karaktere sınırlar
    """
    s = re.sub(r"[^a-zA-Z0-9]+", "-", url)  # harf/rakam dışındaki her şeyi tire yap
    return s.strip("-").lower()[:120]

def take_snapshot(url: str) -> dict:
    """
    Verilen URL'den snapshot alır:
      - status code
      - title
      - visible text hash
      - tam HTML
    """
    try:
        resp = requests.get(url, timeout=10)
    except Exception as e:
        return {"url": url, "error": str(e)}

    # sayfanın ham HTML'i
    html = resp.text

    # BeautifulSoup ile parse
    soup = BeautifulSoup(html, "html.parser")

    # Başlık
    title = soup.title.string.strip() if soup.title else ""

    # Görünür metin (script/style hariç)
    for tag in soup(["script", "style"]):
        tag.extract()

    visible_text = soup.get_text(separator=" ", strip=True)
    norm = re.sub(r'\s+', ' ', visible_text).strip()

    # Kelime-dışı metinleri (noktalama/emoji vs.) de yakala:
    tokens = re.findall(r'[^\s]+', norm)   # boşluk olmayan tüm parçalar
    text_hash = hashlib.sha256(' '.join(tokens).encode('utf-8')).hexdigest()
    # DOM özet bilgisi
    dom = {
        "hash": text_hash,
        "text_len": len(visible_text)
    }

    # HTTP özet bilgisi (basit: sadece status_code üzerinden)
    http = {
        "status_code": resp.status_code,
        "hash": hashlib.sha256(str(resp.status_code).encode("utf-8")).hexdigest()
    }
    
    # soup hazırlandıktan sonra:
    # --- tag_counts ---
    tags = [t.name for t in soup.find_all(True)]
    tag_counts = dict(Counter(tags))  # JSON'a uygun

    # --- assets (liste + unique + sayılar + hash) ---
    img_srcs   = [ (t.get('src') or '').strip()   for t in soup.find_all('img')    if t.get('src') ]
    link_hrefs = [ (t.get('href') or '').strip()  for t in soup.find_all('link')   if t.get('href') ]
    script_srcs= [ (t.get('src') or '').strip()   for t in soup.find_all('script') if t.get('src') ]

    img_srcs_u   = sorted(set(img_srcs))
    link_hrefs_u = sorted(set(link_hrefs))
    script_srcs_u= sorted(set(script_srcs))

    assets = {
        'img_srcs': img_srcs,                     # duplikasyonlar korunur
        'link_hrefs': link_hrefs,
        'script_srcs': script_srcs,
        'img_count': len(img_srcs),
        'link_count': len(link_hrefs),
        'script_count': len(script_srcs),

        'img_srcs_unique': img_srcs_u,            # benzersizler
        'link_hrefs_unique': link_hrefs_u,
        'script_srcs_unique': script_srcs_u,

        # Liste hash (duplikasyonları yakalar)
        'imgs_list_hash': _sha('\n'.join(img_srcs)),
        'links_list_hash': _sha('\n'.join(link_hrefs)),
        'scripts_list_hash': _sha('\n'.join(script_srcs)),

        # Unique hash (yeni/çıkan kaynakları yakalar)
        'imgs_unique_hash': _sha('\n'.join(img_srcs_u)),
        'links_unique_hash': _sha('\n'.join(link_hrefs_u)),
        'scripts_unique_hash': _sha('\n'.join(script_srcs_u)),
    }

    # --- normalize HTML hash ---
    normalized_html = re.sub(r'\s+', ' ', soup.decode())
    html_hash = _sha(normalized_html)

    structure = {
        'tag_counts': tag_counts,
        'assets': assets,
        'html_hash': html_hash,
    }
    """
    result['structure'] = {
        'tag_counts': tag_counts,
        'assets': assets,
        'html_hash': html_hash,
    }
    """

    return {
        "url": url,
        "status_code": resp.status_code,
        "title": title,
        "text_hash": text_hash,
        "length": len(html),
        "html": html,
        #"dom": dom,
        "http": http,
        "dom": {"hash": text_hash, "text_len": len(visible_text)},
        "structure": structure
    }

def capture_single(url: str, out_path: str, meta: dict | None = None) -> dict:
    snap = take_snapshot(url)

    # Hem dict hem dataclass ile uyumlu olsun:
    if 'get' in dir(snap) and isinstance(snap, dict):
        snap_dict = snap
    elif 'type' in dir(snap) and is_dataclass(snap):  # is_dataclass check
        snap_dict = asdict(snap)
    else:
        raise TypeError("take_snapshot() dict veya dataclass döndürmelidir.")

    if meta:
        snap_dict["meta"] = meta

    dirpath = os.path.dirname(out_path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snap_dict, f, ensure_ascii=False, indent=2)

    return snap_dict

def read_urls_from_file(path: str) -> List[str]:
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    urls = []
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            urls.append(line)
    return urls


def capture_from_list(file_path: str, out_dir: str) -> List[Dict[str, Any]]:
    out_dir = os.path.abspath(out_dir)
    ensure_dir(out_dir)
    urls = read_urls_from_file(file_path)
    results = []
    for idx, url in enumerate(urls, start=1):
        slug = slugify(url) or f'url{idx}'
        fname = f"{idx:03d}_{slug}.json"
        out_json = os.path.join(out_dir, fname)
        try:
            res = capture_single(url, out_json)
            results.append({'index': idx, 'url': url, 'status': 'ok', 'out': res})
        except Exception as e:
            results.append({'index': idx, 'url': url, 'status': 'error', 'exception': repr(e)})
    return results


def _read_png_hex_near_json(json_path: str) -> Optional[str]:
    try:
        j = load_json(json_path)
        if not j:
            return None
        if j.get('screenshot_hex'):
            return j.get('screenshot_hex')
        base, _ = os.path.splitext(json_path)
        png = base + '.png'
        if os.path.exists(png):
            with open(png, 'rb') as f:
                return f.read().hex()
    except Exception:
        return None
    return None

def main():
    ap = argparse.ArgumentParser(description='Capture and compare snapshots (merged tool)')
    sub = ap.add_subparsers(dest='cmd', required=True)

    cap = sub.add_parser('capture', help='Capture snapshot(s)')
    capgrp = cap.add_mutually_exclusive_group(required=True)
    capgrp.add_argument('--url', '-u', help='Single URL to capture')
    capgrp.add_argument('--file', '-f', help='File with URLs (one per line) to capture')
    cap.add_argument('--out', help='Output JSON path for single URL mode (e.g. snapshots/first.json)')
    cap.add_argument('--out-dir', help='Output directory for list mode (e.g. snapshots/)')

    cmp = sub.add_parser('compare', help='Compare two snapshot JSON files')
    cmp.add_argument('--first', '-f', required=True, help='First snapshot JSON path (baseline)')
    cmp.add_argument('--second', '-s', required=True, help='Second snapshot JSON path (current)')
    cmp.add_argument('--out', '-o', required=False, help='Optional output diff json path')

    cmpd = sub.add_parser('compare-dirs', help='Compare two directories of snapshot JSON files by basename')
    cmpd.add_argument('--base-dir', required=True, help='Directory with baseline JSONs')
    cmpd.add_argument('--current-dir', required=True, help='Directory with current JSONs')
    cmpd.add_argument('--out-dir', required=False, help='Where to write diffs (default: diffs/)')

    args = ap.parse_args()
    
    DIFFS_DIR = 'diffs' 
    ensure_dir(DIFFS_DIR)
    

    if args.cmd == 'capture':
        if args.url:
            if not args.out:
                print(json.dumps({'error': 'out_required_for_single_url', 'msg': 'Use --out to set output JSON path for single URL mode.'}, ensure_ascii=False, indent=2))
                sys.exit(2)
            res = capture_single(args.url, args.out, None)
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            if not args.out_dir:
                print(json.dumps({'error': 'out_dir_required_for_file_mode', 'msg': 'Use --out-dir to set directory for saving snapshots.'}, ensure_ascii=False, indent=2))
                sys.exit(2)
            try:
                results = capture_from_list(args.file, args.out_dir)
                print(json.dumps({'message': 'batch_complete', 'count': len(results), 'results': results}, ensure_ascii=False, indent=2))
            except FileNotFoundError as e:
                print(json.dumps({'error': 'file_not_found', 'path': str(e)}, ensure_ascii=False, indent=2))
                sys.exit(2)
    elif args.cmd == 'compare':
        res = compare_snapshots(args.first, args.second, out_json=args.out)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.cmd == 'compare-dirs':
        res = compare_dirs(args.base_dir, args.current_dir, out_dir=args.out_dir)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        ap.print_help()


if __name__ == '__main__':
    main()
