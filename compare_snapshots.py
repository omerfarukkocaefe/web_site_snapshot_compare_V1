#!/usr/bin/env python3
#\"\"\"compare_snapshots.py

#İki önceden alınmış snapshot JSON dosyasını karşılaştırır (ve varsa PNG'lerini kullanır).
#Çıktı diffs/<first_basename>_vs_<second_basename>.json veya klasör şeklinde kaydedilir.

#Kullanım:
# Tek çift
#python3 compare_snapshots_v1.py pair --first snaps/base/001_example-com.json --second snaps/curr/001_example-com.json --out diffs/001_diff.json

# Tüm klasör
#python3 compare_snapshots_v1.py dirs --base-dir snaps/base --current-dir snaps/curr --out-dir diffs#\"\"\"

import argparse
import json
import os
import sys
from typing import Optional
from typing import Dict, Any

# Görsel karşılaştırma kütüphaneleri opsiyonel
_VIS_LIBS = False
try:
    from PIL import Image
    import imagehash
    import numpy as np
    from skimage.metrics import structural_similarity as ssim
    _VIS_LIBS = True
except Exception:
    _VIS_LIBS = False

DIFFS_DIR = 'diffs'

def dom_signature(visible_text: str) -> Dict[str, Any]:
    return {
        'text_len': len(visible_text),
        'hash': stable_hash(visible_text),
    }


# ---- Görsel metrikler (opsiyonel) ----
def visual_metrics(png_hex_a: str, png_hex_b: str) -> Optional[Dict[str, Any]]:
    if not _VIS_LIBS:
        return None
    import io
    a = Image.open(io.BytesIO(bytes.fromhex(png_hex_a))).convert('L')
    b = Image.open(io.BytesIO(bytes.fromhex(png_hex_b))).convert('L')
    ph_a = imagehash.phash(a)
    ph_b = imagehash.phash(b)
    ph_dist = (ph_a - ph_b)
    aw, ah = a.size
    bw, bh = b.size
    if (aw, ah) != (bw, bh):
        b = b.resize((aw, ah))
    import numpy as np
    ssim_score = float(ssim(np.array(a), np.array(b)))
    return {
        'phash_distance': int(ph_dist),
        'ssim': ssim_score,
    }

