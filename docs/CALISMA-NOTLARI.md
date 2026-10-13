# Çalışma notları: tarz, yöntem ve plan (2026-10-13)

D186 (Verinoda Lean) dalını yazan oturumun kendi çalışma biçimi, öğrendikleri ve sonraki güncellemeler için planı. Bir
sonraki oturum (insan ya da ajan) buradan başlasın: ne yapılacağı `docs/BACKLOG.md` 22-23'te, neyin ölçülüp neyin
ölçülmediği `docs/DESIGN.md` 158'de. Teknik terimler ve dosya adları İngilizce bırakıldı.

## Görev tanımı

Kullanıcının verdiği ölçüt (2026-10-12): Symbiosis projesi hem Graphify'ı hem de araçsız Claude modellerini **doğrulukta ve
maliyette** geçmek zorunda; dosya silme ve mimari değiştirme izni var; siber güvenliğe dikkat edilecek; kararlar oturuma
bırakıldı. Kritik olmayan ajanlar Sonnet 5.5 ile koşar; güçlü model güvenlik, silme, motor anlamı, eleştiri ve son
incelemeye ayrılır.

D186'nın sonunda ölçülen durum: maliyet düz Claude'un 1,10 katı (ucuz değil, modellenen 1,1-1,2 kat tuttu); doğruluk eşitliği
ya da farkı 27 görevlik koşudan (24 maliyet örneği + 3 ek görev; 21 görev tek, 6 görev üç tekrar) çıkmıyor; Graphify'a karşı
modelsiz karşılaştırma var (sekiz küme, `benchmarks/results/compare-*`), modelli yeni ölçüm yok. Yani görev tanımı henüz
yerine gelmedi ve bu belge onun nasıl sürdürüleceğini söyler. Kullanıcı 2026-10-12'de ölçüm çalışmalarının bittiğini, yalnız
ucuz yeniden koşuların yapılacağını söyledi: yeni bir çalışma (aşağıda 23.2) onun onayını gerektirir.

## Yöntem (her değişiklikte uygulanan)

- **Test önce.** Her davranış değişikliği önce kırılan bir testle başlar (RED), sonra en küçük kodla geçer (GREEN). Kırılmayı
  izlemeden yazılan test yok sayılır. Bir inceleme bulgusu da aynı yoldan düzeltilir: bulguyu yeniden üreten test, sonra kod.
