# Seefracht-Konsolidierung (LCL) – Streamlit-Demo

Interaktive Demo zur Konsolidierung von Sammelgut-Sendungen (LCL - Less than Container
Load): Welche Packstücke teilen sich einen Container, und über welchen Hafen wird jeder
Container verschifft, um See- und Straßenfrachtkosten **gemeinsam** zu minimieren?
Vierte Demo im Portfolio für die Website "Sebastian Hanisch – Operations Research und
Machine Learning" - nach Tourenplanung, 3D-Packungsoptimierung und Liniennetz-Design.

## Warum diese Demo anders ist als die ersten drei

Bei Tourenplanung, Packungsoptimierung und Liniennetz-Design gibt es jeweils **eine**
Entscheidungsebene (Reihenfolge, Positionierung, Streckenführung). Hier müssen **zwei
gekoppelte Ebenen** gemeinsam optimiert werden: welche Packstücke teilen sich einen
Container (Packproblem), und über welchen Hafen wird jeder Container verschifft
(Zuordnungsproblem). Beide Entscheidungen hängen voneinander ab - die beste Hafenwahl
für einen Container ergibt sich erst aus seinem tatsächlichen Inhalt.

## Dateistruktur

| Datei | Inhalt |
|---|---|
| `app.py` | Streamlit-Hauptablauf (Primäransicht, Sidebar, Detail-Expander) |
| `freight_constants.py` | Konstanten |
| `freight_data.py` | Häfen, Zielregionen, Straßenkosten-Matrix, Packstücke |
| `freight_heuristics.py` | Blind gepackt und hafen-bewusst gruppierte Konstruktion |
| `freight_evaluation.py` | Kostenaggregation (See + Straße) |
| `freight_visualization.py` | 2D-Karte (Plotly) |
| `freight_pdf_export.py` | PDF-Konsolidierungsplan-Erzeugung |
| `freight_feedback.py` | Feedback-Logging |
| `freight_ui_panel.py` | Wiederverwendbares UI-Panel je Heuristik |
| `freight_presets.py` | Beispielszenarien, Permalink-Logik (`SETTING_SPECS`) |

## Funktionsumfang

- **Drei eigene Heuristiken, gleicher Packmechanismus:** Alle drei nutzen First-Fit-
  Decreasing-Bin-Packing und dieselbe Hafenwahl-Logik je Container - der Unterschied
  liegt in der Gruppierung *vor* dem Packen und darin, ob mehrere Packvarianten
  durchprobiert werden:
  - *Blind gepackt* (Baseline): Packstücke werden rein nach Größe gepackt, ohne
    Rücksicht auf Zielregion.
  - *Hafen-bewusst gruppiert*: Packstücke werden zuerst nach ihrem günstigsten Hafen
    (anhand der Straßenkosten ihrer Zielregion) gruppiert, erst danach gepackt.
  - *Beam Search*: wie hafen-bewusst gruppiert, probiert aber je Gruppe mehrere
    ("Beam-Breite", einstellbar) deterministische Packvarianten durch und behält die
    beste - nachweislich **monoton** in der Beam-Breite (siehe eigener Abschnitt
    unten, auf ausdrücklichen Wunsch ergänzt).
- **Primäransicht "Ihre kostenoptimierte Konsolidierung"** von Anfang an (Lehre aus
  der Tourenplanung-Demo direkt übernommen): zeigt die tatsächlich günstigere Methode,
  **dynamisch bei jedem Lauf neu bestimmt** (siehe Kipppunkt unten) - kein
  Algorithmus-Name in der Überschrift, Methode als Caption genannt.
- **Kostenverhältnis als explorierbarer Regler:** "Seefracht je Container (€)" macht
  den zentralen Trade-off dieser Demo direkt erfahrbar (siehe unten).
- **Karte, PDF-Export, Permalink, Feedback-Mechanismus:** wie bei den anderen Demos.
- Von Anfang an mit dem `SETTING_SPECS`-Muster und NaN/Bounds-Schutz im Permalink
  gebaut (keine nachträglich gefundenen Absturz-Bugs wie bei der Tourenplanung-Demo).

