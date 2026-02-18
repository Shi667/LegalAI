import requests
from bs4 import BeautifulSoup
import re
import time
import random
import urllib3
import json

# -----------------------------
# CONFIG
# -----------------------------
BASE_URL = "https://www.mjustice.gov.dz"
PATHS = [
    "/fr/la-plainte/",
    "/fr/la-requete/",
    "/fr/lassistance-judiciaire/",
    "/fr/le-tuteur/",
    "/fr/le-tuteur-testamentaire/",
    "/fr/le-recueil-legal/",
    "/fr/le-mineur-et-la-justice/",
    "/fr/designation-dun-expert/",
    "/fr/le-mariage-des-mineurs/",
    "/fr/extraire-des-documents/",
]

DELAY_RANGE = (3, 7)  # délai aléatoire entre requêtes
OUTPUT_TXT = "Q&A_ministere_de_la_justice.txt"
OUTPUT_JSON = "Q&A_ministere_de_la_justice.json"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
})


# -----------------------------
# FONCTIONS D'EXTRACTION
# -----------------------------
def extract_faq_text(full_text: str) -> str:
    """
    Isole le bloc de texte de la FAQ:
    entre 'Foire aux questions' et 'Structures du Ministère de la Justice'.
    """
    m = re.search(r"Foire\s+aux\s+questions", full_text, flags=re.IGNORECASE)
    if not m:
        return ""

    start = m.end()
    faq_part = full_text[start:]

    stop_marker = "Structures du Ministère de la Justice"
    stop_idx = faq_part.find(stop_marker)
    if stop_idx != -1:
        faq_part = faq_part[:stop_idx]

    return faq_part.strip()


def extract_qa_pairs(full_text: str):
    """
    À partir du texte complet d'une page, retourne une liste de
    {question, answer} pour la FAQ.
    """
    faq_part = extract_faq_text(full_text)
    if not faq_part:
        return []

    # On découpe en lignes en gardant les offsets pour reconstituer les blocs
    lines = faq_part.split("\n")

    offsets = []
    text_builder = []
    pos = 0
    for line in lines:
        line_with_nl = line + "\n"
        text_builder.append(line_with_nl)
        offsets.append((pos, pos + len(line_with_nl), line))
        pos += len(line_with_nl)

    rebuilt = "".join(text_builder)

    # Questions = lignes qui se terminent par '?'
    questions = []
    for start_i, end_i, line in offsets:
        if line.strip().endswith("?"):
            questions.append({
                "text": line.strip(),
                "start": start_i,
                "end": end_i,
            })

    qa_pairs = []
    if not questions:
        return qa_pairs

    # Pour chaque question, réponse = texte entre cette question et la suivante
    for i, q in enumerate(questions):
        q_start = q["start"]
        q_end = q["end"]

        if i + 1 < len(questions):
            next_q_start = questions[i + 1]["start"]
            answer_block = rebuilt[q_end:next_q_start]
        else:
            # dernière question : jusqu'à la fin du bloc FAQ
            answer_block = rebuilt[q_end:]

        answer = answer_block.strip()

        # Nettoyage des lignes vides
        answer_lines = [l.strip() for l in answer.split("\n")]
        answer = "\n".join([l for l in answer_lines if l])

        qa_pairs.append({
            "question": q["text"],
            "answer": answer,
        })

    return qa_pairs


# -----------------------------
# SCRAPING
# -----------------------------
data = []

for path in PATHS:
    url = BASE_URL + path
    print(f"[INFO] Fetching {url}")

    try:
        resp = session.get(url, verify=False, timeout=20)
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        continue

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    full_text = soup.get_text("\n", strip=True)

    qa_pairs = extract_qa_pairs(full_text)

    data.append({
        "url": url,
        "qa": qa_pairs,
    })

    time.sleep(random.uniform(*DELAY_RANGE))


# -----------------------------
# SAUVEGARDE TXT
# -----------------------------
with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
    for item in data:
        f.write(f"=== URL: {item['url']} ===\n")
        print(f"\n=== URL: {item['url']} ===")

        if not item["qa"]:
            f.write("(aucune QA trouvée)\n\n")
            print("(aucune QA trouvée)")
            continue

        for pair in item["qa"]:
            q = pair["question"]
            a = pair["answer"]

            # affichage console
            print("Q:", q)
            print("A:", a)
            print("-" * 80)

            # écriture fichier
            f.write("Q: " + q + "\n")
            f.write("A: " + a + "\n")
            f.write("-" * 80 + "\n")

        f.write("\n")

print(f"\nDonnées sauvegardées dans '{OUTPUT_TXT}'")

# -----------------------------
# SAUVEGARDE JSON
# -----------------------------
with open(OUTPUT_JSON, "w", encoding="utf-8") as jf:
    json.dump(data, jf, ensure_ascii=False, indent=2)

print(f"Données sauvegardées dans '{OUTPUT_JSON}'")
