# AI Kodlama Ajanları, Odak Modu ve Proje Beyni: Bulgular Raporu

Oct 11, 2026 · @Esra

## Özet

AI kodlama ajanlarında kaliteyi en çok "sihirli prompt" değil, ajanın işini doğrulayabildiği bir döngü ve iyi yönetilen bağlam artırıyor. Bu ilkeyi Claude Code'a **Odak** adlı bir mod olarak uyguladık ve Verinoda deposunda ölçtük: 24 çalıştırmada ortalama maliyet yalnızca %4 düştü ($0,117 → $0,112), yani fark gürültü payının içinde.

Üç ana sonuç:

- **Araştırma:** Aynı model, yalnızca araç ve çalışma ortamı farkıyla benchmark'larda 5–25 puan oynayabiliyor. En yüksek getiri doğrulama kanalından (test, linter, tarayıcı) geliyor. Prompt injection hâlâ çözülmüş değil.
- **Odak:** Yeri belirsiz görevlerde maliyeti %7–25 düşürdü, aranan metnin istemde aynen verildiği görevlerde %15 artırdı. İlk sürümdeki doğrulama kapısı, projede zaten var olan lint hataları yüzünden modeli döngüye sokup maliyeti 2–3 katına çıkardı. Kapı artık yalnızca yeni hataları gösteriyor.
- **Proje beyni:** Proje bilgisini bir grafiğe çevirip ajanın yalnızca gereken yoldan geçmesini sağlama fikri bilimsel olarak sınanmış (HippoRAG). Ama değer üretmesi için bilginin modele araç çağrısı beklemeden gelmesi, haritanın kodla birlikte güncel kalması ve kendi deponda ölçülmesi gerekiyor.

## Araştırmanın ana bulguları

Araştırmanın tamamı ayrı rapordadır. Bu bölüm, Odak'ın ve proje beyni fikrinin dayandığı bulguları özetliyor.

**Yönlendirme**

- En tutarlı kazanç plan → uygula → doğrula döngüsünden geliyor. Boris Cherny'ye göre ajana işini doğrulama imkânı vermek kaliteyi 2–3 kat artırıyor (uygulayıcı tahmini).
- Anthropic'in ilkesi "en küçük, yüksek sinyalli token kümesi": minimal bir sistem prompt'uyla başla, gözlenen hatalara göre ekle.
- CLAUDE.md / AGENTS.md kısa tutulmalı ve her hatada bir kural eklenerek büyümeli.
- Alt-ajanlar okuma, keşif ve doğrulama için işe yarıyor; paralel yazma için yaramıyor.

**Sınırlar**

- METR: Claude Opus 4.5'in %50 zaman ufku yaklaşık 4 saat 49 dakika, ama %80 ufku yalnızca yaklaşık 27 dakika. Fark bir güvenilirlik sorununa işaret ediyor.
- METR'in 2025 RCT'sinde deneyimli geliştiriciler AI ile %19 yavaşladı ama %20 hızlandıklarını sandılar. 2026 takibi hızlanmaya işaret ediyor, METR ise verinin güvenilmez olduğunu söylüyor. Öz-bildirime güvenilmemeli, ölçülmeli.
- Context rot: Chroma'nın test ettiği 18 modelin hepsinde girdi uzadıkça performans düşüyor.

**Güvenlik**

- Veracode: AI kodunun %45'i OWASP Top 10 açığı içeriyor.
- Önerilen paketlerin %19,7'si var olmayan paketler (slopsquatting riski).
- Willison'ın "lethal trifecta" kuralı: özel veri, güvenilmeyen içerik ve dışarı iletişim aynı ajanda birleşmemeli.
- Replit olayı: "dondurma" talimatı bir prompt'tur, kontrol değildir.

**Maliyet ve araçlar**

- Prompt caching okuma maliyetini girdi fiyatının %10'una veya altına indiriyor; Batch API %50 indiriyor.
- Kod yürütmeli MCP bir örnekte 150.000 tokeni 2.000'e, Tool Search araç tanımlarını %85 azaltıyor (şirket ölçümleri).
- SWE-agent'ta aynı GPT-4 Turbo yalnızca arayüz tasarımıyla SWE-bench Lite'ta %11'den %18'e çıktı. Kötü tasarlanmış bir arama aracı, hiç araç olmamasından daha kötü sonuç verdi.