## Der zentrale Befund: ein echter Kipppunkt, kein Selbstläufer

Die ursprüngliche Erwartung war, dass hafen-bewusste Gruppierung immer (oder fast
immer) gewinnt. Systematisches Nachrechnen zeigt: **das stimmt nur bei niedriger bis
mittlerer Seefracht.**

**Mechanismus:** Hafen-bewusste Gruppierung zerteilt den Packstück-Pool vor dem Packen
(getrennt nach bevorzugtem Hafen) - das führt tendenziell zu **mehr, dafür weniger
voll ausgelasteten Containern** als blindes Packen. Verifiziert über 5 Testinstanzen:
Blind nutzt 5-6 Container, hafen-bewusst 7 (`test_port_aware_uses_at_least_as_many_containers`).

**Bei Standard-Seefracht (800 €/Container):** hafen-bewusste Gruppierung gewinnt in
8 von 8 Testinstanzen, im Schnitt ca. 700 € Ersparnis (`test_port_aware_wins_at_default_sea_freight`).

**Systematische Suche nach dem Kipppunkt** (40 Packstücke, 6 Regionen, 3 Häfen, 10
Seeds je Stufe):

| Seefracht-Multiplikator | Hafen-bewusst gewinnt |
|---|---|
| 1,0× (800 €) | 10 / 10 |
| 1,5× | 6 / 10 |
| 2,0× | 3 / 10 |
| 2,5× | 2 / 10 |
| 3,0× | 1 / 10 |

Der Übergang ist graduell, nicht abrupt - ab ca. dem 2- bis 3-fachen der Standard-
Seefracht kehrt sich der Vorteil im Mehrheit der Fälle um: die zusätzlichen Container
der hafen-bewussten Gruppierung kosten mehr, als die bessere Hafenwahl einspart.
Deshalb bestimmt die App **bei jedem Lauf neu**, welche Methode tatsächlich günstiger
ist (`best = min(candidates, key=lambda c: c["total_cost"])`) - keine Methode wird
fest als "die bessere" angenommen, das wäre bei hoher Seefracht schlicht falsch.

**Praktische Konsequenz für die Demo:** Der Regler "Seefracht je Container" macht
diesen Kipppunkt direkt erfahrbar - beide Methoden werden bei jeder Einstellung neu
gerechnet, sichtbar in Primäransicht und Vergleichstabelle.

## Beam Search: monoton in der Beam-Breite (auf Wunsch ergänzt)

Ausdrücklicher Wunsch: eine Beam-Search-Variante, bei der eine größere Beam-Breite das
Ergebnis nachweislich nie verschlechtert. Das war nicht auf Anhieb korrekt - zwei echte
Fehler wurden beim Bauen gefunden und behoben, beide durch systematisches Testen, nicht
durch Zufall.

### Fund 1: Die naheliegende Umsetzung ist nicht monoton

Die erste Implementierung folgte demselben Muster wie die Beam-Search-Varianten der
Touren- und Packungsdemo: bei jedem Schritt (ein Packstück nach dem anderen, nach Größe
absteigend) wird aus allen aktuellen Beam-Zuständen die vollständige Kandidatenmenge
erzeugt, deterministisch sortiert, auf die besten `beam_width` gekürzt.

Die Annahme dahinter: "Der Kandidatenpool bei Breite K+1 ist eine Obermenge des Pools
bei Breite K, also bleiben die Top-K erhalten." Diese Annahme ist **falsch** - ein
konkretes Gegenbeispiel (Seed 7, 30 Packstücke) zeigt es:

| Beam-Breite | 1 | 2 | 4 | 8 | 16 |
|---|---|---|---|---|---|
| Gesamtkosten | 14.721 | 14.721 | 14.029 | **13.110** | **13.240** |

