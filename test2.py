import streamlit as st
import re
from datetime import datetime
import PyPDF2

st.title("🕒 Vérification de la continuité des horaires dans un PDF")

uploaded_file = st.file_uploader("Déposez un fichier PDF contenant des horaires", type="pdf")

# Fonction pour extraire le texte du PDF
def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text
    return text

# Fonction pour extraire les plages horaires avec date complète
def extract_time_ranges(text):
    pattern = r"Du (\d{1,2}) (\w+) (\d{4}) à (\d{1,2}) heure(?:s)? (\d{1,2}) minute(?:s)? au (\d{1,2}) (\w+) (\d{4}) à (\d{1,2}) heure(?:s)? (\d{1,2}) minute(?:s)?"
    matches = re.findall(pattern, text, re.IGNORECASE)

    mois_map = {
        "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
        "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12
    }

    results = []
    for d1, mois1, y1, h1, m1, d2, mois2, y2, h2, m2 in matches:
        try:
            start = datetime(int(y1), mois_map[mois1.lower()], int(d1), int(h1), int(m1))
            end = datetime(int(y2), mois_map[mois2.lower()], int(d2), int(h2), int(m2))
            results.append((start, end))
        except Exception as e:
            st.error(f"Erreur de parsing : {e}")
    return results

# Si un fichier est chargé
if uploaded_file:
    text = extract_text_from_pdf(uploaded_file)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)  # Supprime les espaces multiples

    intervals = extract_time_ranges(text)

    if not intervals:
        st.warning("⚠️ Aucune plage horaire trouvée dans le fichier.")
    else:
        intervals.sort()
        st.subheader("📋 Horaires extraits :")
        for i, (start, end) in enumerate(intervals):
            st.write(f"{i+1}. Du {start.strftime('%d/%m/%Y %H:%M')} au {end.strftime('%d/%m/%Y %H:%M')}")

        st.subheader("🔍 Vérification de la continuité :")
        for i in range(len(intervals) - 1):
            _, end_current = intervals[i]
            start_next, _ = intervals[i + 1]
            if end_current != start_next:
                st.error(f"❌ Incohérence entre {end_current.strftime('%d/%m/%Y %H:%M')} et {start_next.strftime('%d/%m/%Y %H:%M')}")
            else:
                st.success(f"✔️ OK : {end_current.strftime('%d/%m/%Y %H:%M')} → {start_next.strftime('%d/%m/%Y %H:%M')}")

        st.subheader("📄 Texte extrait du PDF")


################################################################

st.title("📄 Cahier de garde à vue")

def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += " " + page_text
    # Supprimer les apostrophes
    text = text.replace("'", "")
    return text

# --- Extraction des périodes et titres associés ---
def extract_periods_with_titles(text):
    text = re.sub(r"\s+", " ", text)

    # Pattern pour trouver les périodes
    pattern = r"(Du \d{1,2} \w+ \d{4} à \d{1,2} heure[s]? \d{1,2} minute[s]? au \d{1,2} \w+ \d{4} à \d{1,2} heure[s]? \d{1,2} minute[s]?)"

    # On cherche tous les titres (groupes en MAJUSCULES)
    all_titles = list(re.finditer(r"\b([A-ZÉÈÀÙÂÊÎÔÛÄËÏÖÜÇ ]{4,})\b", text))
    all_periods = list(re.finditer(pattern, text))

    results = []

    for period_match in all_periods:
        period_text = period_match.group(1)
        period_start = period_match.start()

        # Trouver le titre le plus proche (avant ou après)
        closest_title = "TITRE NON TROUVÉ"
        min_distance = float("inf")

        for title_match in all_titles:
            title_text = title_match.group(1).strip()
            distance = abs(title_match.start() - period_start)
            if distance < min_distance:
                min_distance = distance
                closest_title = title_text

        # Format final avec tiret
        final_line = f"{period_text} - {closest_title.title()}"
        results.append(final_line)

    return results

# --- Traitement principal ---
if uploaded_file:
    text = extract_text_from_pdf(uploaded_file)
    results = extract_periods_with_titles(text)

    if not results:
        st.warning("Aucune période détectée.")
    else:
        st.subheader("🕒 Périodes extraites avec titre :")
        for r in results:
            st.write(r)
