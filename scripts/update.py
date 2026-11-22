"""Lit le calendrier FFvolley de la poule et écrit data.json.

Lancé automatiquement par GitHub Actions (voir .github/workflows/update.yml).
Utilisation locale : python scripts/update.py  (ou python scripts/update.py page.html pour tester sur un fichier)
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

SOURCE_URL = (
    "https://www.ffvbbeach.org/ffvbapp/resu/vbspo_calendrier.php"
    "?saison=2026%2F2027&codent=PTPL72&poule=18M&division=&tour=&calend=COMPLET&x=37&y=7"
)
OUT = Path(__file__).resolve().parent.parent / "data.json"


class Rows(HTMLParser):
    """Récupère le texte de chaque cellule <td>, ligne par ligne."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag == "td" and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def num(s):
    try:
        return int(s)
    except (TypeError, ValueError):
        return 0


def parse(html):
    p = Rows()
    p.feed(html)
    matches, standings, journee = [], [], None
    for c in p.rows:
        m = re.match(r"^Journ[ée]e\s*(\d+)", c[0], re.I)
        if m and len(c) == 1:
            journee = int(m.group(1))
            continue
        if re.match(r"^\d+\.$", c[0]) and len(c) >= 18:
            standings.append({
                "rank": int(c[0][:-1]), "team": c[1], "pts": num(c[2]), "j": num(c[3]),
                "g": num(c[4]), "p": num(c[5]), "setP": num(c[13]), "setC": num(c[14]),
                "ptP": num(c[16]), "ptC": num(c[17]),
            })
            continue
        if len(c) >= 6 and re.match(r"^[0-9A-Z]{3,}\d{3}$", c[0]) and re.match(r"^\d{2}/\d{2}/\d{2}$", c[1]):
            d, mo, y = (int(x) for x in c[1].split("/"))
            hh, mm = (c[2] or "00:00").split(":")
            s1 = c[6] if len(c) > 6 else ""
            s2 = c[7] if len(c) > 7 else ""
            # Une lettre (P = pénalité, F = forfait...) à la place d'un score = forfait de cette équipe
            forf = re.compile(r"^[A-Z]{1,3}$")
            played = (s1.isdigit() and (s2.isdigit() or bool(forf.match(s2)))) or (s2.isdigit() and bool(forf.match(s1)))
            forfeit = "home" if played and forf.match(s1) else "away" if played and forf.match(s2) else None
            matches.append({
                "code": c[0], "journee": journee,
                "date": f"{2000 + y:04d}-{mo:02d}-{d:02d}T{int(hh):02d}:{int(mm):02d}",
                "home": c[3], "away": c[5], "played": played,
                "sh": (int(s1) if s1.isdigit() else 0) if played else None,
                "sa": (int(s2) if s2.isdigit() else 0) if played else None,
                "forfeit": forfeit,
                "sets": (c[8] if len(c) > 8 else "") if played else "",
                "points": (c[9] if len(c) > 9 else "") if played else "",
                "venue": "" if played else (c[7] if len(c) > 7 else ""),
            })
    return matches, standings


def main():
    if len(sys.argv) > 1:
        raw = Path(sys.argv[1]).read_bytes()
    else:
        req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0 (calendrier ASCA)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
    html = raw.decode("cp1252", errors="replace")
    matches, standings = parse(html)
    if not matches:
        sys.exit("Aucun match trouvé : la page FFvolley a peut-être changé. data.json n'est pas modifié.")

    payload = {"source": SOURCE_URL, "matches": matches, "standings": standings}
    # On ne réécrit le fichier que si les matchs ou le classement ont changé,
    # pour éviter un commit inutile à chaque passage.
    if OUT.exists():
        old = json.loads(OUT.read_text(encoding="utf-8"))
        if old.get("matches") == matches and old.get("standings") == standings:
            print("Aucun changement.")
            return
    payload["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"data.json mis à jour : {len(matches)} matchs, {len(standings)} équipes.")


if __name__ == "__main__":
    main()