Zwischen Breite 8 und 16 *steigen* die Kosten. Der Grund: Breite 16 hat bei Schritt 6
einen doppelt so großen Eltern-Zustandspool wie Breite 8 (16 statt 8 Vorgänger-Zustände
erzeugen jeweils eigene Kandidaten) - dadurch kommen bei Breite 16 deutlich mehr neue,
teils bessere Kandidaten hinzu, die einen Zustand aus den Top-16 verdrängen können, der
bei Breite 8 noch sicher in den Top-8 war. "Mehr Konkurrenz um mehr Plätze" gleicht sich
nicht zwangsläufig aus. Festgehalten in `test_naive_stepwise_beam_search_would_have_violated_monotonicity`
als Dokumentation des verworfenen Ansatzes.

### Die korrekte Konstruktion

Für echte Monotonie braucht es eine andere Struktur: `beam_width` **unabhängige,
deterministische Varianten**, von denen die beste genommen wird. Jede Variante nutzt
dieselbe Gruppierung wie `port_aware_construction` (nach günstigstem Hafen je Region),
packt aber mit einer variantenspezifisch (über einen festen Sub-Seed) verschobenen
Sortierreihenfolge. Eine größere Beam-Breite fügt dem Kandidatenpool einfach eine
weitere Variante hinzu - "Minimum über eine wachsende Menge" kann per Definition nie
schlechter werden. Kein Induktionsargument über mehrere Schritte nötig, das schiefgehen
könnte - nur simple Mengenlehre.

### Fund 2: fast richtig, aber eine Garantie fehlte

Verifiziert wurde nicht nur Monotonie in der Breite, sondern auch "Beam Search ist nie
schlechter als Hafen-bewusst gruppiert" (naheliegend, da dieselbe Gruppierung als
Ausgangspunkt dient). Ein Test dafür fand eine winzige, aber echte Verletzung: bei Seed 4
lieferte Beam Search 10.315 € statt der 10.314 € von Hafen-bewusst gruppiert. Ursache:
alle Varianten nutzten eine gestörte Sortierreihenfolge - keine Variante testete jemals
exakt die *unveränderte* Reihenfolge, die `port_aware_construction` verwendet. Fix:
Variante 0 ist jetzt bewusst ungestört (`jitter_strength=0`), identisch zur Hafen-bewusst-
Methode - dadurch ist `beam_width=1` jetzt nachweislich **exakt** gleich zu
`port_aware_construction` (über 14 Testinstanzen mit Differenz < 1e-6 bestätigt,
`test_beam_search_width_one_exactly_matches_port_aware`), und jede zusätzliche Variante
kann das Ergebnis nur gleich gut oder besser machen.

### Ergebnis nach beiden Fixes

Über 14 Testinstanzen: Monotonie hält durchgehend (`test_beam_search_is_monotone_in_beam_width`),
`beam_width=1` reproduziert Hafen-bewusst exakt, höhere Breiten sind nie schlechter
(`test_beam_search_never_worse_than_port_aware`). Im direkten Methodenvergleich (10
Instanzen, `beam_width=16`) gewinnt Beam Search in allen 10 - erwartbar, da es strukturell
mindestens die Hafen-bewusste Lösung erreicht und oft eine bessere Packvariante findet.
Performance bleibt auch im Worst Case (100 Packstücke, Breite 32) unter 15ms.

## Zweiter Ansatz zum Vergleich: monobeam (Lemons et al., ICAPS 2022)

