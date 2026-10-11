# Verinoda: benchmark bulguları ve bilinen eksikler

Tarih: 2026-10-11. Kaynak: `benchmarks/results/**`, `docs/SYMBIOSIS-GAPS.md`, `docs/BACKLOG.md` (bölüm 13 ve 20).
Bu belge ölçülenleri ve ölçülmeyenleri ayırır. Bir sayı burada yoksa, ölçülmediği anlamına gelir.

## 1. En önemli sonuç: SWE-bench Lite, 100 örnek

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

## 5. Önerilen sıra

1. SWE-bench sonucunu ürün dili için tekrar ölç: Verinoda'yı yalnız gerektiğinde çağıran bir protokol (tek `analyze`, `code_check`
   yok) ve aynı 100 örnek. Kazanç olmazsa maliyet artışı belgelenir.
2. `analyze` için ilişki iddiası (BACKLOG 20.1 aşama B), gerçek bir corpus ve altın verisiyle.
3. Çağrı başına token kullanımı (madde 7); maliyet ölçümü olmadan hiçbir maliyet iddiası yapılmaz.
4. Proje başına MCP bağlama ve `setup` yan dosyaları (madde 4, 5).
