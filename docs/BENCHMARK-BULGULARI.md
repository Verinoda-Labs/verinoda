# Verinoda: benchmark bulguları ve bilinen eksikler

Tarih: 2026-10-11 (§5: 2026-10-13). Kaynak: `benchmarks/results/**`, `docs/SYMBIOSIS-GAPS.md`, `docs/BACKLOG.md` (bölüm 13, 20 ve "Deferred from D186" bölümü),
`docs/DESIGN.md` (bölüm 158, §5 için).
Bu belge ölçülenleri ve ölçülmeyenleri ayırır. Bir sayı burada yoksa, ölçülmediği anlamına gelir.

## En yeni sonuç (2026-10-11): yanlış iddia çalışması, Verinoda'nın tezi ölçüldü

Ön kayıt: `benchmarks/agent_compare/DESIGN_CLAIMS.md`; sonuçlar: `benchmarks/results/claims-2026-10-11/` (D185). Önceki
çalışmaların hepsi dosya bulma ya da çözüm oranı ölçüyordu; bu çalışma Verinoda'nın asıl iddiasını ölçer: ajan kanıtsız iddia
yerine kanıtlı iddia ve `unknown` üretir mi. On gerçek depoda 40 "neden / ne zaman / neyi etkiler" sorusu (10'u depoda cevabı
olmayan tuzak), altın git'ten ve Verinoda'sız yazıldı, oturumdan önce commit'lendi. İki kol, aynı "kanıt göster, bulamazsan
bilinmiyor de" duruşu; tek fark araç. 3 tekrar, 240 oturum, hata 0. Kolu bilmeyen bir hakem cevabı iddialara ayırıp altına
karşı puanlar; atıflar mekanik doğrulanır.

| | yalnız Claude Code | Verinoda ile | fark | %95 aralık |
|---|---|---|---|---|
| Cevaplı 30 görev: yanlış düz iddia içeren cevap payı | 0,044 (90'da 4) | 0,056 (90'da 5) | +0,011 | -0,044 ile +0,078 |
| 10 tuzak: uyduran cevap payı | 0,000 (30'da 0) | 0,000 (30'da 0) | 0 | 0 ile 0 |

- **Ölçülen fark yok; iddia yok.** Tuzaklarda iki kolda da hiçbir şey olmadı: 60 cevabın 60'ı "depoda cevap yok" dedi.
- **Karıştırıcı (gözden geçirmede bulundu):** her oturumun istemi görev kimliğini taşıyordu ve kimlik türü adlandırıyor
  (`.../gin-trap-1/none/r1`). Eşleştirilmiş fark simetrik, ayakta; tuzak tabanı tek başına değil. 10 tuzak opak kopya
  adlarıyla yeniden koşuldu (60 oturum, `traps-opaque/`): yine iki kolda 30/30 "bilinmiyor". Tarihli ikincil analiz.