def slugify(url: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", url)
    return s.strip('-').lower()[:120]


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def save_json(path: str, data: Dict[str, Any]):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def read_png_hex_near_json(json_path: str) -> Optional[str]:
    """If the snapshot JSON doesn't contain screenshot_hex, try to find a PNG with same basename."""
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


def compare(first_json: str, second_json: str, out_json: Optional[str] = None) -> dict:
    first_json = os.path.abspath(first_json)
    second_json = os.path.abspath(second_json)
    if not os.path.exists(first_json):
        return {'error': 'first_not_found', 'path': first_json}
    if not os.path.exists(second_json):
        return {'error': 'second_not_found', 'path': second_json}

    first = load_json(first_json)
    second = load_json(second_json)
    if not first or not second:
        return {'error': 'failed_to_load_json', 'first': bool(first), 'second': bool(second)}

    # ensure screenshot_hex present by trying adjacent png files
    if not first.get('screenshot_hex'):
        fh = read_png_hex_near_json(first_json)
        if fh:
            first['screenshot_hex'] = fh
    if not second.get('screenshot_hex'):
        sh = read_png_hex_near_json(second_json)
        if sh:
            second['screenshot_hex'] = sh
    
    http_changed = (
        first.get('http', {}).get('hash') != second.get('http', {}).get('hash')
    )

    # "text_changed": yalnızca görünen metin (visible text) farkı
    text_changed = (
        first.get('dom', {}).get('hash') != second.get('dom', {}).get('hash')
    )

    # Metin uzunluğu farkı (rapor için faydalı)
    text_len_delta = (
        (second.get('dom', {}).get('text_len') or 0) - (first.get('dom', {}).get('text_len') or 0)
    )

    # ------------------ Yapısal (gerçek DOM sinyalleri) ------------------
    f_struct = first.get('structure', {}) or {}
    s_struct = second.get('structure', {}) or {}

    # Tag sayımları
    tag_counts_changed = (f_struct.get('tag_counts') != s_struct.get('tag_counts'))

    # Assets
    f_assets = f_struct.get('assets', {}) or {}
    s_assets = s_struct.get('assets', {}) or {}

    assets_changed = any([
        # Liste hash'leri (duplikasyonları da yakalar)
        f_assets.get('imgs_list_hash')     != s_assets.get('imgs_list_hash'),
        f_assets.get('links_list_hash')    != s_assets.get('links_list_hash'),
        f_assets.get('scripts_list_hash')  != s_assets.get('scripts_list_hash'),

        # Unique hash'ler (yeni/kalkan kaynaklar)
        f_assets.get('imgs_unique_hash')   != s_assets.get('imgs_unique_hash'),
        f_assets.get('links_unique_hash')  != s_assets.get('links_unique_hash'),
        f_assets.get('scripts_unique_hash')!= s_assets.get('scripts_unique_hash'),

        # Sayılar
        f_assets.get('img_count')          != s_assets.get('img_count'),
        f_assets.get('link_count')         != s_assets.get('link_count'),
        f_assets.get('script_count')       != s_assets.get('script_count'),
    ])


    # Normalize HTML hash farkı
    html_hash_changed = (f_struct.get('html_hash') != s_struct.get('html_hash'))

    # Tag sayımları farkı
    tag_counts_changed = (f_struct.get('tag_counts') != s_struct.get('tag_counts'))

    # "dom_changed": yapısal değişimin özeti (html/tag/assets'ten herhangi biri)
    dom_changed = any([html_hash_changed, tag_counts_changed, assets_changed])

    visual = None
    if _VIS_LIBS and first.get('screenshot_hex') and second.get('screenshot_hex'):
        try:
            visual = visual_metrics(first['screenshot_hex'], second['screenshot_hex'])
        except Exception as e:
            visual = {'error': 'visual_failed', 'exception': repr(e)}

    # prepare output name
    fbase = os.path.splitext(os.path.basename(first_json))[0]
    sbase = os.path.splitext(os.path.basename(second_json))[0]
    diff_name = f"{fbase}_vs_{sbase}"[:180]
    if not out_json:
        out_json = os.path.join(DIFFS_DIR, f"{diff_name}.json")

    result = {
        'first': {'path': first_json, 'url': first.get('url')},
        'second': {'path': second_json, 'url': second.get('url')},
        'http': {
            'first_hash': first['http']['hash'],
            'second_hash': second['http']['hash'],
            'changed': http_changed,
        },
        'dom': {
            'first_hash': first['dom']['hash'],
            'second_hash': second['dom']['hash'],
            'changed': dom_changed,
            'text_len_delta': second['dom']['text_len'] - first['dom']['text_len'],
        },
        'visual': visual or ('not_available' if not _VIS_LIBS else 'not_computed'),
        'artifacts': {
            'diff_json': out_json,
            'first_json': first_json,
            'second_json': second_json,
            'first_png': os.path.splitext(first_json)[0] + '.png',
            'second_png': os.path.splitext(second_json)[0] + '.png',
        }
    }

    changed = any([http_changed, dom_changed, assets_changed, html_hash_changed, tag_counts_changed])
    #changed = http_changed or dom_changed
    if isinstance(visual, dict):
        ph = visual.get('phash_distance')
        sv = visual.get('ssim')
        result['summary'] = {
            'changed': changed,
            'http_changed': http_changed,
            'dom_changed': dom_changed,
            'visual_phash_distance': ph,
            'visual_ssim': sv,
            'visual_hint': (
                'significant' if (ph is not None and ph > 8) and (sv is not None and sv < 0.95) else 'minor_or_none'
            )
        }
    else:
        """
        result['summary'] = {
            'changed': changed,
            'http_changed': http_changed,
            'dom_changed': dom_changed,
            'visual': 'skipped',
        }
        """
        result['summary'] = {
            'changed': changed,
            'http_changed': http_changed,
            'text_changed': text_changed,      # sadece görünen yazılar
            'dom_changed': dom_changed,        # yapısal değişiklikler
            'html_hash_changed': html_hash_changed,
            'tag_counts_changed': tag_counts_changed,
            'assets_changed': assets_changed,
            'visual': 'skipped',
        }
    save_json(out_json, result)
    return result

def _json_map_by_stem(dir_path: str) -> dict[str, str]:
    """
    Klasördeki .json dosyalarını stem -> path şeklinde eşler.
    Örn: 001_example-com.json -> {'001_example-com': '/abs/path/...'}
    """
    m = {}
    for name in os.listdir(dir_path):
        if name.lower().endswith('.json'):
            stem = os.path.splitext(name)[0]
            m[stem] = os.path.join(dir_path, name)
    return m

def compare_dirs(base_dir: str, current_dir: str, out_dir: str | None = None) -> dict:
    """
    İki klasörde aynı basename/stem'e sahip JSON'ları eşleyip toplu kıyaslar.
    Örn: 001_example-com.json ↔ 001_example-com.json
    """
    base_dir = os.path.abspath(base_dir)
    current_dir = os.path.abspath(current_dir)
    if not os.path.isdir(base_dir):
        return {'error': 'base_dir_not_found', 'path': base_dir}
    if not os.path.isdir(current_dir):
        return {'error': 'current_dir_not_found', 'path': current_dir}

    if out_dir is None:
        out_dir = 'diffs'
    ensure_dir(out_dir)

    base_map = _json_map_by_stem(base_dir)
    curr_map = _json_map_by_stem(current_dir)

    common = sorted(set(base_map.keys()) & set(curr_map.keys()))
    missing_in_curr = sorted(set(base_map.keys()) - set(curr_map.keys()))
    missing_in_base = sorted(set(curr_map.keys()) - set(base_map.keys()))

    results = []
    for stem in common:
        first = base_map[stem]
        second = curr_map[stem]
        # diff dosya adı: diffs/<stem>_diff.json
        out_json = os.path.join(out_dir, f'{stem}_diff.json')
        diff = compare(first, second, out_json=out_json)
        results.append({'stem': stem, 'first': first, 'second': second, 'out': out_json, 'summary': diff.get('summary')})

    summary = {
        'count_compared': len(common),
        'missing_in_current': missing_in_curr,
        'missing_in_base': missing_in_base,
        'out_dir': os.path.abspath(out_dir),
        'results': results,
    }
    # Toplu özet de yazılsın:
    with open(os.path.join(out_dir, '_batch_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary

def main():

    ap = argparse.ArgumentParser(description='Compare snapshots')
    sub = ap.add_subparsers(dest='cmd', required=True)

    # Tek çift
    p_pair = sub.add_parser('pair', help='Compare a single pair of JSONs')
    p_pair.add_argument('--first','-f', required=True)
    p_pair.add_argument('--second','-s', required=True)
    p_pair.add_argument('--out','-o')

    # Klasör ↔ klasör (toplu)
    p_dirs = sub.add_parser('dirs', help='Compare all matching JSONs in two dirs')
    p_dirs.add_argument('--base-dir', required=True)
    p_dirs.add_argument('--current-dir', required=True)
    p_dirs.add_argument('--out-dir', default='diffs')

    args = ap.parse_args()

    if args.cmd == 'pair':
        res = compare(args.first, args.second, args.out)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.cmd == 'dirs':
        res = compare_dirs(args.base_dir, args.current_dir, args.out_dir)
        print(json.dumps(res, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