## Claude Code'un genişletilebilirliği

Claude Code 1 Ekim 2026'dan beri **mod** destekliyor (2.1.287 ve üstü). Mod, plugin içinde gelen bir TypeScript modülü. Oturumdaki olayları izleyebiliyor, araç çağrılarını reddedebiliyor veya yeniden yazabiliyor, modele yeni araç ve komut verebiliyor, arayüze çizim yapabiliyor.

| Mekanizma | Ne değiştirir | Odak'ta kullanımı |
| --- | --- | --- |
| `prompt.compose` | Sistem prompt bölümlerini ekler, değiştirir veya çıkarır | Beş kuralık kısa bölüm |
| `prompt.submit` | İstemi veya yanındaki bağlamı | Küçük iş sözleşmesi |
| `tool.call` | Araç çağrısını gözler, yeniden yazar veya reddeder | Okuma sınırı, gürültü ve tarama korumaları, import kontrolü |
| `classic.Stop` | Turun bitişini engelleyip modele geri gönderir | Doğrulama kapısı |
| `session.append` | Konuşmaya eklenen satırı (araç sonucu dahil) | Uzun Bash çıktısını kırpma |
| `$.tool.register` | Modele yeni araç verir | `mcp__odak__locate` |
| `ui.render` | İstemin üstündeki bandı ve panelleri çizer | Tur başına arama, okuma, token ve maliyet |

