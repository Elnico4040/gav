from flask import Flask, request, render_template_string
import re
from datetime import datetime
import PyPDF2
import io

app = Flask(__name__)

# Fonctions utilitaires (extraites du code Streamlit)
def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += " " + page_text
    text = text.replace("'", "")  # Supprimer les apostrophes
    text = re.sub(r"\s+", " ", text)
    return text

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
        except Exception:
            continue
    return results

def extract_start_guard_time(text):
    pattern = r"Cette mesure prend effet le (\d{1,2}) (\w+) (\d{4}) à (\d{1,2}) heure(?:s)? (\d{1,2}) minute(?:s)?"
    match = re.search(pattern, text, re.IGNORECASE)
    mois_map = {
        "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
        "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12
    }
    if match:
        d, m, y, h, mn = match.groups()
        try:
            return datetime(int(y), mois_map[m.lower()], int(d), int(h), int(mn))
        except Exception:
            return None
    return None

def extract_end_guard_time(text):
    pattern = r"Le (\d{1,2}) (\w+) (\d{4}) à (\d{1,2}) heure(?:s)? (\d{1,2}) minute(?:s)?, il est mis fin à la garde à vue"
    match = re.search(pattern, text, re.IGNORECASE)
    mois_map = {
        "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
        "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12
    }
    if match:
        d, m, y, h, mn = match.groups()
        try:
            return datetime(int(y), mois_map[m.lower()], int(d), int(h), int(mn))
        except Exception:
            return None
    return None

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

# Page HTML avec formulaire
HTML_TEMPLATE = """
<!doctype html>
<title>Vérification Horaires GAV</title>
<h2>📤 Déposez un fichier PDF</h2>
<form method=post enctype=multipart/form-data>
  <input type=file name=file accept=application/pdf>
  <input type=submit value=Analyser>
</form>
<hr>
{% if result %}
    <h3>Résultat</h3>
    {{ result|safe }}
{% endif %}
"""

@app.route("/", methods=["GET", "POST"])
def index():
    result = ""
    if request.method == "POST":
        file = request.files.get("file")
        if file:
            text = extract_text_from_pdf(io.BytesIO(file.read()))
            intervals = extract_time_ranges(text)
            start_guard = extract_start_guard_time(text)
            end_guard = extract_end_guard_time(text)
            period_titles = extract_periods_with_titles(text)

            verif1 = verification(intervals)

            if not intervals or not start_guard or not end_guard:
                result = f"<p style='color:red;'>Erreur : données incomplètes ou texte mal lu {text} .</p>"
            else:
                # Théorique
                theorique_total = (intervals[-1][1] - intervals[0][0]).total_seconds()
                hours = int(theorique_total // 3600)
                minutes = int((theorique_total % 3600) // 60)

                # Effectif
                total_seconds = int((end_guard - start_guard).total_seconds())
                hours2 = total_seconds // 3600
                minutes2 = (total_seconds % 3600) // 60

                verif2 = 1 if (hours == hours2 and minutes == minutes2) else 0

                global_verif = verif1 and verif2

                result += f"""
                <p><strong>Début :</strong> {start_guard.strftime('%d/%m/%Y %H:%M')}</p>
                <p><strong>Fin :</strong> {end_guard.strftime('%d/%m/%Y %H:%M')}</p>
                <p><strong>Durée mesurée :</strong> {hours2}h {minutes2}m</p>
                <p><strong>Durée théorique :</strong> {hours}h {minutes}m</p>
                <p style="color:{'green' if verif2 else 'red'};"><strong>{"✔️ Temps OK" if verif2 else "❌ Temps incohérent"}</strong></p>
                <p style="color:{'green' if verif1 else 'red'};"><strong>{"✔️ Horaires cohérents" if verif1 else "❌ Incohérence horaires"}</strong></p>
                <p style="color:{'green' if global_verif else 'red'};"><strong>{"✔️ Aucun problème détecté" if global_verif else "❌ Problèmes détectés"}</strong></p>
                <h4>Horaires extraits :</h4>
                <ul>
                {''.join([f"<li>Du {start.strftime('%d/%m/%Y %H:%M')} au {end.strftime('%d/%m/%Y %H:%M')}</li>" for start, end in intervals])}
                </ul>
                <h4>Cahier de GAV :</h4>
                <ul>
                {''.join([f"<li>{line}</li>" for line in period_titles])}
                </ul>
                """

    return render_template_string(HTML_TEMPLATE, result=result)

if __name__ == "__main__":
    app.run(debug=True)

