# app.py
from flask import Flask, request, render_template
import re
from datetime import datetime
import PyPDF2
import io
from jinja2 import Environment
from odf.opendocument import load
from odf.text import P


app = Flask(__name__)

# Fonctions utilitaires (inchangées)
def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += " " + page_text
    text = text.replace("'", "")
    text = re.sub(r"\s+", " ", text)
    return text

def extract_text_from_odt(file):
    try:
        odt_doc = load(file)
        all_paragraphs = odt_doc.getElementsByType(P)
        text = " ".join([str(p.firstChild.data) for p in all_paragraphs if p.firstChild])
        text = text.replace("'", "")
        text = re.sub(r"\s+", " ", text)
        return text
    except Exception as e:
        print("Erreur ODT :", e)
        return ""


def extract_time_ranges(text):
    #pattern = r"Du (\d{1,2}) (\w+) (\d{4}) à (\d{1,2}) heure(?:s)? (\d{1,2}) minute(?:s)? au (\d{1,2}) (\w+) (\d{4}) à (\d{1,2}) heure(?:s)? (\d{1,2}) minute(?:s)?"
    #pattern = r"Du\s+(\d{1,2})\s+(\w+)\s+(\d{4})\s+à\s+(\d{1,2})\s+heure[s]?\s+(\d{1,2})\s+minute[s]?\s+au\s+(\d{1,2})\s+(\w+)\s+(\d{4})\s+à\s+(\d{1,2})\s+heure[s]?\s+(\d{1,2})\s+minute[s]?"
    pattern = r"(?:Du|Le)\s+(\d{1,2})\s+(\w+)\s+(\d{4})\s+à\s+(\d{1,2})\s+heure[s]?\s+(\d{1,2})\s+minute[s]?\s+(?:au\s+(\d{1,2})\s+(\w+)\s+(\d{4})\s+à\s+(\d{1,2})\s+heure[s]?\s+(\d{1,2})\s+minute[s]?)?"
    matches = re.findall(pattern, text, re.IGNORECASE)
    mois_map = {"janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
        "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12}
    results = []
    for d1, mois1, y1, h1, m1, d2, mois2, y2, h2, m2 in matches:
        try:
            start = datetime(int(y1), mois_map[mois1.lower()], int(d1), int(h1), int(m1))
            end = datetime(int(y2), mois_map[mois2.lower()], int(d2), int(h2), int(m2))
            results.append((start, end))
        except Exception:
            continue
    return results

def extract_start_guard_time(text):
    pattern = r"Cette mesure prend effet le (\d{1,2}) (\w+) (\d{4}) à (\d{1,2}) heure(?:s)? (\d{1,2}) minute(?:s)?"
    match = re.search(pattern, text, re.IGNORECASE)
    mois_map = {"janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
        "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12}
    if match:
        d, m, y, h, mn = match.groups()
        try:
            return datetime(int(y), mois_map[m.lower()], int(d), int(h), int(mn))
        except Exception:
            return None
    return None

def extract_end_guard_time(text):
    #pattern = r"Le (\d{1,2}) (\w+) (\d{4}) à (\d{1,2}) heure(?:s)? (\d{1,2}) minute(?:s)?, il est mis fin à la garde à vue"
    pattern = r"Le\s+(\d{1,2})\s+(\w+)\s+(\d{4})\s+à\s+(\d{1,2})\s*heure(?:s)?\s*(\d{1,2})\s*minute(?:s)?\s*,?\s*il\s+est\s+mis\s+fin\s+à\s+la\s+garde\s+à\s+vue"
    matches = re.findall(pattern, text, re.IGNORECASE)  
    mois_map = {
        "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
        "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12
    }
    for match in matches:
        try:
            jour, mois_str, annee, heure, minute = match
            jour = int(jour)
            annee = int(annee)
            heure = int(heure)
            minute = int(minute) if minute else 0

            mois = mois_map.get(mois_str.lower())
            if mois is None:
                continue  # mois non reconnu

            return datetime(annee, mois, jour, heure, minute)
        except Exception as e:
            print("Erreur de parsing :", e)
            continue

    return None  # Aucun résultat valide

def extract_periods_with_titles(text):
    pattern = r"(Du \d{1,2} \w+ \d{4} à \d{1,2} heure[s]? \d{1,2} minute[s]? au \d{1,2} \w+ \d{4} à \d{1,2} heure[s]? \d{1,2} minute[s]?)"
    titles = list(re.finditer(r"\b([A-ZÉÈÀÙÂÊÎÔÛÄËÏÖÜÇ' ]{4,})\b", text))
    periods = list(re.finditer(pattern, text))
    results = []
    for period_match in periods:
        period_text = period_match.group(1)
        period_start = period_match.start()
        closest_title = "TITRE NON TROUVÉ"
        for title_match in reversed(titles):
            if title_match.start() < period_start:
                closest_title = title_match.group(1).strip()
                break
        results.append(f"{period_text} : {closest_title.title()}")
    return results

def verification(intervals):
    for i in range(len(intervals) - 1):
        _, end_current = intervals[i]
        start_next, _ = intervals[i + 1]
        if end_current != start_next:
            return 0
    return 1

@app.route("/", methods=["GET", "POST"])
def index():
    result = ""
    start_guard = None
    end_guard = None
    text = None
    intervals = []
    period_titles = []
    verif1 = 0
    verif2 = 0
    global_verif = 0
    hours = minutes = hours2 = minutes2 = 0
    verif_intervals = []  # <-- liste de booléens de vérification horaire entre chaque intervalle

    if request.method == "POST":
        file = request.files.get("file")
        if file:
            filename = file.filename.lower()
            content = io.BytesIO(file.read())

            if filename.endswith(".pdf"):
                text = extract_text_from_pdf(content)
            elif filename.endswith(".odt"):
                text = extract_text_from_odt(content)
            else:
                result = "<p style='color:red;'>Format non supporté. Veuillez déposer un fichier PDF ou ODT.</p>"

            intervals = extract_time_ranges(text)
            start_guard = extract_start_guard_time(text)
            end_guard = extract_end_guard_time(text)
            period_titles = extract_periods_with_titles(text)

            verif1 = verification(intervals)


            if not intervals or not start_guard:
            # S'il manque start_guard ou intervals, on ne peut pas faire de calcul complet
                result = "<p style='color:red;'>Erreur : données incomplètes ou texte mal lu.</p>"
            else:
                theorique_total = (intervals[-1][1] - intervals[0][0]).total_seconds()
                hours = int(theorique_total // 3600)
                minutes = int((theorique_total % 3600) // 60)

                if end_guard is not None:
                    total_seconds = int((end_guard - start_guard).total_seconds())
                    hours2 = total_seconds // 3600
                    minutes2 = (total_seconds % 3600) // 60

                    verif2 = 1 if (hours == hours2 and minutes == minutes2) else 0
                else:
                    #   Pas d'heure de fin, on ne peut pas vérifier la durée théorique, on considère ça OK (ou neutre)
                    hours2 = minutes2 = None
                    verif2 = 1

                global_verif = verif1 and verif2

                # Calcul de la vérification horaire entre chaque intervalle (heure par heure)
                verif_intervals = []
                for i in range(len(intervals)):
                    if i == 0:
                        verif_intervals.append(True)  # Premier intervalle considéré OK
                    else:
                        prev_end = intervals[i-1][1]
                        current_start = intervals[i][0]
                        verif_intervals.append(prev_end == current_start)

    return render_template("index.html",
                           result=result,
                           start_guard=start_guard,
                           end_guard=end_guard,
                           hours=hours,
                           minutes=minutes,
                           hours2=hours2,
                           minutes2=minutes2,
                           verif1=verif1,
                           verif2=verif2,
                           global_verif=global_verif,
                           intervals=intervals,
                           period_titles=period_titles,
                           verif_intervals=verif_intervals,
                           text=text)

if __name__ == "__main__":
    app.run(debug=True)

