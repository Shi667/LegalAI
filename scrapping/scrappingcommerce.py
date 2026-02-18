import requests
from bs4 import BeautifulSoup
import time
import random
import json
import csv
import re

# =============================
# CONFIG
# =============================
BASE_URL = "https://www.commerce.gov.dz/fr/questions-frequentes"
DELAY_RANGE = (2, 5)
MAX_PAGE = 50

# =============================
# SESSION (anti-blocage basique)
# =============================
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


# =============================
# TEXT NORMALIZATION
# =============================
def normalize_text(text: str) -> str:
    """
    Corrige les textes avec lettres artificiellement espacées
    tout en conservant les vrais séparateurs de mots.
    """

    # Normaliser apostrophes & espaces
    text = text.replace("’", "'")
    text = re.sub(r"\s+", " ", text)

    # Recolle les lettres éclatées: v e n t e s -> ventes
    text = re.sub(
        r'(?<!\w)((?:[A-Za-zÀ-ÖØ-öø-ÿ]\s){2,}[A-Za-zÀ-ÖØ-öø-ÿ])(?!\w)',
        lambda m: m.group(0).replace(" ", ""),
        text
    )

    # Nettoyage ponctuation
    text = re.sub(r"\s+([,.;:?!])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)

    return text.strip()


# =============================
# FAQ EXTRACTION
# =============================
def extract_faq_block(full_text: str) -> str:
    """
    Isole le texte entre 'FOIRE AUX QUESTIONS'
    et '[xx] questions trouvées'.
    """
    m_start = re.search(r"FOIRE\s+AUX\s+QUESTIONS", full_text, re.IGNORECASE)
    if not m_start:
        return ""

    sub = full_text[m_start.end():]

    m_end = re.search(
        r"\[\s*\d+\s*\]\s*questions\s+trouvées",
        sub,
        re.IGNORECASE
    )

    return sub[:m_end.start()].strip() if m_end else sub.strip()


def extract_qa_from_text(full_text: str, page_number: int):
    faq_text = extract_faq_block(full_text)
    if not faq_text:
        return []

    lines = [l.strip() for l in faq_text.splitlines() if l.strip()]

    qa_pairs = []
    current_q = None
    current_a = []

    for line in lines:
        if line.endswith("?"):
            if current_q and current_a:
                qa_pairs.append({
                    "page": page_number,
                    "question": normalize_text(current_q),
                    "answer": normalize_text(" ".join(current_a)),
                })
            current_q = line
            current_a = []
        else:
            current_a.append(line)

    # Dernière Q/R
    if current_q and current_a:
        qa_pairs.append({
            "page": page_number,
            "question": normalize_text(current_q),
            "answer": normalize_text(" ".join(current_a)),
        })

    return qa_pairs


# =============================
# MAIN SCRAPER
# =============================
def scrape_all_faq():
    all_qa = []

    for page in range(1, MAX_PAGE + 1):
        print(f"[INFO] Fetching page {page}")

        try:
            resp = session.get(BASE_URL, params={"page": page}, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"[ERROR] Page {page}: {e}")
            time.sleep(random.uniform(*DELAY_RANGE))
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        full_text = soup.get_text("\n", strip=True)

        page_qa = extract_qa_from_text(full_text, page)
        print(f"[INFO] → {len(page_qa)} Q/A")

        all_qa.extend(page_qa)
        time.sleep(random.uniform(*DELAY_RANGE))

    return all_qa


# =============================
# EXPORT
# =============================
if __name__ == "__main__":
    data = scrape_all_faq()

    # JSON
    with open("faq_commerce_dz.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # CSV
    with open("faq_commerce_dz.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["page", "question", "answer"])
        for item in data:
            writer.writerow([item["page"], item["question"], item["answer"]])

    # TXT
    with open("faq_commerce_dz.txt", "w", encoding="utf-8") as f:
        for i, item in enumerate(data, start=1):
            f.write(f"Q{i} (page {item['page']}): {item['question']}\n")
            f.write(f"A{i}: {item['answer']}\n")
            f.write("-" * 80 + "\n")

    print(f"\n[SUCCESS] Total Q/A extracted: {len(data)}")