Daha basit seçenekler de var: output style (sistem prompt'una talimat ekler), ayar hook'ları, izin kuralları, alt-ajan ve skill dosyaları. Ancak bir talimat yalnızca prompt'ta kalırsa model onu çiğneyebilir. Bu yüzden Odak'ta kurallar mümkün olduğunca hook'larla zorlanıyor.

Yazarken karşılaşılan teknik ayrıntılar:

- Custom output style varsayılan olarak Claude Code'un mühendislik talimatlarını düşürüyor. `keep-coding-instructions: true` verilmezse kaliteyi artırmak için yazılan stil kaliteyi düşürür.
- Doğrulayıcı (`claude plugin validate`), `$` alan yardımcı fonksiyonların modülün en üstünde tanımlanmasını şart koşuyor.
- Aynı olaya matcher'sız ikinci bir hook eklenemiyor; `{ tool: /^(Edit|Write)$/ }` gibi regex matcher'lar kullanılmalı.
- Kullanıcı ayarları modül düzeyinde bir değişkende değil, `register` içindeki closure'da tutulmalı. Aksi halde bir hata ayarları sessizce boş bırakıyor; bu hatayı testler yakaladı.
- Bu bulut ortamında hot reload'a açılan mod, alt `claude -p` oturumlarına da sızıyordu. Temiz ölçüm için oturum ortam değişkenleri kaldırılarak çalıştırıldı.

## Odak modu

Odak, karmaşık bir projede küçük bir değişiklik istendiğinde ajanın depoyu taraması ve görmediği şeyleri uydurması sorununa karşı yazıldı. Hedef, hedefi depoyu taramadan bulmak, yalnızca görülen şeye dayanmak ve değişikliği doğrulamadan bitirmemek. Kaynak, 13 test ve Türkçe README `odak.zip` içinde.

| Parça | Ne yapar |
| --- | --- |
| `locate` aracı | Tanımlayıcı, dosya adı veya metinle arar; tanımları kullanımların, kodu doküman ve kopyaların önüne koyar. `max_items`, `max-items` ve `maxItems` aynı terim sayılır. Verinoda dizini varsa onu kullanır, yoksa `git grep`. |
| Sistem prompt bölümü | Beş kural: önce bul sonra oku, görmediğini adlandırma, değişikliği küçük ve stile uygun tut, belirsizse tek soru sor, bitince kanıt ver. Yaklaşık 300 token, İngilizce. |
| Küçük iş sözleşmesi | İstem küçük bir değişikliğe benziyorsa o tura kısa bir sözleşme ve arama bütçesi ekler. |
| Okuma sınırı | Küçük işte 400, normal işte 1000 satırı aşan dosyanın tamamı istenirse ilk 250 / 600 satırı döner. Model ısrar ederse bütün dosyayı verir. |
| Gürültü koruması | `node_modules`, `dist`, kilit dosyaları ve `.min.js` okumalarını ilk denemede tutar. |
| Arama bütçesi | Küçük işte 10, normal işte 30 arama çağrısı. Küçük işte `**/*` veya `find .` gibi tüm depoyu tarayan çağrıları ilk seferde tutar. |
| Import kontrolü | JS/TS'de göreli yolu ve paketin `package.json`'da olup olmadığını, Python'da göreli modülü kontrol eder. Yeni paket için "adı doğrula, kullanıcıya sor" der. |
| Doğrulama kapısı | Düzenleme yapılan turda projenin hızlı kontrolünü ilk düzenlemeden önce ve tur sonunda çalıştırır, modele yalnızca yeni hataları gösterir. En fazla iki kez durdurur. |
| Bash kırpma | 16.000 karakteri aşan çıktının ilk 3.000 ve son 6.000 karakterini tutar. |
| Bant | İstemin üstünde iş boyutu, arama sayısı, okunan ve düzenlenen dosya, engellenen çağrı, kontrol durumu, token ve maliyet. |
| `odak:scout` | Haiku ile çalışan, yalnızca okuyan, en fazla 15 satır kanıt döndüren keşif alt-ajanı. |

Tasarım kararları:

- **Kurallar hook'larla zorlanıyor, prompt'a güvenilmiyor.** Replit olayının dersi.
- **Varsayılan yumuşak mod:** İlk denemede tutar, model ısrar ederse izin verir. Kör bir yasak meşru işi de engeller.
- **Model çağrısı yok:** Görev boyutu sezgisel olarak belirleniyor, her istemde token harcanmıyor.
- **Modelin okuduğu metin İngilizce:** Aynı kurallar Türkçede yaklaşık iki kat token tutuyor. Kullanıcının gördüğü her şey Türkçe.

## Ölçüm

Odak, görevin türüne göre maliyeti iki yönde değiştiriyor ve ortalamada %4 düşürüyor. Bu fark gürültü payının içinde.

Kurulum: Verinoda deposunda dört küçük görev, Odak açık ve kapalı olarak üçer kez, temiz `claude -p` oturumlarında (`--permission-mode acceptEdits`, en fazla 25 tur). Her çalıştırmadan önce depo `git checkout` ile sıfırlandı; maliyet, tur ve token sayıları oturum sonucundan, doğruluk diff'ten okundu.

&#91;embedded content: tools/ab.sh · Verinoda deposu · Claude Code 2.1.296, varsayılan model · 4 görev × 2 koşul × 3 tekrar\]

Yeri belirsiz görevlerde Odak'ın `locate` aracı modeli doğrudan hedefe götürdü. Metnin istemde aynen verildiği görevlerde ise grep zaten anında buluyordu ve `locate` fazladan bir tur ekledi. Tur sayısı ortalamada 4,6'dan 5,2'ye çıktı; doğruluk iki koşulda da 12/12.

Bu sonuçlar düzeltilmiş sürüme ait. İlk sürümde doğrulama kapısı, projede zaten var olan yaklaşık 4.000 ruff hatası yüzünden modeli döngüye soktu: ilk iki görevde 11–14 tur ve $0,18–$0,34 maliyet, yani modsuzun 2–3 katı. Tek depo ve görev başına üç tekrar olduğu için bu rakamlar bir eğilim gösteriyor, kanıt değil.

## Çıkarılan dersler

En önemli ders, ölçmeden "daha iyi" denmemesi gerektiği: mantıklı görünen iki parça ölçümde ters sonuç verdi.

1. **Doğrulama kapısının eski hataları bilmesi gerekiyor.** İlk sürüm, projede zaten var olan yaklaşık 4.000 ruff hatasını yeni hata sandı ve modeli döngüye soktu: 11–14 tur, 2–3 kat maliyet. Kapı artık kontrolü ilk düzenlemeden önce de çalıştırıyor, satır numaralarını yok sayarak karşılaştırıyor ve modele yalnızca yeni hataları gösteriyor.
2. **Araç çağrısının kendisi bir maliyet.** Aranan metin istemde aynen verildiğinde grep zaten anında buluyor. `locate` çağrısı ise fazladan bir tur ekledi ve maliyeti %15 artırdı. Bilginin modele araç çağrısı beklemeden, istemin yanında gelmesi gerekiyor.
3. **Literal arama, kavramsal soruda gürültü üretiyor.** "query limit default 10" gibi doğal dilde bir sorguda ilk sırada dokümanlar ve kopya klasörler çıktı. Nadir terimlere ağırlık verme, kod dışı dosyaları ve kopya klasörleri geri itme bu sorunu gideriyor.
4. **Bugünkü Claude Code depoyu taramadı.** Modsuz çalıştırmalarda bile model 2–5 hedefli `grep` ile doğru yeri buldu. Şikâyet edilen davranış bu depoda yeniden üretilemedi; kendi projende ölçülmeli.
5. **Görev boyutu sezgisi yanılabiliyor.** Bu raporu isteyen "bulduğumuz bilgileri" cümlesi, "bul" kökü yüzünden küçük bir kod değişikliği sanıldı ve tura gereksiz bir sözleşme eklendi. Sözcük listesi daraltılmalı ya da `/odak boyut` ile sabitlenmeli.
6. **Ayar hatasını testler yakaladı.** Kullanıcının kontrol komutu sessizce boş kalıyordu. Doğrulama kapısının testi olmasaydı bu fark edilmeyecekti.

## Proje beyni fikri

Proje bilgisini bir grafiğe çevirip ajanın yalnızca gereken yoldan geçmesini sağlamak bilimsel olarak sınanmış bir fikir. Ama kazanç için bilginin modele araç çağrısı beklemeden gelmesi gerekiyor.

Görseldeki nöron ağı aslında bir bilgi grafiği: düğümler bilgi parçaları, kenarlar ilişkiler. Claude'un kendi nöronları eğitimle sabitlenmiş ağırlıklar; dışarıdan nöron eklenemez. Yapılabilecek şey, modele doğru anda doğru bilgiyi veren bir dış hafıza kurmak.

En yakın kanıt HippoRAG (NeurIPS 2024). İnsan uzun süreli belleğindeki hipokampal indeksleme kuramından esinleniyor: metinleri bir bilgi grafiğine çeviriyor, sorudaki kavramları tohum yapıp aktivasyonu Personalized PageRank ile yayıyor. [Makaleye göre](https://huggingface.co/papers/2405.14831) çok adımlı sorularda en iyi yöntemleri %20'ye kadar geçmiş; adım adım arayan IRCoT kadar iyi sonuç verirken 10–30 kat ucuz ve 6–13 kat hızlı çalışmış. Bu ölçümler soru-cevap veri setlerinde, kod tabanında değil.

&#91;embedded content: önerilen mimari · 5 adım, Verinoda grafiği ve Odak hook'ları üzerine\]

Parçaların yarısı zaten var. Verinoda projeyi kanıtlı bir grafiğe çeviriyor; Odak ajanın nasıl aradığını ve ne zaman doğrulandığını kontrol ediyor. Eksik olanlar yayılma algoritması, kart formatı, `prompt.submit` ile enjeksiyon ve kullanımla değişen ağırlıklar.

**Riskler**

- **Bayatlık:** Kodla birlikte güncellenmeyen bir harita, modele kendinden emin ama yanlış bilgi verir. Anthropic Claude Code'da vektör indeksi yerine grep'i bu yüzden seçti. Kenarlar mümkün olduğunca AST, git ve linklerden çıkarılmalı; her kart kaynağının hash'ini taşımalı.
- **LLM'in çizdiği kenarlar:** "Bu modül şunu etkiler" gibi anlamsal kenarlar ayrı türde tutulmalı, düşük ağırlık almalı ve kanıt istemeli.
- **Kendini güçlendirme:** Sık kullanılan yol daha sık seçilip daha da güçlenir. Ağırlıkların sınırı olmalı, zamanla sönümlenmeli ve deterministik kenarları ezmemeli.

**Grep'ten iyi olacağı yerler:** çok adımlı sorular, istemle kodun farklı kelimeler kullandığı durumlar ("giriş ekranı" ve `AuthGate`), kod ile doküman, karar ve issue arasındaki bağlar, büyük ve olgun depolar. Tam isimle sorulan küçük işlerde grep'i geçemez; bu görevlerde enjeksiyon küçük kalmalı veya hiç yapılmamalı.

## Açık sorular ve sonraki adımlar

Asıl soru hâlâ açık: şikâyet edilen tarama ve uydurma davranışı hangi projelerde, hangi modelle ortaya çıkıyor? Önce bunu ölçmek, sonra beyni kurmak gerekiyor.

Açık sorular:

- Sorunun yaşandığı projede Odak ölçülebilir bir fark yaratıyor mu? Bu depodaki görevler sorunu tetiklemedi.
- Okuma sınırı, import kontrolü ve Bash kırpma gerçek bir tarama veya uydurma anında ne kadar tasarruf sağlıyor? Bu ölçümde hiçbiri tetiklenmedi.
- Ön-enjeksiyon, tam isimli görevlerde de maliyeti artırmadan çalışabilir mi?

Sonraki adımlar:

- [ ] Odak'ı bilgisayarına kur ve sorunu gördüğün projede `/odak durum` ile arama arka ucunu ve kontrol komutunu doğrula.
- [ ] O projeden 5–10 istem seç (tam isimli, belirsiz ve çok adımlı karışık) ve `tools/ab.sh <repo> gorevler.txt 3` ile ölç.
- [ ] Görev boyutu sınıflandırıcısındaki "bul" yanlış pozitifini düzelt.
- [ ] Verinoda'nın `atlas.db` şemasına yayılan aktivasyon geri getirimini prototiple.
- [ ] Odak'a `prompt.submit` ile kart enjeksiyonu ekle ve aynı A/B ile tam isimli, belirsiz ve çok adımlı görevlerde karşılaştır.
- [ ] Ölçüm kazanç gösterirse kullanıma dayalı kenar güçlendirmeyi, başarı sinyali olarak doğrulama kapısına bağlayarak ekle.

## Kaynaklar

Araştırma raporunun tam kaynak listesi o raporda. Burada bu rapordaki iddiaların dayandığı başlıca kaynaklar var. Odak ölçümleri bu çalışmada yapıldı; ham transcript'ler ve diff'ler `tools/ab.sh` ile yeniden üretilebilir.

- [Getting started with Claude Code mods (claude.dev)](https://claude.dev/blog/getting-started-with-claude-code-mods/)
- [Claude Code output styles (resmi doküman)](https://code.claude.com/docs/en/output-styles)
- [HippoRAG: Neurobiologically Inspired Long-Term Memory for LLMs](https://huggingface.co/papers/2405.14831)
- [Anthropic: Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic: Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Anthropic: Advanced tool use (Tool Search, Programmatic Tool Calling)](https://www.anthropic.com/engineering/advanced-tool-use)
- [SWE-agent: Agent-Computer Interfaces (arXiv)](https://arxiv.org/html/2405.15793v1)
- [Simon Willison: The lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/)
- [Veracode GenAI Code Security Report](https://www.veracode.com/blog/genai-code-security-report/)
- [AI hallucinations create a new software supply chain threat (SecurityWeek)](https://www.securityweek.com/ai-hallucinations-create-a-new-software-supply-chain-threat/)
- [METR 2026 developer productivity study (özet)](https://ingenire.com/blog/metr-2026-developer-productivity-study)
- [Verinoda (GitHub)](https://github.com/ozcinax-star/verinoda)
