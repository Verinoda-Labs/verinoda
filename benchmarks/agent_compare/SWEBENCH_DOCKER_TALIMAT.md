# SWE-bench Lite çalışması: Docker kurulu makinede yapılacaklar (talimat)

**Amaç:** Claude Code'un tek başına ve Verinoda Symbiosis ile ürettiği 200 yamayı (100 örnek × 2 kol) SWE-bench'in resmi
değerlendirmesinden geçirip her kolun kaç örneği **çözdüğünü** ölçmek. Yamalar hazır; çözüm oranı **ölçülmedi**, çünkü resmi
değerlendirme Docker imajları gerektiriyor ve yamaları üreten Windows makinede Docker yok. Bu belge, Docker'lı bir makinede
(ya da bulutta) bunu nasıl yapacağını adım adım anlatır. Başka bir şey yapman gerekmez; yamaları yeniden üretme.

Bu işi bitirmeden çalışmadan "Verinoda çözüm oranını artırıyor / artırmıyor" denemez (`DESIGN_SWEBENCH.md`).

## Neye ihtiyaç var

| | |
|---|---|
| Makine | `x86_64` Linux (önerilen), en az **120 GB boş disk**, 16 GB RAM, 8 çekirdek. ARM (Apple M serisi) deneysel. Windows/macOS'ta Docker Desktop'ın sanal diski ~120 GB'a çıkarılmalı. |
| Yazılım | Docker, Python 3.10+, git |
| Süre | Birkaç saat (imaj indirme/oluşturma ilk seferde uzun sürer; 100 örnek × 2 kol). Disk ve çekirdek sayısına bağlı. |
| Bu depodan | `benchmarks/results/swebench-lite-100-2026-10-10/` klasörü |

Docker kurmak yerine: **buluta ya da SWE-bench'in kendi değerlendirmesine** gönderebilirsin (aşağıda "Alternatif yollar").

## 1. Dosyaları al

```bash
git clone https://github.com/Verinoda-Labs/verinoda-symbiosis.git
cd verinoda-symbiosis/benchmarks/results/swebench-lite-100-2026-10-10
ls    # predictions-none.jsonl  predictions-verinoda_guided.jsonl  tasks.json  results.jsonl  summary.json ...
```

- `predictions-none.jsonl`: Verinoda olmadan, düz Claude Code'un 100 yaması.
- `predictions-verinoda_guided.jsonl`: Verinoda Symbiosis ile çalışan Claude Code'un 100 yaması.
- Biçim SWE-bench'in beklediği: her satır `{"instance_id", "model_name_or_path", "model_patch"}`. **Dosyaları değiştirme.**
- `tasks.json`: örneklem (100 örnek). Analizde kullanılır.

## 2. SWE-bench'i kur ve kurulumu doğrula

```bash
git clone https://github.com/SWE-bench/SWE-bench.git
cd SWE-bench
pip install -e .
git clone --depth 1 https://github.com/SWE-bench/swe-bench-tasks.git ./swe-bench-tasks
swebench dataset check ./swe-bench-tasks
```

Önce kurulumun çalıştığını SWE-bench'in kendi örneğiyle (tek örnek, gerçek yama) doğrula:

```bash
swebench eval verified --gold -i sympy__sympy-20590 --run-id validate-gold --task-repo ./swe-bench-tasks
```

Bu, `1 / 1 resolved` benzeri bir sonuç vermeli. Vermiyorsa **durma**: Docker/disk/ağ sorununu çöz, sonra devam et. (Komutlar SWE-bench'in
güncel README'sine göre yazıldı. Ayrıntı için: `swebench eval --help`. Eski `python -m swebench.harness.run_evaluation ...` biçimi
de aynı argümanlarla çalışır.)

## 3. İki kolu da değerlendir

Her kol için aynı veri kümesi (**SWE-bench Lite**) ve aynı örnekler kullanılmalı. Her kol için ayrı bir `--run-id` ver (harness sonuçları
`run_id` ve örnek kimliğine göre önbelleğe alır; aynı `run_id` ile yeniden çalıştırırsan eski sonucu kullanır).

Önce 100 örneğin kimlik listesini çıkar:

```bash
python - <<'EOF'
import json
ids = [t["id"] for t in json.load(open("<DEPO>/benchmarks/results/swebench-lite-100-2026-10-10/tasks.json"))["tasks"]]
print(",".join(ids))
EOF
```

Sonra (ya yeni CLI ile):

```bash
P=<DEPO>/benchmarks/results/swebench-lite-100-2026-10-10
swebench eval SWE-bench/SWE-bench_Lite -p $P/predictions-none.jsonl            --run-id swe100-none   -j 8 --task-repo ./swe-bench-tasks
swebench eval SWE-bench/SWE-bench_Lite -p $P/predictions-verinoda_guided.jsonl --run-id swe100-guided -j 8 --task-repo ./swe-bench-tasks
```

ya da eski biçimle:

```bash
python -m swebench.harness.run_evaluation --dataset_name SWE-bench/SWE-bench_Lite \
    --predictions_path $P/predictions-none.jsonl --run_id swe100-none --max_workers 8
python -m swebench.harness.run_evaluation --dataset_name SWE-bench/SWE-bench_Lite \
    --predictions_path $P/predictions-verinoda_guided.jsonl --run_id swe100-guided --max_workers 8
```

Notlar:
- `-j` / `--max_workers` değeri çekirdek sayına göre; SWE-bench `min(0.75 × çekirdek, 24)` altında bir değer öneriyor.
- Harness yalnızca tahmin dosyasındaki örnekleri değerlendirmelidir. Tüm 300 örneği çalıştırmaya kalkarsa durdur ve örnekleri `-i` ile
  100 kimliğe sınırla (birden çok kimliğin nasıl verildiğini `swebench eval --help` çıktısından doğrula; bu belgede denenmedi).