- Pilotun düz kol oranı (8'de 2 = 0,25) önceden kayıtlı kuralla N'i 40'ta tuttu; ana koşuda oran 0,044. Yarıya iniş (-0,022)
  aralığın içinde: sonuç gerçek bir etkiye karşı **zayıf** kanıt, yokluğunun kanıtı değil.
- 12 yanlış iddianın 7'si iki kolda da aynı **yokluk iddiası** ("depoda gerekçe yok"); gerekçe dosyanın taşınma öncesi yolundaki
  commit'te (`546dc8b`) ve `git log -S` güncel yolda onu göremiyor. Verinoda'nın `history_search`'ü de aynı yere düştü. Duruş
  uydurmayı durduruyor, kendinden emin olumsuzu durdurmuyor.
- Körleme başarısız: hakem kolu %72 tanıyor (aralık 0,5'i dışlıyor); kanal maskenin kendisi (Verinoda cevabında ortalama 4
  `[tool]` maskesi, düzde 0,1). Bu çekinceyle raporlandı.
- Maliyet: Verinoda kolu oturum başına 1,66 kat dolar, 1,5 kat süre; `analyze` çağrı başına ~2.700 tahmini token.
- Ölçülmedi: duruşun kendisi mi aracı gereksiz kılıyor (iki kol da duruşu taşıyor; duruşsuz tek bir kol ~2 $'a cevaplar);
  Verinoda yalnız sunulduğunda; insanın güveni. Kişinin elle kontrolü (40 iddia) bekliyor.

**Ne demek:** Bu depo kümesinde ve bu duruşla, üç ayrı ölçüde de ölçülen bir fark yok: dosya bulma (önceki çalışmalar),
çözüm oranı (SWE-bench, 72 = 72) ve yanlış iddia oranı (+0,011 [−0,044, +0,078]). Üçü de aralığıyla okunmalı: bu çalışmada
yarıya iniş büyüklüğünde bir etki dışlanmadı, körleme başarısız ve elle kontrol bekliyor. Ajana dönük hatta kalan tek
önceden kayıtlı deney test kanalı (§5.4, madde 1); o da fark göstermezse hat kapanır. Açık hat, insana dönük denetim katmanı.

## 1. SWE-bench Lite, 100 örnek

Tasarım: `benchmarks/agent_compare/DESIGN_SWEBENCH.md` (önceden kayıtlı). Her örnek ve kol için bir `claude -p` oturumu,
model `claude-sonnet-5-5`. Kollar: `none` (yalnız Claude Code) ve `verinoda_guided` (Verinoda indeksi, MCP sunucusu,
verinoda-live modu ve prompt'ta üç adımlı bir protokol). Resmi SWE-bench değerlendirmesi Docker'da çalıştı (harness 5.0.2,
veri seti SWE-bench_Lite, 100 örnek, iki kolda da 100 tamamlandı).

| | yalnız Claude Code | Verinoda ile |
|---|---|---|
| Çözülen (resmi değerlendirme) | **72 / 100** | **72 / 100** |
| İki kolda da çözülen | 66 | 66 |
| Yalnız bu kolda çözülen | 6 | 6 |
| İki kolda da çözülmeyen | 22 | 22 |

- Eşleştirilmiş fark (Verinoda eksi düz): **0,00**, %95 aralık -0,07 ile 0,07 arası, tam McNemar p = 1,0.
- **Sonuç: ölçülebilir fark yok.** 100 örnekte yaklaşık 7 puandan küçük fark şansla ayırt edilemez. Bu, iki kolun eşit olduğunu
  kanıtlamaz; yalnızca fark gösterilemedi.
- Mutlak oran (%72) lider tablosuyla karşılaştırılamaz: bağımlılıklar kurulmadığı için ajanlar proje testlerini çalıştıramadı.

Maliyet ve davranış (ölçüldü, eşleştirilmiş, 100 örnek):

| | ortalama fark (Verinoda eksi düz) | %95 aralık | Verinoda kolu daha fazla / aynı / daha az |
|---|---|---|---|
| Dolar | +0,049 (ortalama yaklaşık %60 fazla) | 0,043 - 0,056 | 98 / 0 / 2 |
| Tur | +2,3 | 1,9 - 2,7 | 89 / 4 / 7 |
| Giriş token'ı | +71.600 (yaklaşık %55 fazla) | 56.800 - 85.300 | 96 / 0 / 4 |
| Saniye | +44,5 | 28,7 - 60,4 | 80 / 0 / 20 |
| Yama satırı | +1,3 | -0,3 - 3,0 | 35 / 43 / 22 |

- Toplam maliyet: düz 7,94 USD, Verinoda 12,88 USD.
- Verinoda kolunda protokol her oturumda çalıştı: `analyze` 100 kez, `code_check` 98 kez, her iki kolda da hata yok.
- Yama proxy'leri: aynı dosya kümesi 90/100, birebir aynı yama 31/100. Yalnız bir yama `git apply --check` ile uymadı
  (`sympy__sympy-15346`); harness yine uyguladı.

**Ne demek:** Bu protokolle Verinoda, bu örnek kümede çözüm oranını artırmadı; maliyeti ve süreyi yaklaşık %60 artırdı.
Sınırlar: örnek başına tek oturum; protokol bir elle yönlendirme (prompt) ve aracın kendi yazarlarının; model SWE-bench
çözümlerini bilmiş olabilir (iki kol da için geçerli). Pilot (4 örnek, Docker'sız) yalnız proxy ölçtü:
`benchmarks/results/swebench-lite-pilot-2026-10-10/README.md`.

## 2. Ölçülen diğer bulgular

### 2.1 Cevap yolları (sentetik Türkçe biyoloji corpus'u, 40 ve 400 dosya)

`benchmarks/results/field-test-synthetic-2026-10-10/README.md`. Corpus üreteci ve sorular aynı kişi tarafından yazıldı;
bağımsız değil, gerçek alan testi değil.

- 40 dosyada: standart kütüphane tabanlı cevap, kanıt oranı 0,457; `query --sentences` 0,571; düz `query` 0,70 (cevap başına
  token tahmini 218 / 277 / 334).
- 400 dosyada tablo tersine döner: kanıt oranı 0,283 / 0,35 / 0,167; ilk kanıtın ilk 3'te olduğu sorgu sayısı 1 / 7 / -.
- Sıcak sorgu (indeks yüklü): 400 dosyada yaklaşık 8 - 30 ms. Soğuk başlatma: yaklaşık 0,45 s.
- Güncelleme: tek dosya değişince 400 dosyada 4,74 s; değişiklik yokken 0,52 s.
- Kurulum: `pip install verinoda` 63 paket, 293 MB.

### 2.2 İlişki kenarları (aynı sentetik corpus)

Kural tabanlı `verinoda relations`: planlanan 460 kenarın 460'ı doğru okundu (400 dosya), yanlış yönlü 0. Bu bir öz-tutarlılık
ölçümü: kurallar üreteçin cümle kalıplarına göre yazıldı. Gerçek metinde ölçülmedi.

### 2.3 Bayat indeks (`verinoda locate`, 21 seL4 görevi, model çalışması yok)

`benchmarks/results/stale-locate-2026-10-04/README.md`. Depo 100 commit ileri alınıp indeks güncellenmediğinde 21 görevin 17'sinde
cevap listesi aynı kaldı (ortalama örtüşme 0,934). Altın dosyalardan 18'i taze, 16'sı bayat indeksle bulundu; hiçbiri kazanılmadı.
Her bayat cevap "N dosya değişti, `verinoda update` çalıştırın" notunu taşıdı. Ajanın bayat cevapla ne yaptığı ölçülmedi.

### 2.4 Gerçek depolar (9 depo, 2026-10-02)

`benchmarks/results/realworld-2026-10-02-r3/summary.md`. fastapi, sqlmodel, express, axios, fzf, gin, bat, gson, guzzle:
254 - 974 dosya, tarama 10 - 35 s, güncelleme 8 - 25 s, sorgu medyanı 1,3 - 1,9 s, analyze medyanı 2,6 - 4,6 s. Çökme ve zaman aşımı 0.
Altın gerçekler (kendi yazılmış, v1): 7 ile 10 / 10 arası. Altın gerçekler ölçümden önce donduruldu; ama yazarı Verinoda'nın kendisi.

### 2.5 Maliyet ölçümünün eksikliği

Ajan bildirimleri yalnızca toplam token verir. Bir Verinoda çağrısının kendi maliyeti (giriş/çıkış token'ı) bilinmiyor
(`SYMBIOSIS-GAPS.md` madde 7). SWE-bench'te maliyet toplam oturum maliyetiydi, Verinoda çağrısı ayrı ölçülmedi.

## 3. Bilinen zayıflıklar ve eksikler

Öncelik sırasıyla. Her madde için kaynak verildi.

1. **`analyze` ilişki iddiası üretmiyor (kritik).** Biyoloji testinde 5 konu çiftinde 13 iddianın hiçbiri ilişki değildi
   (tanım ve konum iddiaları). Sonuç: ürün kenarları kendi kural katmanında yazdı. Yol haritası: `BACKLOG.md` 20.1 (aşama B) açık.
2. **`query` pasaj döndürüyor, cümle değil.** Önkoşul soruları ilgisiz pasaj ve konu satırları döndürdü (5 - 5,3 bin karakter).
   `query --sentences` (D180) bunu kısmen çözdü; yalnız sentetik corpus'ta ölçüldü.
3. **Kanıt durumu kullanıcının kuralını bilmiyor.** Ürün "kanıtlı" dediği bir kenarı Verinoda'nın "statically_verified"ından
   farklı sayıyor. Kullanıcı tanımlı kanıt kuralı kısmen var (D182, yalnız `relations` için, yalnız durumu düşürür). `BACKLOG.md` 20.3.
4. **MCP sunucusu bir depoya bağlı.** Başka klasördeki bir oturum ana depoya cevap verdi, ürünün klasörüne değil. Kısmen
   çözüm (D179, `projects add`); ölçümü yapılmadı. `BACKLOG.md` 20.4.
5. **`verinoda setup` yan dosyalar üretiyor** (`.claude/`, `.codex/`, `.agents/`, `.mcp.json` mutlak yollarla). Bayrak yok.
6. **Sorgu sırasında yazma gözlemi doğrulanmadı.** Bir ajan `kb/.verinoda/index` altında yazma gördüğünü bildirdi; ölçülmedi.
7. **Çağrı başına token maliyeti ölçülemiyor** (madde 2.5).
8. **Çalışma zamanında paket kullanılmıyor (ürün tarafı).** Ürün stdlib üzerinde çalıştı; Verinoda yalnız veri üretiminde
   ve geliştirmede yardımcı oldu. "Verinoda ürünü" iddiasını sınırlar.
9. **Verinoda kolu daha pahalı, daha yavaş, aynı çözüm oranı.** SWE-bench'in ana sonucu. Protokolün maliyeti (ilk adımda
   `analyze`, her düzenlemeden sonra `code_check`) kazanç getirmedi.
10. **Bayat indeks ajanı yanıltabilir.** Yalnız "not" ile uyarıyor; bayat cevabın ajan davranışına etkisi ölçülmedi.
11. **İlk kontrol listesi paneli (`BACKLOG.md` 13.9):** uzun liste okunmuyor; tahmin, gerçek gibi okunuyor; liste "iyi"nin
    ne olduğunu çerçeveliyor; her gözden geçirme tam bir geçiş. Gerçek bir terminal oturumunda henüz denenmedi.
12. **Okuma kapsamı.** Verinoda'nın ilk sürümü ve sentetik corpus'lar küçük (40 - 974 dosya); 10 000+ dosyalı depolarda
    ölçüm yok.

## 4. Ölçülmeyenler

- SWE-bench'te protokolsüz (ajanın kendi başına Verinoda'yı seçtiği) kol.
- Verinoda'nın çözüm oranına etkisi Python dışındaki dillerde (SWE-bench yalnız Python).
- Gerçek alan testinin verisi (`biyo-platform-test` dalı uzak depoda yok).
- Bayat indeksin ajan davranışına etkisi.
- Çağrı başına maliyet.

## 5. Önerilen sıra (2026-10-13'te yeniden yazıldı, D186 sonrası)

Ajana dönük hat üç farklı ölçümde (dosya bulma, çözüm oranı, yanlış iddia) ölçülen bir fark vermedi; her birinde fark
aralığın içinde kaldı. Aynı sorunun bir varyantını daha koşmak (örneğin "tek `analyze`, `code_check` yok" protokolü)
önerilmez; üç aralık da aynı yöne işaret ediyor. D186 (Verinoda Lean, `docs/DESIGN.md` bölüm 158) bu sonuca yeni bir deneyle
değil, ölçülen mekanizmaları düzelten bir değişiklikle yanıt verdi. Aşağıda sırayla: ne gönderildi, koşular şimdiye kadar ne
gösterdi, ne ölçülmedi ve sıra. Sayıların kaynağı her satırda yazılı; "yerel çözümleme", oturum kayıtlarından yapılmış ve
depoda sonuç klasörü olmayan çözümleme demektir.

### 5.1 Ne gönderildi (D186)

- **`analyze` MCP cevabı bir soruşturma değil, ipucu:** hüküm (`answered` / `partly_answered` / `unanswered`), cevap iddiaları
  tam, `dosya:satır` ile en çok sekiz ipucu, en çok altı bağlam satırı; 2.500 karakteri aşmaz (eskiden SWE-bench'te ortanca
  10.495 karakter, fastapi sorusunda 10.355; yerel çözümleme). Sebep:
  D185'te Verinoda kolu oturumların 103/120'sinde yönlendirilen asgariyle (`analyze`, sonra cevap) bitti ve `analyze` 120/120
  çağrıda `answered` dedi (yerel çözümleme).
- **`history_search` tek düz liste; git'in kör olduğu iki sınıf düzeltildi.** Taşınmış dosyada tek satırlık değişiklik
  (`--follow`; D185'in 12 yanlış olgusunun 7'sinin kaynağı: altın commit 546dc8b 14 commit'in 11.'siydi ve 12.000 karakterlik
  sınır ilk 10'u tuttu) ve metnin başka bir dosyada doğmuş olması (yoldan bağımsız en eski görünüş). Zaman aşımı hata değil,
  kısmi sonuçtur.
- **Modele tek bir durum kuralı:** yalnız doğrulanmış durumlar olgudur; Verinoda çıktısı ipucudur, "böyle bir değişiklik yok"
  demeden önce kendi git/grep kontrolünü yap; kesik liste yokluğu kanıtlamaz. Aynı cümle sunucu yönergelerinde, iki beceri
  dosyasında (58 ve 59 satır) ve öteki ajanların kural dosyasında.
- **Mod (0.7.0):** araçlar modelin önünde (ToolSearch'ün arkasında değil), bir paragraflık çağrı kuralı, tazelik. Arama
  (`search`), dürtme (`nudge`), `assist`, commit-inceleme bekçisi ve ısınma kalktı; düzenleme sonrası ad denetimi varsayılan
  olarak kapalı; depodan hiçbir program çalıştırılmaz.
- **Paket:** tek git kapısı, yol kapsama, daemon durumunun depodan çıkması; yukarı akış Graphify komut satırı (`verinoda index`),
  LLM/PR/medya katmanı ve `graspologic-native` bağımlılığı (scipy dahil yaklaşık 107 MB) paketten çıktı.

Hedef şudur ve **henüz ölçülmedi**: doğrulukta düz Claude Code'dan kötü olmamak (D185 ölçülen bir fark bulmadı, aralık -0,044
ile +0,078; bu eşitlik demek değildir); dolarda düz Claude Code'un eşleştirilmiş aralığı içinde (modellenen 1,1-1,2 kat;
SWE-bench'te 1,62 ve D185'te 1,66 katından aşağı); git'in kör olduğu, depo kopyalarında denenen üç durumda (fastapi, guzzle, gin)
doğru geçmiş. 1,1-1,2 kat ile aşağıdaki arama çağrısı sayıları `docs/drafts/2026-10-12-verinoda-lean-design.md` bölüm 2'den
alınmıştır: D184 ve D185 oturum kayıtları ile `total_cost_usd`'ye en iyi uyan fiyatlar üzerinde yerel aritmetik; burada yeniden
türetilmedi, model olarak okunmalı. **"Düz Claude'dan ucuz" iddia edilmez:** arama çağrılarını yerine koyan bir araç en çok düz
ajanın yaptığı arama çağrılarını kaldırabilir (SWE-bench'te oturum başına 1,31 arama çağrısı, D185'te 0,89; modelleme), bu da bir
Verinoda çağrısının sonucuyla birlikte maliyetinden azdır.

### 5.2 Koşular şimdiye kadar ne gösterdi

Hiçbiri yeniden tasarlanan aracın maliyetinin ya da ajan davranışının puanlı bir ölçümü değil: tek oturumluk denemeler gözlemdir,
katı atıf kontrolü D185'in (eski araçla verilmiş) cevaplarını puanlar.

- **Modelsiz benchmark, sekiz küme (işlenmiş sonuç: `benchmarks/results/compare-2026-10-12-branch/`):** dalın c678d46
  sürümünde olgu kaybı da kazancı da yok (sorgu 284/319 → 284/319, analyze 285/319 → 285/319); `analyze` soru başına token'ı
  86 sorunun 14'ünde düştü (-9 ile -87), hiçbirinde artmadı. D186'nın tamamından sonraki koşu henüz yapılmadı.
- **Hüküm denetimi (koşuldu, çıktısı commit'lenmedi):** 39 vaka, yanlış `met` 1 (`forge-maxheat-declared`), tavan üstü 0,
  korunan kontrol 15/22; ilk iki dalga öncesinde ve sonrasında aynı yedi kontrol kayıp. `DESIGN.md` D39 satırı 19/22 diyordu
  (2026-09-26, `benchmarks/results/verdict-audit-2026-09-26/after.json`); HEAD'de 15/22 çıktı ve fark nedeni araştırılmadı. Satır
  artık ikisini de tarihiyle söylüyor.
- **SWE-bench `analyze` çıktılarının çevrimdışı yeniden sıralanması (yerel çözümleme):** altın dosya 1. sırada 31 → 60/100,
  ilk 3'te 46 → 76, ilk 8'de 71 → 86; çıktıda hiç olmayan 8 → ipuçlarında hiç olmayan 11 (kötüleşen tek sayı: sekiz ipucu sınırı).
- **Uçtan uca, çalışma kopyalarında (commit iletilerindeki ölçümler):** fastapi görevinde `analyze` 10.355 → 1.987 karakter,
  `history_search` 28.725 → 2.989 karakter (14 satır, 546dc8b içinde); guzzle'da ilk olay `new_file` ve iddia yoldan bağımsız
  91f1e347'den yeniden kuruluyor; gin'de `earlier_elsewhere` 15216a0'ı adlandırıyor. "30 satır için en çok 2.000 karakter"
  hedefi gerçek konu satırlarıyla tutmadı (satır başına yaklaşık 100 karakter).
- **Tek oturumluk denemeler (gözlem, ölçü değil):** yalnız duruş istemi ve modsuz: Grep, Read, Read, Bash ve "geçmiş gerekçe
  vermiyor" (ölçülen hata); araçlar önde ama kuralsız: aynı yol; araçlar önde ve tek paragraflık kuralla: `analyze` → Grep →
  `git show 546dc8b`, cevap 546dc8b'yi "güvenlik için" diye anıyor, 3-4 API çağrısı.
- **D185 cevaplarında katı mekanik atıf kontrolü (yerel koşu, çıktısı commit'lenmedi):** düz 905 doğrulanan / 216 yanlış / 6 eksik
  (0,803), Verinoda 1.047 / 254 / 20 (0,793); D185'in gevşek kontrolü 0,975 ve 0,958 vermişti. Gevşek kontrol üst sınır, katı
  kontrol alt sınırdır; Verinoda kolu iki kontrolde de daha düşük, aralık hesaplanmadı.
- **Testler:** birinci dalga sonrası birleşik ağaçta 31 test dosyası, 1.084 geçti, 2 başarısız (temiz çıkışta da başarısız olan
  iki beceri uzunluğu testi; ikinci dalgada düzeldi); mod: 85 test geçti; `tests_upstream` silmelerden sonra 38 başarısız (hepsi
  daha önce de başarısız olan türden), 3.645 geçti, 130 atlandı; Louvain kapısı (graspologic-native'siz tüm ürün takımı): 20
  başarısız, hiçbiri Louvain'den değil.

### 5.3 Ölçülmedi

- **Dolar ve doğruluk.** Yeniden tasarlanan aracın bir modelle doğruluğu ölçülmedi. 1,1-1,2 kat modellenmiştir (taslak tasarımın
  bölüm 2'sindeki aritmetik, burada yeniden türetilmedi), ölçülmemiştir. Yeniden koşular henüz yapılmadı: D185'in altı görevi
  (Verinoda kolu, üç tekrar) ve 24 çiftlik maliyet örneği (24 cevaplanabilir görev, iki kol). Başarı ölçütü önceden belirli:
  eşleştirilmiş farkın aralığı +0,015 $'ı dışlamalı ve Verinoda çıktısı oturum başına en çok 4.500 karakter olmalı. Sayılar ve
  sonuç klasörü `docs/DESIGN.md` 158.3'e yazılacak.
- Modelin ilk Read'inin 1. ipucunu izleyip izlemediği; `show="lead"`'in etkisi (kapalı; Verinoda kolunun kendi model çağrıları
  düz kolunkinden en az 1,5 az değilse kapalı kalır); modelin kısalmış metinle ne yaptığı; metin boyutlarının gerçek bir depoda
  değeri (ölçümler örnek proje `orders_app` üzerinde).
- 50.000 commit'lik bir depoda 60 sn'lik zaman aşımı; `--no-optional-locks` ile eskimiş bir ağaçta `status` gecikmesi.
- Başlık sayıları ve kümeleme süresi Louvain ile (şimdiye kadarki her sonuç Leiden ile koşuldu); temiz bir kurulumda boyut.
- SWE-bench yeniden koşulmadı (taslak tasarımın bölüm 8'indeki tahmin yaklaşık 25 $ ve tekrar başına 7 saat Docker; ölçülmedi);
  ContextBench `analyze` kolu, CLI'nin `render_text`'i değişmediği için yeniden koşulmadı.

### 5.4 Sıra

Önce, yeni bir çalışma değil, D186 planının son adımı: §5.3'teki yeniden koşular ile D186 sonrası sekiz küme ve hüküm
denetimi, sonuç klasörleriyle commit'lenerek. Dolar rakamı o zamana kadar bir modeldir ve yeniden tasarlanan aracın doğruluğu ölçülmemiştir.

1. **Ajan tarafında kalan tek açık deney: test kanalı.** SWE-bench çalışmasında iki kolda da proje testleri çalışmıyordu;
   literatürün en yüksek getiri dediği kanal hiç ölçülmedi. Aynı 100 örnek, bağımlılıkları kurulu Docker ortamında, önce
   düz, sonra Verinoda ile. Bu da sıfır verirse ajan hattı kapanır.
2. **Duruş mu, araç mı?** Yanlış iddia çalışmasına duruşsuz bir düz kol ekle (10 tuzak × 3 tekrar, opak kopya adlarıyla,
   ~2 $). Düşük uydurma oranının kaynağı talimatsa, ürünün ajana söyleyecek tek şeyi o beş cümledir. Mekanik atıf kontrolünün
   sıkılaştırılması yapıldı (D186): ölçülen dosyalara dokunmayan yeni bir dosya, `benchmarks/agent_compare/claims_mech_strict.py`;
   sonucu §5.2'de; yeniden koşular iki kontrolü birlikte raporlar.
3. **İnsana dönük denetim katmanı.** Verinoda'nın ölçülmemiş tek değer iddiası: ajanın söylediğini kanıta bağlayan, inceleyen
   kişinin güvenebileceği bir katman. Ölçüsü insanla: inceleme süresi, yakalanan yanlış iddia, güven.
4. Çağrı başına token kullanımı artık ölçülüyor (D178; D186 öncesi `analyze` ~2.700 tahmini token / çağrıydı; yeni cevap en çok
   2.500 karakter, 0,4 token/karakterle yaklaşık 1.000 token olarak hesaplanır, ölçülmedi). Proje başına MCP bağlama ve `setup`
   yan dosyaları (madde 4, 5) ürün hijyeni olarak kalır.
5. **Ertelenenler (`docs/BACKLOG.md`, "Deferred from D186" bölümü):** iki oturumlu kalıcılık çalışması (proje beyni: hiçbir çalışma iki oturumu ya da
   bağlam sıkıştırmasını kapsamadı; ölçülen tek önden enjeksiyon olgu kaybettirdi, 207'ye karşı 212), Louvain ile başlık
   sayılarının yeniden ölçümü, `.verinoda` sahip damgası, varsayılan salt-okunur sorgu, laboratuvar araçlarının ayrılması, gramer
   kırpması ve when-kuralının sınırları.