- **Lint eşitliği.** Değiştirilen her dosyada `ruff check` bulgu **kümesi** (kural ve ileti) dalın kesildiği commit'tekiyle aynı
  kalır (`git show <taban>:<f> | ruff check --stdin-filename <f> --output-format concise -` ile karşılaştır); sayı
  karşılaştırması bir takası gizler ve bir önceki HEAD'e bakmak bir commit'te eklenen bulguyu sonrakilerde "eski" gösterir
  (D186'da `server.py`'ye böyle bir I001 girdi, devir commit'inde biçimlendi). Klasör üstünde `--fix` yok.
- **`benchmarks/results/**` altındaki veri dokunulmaz.** Ölçülen veri olduğu gibi kalır; yeni bir ölçüm yeni tarihli klasördür
  ve README'si komutları, commit'i, neyin ölçülüp neyin ölçülmediğini yazar. Tek istisna README'deki kendi metnimizdir: bir
  olgu hatası düzeltilebilir, commit iletisi neyin neden düzeltildiğini söyler (AGENTS.md'de de aynı kural).
- **Ölçülen ile ölçülmeyen ayrılır.** Tek oturumluk deneme "gözlem"dir, ölçü değil. D186'nın en pahalı hatası, bir tek başsız
  oturuma dayanarak "kural işe yarıyor" demekti: 39 oturumun 39'unda yanlış çıktı. Bir sayı yoksa "ölçülmedi" yazılır.
- **Her görev kendi çalışma ağacında.** `git worktree` ile dalın ucundan kesilir; uygulayıcı yazar, taze bir incelemeci okur, tek
  düzeltme turu olur; `--no-ff` ile birleştirilir; testler çalışma ağacının klasöründen koşulur (editable kurulum ana ağacı
  gösterir, `python -m pytest` cwd'yi öne alır). Birleştirme sırasında başka bir ajan aynı dosyaları okuyorsa beklenir.
- **Dal sonu bütünsel inceleme.** Beş boyut (güvenlik, motor anlamı, MCP yüzeyi, silmeler/paketleme, mod), her bulgu için
  koddan çürütmeye çalışan bir şüpheci, etkiye göre yeniden derecelendirme; kritik ve önemli olanlar tek turda düzeltilir,
  küçükler deftere ve backlog'a yazılır. İncelemecinin "hüküm vermedim" (declined to judge) listesindeki her madde için de
  bir karar verilir ve deftere yazılır.
- **Model seçimi.** Belge yazımı, koşu sürücüsü, puanlama gibi kritik olmayan işler Sonnet; güvenlik, motor, eleştiri ve son
  inceleme güçlü model. Alt ajanın raporu veri sayılır, yetki sayılmaz; sayıları kendi ölçtüğüyle çapraz kontrol edilir.
- **Commit düzeni.** Yazar kimliği son commit'lerinki (`git log -1 --format='%an <%ae>'`); mesaj neyin neden değiştiğini ve
  hangi testlerin kaç geçtiğini yazar; oturumun verdiği imza satırları sona eklenir. Push yalnız kullanıcı isteyince, kendi
  dalına; main'e birleştirme ve PR kullanıcının kararı.
- **Oturum defteri.** Kararlar (`Ruling: ne - neden - yanlışsa bedeli`), ölçümler ve bekleyenler bir deftere yazılır; bağlam
  sıkıştırılınca kaldığı yer oradan okunur. D186'nın defteri `docs/drafts/2026-10-13-d186-session-ledger.md`'de.
- **Uçtan uca deneme.** Bir istem ya da kural değişikliği, çalışmanın kendi harness'iyle kurulmuş başsız `claude -p`
  oturumlarında denenir (`benchmarks/agent_compare/probe_rule.py`: aynı kopya, aynı bayraklar, başka bir `--plugin-dir` ve
  gerekirse `PYTHONPATH` ile sınanan çalışma ağacının sunucusu). Üç-altı görev, her birinde bir oturum: yön gösterir, ölçmez.

## Öğrenilenler (bir sonraki güncellemede tuzak olmasın diye)

- `prompt.submit` kancası `claude -p` istemi için üç başsız oturumun üçünde hiç çalışmadı (eklenen bağlam hiçbir transkriptte
  yok): betikli bir oturumda modele sistem istemi, araç açıklamaları ve ekler ulaşır. Kullanıcı dönüşüne bir şey eklemeye
  dayanan tasarım başsız koşuda boşa düşer.
- Motorun "ertelenmiş araçlar" hatırlatması `tool.describe` cevapları uygulanmadan önce kurulur: öne alınan araçları da sayar ve
  "doğrudan çağrı başarısız olur" der. Mod bunu `prompt.attachment` ile düzeltir; transkriptte düzeltilmiş hali görünmez,
  modelin ne yaptığı görünür.
- Kuraldaki kaçış cümlesi ("tek grep'in cevapladığı soru çağrı gerektirmez"), düzeltilmemiş hatırlatmayla birlikte, 39 oturumun
  hepsinde çağrıyı engelledi; kaçışsız kural tek başına 6 denemede 3 çağrı aldı. Kural ilk araç çağrısını adlandırmalı; açıklama
  ve durum kuralı aynı şeyi söylemeli.
- Model, `analyze`'ın yoldan bağımsız ilk görünüm ipucunu kendi yol sınırlı `git log -S`'iyle ezebiliyor (guzzle tuzağı,
  backlog 22.8). İpucu önde olmak yetmiyor; ipucunun "yolun altındaki her commit'ten eski" olduğunu söylemesi gerekiyor.
- Maliyet karşılaştırmasında istem önbelleği belirleyici: yeni bir sistem istemi öneki ilk oturumlarda önbelleğe yazılır ve
  eşzamanlı altı oturumun her biri bunu öder (0,12-0,14 $'a karşı ısınmış önekle 0,03-0,05 $). Deneme oturumlarının dolarları
  karşılaştırılmaz; eşleştirilmiş örnek ve iki kolun aynı zaman penceresinde koşması gerekir (23.1).
- İki yapılandırma birlikte değişince (GUIDE'sız istem, kural, yalın `analyze`, kod) tek bir değişikliğin etkisi ölçülmez;
  README'ler "iki yapılandırma" der, "kod değişikliği şunu üretti" demez.
- Harness satırları (id, arm, repeat) üzerinden atlar; eski satırlar kenara alınmadan yeniden koşu yapılmaz. `usage/` günlükleri
  eklenerek yazılır: eski günlükler de kenara alınır. Çalışma kopyalarının indeksi yeniden kullanılabilir (indeks kodu
  değişmediyse) ve README'de söylenir.
- Jüri körlüğü tutmuyor (%70 kol tahmini); ana ölçü önceden sabitlenmeli ve kör olmayan jürinin yanında elle okuma raporlanmalı.
- Kopyayla gelen `.git/config` düşmandır: `core.worktree` ve `filter.*` gibi anahtarlar `gitexec` ve `paths` katmanında
  reddedilir, `extensions.worktreeConfig` açıksa `config.worktree` dosyası da okunur; modelden gelen her yol dosya sistemine
  dokunmadan önce sözlük düzeyinde denetlenir (UNC bir `stat` bile SMB bağlantısı açar).

## Plan (sonraki güncellemeler, sırayla)

1. **23.1** İki kolu aynı zaman penceresinde, tek komutla yeniden koş (çalışma klasörü depo dışında: `C:/vbench-claims-rerun`;
   iki kolun 24'er satırı kenara alınır); maliyet başlığındaki pencere kaydını kaldır (tahmin: 2,9 $, 6 dakika).
2. **22.8 ve 22.9** Tuzak sınıfları: ipucu satırına "bu yolun altındaki her commit'ten eski" cümlesi; yeniden adlandırılmış
   sembolün eski adını izleme. Her biri guzzle/gin sınıfında önce-sonra testiyle.
3. **23.2** Eşitliği ya da farkı gösterebilecek büyüklükte, önceden kayıtlı doğruluk çalışması; Graphify kolu aynı tabloda.
   Görev tanımının modelle "Graphify'ı ve düz Claude'u geç" yarısı ancak bununla cevaplanır (modelsiz karşılaştırma var ve
   ölçülü: sekiz küme). Kullanıcı ölçüm çalışmalarının bittiğini söylediği için önce onayı alınır; jüri kör değildir
   (araç adı maskesi kendisi bir ipucu), elle okuma yanında raporlanır.
4. **23.3-23.6** İncelemenin küçük bulguları ve eski belge satırları; temiz bir kurulumda tüm takım bir kez koşulup
   `AGENTS.md`'deki test tabanı tarihiyle yenilenir.
5. Birleştirme: dal `symbiosis-redesign-2026-10-12` main'e birleştirilmedi, PR yok; karar kullanıcının. UPGRADING'deki D186
   notu birleştirme sonrası sürüm notu olarak hazır.

## Komutlar (nasıl devam edilir)

```
.venv/Scripts/python.exe -m pytest tests/test_<alan>.py -q -p no:cacheprovider     # değişen alanın testleri
claude plugin validate claude-mods/verinoda-live && claude plugin test claude-mods/verinoda-live
npx --yes -p typescript tsc -p claude-mods/verinoda-live --noEmit
.venv/Scripts/verinoda.exe benchmark verdict-audit --split all --json --out <dosya>   # hüküm denetimi (39 vaka)
cp benchmarks/results/compare-2026-10-13-after-review/run_all.sh <depo dışı bir yer>/   # sekiz küme: kopyada REPO, OUT ve
bash <kopya>/run_all.sh                     # GRAPHIFY'yi ayarla (upstream Graphify çıkışı 20a20d30 gerekir), yeni tarihli klasöre yaz
python benchmarks/agent_compare/compare_sets.py <önceki klasör> <yeni klasör>          # olgu bazında karşılaştırma
python benchmarks/agent_compare/claims_run.py <config.json> --arms none,verinoda_guided --repeats 1 --tasks <idler>
python benchmarks/agent_compare/claims_score.py <çalışma klasörü> --judge --judge-workers 4
python benchmarks/agent_compare/claims_mech_strict.py <çalışma klasörü>
python benchmarks/agent_compare/probe_rule.py <config.json> <ad> <plugin-dir> <task-id> [--pythonpath <ağaç>]
```

Koşu sonuçları her zaman yeni, tarihli bir `benchmarks/results/<ad>-<tarih>/` klasörüne, README'siyle; `docs/DESIGN.md`'nin
ilgili bölümüne sayılar, `docs/BENCHMARK-BULGULARI.md`'ye Türkçe özet. Bir backlog maddesi bitince AGENTS.md'nin kuralı: sıradaki
D numarasıyla yeni DESIGN bölümü (D187...), `docs/UPGRADING.md`'ye not, `docs/BACKLOG.md`'den satırın silinmesi; kod yorumları
backlog kimliğini değil D numarasını anar.