- Bir örnek hata verirse (imaj oluşmadı vb.) çalışmayı durdurma; harness onu tamamlanmamış sayar. Hangi örneklerin tamamlanmadığı raporda yazılıdır.
- Disk dolarsa: `swebench images clean --run-id <run_id>` ve kullanılmayan Docker imajlarını temizle; sonra aynı komutu aynı `run_id` ile yeniden çalıştır.

## 4. Raporları bul

Harness her kol için bir özet raporu üretir (genelde `<model_adı>.<run_id>.json`, çalıştırdığın klasörde; ayrıntılar
`logs/evaluation/<run_id>/` altında). İçinde `resolved_ids` listesi ve `completed_ids` bulunur.

```bash
ls *.swe100-none.json *.swe100-guided.json
```

Raporların adı farklıysa, içinde `resolved_ids` olan JSON dosyasını bul. Kendi `results.json`'ını (`logs/evaluation/<run_id>/results.json`)
bu listeyle karıştırma.

## 5. İki kolu karşılaştır

Bu depodaki betik, iki rapordan eşleştirilmiş sonucu (iki kolun çözüm oranı, yalnızca bir kolda çözülenler, fark ve %95 aralığı,
McNemar testi) hesaplar:

```bash
cd <DEPO>
python benchmarks/agent_compare/swebench_compare.py \
    <rapor-none>.json <rapor-guided>.json \
    benchmarks/results/swebench-lite-100-2026-10-10/tasks.json \
    benchmarks/results/swebench-lite-100-2026-10-10/resolved-comparison.json
```

Çıktının `claim` alanı: aralık sıfırı içeriyorsa "no measured difference", içermiyorsa "a difference". 100 örnekte yalnızca büyük bir farkı
(kabaca 10 puan ve üzeri) ayırt edebilirsin; küçük bir fark şansla açıklanabilir. Aralık sıfırı içeriyorsa **fark yok** demek yerine
"ölçülemedi" de.

## 6. Sonucu depoya yaz

Aşağıdakileri `benchmarks/results/swebench-lite-100-2026-10-10/` klasörüne koy ve commit'le:

- İki raporu (`report-none.json`, `report-guided.json`) ve `resolved-comparison.json`.
- Her kolun `logs/evaluation/<run_id>/` içindeki örnek başına sonuç özetini (büyükse yalnızca `results.json`).
- Hangi harness sürümünü, hangi makineyi (işletim sistemi, çekirdek, RAM), hangi tarihte kullandığını `README.md`'ye bir paragraf olarak ekle.

Ardından:
1. `README.md`'deki "The resolved share was NOT measured" bölümünü gerçek sonuçla değiştir (kaç örnek çözüldü, fark, aralık, tamamlanmayan örnekler).
2. `docs/DESIGN.md`'ye yeni bir `D` bölümü yaz (ne yapıldı, neden, ölçüldü, ölçülmedi, yapılmadı); `docs/UPGRADING.md`'ye not ekle; `docs/BACKLOG.md`'den 21.1 satırını sil.
   (`AGENTS.md` kuralı: bir backlog maddesi bitince bu üç şey yapılır.)
3. Aynı satır `Verinoda-Labs/verinoda` deposunun `docs/BACKLOG.md` dosyasında 20.1 olarak duruyor; orada da sil.

## Sonucu yorumlarken

- Bu çalışmada ajanlar projelerin bağımlılıklarını **kurmadı**; testleri çalıştıramadılar. Mutlak çözüm oranları SWE-bench liderlik tablosuyla
  **kıyaslanmaz**. Anlamlı olan yalnızca iki kol arasındaki eşleştirilmiş fark.
- Verinoda kolu, ajana Verinoda'yı kullanması **söylenerek** çalıştırıldı (araçları yükle, `analyze` ile başla, düzenledikten sonra `code_check`
  çalıştır). Önceki çalışmalarda ajan Verinoda'yı kendiliğinden hiç çağırmamıştı; yani sonuç "kendi isteğiyle kullandığında" değil,
  "kullandırıldığında" fark demek.
- Her örnek ve kol için tek oturum var; ajanın kendi tutarsızlığı farkın içinde kalır. Sonuç sınırdaysa aynı 100 örneği ikinci kez üretmek
  (`swebench_run.py`) gerekir; bu belgenin kapsamı dışında.
- Yamaların proxy ölçüleri (uygulanıyor mu, gold dosyaya dokunuyor mu, maliyet) zaten `summary.json` ve `README.md`'de. Özet: Verinoda kolu
  yaklaşık %60 daha pahalı, yama dosyaları büyük ölçüde aynı. Çözüm oranı bu belgeyle ölçülecek.

## Alternatif yollar (Docker kurmadan)

- **`sb-cli` (SWE-bench'in bulut değerlendirmesi, AWS):** `pip install sb-cli`, `sb-cli gen-api-key <e-posta>` (e-postayla gelen kodla
  doğrula), sonra her kol için
  `sb-cli submit swe-bench_lite test --predictions_path <dosya> --run_id <ad>` ve `sb-cli get-report swe-bench_lite test <ad> -o ./reports`.
  Yamalar makinenden dışarı çıkar (yalnızca yamalar). Seçenekler için: `https://www.swebench.com/sb-cli/`.
- **Modal:** aynı harness, `--modal true` ile; ücreti Modal keser. (SWE-bench deposunda `docs/guides/evaluation.md`, "Cloud-Based Evaluation".)

İkisinde de 5. adımdaki karşılaştırma aynıdır: raporlardaki `resolved_ids` listesini `swebench_compare.py` okur.
