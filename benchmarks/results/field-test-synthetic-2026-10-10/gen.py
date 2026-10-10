"""A synthetic Turkish biology corpus at the field test's scale (40 topics), with planted prerequisite sentences.

Deterministic (seed). Writes <out>/kb/konular/*.md, <out>/kb/topics.json and <out>/gold.json:
questions, each with the sentences that state a prerequisite of its topic (the answer's evidence).
Synthetic and written by the same person who measures with it: not independent, not the field corpus.
"""

import json
import random
import sys
from pathlib import Path

TOPICS = ["Hücre", "Doku", "Organ", "Organ sistemleri", "Mitoz", "Mayoz", "DNA", "RNA", "Protein sentezi",
          "Enzimler", "Fotosentez", "Hücresel solunum", "Ekosistem", "Besin zinciri", "Kalıtım", "Gen",
          "Kromozom", "Mutasyon", "Evrim", "Sınıflandırma", "Bakteriler", "Virüsler", "Mantarlar", "Bitkiler",
          "Hayvanlar", "Sindirim sistemi", "Dolaşım sistemi", "Solunum sistemi", "Boşaltım sistemi",
          "Sinir sistemi", "Endokrin sistem", "Üreme", "Büyüme ve gelişme", "Homeostazi", "Hücre zarı",
          "Organeller", "Mitokondri", "Kloroplast", "Ribozom", "Hücre çekirdeği"]
PREREQ = {  # topic -> its prerequisites
    "Doku": ["Hücre"], "Organ": ["Doku"], "Organ sistemleri": ["Organ"], "Mitoz": ["Hücre çekirdeği", "Kromozom"],
    "Mayoz": ["Mitoz"], "RNA": ["DNA"], "Protein sentezi": ["RNA", "Ribozom"], "Enzimler": ["Protein sentezi"],
    "Fotosentez": ["Kloroplast", "Enzimler"], "Hücresel solunum": ["Mitokondri", "Enzimler"],
    "Besin zinciri": ["Ekosistem"], "Gen": ["DNA"], "Kromozom": ["Gen"], "Kalıtım": ["Mayoz", "Gen"],
    "Mutasyon": ["Gen"], "Evrim": ["Mutasyon", "Kalıtım"], "Virüsler": ["Bakteriler"], "Mantarlar": ["Sınıflandırma"],
    "Bitkiler": ["Fotosentez", "Sınıflandırma"], "Hayvanlar": ["Sınıflandırma"], "Sindirim sistemi": ["Organ sistemleri", "Enzimler"],
    "Dolaşım sistemi": ["Organ sistemleri"], "Solunum sistemi": ["Hücresel solunum", "Dolaşım sistemi"],
    "Boşaltım sistemi": ["Dolaşım sistemi"], "Sinir sistemi": ["Doku"], "Endokrin sistem": ["Sinir sistemi"],
    "Üreme": ["Mayoz"], "Büyüme ve gelişme": ["Mitoz", "Endokrin sistem"], "Homeostazi": ["Endokrin sistem", "Boşaltım sistemi"],
    "Organeller": ["Hücre"], "Mitokondri": ["Organeller"], "Kloroplast": ["Organeller"], "Ribozom": ["Organeller"],
    "Hücre çekirdeği": ["Organeller"], "Hücre zarı": ["Hücre"],
}
IN_LATER = ["{T} konusundan önce {P} konusu öğrenilmelidir.", "{T} konusu, {P} konusunun üzerine kurulur.",
            "{T} konusunu anlamak için {P} konusunu bilmek gerekir."]
IN_EARLIER = ["{P} konusu, {T} konusunun ön koşuludur.", "{P} konusundan sonra {T} konusuna geçilir."]
FILLER = ["{T}, canlıların yaşamında önemli bir yer tutar.", "{T} ile ilgili deneyler laboratuvarda yapılır.",
          "{T} günlük yaşamda pek çok örnekle karşımıza çıkar.", "{T} konusunda temel kavramlar tanımlanır.",
          "Bu bölümde {T} ile ilgili şekiller ve tablolar yer alır.", "{T} lise müfredatında ayrı bir ünitedir."]
COMENTION = "{X} konusu ile {Y} konusu sınavlarda birlikte sorulabilir."
QUESTIONS = ["{T} konusundan önce hangi konular öğrenilmeli?", "{T} konusunu öğrenmeden önce neyi bilmek gerekir?"]


def main(out: Path, scale: int = 1) -> None:
    rnd = random.Random(7)
    kb = out / "kb"
    (kb / "konular").mkdir(parents=True, exist_ok=True)
    # a larger corpus: copies of the topics told apart by a qualifier word (a digit would be dropped by tokenizers)
    quals = ["", " ormanda", " denizde", " gölde", " çölde", " toprakta", " havada", " nehirde", " dağda", " mağarada"]
    topics = [t + quals[k] for k in range(scale) for t in TOPICS]
    prereq = {}
    for k in range(scale):
        suffix = quals[k]
        for t, ps in PREREQ.items():
            prereq[t + suffix] = [p + suffix for p in ps]
    files: dict[str, list[str]] = {t: [] for t in topics}
    gold: dict[str, list[str]] = {t: [] for t in topics}
    for t, ps in prereq.items():
        for p in ps:
            if rnd.random() < 0.7:
                s = rnd.choice(IN_LATER).format(T=t, P=p)
                files[t].append(s)
            else:
                s = rnd.choice(IN_EARLIER).format(T=t, P=p)
                files[p].append(s)
            gold[t].append(s)
    for t in topics:
        body = [f.format(T=t) for f in rnd.sample(FILLER, 4)]
        other = rnd.choice([x for x in topics if x != t])
        body.append(COMENTION.format(X=t, Y=other))
        sents = body + files[t]
        rnd.shuffle(sents)
        paras = [" ".join(sents[i:i + 3]) for i in range(0, len(sents), 3)]
        slug = (t.lower().replace(" ", "-").translate(str.maketrans("çğıöşü", "cgiosu")))
        (kb / "konular" / f"{slug}.md").write_text(f"# {t}\n\n" + "\n\n".join(paras) + "\n", encoding="utf-8",
                                                  newline="\n")
    (kb / "topics.json").write_text(json.dumps({"topics": topics, "prerequisites": prereq}, ensure_ascii=False,
                                               indent=1), encoding="utf-8")
    qs = []
    for i, t in enumerate(t for t in topics if gold[t]):
        if scale > 1 and i >= 30:
            break
        qs.append({"topic": t, "question": QUESTIONS[i % 2].format(T=t), "gold": gold[t]})
    (out / "gold.json").write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(topics)} topics, {len(qs)} questions, {sum(len(q['gold']) for q in qs)} gold sentences")


if __name__ == "__main__":
    main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 1)
