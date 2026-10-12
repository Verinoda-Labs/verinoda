# Verinoda Symbiosis

Verinoda and Claude Code, working as one: this repository is [Verinoda](https://github.com/ozcinax-star/verinoda)
(evidence-first code analysis for coding agents) together with **verinoda-live**, a Claude Code mod that lives in
the session beside the agent. Verinoda's own code here is the upstream branch it was built on plus the changes
proposed back to it; the mod is `claude-mods/verinoda-live/`.

## Why a mod

Measured with a model in the loop, pre-registered:

- **Offered** Verinoda, the agent used it in 6 of 57 sessions (`benchmarks/results/agent-compare-2026-10-02/`). An
  index nobody calls and nobody refreshes is no help; the mod keeps it fresh and can put it in the agent's path.
- **Told to start with Verinoda's analyze**, it found the same facts as searching by hand in both studies. On
  corpora of 37-226 files that came at 16 % fewer input tokens and 29 % fewer tool calls; on the ten real-world
  repositories (`benchmarks/results/agent-compare-realworld-2026-10-02/`) at 14 % *more* input tokens and 16 %
  fewer output tokens. Neither study found more facts with it.
- **Handed search results up front**, it found a few facts fewer: leads anchor it.
- **Checking each edit** (`benchmarks/results/agent-compare-guard-2026-10-02/`, 60 real coding sessions with hidden
  tests): with the check and without it the agent passed every test and wrote no name that does not exist; it read
  the code before every edit, so the check had nothing to catch. It stays on as a cheap safety net.
- **On a 27,078-file repository** (`benchmarks/results/agent-compare-big-2026-10-02/`, home-assistant/core, 40 real bug
  reports, 160 real sessions, run twice) **and on seL4** (`agent-compare-sel4-2026-10-02/`, the C microkernel, 21 bug
  reports, each session run three times): the agent with the mod, with Graphify's own integration and with nothing found the
  same files (no claim; the differences are chance). In none of the 286 sessions with Verinoda did the agent call it,
  though the mod's nudge, the MCP server and the skill were in every one and a probe showed they work. Graphify's hook, which
  speaks when the agent starts to `grep`, was followed by use of its tool in 5 of 80 Home Assistant and 21 of 63 seL4
  sessions. The case an index should win, a report that names no component, was not tested.
- **After the code moved on** (`benchmarks/results/agent-compare-stale-2026-10-02/`): a fresh index and a stale
  one found the same facts, and no stale index made the agent describe removed code. Freshness paid off in cost,
  and only on projects too large for `analyze` to refresh itself (300+ files): there a stale index cost about a
  fifth more input tokens than none, and the fresh index the mod keeps removed that (in one of two runs).

## What verinoda-live does

| | |
|---|---|
| **Keeps the index fresh** | Every Edit / Write / NotebookEdit in the project is noted; at the end of the turn one `verinoda update --fast` runs (about 20 s on 2,900 files instead of 130-155 s; `benchmarks/results/mod-live-self-quiet-2026-10-02/`), and the background graph build is watched until it has caught up. Edits during a build wait for it; a failed update keeps its files. |
| **Puts Verinoda in front of the agent** | The server's `analyze`, `project_query` and `run_tool` sit in the model's tool list, not behind ToolSearch, and one paragraph in the system prompt names `analyze` as the first tool call on a why, when, which-commit or what-does-it-affect question (D186). The earlier nudge mode and a softer rule were deleted after they were measured: 0 Verinoda calls in 286 study sessions and in 39 of 39 re-run sessions; the present rule got the call in 6 of 6 probe sessions (`docs/DESIGN.md` 158). |
| **Checks edits** (off) | `/verinoda-check on`: after each edit of a Python, Java or Kotlin file, the names on the changed lines that exist nowhere in the project are told to the model (0 notes in 65 edits of the guard study, so off by default). |
| **Shows it** | `/verinoda-panel`: a Turkish pane with the index state (glyph + words + colour), the check setting with a hotkey, and an animated purple Claude mascot in glasses that reads the code while Verinoda works. |

Settings (`/config`): `root` (project folder), `cli` (Verinoda program), `check`, `improveOffer`, `motion` (the
mascot's animation). An empty `cli` means `verinoda` on PATH outside the project: a program inside the project (its
`.venv`) is never run (D186). An empty `root` means the nearest folder with a `.verinoda` index at or above the
session's folder; one found above it is used only when `verinoda trust` knows it.

## Use it

```
pip install verinoda            # or: uv tool install verinoda
cd your-project && verinoda setup .
claude --plugin-dir <this repository>/claude-mods/verinoda-live
```

Then `/verinoda-panel`. The call rule is on whenever the Verinoda MCP server is connected; nothing else to switch on.

## Verinoda in a product: at build time, not at run time

Verinoda is used where a product is built, not where it runs (D183). A product made with it, such as the knowledge base
of the biology field test (`docs/SYMBIOSIS-GAPS.md`), ships what Verinoda produced as its own data and answers with its
own code; it does not import Verinoda while it runs. On a synthetic corpus of the field test's size
(`benchmarks/results/field-test-synthetic-2026-10-10/`), depending on Verinoda at run time cost about 0.45 s per cold
call (0.08-0.22 s for a standard-library stand-in), 38-42 MB of memory (15-17 MB), 63 packages and 293 MB to install,
an index update of 1-5 s after each change of the corpus, and about 15-25 % more characters per answer when a model
reads it (Verinoda itself calls no model). What it bought there, the sentence that answers ranked higher (mean
reciprocal rank 0.44 against 0.35 on 40 files, 0.27 against 0.06 on 400), comes from its ranking, which a build step
keeps:

```
verinoda relations --topics topics.json --json > data/relations.json
verinoda query "Doku konusundan önce ne öğrenilmeli" --sentences --json > data/evidence/doku.json
```

Depend on Verinoda at run time only when the corpus changes while the product runs (the answers then follow the files and
say when they changed) or when the questions are too open to compute before. Synthetic and self-made, these numbers are
not the field test's; the field test's corpus and gold were not measured.

## Develop it

`claude plugin validate claude-mods/verinoda-live` and `claude plugin test claude-mods/verinoda-live` (86 tests on the
terminal and desktop surfaces). Its design, the three-lens review it went through and the user-eyes redesign of the
pane are in `claude-mods/verinoda-live/README.md`.

---

## Türkçe özet

Verinoda Symbiosis, Verinoda ile Claude Code'u birlikte çalıştırır. **verinoda-live** modu oturumun içinde yaşar:

- Claude dosya düzenledikçe indeksi tazeler.
- Verinoda'nın üç ana aracını modelin araç listesine koyar ve sistem istemindeki tek paragraflık kural, "neden / ne zaman / hangi commit / neyi etkiler" sorularında ilk araç çağrısının `analyze` olmasını söyler (D186). Eski yönlendirme modu ve kaçış cümleli yumuşak kural ölçülüp silindi: 286 çalışma oturumunda ve yeniden koşunun 39 oturumunun 39'unda sıfır Verinoda çağrısı; bugünkü kural altı deneme oturumunun altısında çağrıyı aldı.
- Kod değiştikten sonra sorulan 50 soruda taze ve bayat indeks aynı olguları buldu; bayat indeks ajanı silinmiş kodu anlatmaya yöneltmedi. Tazeliğin faydası maliyette ve yalnızca büyük projelerde (300+ dosya) görüldü: bayat indeks indekssiz çalışmaya göre ~%20 daha fazla girdi token'ı harcattı, taze indeks bunu bir çalışmada geri aldı.
- Claude'un her Python/Java/Kotlin düzenlemesini kontrol edip var olmayan isimleri söyler. 60 gerçek kodlama oturumunda modlu ve modsuz ajan bütün gizli testleri geçti; ajan her düzenlemeden önce kodu okuduğu için kontrolün yakalayacağı bir şey çıkmadı.
- 27 bin dosyalık Home Assistant'ta (40 gerçek hata raporu) ve seL4 çekirdeğinde (21 rapor, her oturum üç kez): modlu, Graphify'lı ve araçsız Claude Code aynı dosyaları buldu, fark yok (şans). Verinoda'lı 286 oturumun hiçbirinde ajan Verinoda'yı çağırmadı, oysa nudge, MCP ve beceri her birinde vardı ve yoklama aracın çalıştığını gösterdi. Graphify'ın `grep` anında konuşan kancası HA'da 80 oturumun 5'inde, seL4'te 63'ün 21'inde aracın kullanılmasına yol açtı. Bileşen adı vermeyen raporlar denenmedi.
- Bunların hepsini hareketli mor maskotlu, Türkçe bir panelde gösterir.

Kurulum için yukarıdaki üç satır yeterli. Kurulumdan sonra `/verinoda-panel`; çağrı kuralı Verinoda MCP sunucusu bağlıyken kendiliğinden açıktır.

Verinoda'yla yapılan bir ürün (biyoloji saha testindeki bilgi tabanı gibi) Verinoda'yı derleme anında kullanır: ürettiği veriyi (ilişkiler, kanıt cümleleri) kendi verisi olarak taşır, çalışırken Verinoda'yı yüklemez. Sentetik bir korpusta çalışma zamanı bağımlılığı soru başına ~0,45 s, ~40 MB bellek, 63 paket / 293 MB kurulum ve her korpus değişikliğinde 1-5 s dizin güncellemesi demekti; kazancı olan daha iyi sıralama derleme adımında da korunur. Çalışma zamanı bağımlılığı yalnızca korpus ürün çalışırken değişiyorsa önerilir.
