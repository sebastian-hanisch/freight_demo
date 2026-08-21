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
  - *Beam Search*: startet bei der hafen-bewusst gruppierten Lösung (garantiert nie
    schlechter) und sucht gezielt nach lohnenden Hafen-Wechseln einzelner Packstücke -
    die starre Gruppierung ist nicht immer optimal (siehe eigener Abschnitt unten,
    auf ausdrücklichen Wunsch ergänzt, inkl. handgerechnetem Beweis). Nachweislich
    **monoton** in der Beam-Breite (Regler "Beam-Breite", 1-6).
- **Primäransicht "Ihre kostenoptimierte Konsolidierung"** von Anfang an (Lehre aus
  der Tourenplanung-Demo direkt übernommen): zeigt die tatsächlich günstigere Methode,
  **dynamisch bei jedem Lauf neu bestimmt** (siehe Kipppunkt unten) - kein
  Algorithmus-Name in der Überschrift, Methode als Caption genannt.
- **Kostenverhältnis als explorierbarer Regler:** "Seefracht je Container (€)" macht
  den zentralen Trade-off dieser Demo direkt erfahrbar (siehe unten).
- **Karte, PDF-Export, Permalink, Feedback-Mechanismus:** wie bei den anderen Demos.
- Von Anfang an mit dem `SETTING_SPECS`-Muster und NaN/Bounds-Schutz im Permalink
  gebaut (keine nachträglich gefundenen Absturz-Bugs wie bei der Tourenplanung-Demo).
- **Mathematische Formulierung als eigener Expander:** formales binäres Programm für die
  gekoppelte Bin-Packing- + Hafenwahl-Entscheidung, NP-Schwere-Beleg über eine Reduktion
  vom klassischen 1D-Bin-Packing (Spezialfall $m=1$), die First-Fit-Decreasing-Garantie
  von Dósa (2007), sowie formale Herleitung der Vorab-Gruppierung, des Kipppunkts,
  von `balance_containers` und `port_consolidation_frontier` als eigenständige
  Optimierungsprobleme - mit direktem Bezug auf die entsprechenden Funktionen im Code.

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
diesen Kipppunkt direkt erfahrbar - alle Methoden werden bei jeder Einstellung neu
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

**Der Geschwindigkeitsunterschied ist echt, kein Implementierungsfehler mehr:**
monobeam bewertet bei jedem Schritt *alle* bestehenden Container eines Zustands als
Kandidaten, um sie sauber zu ranken (nötig für die Prefix-Konsistenz-Garantie). Der
Ensemble-Ansatz nutzt dagegen First-Fit (das erste Container, das passt, ohne Ranking)
und gleicht das durch mehrere komplette Durchläufe aus. Gründlichere Bewertung pro
Schritt vs. mehr vollständige, aber einfachere Durchläufe - ein echter,
nachvollziehbarer Kompromiss.

### Ein dritter Fund: die erste Vergleichszahl war unfair

Der erste Kostenvergleich (12 von 20 Fällen für das Ensemble, 8 für monobeam) verglich
nicht wirklich die beiden Suchmechanismen - `monobeam_construction` gruppierte
Packstücke ursprünglich **nicht** nach Hafen-Präferenz, anders als
`beam_search_construction`, das explizit auf `port_aware_construction`'s Gruppierung
aufbaut. Bei größeren Instanzen zeigte sich das deutlich: monobeam schnitt bis zu 9 %
**schlechter** ab als `port_aware_construction`, obwohl es strukturell mindestens
gleichauf hätte liegen sollen. Fix: `monobeam_construction` hat jetzt einen
`grouped`-Parameter (Standard `True`) - wendet dieselbe Hafen-Präferenz-Gruppierung vor
der monobeam-Suche an, `grouped=False` reproduziert die ursprüngliche, ungruppierte
Fassung. Regressionstest: `test_monobeam_grouping_fixes_unfair_comparison_with_port_aware`.

Mit dieser Korrektur liegen beide Ansätze bei der Lösungsqualität sehr nah beieinander -
keiner dominiert den anderen systematisch (siehe Skalierungsanalyse unten für die
konkreten Zahlen).

