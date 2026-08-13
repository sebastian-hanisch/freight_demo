"""
Erzeugt einen Konsolidierungsplan als downloadbares PDF (in-memory) -
Zusammenfassung der Gesamtkosten + Container-/Hafenliste.
"""

import time

from freight_evaluation import evaluate_assignment


def generate_consolidation_plan_pdf(label, assignments, item_sizes, item_regions, road_cost, sea_freight):
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    stats = evaluate_assignment(assignments, item_sizes, item_regions, road_cost, sea_freight)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Konsolidierungsplan - {label}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Erstellt: {time.strftime('%d.%m.%Y %H:%M')} Uhr", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Zusammenfassung", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Gesamtkosten: {stats['total_cost']:.0f} EUR", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"davon Seefracht: {stats['sea_cost_total']:.0f} EUR", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"davon Strassenfracht: {stats['road_cost_total']:.0f} EUR", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"Anzahl Container: {stats['n_containers']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Container-Zuweisungen", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    headers = ["#", "Hafen", "Packstuecke", "Kosten (EUR)"]
    widths = [12, 25, 25, 30]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(235, 235, 235)
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, h, border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln(7)

    pdf.set_font("Helvetica", "", 9)
    for i, c in enumerate(assignments):
        row = [str(i + 1), f"Hafen {c['port'] + 1}", str(len(c["items"])), f"{c['cost']:.0f}"]
        for val, w in zip(row, widths):
            pdf.cell(w, 6, val, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(6)

    return bytes(pdf.output())