Nach dem eigenen Ensemble-Ansatz stellte sich die Frage, ob er demselben Mechanismus
folgt wie ["Beam Search: Faster and Monotonic"](https://arxiv.org/abs/2204.02929)
(Lemons, Linares López, Holte & Ruml, ICAPS 2022) - ein Paper, das explizit dasselbe
Ziel verfolgt (Monotonie in der Beam-Breite) und zufällig auch aus 2022 stammt. Antwort:
**nein, anderer Mechanismus** - deshalb zusätzlich implementiert (`monobeam_construction`
in `freight_heuristics.py`) und direkt verglichen.

### Der Unterschied in der Konstruktion

**Eigener Ansatz (`beam_search_construction`):** `beam_width` unabhängige,
deterministisch unterschiedliche vollständige Konstruktionen, das beste Ergebnis wird
genommen. Monotonie folgt aus simpler Mengenlehre (Minimum über eine wachsende Menge
kann nie schlechter werden) - einfach zu beweisen, aber jede Variante wird komplett neu
berechnet, keine geteilte Arbeit zwischen den Breiten.

**Paper-Ansatz (`monobeam_construction`):** Der Beam wird als **geordnete Folge
nummerierter Slots** behandelt und **sequenziell** gefüllt - Slot 1 zuerst, dann Slot 2,
usw. Alle Slots teilen sich einen gemeinsamen Kandidatenpool: Slot c expandiert seinen
Zustand, legt die Kinder in den Pool, entnimmt **sofort** das beste verbliebene Element
für sich selbst - bevor Slot c+1 überhaupt an der Reihe ist. Dadurch hat Slot c nur
Zugriff auf Kandidaten aus Slots 1..c, nie aus späteren. Das Paper beweist per Induktion
(ihr Lemma 1): die Wahl für Slot c ist dadurch komplett unabhängig von der Beam-Breite -
eine schmalere Suche ist buchstäblich ein **Präfix** einer breiteren, nicht nur
"meistens ähnlich". Eleganter und mit geteilter Arbeit über die Breiten hinweg, aber
mit einer subtileren Korrektheitsargumentation.

**Vereinfacht gegenüber dem Original:** Unser Problem hat eine feste Anzahl
Entscheidungsebenen (ein Packstück nach dem anderen in fester Reihenfolge, kein
variabler Zieltest wie bei Zustandsraumsuche) - Pathmax, Inkumbent-Verwaltung über
unterschiedliche Tiefen und die Duplikat-Slot-Verwaltung des Originals (deren
Algorithmus 3) werden dadurch nicht gebraucht.

### Eine schöne Bestätigung beim Lesen des Papers

Das Paper beschreibt exakt dasselbe Fehlermuster, das die erste (verworfene) Version
von `beam_search_construction` bzw. die dokumentierte, zuerst versuchte
schrittweise-Pruning-Variante zeigte: ein Knoten aus einem später hinzukommenden,
größeren Beam kann einen zuvor sicher platzierten Knoten verdrängen. Das Paper nennt
das **"cuckoo nodes"** (nach dem Vogel, der fremde Eier aus dem Nest wirft) - dieselbe
strukturelle Ursache, unabhängig gefunden.

### Zwei Fairness-Korrekturen, bevor der Vergleich aussagekräftig war

Eine erste, naive Adaption von monobeam war zwar korrekt monoton, aber unfair langsam
im Vergleich zum Ensemble-Ansatz - beide Korrekturen waren nötig, um tatsächlich die
Algorithmen zu vergleichen, nicht meine Implementierungsqualität:

1. **Inkrementelle statt vollständiger Kostenberechnung.** Die erste Fassung berechnete
   bei jedem Kandidaten die Kosten *aller* Container im Zustand neu, statt nur des durch
   das aktuelle Packstück veränderten. Fix: `new_score = alter_score - alte_kosten_des_
   veraenderten_containers + neue_kosten_des_veraenderten_containers`.
2. **Echte Prioritätswarteschlange (heapq) statt einer bei jedem Slot neu sortierten
   Liste.** Das Paper beschreibt den Kandidatenpool explizit als Priority Queue - meine
   erste Fassung sortierte stattdessen die komplette (wachsende) Liste bei jeder
   Slot-Entnahme neu.

### Ergebnis des fairen Vergleichs

Über 10 Testinstanzen (30 Packstücke, 5 Regionen, 3 Häfen), Beam-Breiten 4 und 16:

| Kriterium | Ensemble-Ansatz | monobeam |
|---|---|---|
| Monoton in der Breite | Ja (14/14 Instanzen) | Ja (14/14 Instanzen) |
| Rechenzeit (bw=16, Ø) | ~2,5 ms | ~10,8 ms (Faktor ~4,3×) |
| Gesamtkosten günstiger | 12 von 20 Fällen | 8 von 20 Fällen (bei bw=16 exakt 5:5) |

**Der verbleibende Geschwindigkeitsunterschied ist echt, kein Implementierungsfehler
mehr:** monobeam bewertet bei jedem Schritt *alle* bestehenden Container eines
Zustands als Kandidaten, um sie sauber zu ranken (nötig für die Prefix-Konsistenz-
Garantie). Der Ensemble-Ansatz nutzt dagegen First-Fit (das erste Container, das passt,
ohne Ranking) und gleicht das durch mehrere komplette Durchläufe aus. Gründlichere
Bewertung pro Schritt vs. mehr vollständige, aber einfachere Durchläufe - ein echter,
nachvollziehbarer Kompromiss.

**Kein Ansatz dominiert den anderen bei der Lösungsqualität** - für dieses konkrete
Problem (Bin-Packing mit anschließender Hafenwahl) ist keiner der beiden Mechanismen
grundsätzlich überlegen; beide sind mathematisch korrekt monoton, unterscheiden sich
aber in Rechenaufwand und finden je nach Instanz unterschiedlich gute Lösungen.
`monobeam_construction` ist Teil der Codebasis und vollständig getestet
(`test_monobeam_is_monotone_in_beam_width` und weitere), aber bewusst **nicht** in die
Haupt-App integriert - sie dient hier als dokumentierter, funktionierender Vergleich im
Code, nicht als vierte auswählbare Methode in der Oberfläche (die App hat mit drei
Methoden bereits eine sinnvolle Kernaussage, siehe README-Hinweise zur Tourenplanung-
Demo zum Thema "wie viele Methoden verträgt eine Demo").

## Ein Fund beim Bauen des "Teure Seefracht"-Presets

Der erste Entwurf des Presets (Seefracht 2.800 €, Seed 5) sollte den Kipppunkt zeigen,
tat es aber nicht zuverlässig - bei diesem konkreten Seed gewann trotzdem die
hafen-bewusste Methode, obwohl der Hilfetext das Gegenteil versprach. Systematisch nach
einer robusteren Kombination gesucht (verschiedene Seefracht-Stufen × 10 Seeds) und auf
Seefracht 3.000 €, Seed 6 korrigiert (klarer Vorsprung für "Blind gepackt", 2.517 €
Differenz). Regressionstest: `test_teure_seefracht_preset_reliably_flips_winner`.

## 1. Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## 2. Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

67 Tests, laufen automatisch bei jedem Push/PR über GitHub Actions.

## 3. Kostenlos online stellen (Streamlit Community Cloud)

1. Diesen Ordner in ein GitHub-Repository hochladen.
2. Auf [share.streamlit.io](https://share.streamlit.io) anmelden.
3. "New app" → Repository und `app.py` als Hauptdatei → Deploy.

## 4. Bewusst nicht enthalten (Scope-Entscheidung)

- Keine echte 3D-Packung innerhalb des Containers (reines 1D-Volumen/Kapazitäts-
  Bin-Packing - die räumliche Packung selbst zeigt bereits die Packungsoptimierung-Demo)
- Keine echte Straßenroutenplanung ab Hafen (Straßenkosten sind eine Region-Hafen-
  Kostenmatrix, keine tatsächliche Tourenplanung mit mehreren Lieferfahrzeugen)
- Keine Mehrfach-Zielorte je Packstück, keine Liefertermine/Zeitfenster
- Kein dritter Ansatz - zwei Methoden mit demselben Packmechanismus und
  unterschiedlicher Gruppierung reichen, um den Kipppunkt sauber zu isolieren

## 5. Anpassungsideen für später

- Echte Tourenplanung ab Hafen statt einer Kostenmatrix (Wiederverwendung der
  Tourenplanung-Demo-Logik als "letzte Meile" nach der Hafenwahl)
- Gewichtsgrenzen, Gefahrgut-Beschränkungen je Hafen
- Feste Abfahrtstermine je Hafen (Zeitkomponente)
- Test an einem echten Mobilgerät
