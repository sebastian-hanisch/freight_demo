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

85 Tests, laufen automatisch bei jedem Push/PR über GitHub Actions.

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