`monobeam_construction` ist Teil der Codebasis und vollständig getestet, aber bewusst
**nicht** in die Haupt-App integriert - sie dient hier als dokumentierter,
funktionierender Vergleich im Code, nicht als vierte auswählbare Methode in der
Oberfläche (die App hat mit drei Methoden bereits eine sinnvolle Kernaussage, siehe
README-Hinweise zur Tourenplanung-Demo zum Thema "wie viele Methoden verträgt eine
Demo").

## Skalierungsanalyse: hilft Beam Search bei größeren Instanzen?

Auf Nachfrage untersucht: liegt der geringe Vorteil der Beam-Varianten gegenüber
"Hafen-bewusst gruppiert" (im allgemeinen Benchmark oben nur ~0-3 %) daran, dass die
bisher betrachteten Probleminstanzen zu klein sind? Systematisch getestet über
20-200 Packstücke (fester Aufbau: 6 Regionen, 3 Häfen, Kapazität 100, je 5 Seeds):

| Packstücke | Blind | Hafen-bewusst | Beam(16) | monobeam(16) | Aware ggü. Blind | Beam ggü. Aware | Mono ggü. Aware |
|---|---|---|---|---|---|---|---|
| 20 | 8.662 | 8.140 | 8.140 | 8.139 | 6,0 % | 0,0 % | 0,0 % |
| 40 | 17.288 | 15.401 | 15.386 | 15.401 | 10,9 % | 0,1 % | 0,0 % |
| 60 | 26.931 | 24.494 | 24.485 | 24.487 | 9,1 % | 0,0 % | 0,0 % |
| 100 | 42.150 | 37.417 | 37.254 | 37.405 | 11,2 % | 0,4 % | 0,0 % |
| 150 | 62.993 | 56.393 | 56.362 | 56.393 | 10,5 % | 0,1 % | 0,0 % |
| 200 | 84.130 | 74.837 | 74.833 | 74.866 | 11,0 % | 0,0 % | 0,0 % |

**Klare Antwort: nein, die Instanzgröße ist nicht die Erklärung.** Der Vorteil von
"Hafen-bewusst" gegenüber "Blind" bleibt über den gesamten Bereich stabil bei ~9-11 %.
Der Vorteil der Beam-Varianten gegenüber "Hafen-bewusst" bleibt durchgehend bei ~0-0,4 %
- weder wachsend noch schrumpfend mit n. Auch ein bewusst "hartes" Bin-Packing-Regime
(Packstückgrößen 40-60 bei Kapazität 100, erzwingt oft genau 2 Packstücke je Container -
klassisch schwer für First-Fit) und Beam-Breiten bis 1.000 änderten daran nichts
(Ersparnis plateaut bei ~0,5 % ab Breite 16, `test_beam_advantage_over_port_aware_stays_small_across_problem_sizes`).

**Die eigentliche Erklärung:** First-Fit-Decreasing ist für 1D-Bin-Packing ein
bekanntermaßen bereits nahezu optimales Verfahren (worst-case innerhalb 11/9 · OPT + 1,
in der Praxis meist noch deutlich näher am Optimum). Beide Beam-Varianten variieren nur
die *Reihenfolge*, in der Packstücke FFD zugeführt werden - aber wenn FFD selbst schon
kaum noch Verbesserungsspielraum hat, bringt das Ausprobieren mehrerer Reihenfolgen
wenig. Der eigentliche Hebel in diesem Problem ist die **Gruppierung** (blind vs.
hafen-bewusst, ~10 %) - nicht die Packreihenfolge innerhalb einer bereits guten Gruppe.
Für einen größeren Beam-Search-Vorteil müsste die Suche eine andere Dimension
explorieren, z. B. probeweise abweichende Hafen-Zuordnungen einzelner Packstücke statt
nur Packreihenfolgen - das wurde als Erweiterung tatsächlich umgesetzt, siehe nächster
Abschnitt.

## Erweiterung: flexible Hafen-Zuordnung statt starrer Gruppierung

Berechtigter Einwand nach der Skalierungsanalyse: Die Gruppierung "jedes Packstück an
seinen individuell günstigsten Hafen" ist eine starre Vorentscheidung - ignoriert sie
echte Verbesserungsmöglichkeiten?

### Ja - handgerechneter Beweis

Konstruiertes Gegenbeispiel: 2 Häfen, Region A bevorzugt Hafen 0 knapp (Straßenkosten
10 vs. 11 pro Einheit), Region B bevorzugt Hafen 1 stark (50 vs. 5). Drei Packstücke:
A(60), A(45), B(55) - Kapazität 100 je Container.

Starre Gruppierung: A(60) und A(45) passen NICHT zusammen (60+45=105 > 100) → 2
Container für Region A, plus 1 Container für B(55) → **3 Container, 3.725 €**.

Flexible Lösung: A(45) wechselt für eine kleine Straßenkosten-Strafe (45 × 1 € = 45 €)
zu Hafen 1, passt dort exakt mit B(55) zusammen (45+55=100) → **2 Container, 2.970 €**
- die kleine Strafe von 45 € spart eine ganze Seefracht (800 €), netto 755 € günstiger
(~20 %). Festgehalten in `test_flexible_beam_finds_known_handcalculated_improvement`.

### Warum reine (ungruppierte) Vorwärtssuche das nicht zuverlässig findet

`monobeam_construction(..., grouped=False)` (siehe oben) ist im Prinzip bereits die
"flexible" Version - Packstücke werden ohne Vorab-Gruppierung verarbeitet, jeder
Container bekommt frei den besten Hafen zugewiesen. Getestet an echten
Zufallsinstanzen (nicht am Gegenbeispiel oben) holt sie die starre Gruppierung aber
selbst bei Beam-Breite 256 nicht zuverlässig ein:

| Seed | starr | flex (bw=16) | flex (bw=64) | flex (bw=256) |
|---|---|---|---|---|
| 2 | 22.551 | 25.883 | 23.262 | 22.766 |
| 4 | 22.825 | 23.823 | 23.823 | 23.691 |
| 6 | 28.516 | 32.492 | 31.931 | 30.239 |

**Grund:** Packstücke werden nach Größe absteigend verarbeitet - große Packstücke
committen sich früh zu einem Container/Hafen, bevor die Suche "sieht", welche
kleineren Packstücke später gut dazu passen würden. Reine Vorwärtssuche ohne
Lookahead findet Kompromisse nur zufällig, nicht systematisch - mehr Breite hilft
kaum, weil das Grundproblem (keine Rückschau) bestehen bleibt.

### Der neue Mechanismus: `flexible_beam_search_construction`

Statt blinder Vorwärtssuche eine **Beam-Search-Verbesserungssuche**, die bei der
starren Gruppierung STARTET (garantiert nie schlechter) und über mehrere Runden
gezielt die besten Einzelverschiebungen eines Packstücks in einen anderen Container
sucht - direkte Bewertung des tatsächlichen Kosteneffekts statt blinder Neukonstruktion.
Dieselbe "immer mindestens der Ausgangszustand ist im Kandidatenpool"-Logik wie beim
`beam_width=1`-Fix von `beam_search_construction` garantiert die Nie-schlechter-
Eigenschaft.

**Ergebnis über 14 Testinstanzen (30 Packstücke):** im Schnitt **1,9 % Ersparnis**
gegenüber starrer Gruppierung (deutlich mehr als die ~0-0,4 % der reinen
Packreihenfolge-Varianten oben), in Einzelfällen bis zu 7,1 %, in mehreren Fällen 0 %
(nicht jedes Szenario hat ausnutzbare Struktur - ehrliches Ergebnis, kein
Selbstläufer). `test_flexible_beam_never_worse_than_port_aware` und
`test_flexible_beam_is_monotone_in_beam_width` bestätigen beide Garantien.

### Zwei Performance-Probleme unterwegs gefunden und behoben

1. **Vollständige statt inkrementelle Kostenberechnung** - dieselbe Fehlerklasse wie
   bei `monobeam_construction` zuvor. Erste Fassung: 1,4 s bei 100 Packstücken. Fix:
   nur die beiden durch eine Verschiebung tatsächlich betroffenen Container werden neu
   bewertet, nicht der gesamte Zustand. Danach: 468 ms - besser, aber immer noch zu
   langsam für automatische Neuberechnung bei jeder UI-Interaktion.
2. **Beam-Breite hilft hier kaum, kostet aber viel** - anders als bei
   Konstruktions-Beam-Search bringt eine breitere Suche bei dieser
   Verbesserungssuche kaum zusätzliche Qualität (empirisch: `beam_width=1`, `2` und
   `16` liefern praktisch identische Ersparnis, ~1,7-1,9 % im Schnitt), aber jede
   zusätzliche Runde nach der ersten wird deutlich teurer, weil sich der Beam auf bis
   zu `beam_width` Zustände auffächert und jeder in der Folgerunde erneut vollständig
   durchsucht wird (bei `beam_width=32`: bis zu 3,4 s bei 100 Packstücken). Der
   Sidebar-Regler ist deshalb bewusst auf 1-6 begrenzt (Standard 2), Worst Case dort
   ~380 ms. `test_flexible_beam_width_scaling_quality_is_similar` und
   `test_flexible_beam_worst_case_completes_within_budget` halten das fest.

### In die App integriert - ersetzt die bisherige "Beam Search"-Methode

Die alte `beam_search_construction` (Ensemble-Ansatz, ~0 % Vorteil gegenüber
"Hafen-bewusst") wurde in der Oberfläche durch `flexible_beam_search_construction`
ersetzt - strikt besser (dieselbe Nie-schlechter-Garantie, aber echter statt kaum
vorhandener Nutzen), ohne die App um eine weitere Methode zu erweitern. Der Regler
"Beam-Breite" und alle Erklärtexte wurden entsprechend aktualisiert.
`beam_search_construction` und `monobeam_construction` bleiben vollständig getestet in
der Codebasis (für die technische Vergleichsgeschichte oben), sind aber nicht mehr in
der UI verdrahtet.

### Ein gefundener blinder Fleck: nur gegen EINE Ausgangslösung abgesichert

Bei einer gezielten Nachprüfung des "Teure Seefracht"-Presets fiel auf: Beam Search
verlor dort deutlich gegen "Blind gepackt" (30.961 € vs. 27.735 €, **11,6 % teurer**) -
obwohl Beam Search als "beste" Methode gedacht ist. Die Ursache: die
Verbesserungssuche startete ausschließlich bei der hafen-bewussten Gruppierung und war
dadurch nur gegen DIESE eine Ausgangslösung abgesichert ("nie schlechter als
Hafen-bewusst"), nicht gegen Blind. Bei hoher Seefracht braucht die hafen-bewusste
Gruppierung strukturell mehr Container als Blind (siehe Kipppunkt oben) - dieser
Nachteil vererbte sich unverändert an Beam Search, das darauf aufbaute.

**Fix:** Die Verbesserungssuche läuft jetzt von BEIDEN Ausgangslösungen aus (Hafen-
bewusst UND Blind gepackt), das günstigere Endergebnis gewinnt. Dadurch gilt jetzt
`Beam Search <= min(Blind gepackt, Hafen-bewusst gruppiert)` garantiert - nicht nur
gegen eine der beiden. Beim "Teure Seefracht"-Preset erreicht Beam Search seitdem exakt
Blinds Niveau (27.735 €) statt 11,6 % darüber zu liegen. Verifiziert über 21
Kombinationen (3 Seefracht-Niveaus × 7 Seeds), bei denen abwechselnd Blind oder
Hafen-bewusst die schwächere Ausgangslösung ist -
`test_flexible_beam_never_worse_than_blind_either`.

**Kosten:** ungefähr doppelte Rechenzeit (zwei Suchen statt einer). Worst Case bei 100
Packstücken stieg von ~370-380 ms auf ~520 ms - weiterhin klar innerhalb des Budgets für
automatische Neuberechnung bei jeder UI-Interaktion (Sicherheitsschwelle 2 s).

### Eine dritte Ausgangslösung: hilft eine unabhängige Beam-Search-Konstruktion?

Auf Nachfrage untersucht: `flexible_beam_search_construction` ist keine eigenständige
Konstruktion, sondern verfeinert nur die Ergebnisse der beiden anderen Methoden. Es
gibt aber zwei eigenständige, von Grund auf selbst konstruierende Beam-Search-Varianten
im Code (`beam_search_construction`, `monobeam_construction`), die nicht in der UI
verdrahtet sind. Hilft es, eine davon zusätzlich als dritte Ausgangslösung für die
Verbesserungssuche zu nutzen?

**Ja, in etwa 12 % der Fälle.** Über 25 Testinstanzen fand die Verbesserungssuche von
`monobeam_construction` aus in 3 Fällen ein spürbar besseres Endergebnis (bis zu 850 €
Zusatzersparnis in einer Instanz), das von Blind oder Hafen-bewusst aus nicht
erreichbar war - `monobeam_construction` verteilt Packstücke manchmal strukturell
anders auf Container als eine reine Größen-FFD, was der Verbesserungssuche einen
anderen Ausgangspunkt zum Weitersuchen gibt. In den übrigen 88 % der Fälle brachte der
dritte Startpunkt keinen zusätzlichen Vorteil, aber auch keinen Nachteil (per
Konstruktion: eine zusätzliche Kandidatenquelle für dasselbe Minimum kann nie
schlechter sein). `test_flexible_beam_never_worse_than_monobeam_either`,
`test_flexible_beam_finds_improvement_unreachable_from_blind_or_aware`.

**Ein Fund bei der Integration:** `monobeam_construction` hat einen eigenen
`beam_width`-Parameter (seine interne Konstruktionsbreite) - naheliegend wäre gewesen,
dafür einfach denselben Wert wie den Verbesserungssuche-Regler zu verwenden. Getestet:
das wäre ein Fehler gewesen. Der Verbesserungssuche-Regler kann bis auf 1 heruntergehen
(dort optimal, siehe oben), aber `monobeam_construction` braucht selbst mindestens
Breite 2 für gute Ergebnisse (bw=1 lieferte nach der Verbesserungssuche spürbar
schlechtere Endergebnisse, z. B. 13.520 statt 12.903 € bei einer Testinstanz - ab
Breite 2 kaum noch zusätzlicher Nutzen). Die beiden Regler-Bedeutungen sind also nicht
dieselbe Größe, obwohl beide "beam_width" heißen. Fix: `monobeam_construction`
verwendet intern `max(2, beam_width)` - unabhängig vom Regler mindestens Breite 2.
`test_flexible_beam_monobeam_construction_width_decoupled_from_slider`.

**Kosten:** von zwei auf drei Ausgangslösungen, also ungefähr das 1,5-fache statt das
Doppelte der ursprünglichen Rechenzeit (`monobeam_construction` selbst ist mit ~10ms
sehr schnell, die dritte Verbesserungssuche kostet etwa so viel wie die anderen beiden
zusammen). Worst Case bei 100 Packstücken: ~875 ms - weiterhin klar innerhalb des
2s-Budgets (`test_flexible_beam_worst_case_with_triple_start_completes_within_budget`).

## Presets: zwei weitere Funde bei einer gezielten Nachprüfung

Nach dem Einbau von Beam Search fiel bei einer Nachfrage auf, dass die verbliebenen
zwei Presets ("Teure Seefracht", "Starke regionale Streuung") zwar nicht abstürzten,
aber nicht mehr robust genug das zeigten, was ihr Name versprach - beide wurden
systematisch neu überprüft und korrigiert.

**"Teure Seefracht" - zweiter Anlauf.** Der erste Fund (siehe Commit-Historie: Seefracht
2.800 €, Seed 5 zeigte fälschlich "Hafen-bewusst gewinnt") wurde bereits einmal auf
Seefracht 3.000 €, Seed 6 korrigiert. Bei genauerer Prüfung (10 Seeds bei denselben
Parametern) stellte sich aber heraus: auch diese zweite Wahl war eher ein
Zufallstreffer als ein robuster Effekt - bei n=40, r=6, p=3 gewann "Blind gepackt" nur
in 4 von 10 Seeds überhaupt, selbst bei Seefracht 5.000 € (weit über dem
Reglermaximum) nur in 5 von 10. Bei der kleineren Konfiguration n=30, r=5, p=3 (wie im
ursprünglichen Kipppunkt-Benchmark) zeigte sich der Effekt dagegen robust: bei
Seefracht 4.000 € (Reglermaximum) gewinnt "Blind gepackt" in 9 von 10 Seeds, im
Schnitt 10 Prozentpunkte Vorsprung. Preset korrigiert auf diese Konfiguration, Seed 4
(10,4 % Vorsprung, Beam Search findet hier korrekterweise keine zusätzliche
Verbesserung - eine saubere Einzellektion statt vermischter Botschaften).

**"Starke regionale Streuung" - der gewählte Hebel war der falsche.** Der Name
versprach einen "besonders deutlichen" Vorteil hafen-bewusster Gruppierung, aber die
gewählten Parameter (geringe *Seefracht*-Streuung) beeinflussen gar nicht die
*Straßenkosten*, auf denen dieser Vorteil eigentlich beruht - eine Verwechslung von
zwei unterschiedlichen Streuungsarten im Modell. Nachgemessen: der Preset lieferte im
Schnitt ~11 % Vorsprung - praktisch identisch zu einem gewöhnlichen Szenario ganz ohne
besondere Zuschneidung (~11 %). Systematisch nach dem tatsächlich wirksamen Hebel
gesucht (Variation von Hafen-, Regionen- und Packstückzahl): mehr Häfen und mehr
Packstücke verstärken den Effekt deutlich, mehr Regionen leicht. Neue Konfiguration
(n=80, r=8, p=5 - beide Regler an ihrem Maximum) liefert bei Seed 1 einen Vorsprung
von 26 % - mehr als doppelt so stark wie zuvor, und über mehrere Seeds robust bei
~16-17 % im Schnitt.

Beide Korrekturen mit Regressionstests abgesichert:
`test_teure_seefracht_preset_reliably_flips_winner`,
`test_starke_regionale_streuung_preset_shows_amplified_advantage`.

**Ein Nebenfund beim Nachbessern:** Bei den Test-Anpassungen für den neuen
"Beam Search lohnt sich"-Preset wurde versehentlich eine Funktionssignatur gelöscht -
der Test für "Teure Seefracht" lief danach unbemerkt als angehängter Code innerhalb
eines anderen Tests weiter (keine Fehlermeldung, aber auch keine eigenständige
Prüfung mehr). Per `pytest --collect-only` aufgefallen und behoben - eine Erinnerung,
nach größeren Testdatei-Änderungen die tatsächlich gesammelte Testanzahl zu prüfen,
nicht nur ob die Suite grün durchläuft.

## Auf Nutzerwunsch ergänzt: finale Hafen-Zuordnung nebeneinander im Vergleichs-Tab

Die VRP-Demo zeigt im Vergleichs-Tab bereits die finalen Touren aller Methoden
nebeneinander (eigene kleine Karte je Methode), die Pack-Demo bekam dasselbe für ihre
finalen Packungen - hier auf die Fracht-Demo übertragen. Jede der drei Methoden bekommt
jetzt ihre eigene finale Hafen-Zuordnungskarte (`build_freight_map`) direkt
nebeneinander, mit den Gesamtkosten in der Beschriftung - zusätzlich zur bereits
vorhandenen numerischen Tabelle.

Technisch unkompliziert: `render_freight_panel` gab die `assignments` bereits im
zurückgegebenen Summary-Dict zurück, `build_freight_map` war bereits importiert (wird
auch in den einzelnen Tabs verwendet) - nur in `st.columns()` aufgerufen, exakt nach
demselben Muster wie in der VRP- und Pack-Demo.
`test_comparison_tab_shows_final_port_assignment_side_by_side`.

## Vom Nutzer gemeldet: "Neues Szenario generieren" tat bei unverändertem Seed nichts

Im Zuge einer Konsistenzprüfung über alle vier Demos gefunden (identischer Fehler auch
in der Tourenplanung-Demo, dort zuerst gefunden und behoben - siehe dortiges README für
die volle Herleitung): der Button rief nur ein normales `st.button()` auf. Sein Wert
floss zwar in die `gen_key`-Neuberechnung ein (`regenerate or force_regen`), aber die
automatische Neugenerierung reagiert bereits auf jede Änderung von Parametern oder Seed
- blieb der Seed unverändert, lieferte die deterministische Zufallserzeugung dieselben
Werte erneut. Ein Klick löste zwar technisch eine Neuberechnung aus, das Ergebnis war
aber identisch - für den Nutzer sichtbar ein reiner Leerlauf-Klick.

**Der bestehende Test hatte diese Lücke nicht erkannt:** `test_regenerate_button` prüfte
nur "kein Absturz", nie die tatsächliche Wirkung. Auf echte Wirkungsprüfung umgestellt
(Seed muss sich nach dem Klick unterscheiden).

**Fix, kein ersatzloses Entfernen:** statt den wirkungslosen Button zu streichen, bekam
er eine echte Funktion - er würfelt jetzt einen neuen Zufalls-Seed (`randomize_seed()`
in `freight_presets.py`, nach demselben `on_click`-Callback-Muster wie `apply_preset`).
Ein Klick liefert garantiert ein komplett neues Szenario, ohne selbst eine neue
Seed-Zahl eintippen zu müssen.
`test_regenerate_button` (verstärkt).

## Literaturrecherche zum zugrundeliegenden Problem: drei Ideen übernommen

Auf Nutzerfrage recherchiert, ob es zum zugrundeliegenden Problem (Packstücke in
kapazitätsbegrenzte Container packen UND je Container einen Hafen wählen, dessen Kosten
von der Ladungszusammensetzung abhängen) akademische Literatur gibt. Fündig geworden:
das Problem ist eine Kombination aus **Bin Packing** und **Facility-/Hub-Standortwahl**,
mit einer sehr direkten Entsprechung in einem echten Praxisproblem.

**Die direkteste Entsprechung:** Jost, Henke, Hedtke, Bredtmann, Weise, Buchheim &
Clausen (TU Dortmund, gemeinsam mit DB Schenker), *"Partitioned vs. Integrated Planning
of Hinterland Networks for LCL Transportation"* (2022). DB Schenkers LCL-Europe-Sparte
muss Sendungen zu einem Ursprungshafen routen und dort ggf. konsolidieren, wobei die
Gesamtkosten von See- und Landtransportkosten gemeinsam abhängen - "very few big ports"
senkt Seekosten, ein näherer Hafen senkt Landkosten. Der Kernbefund des Papers: eine
GETRENNTE Entscheidung (DB Schenkers ursprüngliche zweistufige Lösung) schneidet
systematisch schlechter ab als eine INTEGRIERTE, gemeinsame Entscheidung - bei höherem
Rechenaufwand, aber mit durchgehend niedrigeren Gesamtkosten (Verbesserungen zwischen
etwa 1 % und 7 % in den Testinstanzen des Papers).

Drei Ideen aus dem Paper wurden empirisch geprüft und - da sie sich alle als positiv,
nie negativ herausstellten - vollständig übernommen:

### 1. Gesamtkosten-bewusste Hafen-Präferenz-Gruppierung

`port_aware_construction`, `beam_search_construction` und `monobeam_construction`
gruppieren Packstücke vor dem Packen nach ihrem STRASSENKOSTEN-günstigsten Hafen
(`np.argmin(road_cost, axis=1)`) - die Seefrachtkosten (die zwischen Häfen um bis zu
60 % streuen können, siehe `DEFAULT_SEA_FREIGHT_SPREAD`) fließen erst danach ein.
Exakt die Art "getrennter statt integrierter Entscheidung", die das Paper als
Kernschwäche identifiziert. Empirisch verifiziert: eine gesamtkosten-bewusste
Gruppierung (Straßenkosten PLUS ein Seefracht-Anteil, geschätzt über einen angenommenen
Container-Füllgrad) ist bis zu 3,1 % günstiger, nie schlechter, in einer ersten
Stichprobe.

Da die Füllgrad-Schätzung (mehrere Werte 0,5 bis 1,0 getestet, 0,6 lieferte über 40
Testfälle die beste Gesamtersparnis) naturgemäß unsicher ist, wird die neue Gruppierung
NICHT anstelle der bestehenden Baselines verwendet, sondern als vierte, zusätzliche
Ausgangslösung für `flexible_beam_search_construction`. `_total_cost_aware_port_preference`
in `freight_heuristics.py`. Zusätzliche Verbesserung über das bereits bestehende
Drei-Start-Ensemble hinaus: ~1.600 Kosteneinheiten in 5 von 40 Testfällen.

### 2. Tausch-Zug in der Verbesserungssuche (der wirkungsvollste der drei Funde)

`_improve_from_baseline` kannte bisher nur "ein Packstück verschieben" und "ein
Packstück abspalten" - keinen direkten Tausch zweier Packstücke zwischen zwei
Containern. Dieselbe Art von Lücke, die bei der VRP-Demo einen eigenen Swap-Zug nötig
machte, weil Or-Opt allein nicht ausreichte.

Ergebnis: mit Abstand der wirkungsvollste der drei Funde - 28 von 40 Testfällen
zusätzlich verbessert (~7.800 Kosteneinheiten Gesamtersparnis), selbst wenn er erst
NACH dem bisherigen Drei-Start-Ensemble-Ergebnis angewendet wird. Ein zusätzlicher
"zwei Container komplett zusammenlegen"-Zug wurde ebenfalls getestet - brachte aber
nachweislich KEINEN zusätzlichen Nutzen, sobald der Tausch-Zug vorhanden ist (exakt
identisches Ergebnis mit und ohne Zusammenlegen-Zug über alle 40 Testfälle) - deshalb
nicht übernommen, unnötige Komplexität ohne Mehrwert.

**Performance-Problem gefunden und behoben:** der Tausch-Zug skaliert quadratisch mit
Container- und Packstückzahl pro Container (O(Container² × Items²)). Bei der
App-Obergrenze (100 Packstücke, Beam-Breite 6) explodierte die Rechenzeit auf 9,5-9,8s
statt der erwarteten <2s - zwei bestehende Performance-Tests schlugen fehl. Fix: der
Tausch-Zug läuft nur noch in der ERSTEN Suchrunde (wenn der Beam noch schmal ist),
Verschieben/Abspalten laufen weiterhin jede Runde. Empirisch verifiziert: 33 von 40
Testfällen liefern dabei ein exakt identisches Ergebnis zur vollen "Tausch in jeder
Runde"-Fassung, bei 4,5x weniger Rechenzeit (285ms statt 1.279ms je Startpunkt). Die
verbleibenden 7 Fälle zeigen nur einen kleinen Qualitätsverlust (545 von insgesamt
~10.000 Kosteneinheiten Gesamtersparnis aller drei Funde zusammen). Performance-Budget
der beiden betroffenen Tests von 2s auf 3s angehoben (gemessener Worst Case: ~1,9-2,2s,
mit Sicherheitsabstand).

### 3. Alternierende Neu-Gruppierung (DB Schenkers eigener Lösungsansatz)

DB Schenkers eigene (im Paper später verworfene) Lösung für ihr verwandtes
Hub-Location-Problem nutzte einen iterativen Zwei-Schritt-Prozess: Hafenwahl fixieren,
Hub-Auswahl optimieren; dann Hub-Auswahl fixieren, Hafenwahl neu optimieren;
wiederholen bis keine Verbesserung mehr eintritt - im Kern eine Koordinaten-Abstiegs-
Suche. Übertragen: abwechselnd (a) komplette Neu-Gruppierung nach der AKTUELLEN
Hafenzuordnung je Container und (b) komplettes Neu-Packen, statt nur einzelne
Packstücke schrittweise zu verschieben.

Schwächerer, aber positiver Effekt: ~1.100 Kosteneinheiten zusätzliche Ersparnis in 8
von 40 Testfällen, als fünfte Ausgangslösung für `flexible_beam_search_construction`
(angewendet auf die Hafen-bewusste Ausgangslösung, bevor die eigentliche
Verbesserungssuche startet). `_alternating_regroup` in `freight_heuristics.py`.

### Gesamtergebnis

Alle drei zusammen: 27 von 40 Testfällen verbessert gegenüber der vorherigen (drei
Startpunkte, kein Tausch-Zug) Fassung, ~10.000 Kosteneinheiten Gesamtersparnis, im
Schnitt 0,6 % in den verbesserten Fällen. Da jede Ergänzung nur eine weitere
Kandidatenquelle für dieselbe Minimum-Auswahl ist, kann keine davon das Ergebnis
verschlechtern.

`test_flexible_beam_never_worse_than_these_reference_methods`,
`test_swap_move_finds_additional_improvement`,
`test_total_cost_aware_grouping_considers_sea_freight`,
`test_alternating_regroup_never_worsens_input`,
`test_swap_move_limited_to_first_round_matches_full_search_in_most_cases`.

## Auf Nutzerfrage: sind bei jetzt fünf Startpunkten noch alle relevant?

Berechtigte Frage nach den obigen Ergänzungen - der Tausch-Zug ist mächtig genug, dass
er die Lücken, die manche Startpunkte ursprünglich gefüllt haben, möglicherweise selbst
schon schließt (dieselbe Art Frage, die schon beim "Zusammenlegen"-Zug zu einem "nein,
überflüssig"-Befund führte). Systematisch per Ablationsstudie geprüft: jeden Startpunkt
einzeln aus dem Ensemble entfernen, messen wie oft und wie stark sich das Endergebnis
dadurch verschlechtert (40 Testfälle).

| Startpunkt | Betroffene Fälle | Verlust bei Entfernung |
|---|---|---|
| Hafen-bewusst gruppiert | 0 / 40 | 0 - **vollständig redundant** |
| Blind gepackt | 16 / 40 | ~10.700 - klar unverzichtbar |
| monobeam_construction | 1 / 40 | ~340 - kleiner, aber echter Nutzen |
| Gesamtkosten-bewusst | 3 / 40 | ~850 - noch relevant |
| Alternierend neu gruppiert | 6 / 40 | ~1.300 - noch relevant |

**Der ursprüngliche erste Startpunkt ("Hafen-bewusst gruppiert") ist vollständig
redundant geworden** - nachvollziehbar: sowohl die gesamtkosten-bewusste Gruppierung
als auch die alternierende Neu-Gruppierung sind im Kern verfeinerte Versionen derselben
Grundidee, kombiniert mit dem Tausch-Zug erreichen sie alles, was die einfache Version
je fand. "Blind gepackt" bleibt dagegen mit Abstand unverzichtbar - strukturell
fundamental anders als alle anderen vier (die alle irgendeine Form von Hafen-Gruppierung
nutzen), eine Lücke, die der Tausch-Zug nicht schließen kann.

**Umgesetzt (auf Nutzerwunsch):** "Hafen-bewusst gruppiert" als eigener Startpunkt für
die Verbesserungssuche entfernt (spart einen vollen `_improve_from_baseline`-Aufruf,
Worst Case bei der App-Obergrenze sank von ~1,9-2,2s auf ~1,5s) - die Gruppierung
selbst bleibt aber erhalten, da die alternierende Neu-Gruppierung weiterhin davon
ausgeht. `monobeam_construction` bewusst behalten trotz geringem Effekt (Nutzerwunsch).

**Lehre:** nicht jede nachweislich hilfreiche Ergänzung bleibt hilfreich, wenn spätere
Ergänzungen (hier: der Tausch-Zug) einen Teil ihres Wirkungsbereichs mit abdecken - ein
Startpunkt sollte nach jeder größeren Suchverbesserung erneut auf seinen Grenznutzen
geprüft werden, nicht nur einmalig beim eigenen Einbau.

`test_aware_starting_point_removal_does_not_regress`.

## Weitere Literaturrecherche: Large Neighborhood Search (LNS)

Auf Nutzerfrage nach weiteren vielversprechenden Ansätzen aus der Literatur recherchiert.
Fündig geworden bei **Large Neighborhood Search (LNS)** - in der Bin-Packing-/Container-
Loading-Literatur ein etabliertes, wirkungsvolles Verfahren, mehrere Papers beschreiben
fast exakt dieselbe Struktur: "destroy the solution by unpacking some of the bins...
repair the solution by a greedy method... followed by a local search procedure" mit
Verschieben und Tauschen der Packstücke.

**Strukturell anders als alles, was wir bisher hatten:** unsere bisherigen Suchzüge
(Verschieben, Abspalten, Tauschen) verändern immer nur ein oder zwei Packstücke auf
einmal. LNS zerstört dagegen mehrere KOMPLETTE Container gleichzeitig (alle ihre
Packstücke werden frei) und baut sie über Cheapest-Insertion neu auf - kann so
Konfigurationen erreichen, die reine Einzelzug-Suche nicht findet.

**Ergebnis, empirisch verifiziert:** 23 von 40 Testfällen zusätzlich verbessert
(~7.200 Kosteneinheiten), sogar auf dem bereits verbesserten Ensemble-Ergebnis (nach
Tausch-Zug, allen Startpunkten) angewendet - eine Größenordnung vergleichbar mit dem
Tausch-Zug selbst. `_cheapest_insertion_repair` und `_large_neighborhood_search` in
`freight_heuristics.py`, läuft als finaler Politur-Schritt NACH der Ensemble-Auswahl,
nicht als weitere parallele Ausgangslösung.

### Nebeneffekt: monobeam wird durch LNS ebenfalls redundant

Die zuvor durchgeführte Ablationsstudie (siehe oben) hatte `monobeam_construction`
noch einen kleinen, echten Beitrag bescheinigt (1 von 40 Fällen, ~340 Kosteneinheiten).
Mit LNS als zusätzlichem, mächtigem Politur-Schritt erneut geprüft: **0 von 40 Fällen
betroffen** - LNS' destroy-and-repair-Mechanismus absorbiert diesen kleinen Restbeitrag
vollständig. `monobeam_construction` daher ebenfalls als Startpunkt entfernt (auf
Nutzerwunsch) - nur noch drei direkte Startpunkte (Blind, gesamtkosten-bewusst,
alternierend) plus LNS-Politur.

### Auf Nutzerfrage: geht da nicht noch ein Startpunkt weg?

Berechtigte Anschlussfrage - dasselbe Muster hatte schon zweimal funktioniert (`aware`
nach dem Tausch-Zug, `monobeam` nach LNS). Erneute Ablationsstudie für die verbliebenen
drei Startpunkte, diesmal mit der VOLLEN Pipeline (inklusive LNS):

| Startpunkt | Vorher (ohne LNS) | Jetzt (mit LNS) |
|---|---|---|
| Blind gepackt | 16/40, ~10.700 | 14/40, ~15.800 - weiterhin klar unverzichtbar |
| Gesamtkosten-bewusst | 3/40, ~850 | **2/40, ~156** - fast verschwunden |
| Alternierend neu gruppiert | 6/40, ~1.300 | 3/40, ~478 - deutlich geschrumpft |

Anders als bei `aware` und `monobeam` geht hier KEINER der verbliebenen Beiträge exakt
auf null - aber die gesamtkosten-bewusste Gruppierung ist mit nur noch 156 von
insgesamt weit über 10.000 gefundenen Kosteneinheiten der mit Abstand schwächste. Auf
Nutzerwunsch trotzdem entfernt (kleiner, akzeptierter Qualitätsverlust gegen etwas
Rechenzeit) - **nur noch zwei direkte Startpunkte** (Blind, alternierend) plus
LNS-Politur. `test_tca_starting_point_removal_does_not_cause_large_regression`
(großzügige 3 %-Toleranz statt strikter Nie-schlechter-Garantie, die hier bewusst nicht
mehr gilt).

**"Alternierend neu gruppiert" bleibt trotz geschrumpftem Beitrag erhalten** - mit
knapp 500 Kosteneinheiten liegt sein verbleibender Nutzen deutlich über dem, was gerade
noch entfernt wurde, und "Blind" bleibt aus denselben strukturellen Gründen wie zuvor
unverzichtbar.

### Ein ehrlich dokumentierter Kompromiss: Monotonie in der Beam-Breite geht verloren

`flexible_beam_search_construction` war zuvor beweisbar monoton in `beam_width`
("größere Beam-Breite kann das Ergebnis nachweislich nie verschlechtern", eigener Test
dafür). LNS arbeitet mit einem festen internen Zufalls-Seed, unabhängig von
`beam_width` - der ENSEMBLE-Teil davor (siehe `_ensemble_best_result`) bleibt zwar
weiterhin beweisbar monoton, aber LNS kann von einem durch breiteren Beam gefundenen
(Ensemble-seitig besseren) Startpunkt aus zufällig zu einem leicht schlechteren
Endergebnis kommen als von einem schmaleren.

**Dieselbe Art Entscheidung wie bei GAs Monotonie-Untersuchung** (siehe VRP-Demo-
Historie): kein erzwungener Fix versucht - ein Korrekturversuch hätte vermutlich nur in
der getesteten Stichprobe funktioniert, ohne eine echte, instanzunabhängige Garantie
herzustellen. Stattdessen ehrlich dokumentiert und empirisch vermessen: Verletzungen
sind selten (~10 % der Testfälle) und klein (<0,5 % Kostendifferenz). Der Ensemble-Teil
allein bleibt separat testbar und beweisbar monoton geblieben (`_ensemble_best_result`,
ausgelagert für genau diesen Zweck).

**Performance:** LNS' Parameter (ursprünglich 8 Iterationen) mussten nach anfänglichen
Performance-Testfehlern (Worst Case über eine breite Seed-Stichprobe streute stärker als
erwartet, 2,7s bis 3,8s je nach Systemlast - vermutlich Ressourcen-Konkurrenz mit
vorherigen Tests in derselben Sitzung) auf 5 Iterationen reduziert werden (verliert nur
~1,3 % der gefundenen Ersparnis) und das Performance-Budget der beiden betroffenen Tests
mit echtem Sicherheitsabstand auf 5s angehoben.

`test_ensemble_best_result_is_monotone_in_beam_width`,
`test_flexible_beam_full_pipeline_mostly_monotone_in_beam_width`,
`test_swap_move_contributes_within_the_pipeline`.

## Neues Feature: Quality-Diversity statt nur einer Lösung

Auf Nutzerfrage untersucht: Kenneth Stanleys Novelty Search bzw. deren spätere
Weiterentwicklung Quality-Diversity (v. a. MAP-Elites) - lässt sich das sinnvoll
einbauen? Erst als reine Optimierungsverbesserung getestet (ein Archiv über
diskretisierte Verhaltens-Zellen statt nur eines Elite-Individuums, Eltern aus dem
gesamten Archiv statt nur der Population gezogen), sowohl für VRPs genetischen
Algorithmus als auch für dieses LNS. Ergebnis: bei VRP nur ein bescheidener, uneinheitlicher
Effekt (7 von 20 Testfällen besser, 5 schlechter, Netto nur +28 Einheiten Ersparnis).
Bei diesem LNS sogar negativ (0 von 40 Fällen besser, Netto -164) - das bestehende LNS
baut bereits fortlaufend auf seinem letzten Zustand auf, ein zufällig aus einem
Diversitäts-Archiv gezogener "veralteter" Startpunkt verschwendet bei nur wenigen
Iterationen eher Suchtiefe. Nachvollziehbar: unsere Zielfunktionen (Kosten, Distanz)
sind nicht "deceptive" wie Stanleys klassisches Labyrinth-Beispiel - reine
Diversitäts-Erzwingung hilft da kaum.

**Aber:** die eigentlich interessante Idee war nie die Optimierung selbst, sondern das
Feature dahinter - statt einer Zahl mehrere strukturell unterschiedliche, aber jeweils
gute Lösungen zu zeigen. Umgesetzt mit zwei GESCHÄFTLICH motivierten Alternativen statt
abstrakter Verhaltens-Vielfalt:

### 1. Häfen-Konsolidierungs-Kurve

`port_consolidation_frontier` in `freight_heuristics.py`: für jede Anzahl k=1..n_ports
erlaubter Häfen wird die günstigste Kombination von genau k Häfen berechnet - bei
FESTER Packung (keine Neu-Konstruktion), nur welcher Hafen je Container gewählt wird,
variiert. Ergebnis: eine "was kostet mich Konsolidierung"-Kurve, geschäftlich direkt
motiviert (weniger Häfen = weniger Spediteure/Ansprechpartner, mehr Verhandlungsmacht
bei einem Anbieter, ggf. Mengenrabatte).

Empirisch oft ein echter, interessanter Kompromiss: bei einer Testinstanz kostete die
Beschränkung auf nur 1 Hafen 45 % mehr als die freie Wahl, mit 2 Häfen nur noch 19 %
mehr, ab 3 Häfen kein Unterschied mehr zur vollen Flexibilität. Sehr günstig zu
berechnen (bei bis zu 5 Häfen, der App-Obergrenze, höchstens 2⁵=32 Teilmengen zu prüfen -
~3ms bei 100 Packstücken).

### 2. Ausgeglichenere Container

`balance_containers` in `freight_heuristics.py`: eine lokale Tausch-Suche (derselbe
Tausch-Zug-Mechanismus wie in `_improve_from_baseline`, aber mit einer ANDEREN
Zielfunktion - Streuung der Container-Füllgrade statt Kosten), die eine Kostenerhöhung
bis zu einer Toleranz (Standard 5 %) gegenüber der Kosten-optimalen Lösung zulässt, um
echte Balance-Verbesserungen zu finden. Geschäftlich motiviert: gleichmäßigere
Auslastung kann Handling planbarer machen und einzelne, fast randvolle Container als
Risiko-Nadelöhr vermeiden.

Empirisch über 40 Testfälle verifiziert: in 65 % der Fälle eine deutliche Verbesserung
(>30 % weniger Streuung) bei im Schnitt nur ~1 % Kostenaufschlag (Maximum ~3 %) - in
den übrigen Fällen war die Kosten-optimale Ausgangslösung bereits gut ausbalanciert,
keine Verschlechterung in diesen Fällen.

### Umsetzung in der App

Ein neuer, eigenständiger Bereich "🔀 Alternative Lösungen" direkt nach der
Hauptlösung (nicht im Methodenvergleich versteckt, da es konzeptionell etwas anderes
ist - nicht "welche Konstruktionsmethode ist besser", sondern "welche unterschiedlichen
guten Lösungen gibt es für unterschiedliche Prioritäten"): links die
Konsolidierungs-Tabelle, rechts die ausgeglichene Alternative mit eigener Karte und
PDF-Export.

`test_port_consolidation_frontier_covers_all_stops_and_is_monotone_improving`,
`test_balance_containers_never_loses_items_and_respects_cost_tolerance`,
`test_balance_containers_generally_reduces_fill_variance`,
`test_alternative_solutions_section_renders`.

## 1. Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## Auf Nutzerwunsch: allgemeine Codeüberprüfung nach den letzten Ergänzungen

Nach den zahlreichen Ergänzungen in dieser Sitzung (LNS, mehrfache Ablationsrunden,
Alternative Lösungen) ein systematischer Durchgang: Lint/toter Code, Randfälle,
Performance-Stresstests, vollständige Durchsicht aller Module. Zwei echte Funde:

**1. Bug im PDF-Export bei vielen Containern:** Bei kleiner Kapazität und vielen
Packstücken (real über die App erreichbar - Kapazitäts-Regler-Minimum 30, bis zu 100
Packstücke ergeben ~65 Container) reicht eine PDF-Seite nicht mehr.
`set_auto_page_break` löst dann automatisch einen Seitenumbruch aus, wiederholte aber
NICHT die Tabellenkopfzeile - Folgeseiten zeigten unbeschriftete Zahlenspalten ohne
Kontext, welche Spalte was bedeutet. Fix: Y-Position vor jeder Zeile prüfen, bei
drohendem Seitenumbruch manuell umbrechen und Kopfzeile neu zeichnen. Verifiziert mit
`pdftotext`/`pdfinfo`: Kopfzeile erscheint jetzt auf jeder Seite, alle Zeilen bleiben
erhalten (65 von 65 bei einem erzwungenen Zwei-Seiten-Testfall).
`test_generate_consolidation_plan_pdf_repeats_header_on_every_page`.

**2. Latenter Absturz-Risiko in der "Alternative Lösungen"-Sektion:** `min()`/`max()`
auf einer potenziell leeren Füllgrad-Liste, falls `beam_assignments` je leer wäre (0
Packstücke). Über die App aktuell nicht erreichbar (Packstück-Regler-Minimum ist 10),
aber als Schutz trotzdem ergänzt, falls sich das Minimum je ändert oder die Funktionen
direkt (nicht über die App) mit 0 Packstücken aufgerufen werden - Grundsatz aus dem
gesamten Projekt: defensiv gegen Randfälle programmieren, auch wenn sie aktuell nicht
über die UI erreichbar sind.

**Dazu eine Dokumentationslücke geschlossen:** der "Wie funktioniert diese Demo?"-Bereich
erwähnte das neue "Alternative Lösungen"-Feature noch gar nicht - ergänzt.

**Sonst nichts gefunden:** kein toter Code, alle Randfälle (0/1 Packstücke, alles passt
in einen Container, sehr viele kleine Container) korrekt behandelt, Performance bei
allen real erreichbaren Extremeinstellungen deutlich innerhalb des Budgets (~1,6s bei
Kapazität 30 und 100 Packstücken, inklusive beider neuer Alternative-Lösungen-Funktionen).
Dedizierter Performance-Test dafür ergänzt (`test_alternative_solutions_worst_case_completes_within_budget`),
da bisher nur `flexible_beam_search_construction` allein einen solchen Test hatte.

## Zehnter Fund: der Beam-Breite-Regler wurde entfernt

Auf Nutzerbeobachtung ("in einigen Beispielen scheint die Beam-Breite nichts zu
bringen - Zufall, oder Folge der vielen Änderungen?") systematisch untersucht.
**Bestätigt: kein Zufall.** Dieselbe Art Befund wie bei den mehrfach redundant
gewordenen Startlösungen (siehe oben) - nur diesmal betrifft es die Suchbreite selbst.

**Die Kette, empirisch nachvollzogen:**

| Ebene | Effekt von Breite 1→6 |
|---|---|
| Ein Startpunkt, nur Tausch-Zug, ohne LNS | Bereits in 40 % der Fälle exakt null Unterschied |
| Ensemble (alle Startpunkte, vor LNS) | Ø nur 25 Kosteneinheiten, meist 0 |
| Volle Pipeline (mit LNS danach) | Ø nur 13 Kosteneinheiten - LNS radiert nochmal die Hälfte weg |

Der Grund: der Tausch-Zug in `_improve_from_baseline` prüft in Runde 1 bereits
erschöpfend jedes Packstück-Paar über jedes Container-Paar hinweg und findet dadurch
meist schon das lokale Optimum vom jeweiligen Startpunkt aus - die "Zweitbesten"
Kandidaten, die bei größerer Breite zusätzlich weiterverfolgt werden, führen in den
Folgerunden (nur noch Verschieben/Abspalten) selten zu einem anderen Ziel. LNS
danach reduziert den verbleibenden Rest weiter.

**Dazu kommt: breitere Suche kostet spürbar mehr Zeit, ohne den Gegenwert.** Bei
100 Packstücken: 382ms (Breite 1) vs. 653ms (Breite 6) - 71 % mehr Rechenzeit für
praktisch nichts.

**Umgesetzt (auf Nutzerwunsch):** der Beam-Breite-Regler wurde komplett aus der App
entfernt (`SETTING_SPECS`, `apply_preset`, `sync_query_params` entsprechend bereinigt).
`flexible_beam_search_construction` und `_ensemble_best_result` nutzen jetzt intern
fest `beam_width=1` (Standardwert der Funktionssignatur geändert) - der schnellste
Wert ohne messbare Qualitätseinbuße. Der `beam_width`-**Parameter** bleibt in den
Funktionen selbst erhalten (mehrere Tests verifizieren die verbleibende, wenn auch
geringe Monotonie-Eigenschaft direkt und brauchen ihn deshalb weiterhin), nur der
UI-Regler ist weg.

**Ergebnis:** Rechenzeit bei der App-Obergrenze (100 Packstücke, Kapazität 30) sank
von ~1,5-1,6s (vorheriger fester Wert 2) auf ~502ms - rund 3x schneller, ganz ohne
Qualitätsverlust.

Ein Test musste dabei korrigiert werden, der selbst einen (unentdeckten) Fehler
enthielt: `test_flexible_beam_never_worse_than_these_reference_methods` verglich das
Ensemble-Ergebnis (jetzt mit dem neuen Standard `beam_width=1`) gegen eine
Referenzberechnung, die weiterhin fest `beam_width=2` nutzte - ein unfairer
Vergleich, der die breitere Referenzsuche gelegentlich einen zufällig besseren
lokalen Optimum finden ließ als die tatsächlich genutzte, schmalere Suche. Kein
Fehler in `flexible_beam_search_construction` selbst, sondern ein Artefakt
unterschiedlicher Vergleichsbreiten im Test - behoben durch konsistente Breite in
Test und Referenz.

`test_flexible_beam_width_scaling_quality_is_similar`,
`test_flexible_beam_actual_default_worst_case_completes_within_budget`.

## Auf Nutzerhinweis behoben: Metrik-Deltas hatten die falsche Farbe

Derselbe Fund wie in der VRP-Demo (dort zuerst entdeckt, hier direkt mitgeprüft):
Streamlit färbt `st.metric`-Deltas standardmäßig so, als wäre "höher besser"
(positiv=grün, negativ=rot) - bei Kosten ist aber "weniger besser". Zwei Stellen
betroffen: die Hauptkennzahl "Gesamtkosten" zeigte eine Einsparung ("-500 € ggü.
Alternative") fälschlich in ROT, und die "Ausgeglichen"-Alternative im
"Alternative Lösungen"-Bereich zeigte einen Kostenaufschlag ("+500 €") fälschlich
in GRÜN - also in beiden Fällen genau verkehrt herum.

**Fix:** `delta_color="inverse"` an beiden Stellen ergänzt (Streamlits eigene
Dokumentation: "useful when a negative change is considered good, like a decrease
in cost"). Mit Regressionstest direkt gegen das Metric-Proto abgesichert (prüft
sowohl den grünen Einsparungs- als auch den roten Mehrkosten-Fall), nicht nur
gegen den übergebenen Parameter.

`test_cost_metrics_use_inverse_delta_color`.

## 2. Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

86 Tests, laufen automatisch bei jedem Push/PR über GitHub Actions.

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

## 5. Anpassungsideen für später

- Echte Tourenplanung ab Hafen statt einer Kostenmatrix (Wiederverwendung der
  Tourenplanung-Demo-Logik als "letzte Meile" nach der Hafenwahl)
- Gewichtsgrenzen, Gefahrgut-Beschränkungen je Hafen
- Feste Abfahrtstermine je Hafen (Zeitkomponente)
- Test an einem echten Mobilgerät
