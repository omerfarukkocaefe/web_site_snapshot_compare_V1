# 🕵️ Web Snapshot & Compare Tool

Bu proje, web sayfalarının anlık görüntülerini (**snapshot**) alıp bunları JSON formatında kaydetmenizi ve daha sonra farklı zamanlarda alınmış snapshot'ları karşılaştırarak değişiklikleri analiz etmenizi sağlar.  

⚠️**Dikkat: Script'in deneme videosu eklenecektir!** Bu script yalnızca **legal çalışma, öğrenme ve test amaçlıdır**. Herhangi bir **illegal kullanım** tamamen kullanıcı sorumluluğundadır. Script sahibinin bu eylemlerden **hiçbir sorumluluğu yoktur**.

## 📂 İçindekiler
- `capture_snapshot.py`: Web sayfalarından snapshot alma aracı  
- `compare_snapshots.py`: İki snapshot dosyasını veya klasörlerini kıyaslama aracı  
- `snapshots/`: Kaydedilen snapshot JSON dosyalarının tutulacağı klasör  
- `diffs/`: Karşılaştırma çıktılarının tutulacağı klasör  

---

## ⚙️ Özellikler
- Kali Linux içinde test edilmiştir
- Önce capture_snapshot.py dosyası iki kez çalıştırılır (farklı zamanlarda / farklı çıktılarla)
- Sonrasında bu iki JSON çıktısı compare_snapshots.py ile kıyaslanır.
- Tek bir URL için snapshot alma
- Dosyadan birden fazla URL okuma ve snapshot kaydetme
- HTML, başlık, status code, görünür metin hash’i, DOM yapısı, asset (img/link/script) bilgileri toplama
- İki snapshot arasında farkları karşılaştırma:
  - HTTP değişiklikleri
  - Görünür metin değişiklikleri
  - DOM yapısı, tag sayıları, asset farkları
  - Opsiyonel görsel kıyaslama (SSIM, perceptual hash) → `Pillow`, `scikit-image`, `imagehash` kütüphaneleri kurulu ise  

---

## 📸 Örnek Kullanım

### Çalıştırma Sırası

### 1. Tek URL için Snapshot
Bir URL'den tek seferlik snapshot almak için:

```bash
python3 capture_snapshot.py capture --url https://example.com --out snapshots/example.json
```

### 2. Birden Fazla URL (Dosyadan Okuma)
Bir dosyadan tek seferlik snapshot almak için:

```bash
python3 capture_snapshot.py capture --file urls.txt --out-dir snapshots/
```

### 3. İki Snapshot Karşılaştırma
Önceden alınmış iki snapshot dosyasını kıyaslamak için:

```bash
python3 compare_snapshots.py pair --first snapshots/example_old.json --second snapshots/example_new.json --out diffs/example_diff.json
```

### 4. Klasör Bazlı Karşılaştırma
İki farklı klasördeki snapshot’ları karşılaştırmak için:

```bash
python3 compare_snapshots.py dirs --base-dir snapshots/old --current-dir snapshots/new --out-dir diffs/
```
## 📊 Çıktı Örneği
```json
"summary": {
  "changed": true,
  "http_changed": false,
  "text_changed": true,
  "dom_changed": true,
  "html_hash_changed": true,
  "tag_counts_changed": true,
  "assets_changed": false,
  "visual": "skipped"
}
```
---



