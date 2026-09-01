# 🚢 Seefracht-Konsolidierung (LCL-Containerrouting)

Interaktive Demo zur Konsolidierung von Sammelgut-Sendungen (LCL – Less than Container Load): Welche Packstücke teilen sich einen Container, und über welchen Hafen wird jeder Container verschifft, um See- und Straßenfrachtkosten **gemeinsam** zu minimieren?

**[→ Demo live ausprobieren](https://sebastianhanisch-freight-demo.streamlit.app/)**

## Worum geht's?

Ein kombiniertes Packungs- und Standortwahlproblem: Packstücke aus verschiedenen Regionen müssen auf Container verteilt werden, jeder Container läuft über genau einen Hafen — mit einem Trade-off zwischen wenigen, konzentrierten Häfen (einfachere Abwicklung) und mehr, gezielteren Containern (ausgeglichenere Auslastung).

## Methodik

- Drei selbst implementierte Ansätze im Vergleich: **blind gepackt** (nach Größe, ohne Rücksicht auf Herkunft), **hafen-bewusste Gruppierung** und eine **Beam-Search**-Erweiterung
- Welches Verfahren günstiger ist, hängt vom Verhältnis Seefracht- zu Straßenkosten ab und wird bei jedem Lauf neu berechnet, nicht angenommen
- PDF-Export, Permalink für eigene Beispielszenarien

## Lokal ausführen

```bash
pip install -r requirements-dev.txt
streamlit run app.py
```

Tests: `pytest tests/ -v`

---

Teil des [Operations-Research-Demo-Portfolios](https://sebastianhanisch.net/demos.html) von [Sebastian Hanisch](https://sebastianhanisch.net) — Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html).
