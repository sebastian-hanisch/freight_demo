"""
Zentrale Konstanten für die Seefracht-Konsolidierungs-Demo (LCL - Less than
Container Load): welche Packstücke in welchen Container, welcher Hafen je
Container, um See- und Straßenfrachtkosten gemeinsam zu minimieren.
(Sebastian Hanisch - Operations Research und Machine Learning).
"""

PORT_COLOR = "#000000"
REGION_COLORS = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0891b2", "#db2777", "#65a30d"]
EPS = 1e-9

DEFAULT_N_ITEMS = 40
DEFAULT_N_REGIONS = 6
DEFAULT_N_PORTS = 3
DEFAULT_CONTAINER_CAPACITY = 100.0  # abstrakte Volumeneinheiten

DEFAULT_SEA_FREIGHT_BASE = 800.0  # € je genutztem Container
DEFAULT_SEA_FREIGHT_SPREAD = 0.3  # relative Schwankung zwischen Häfen (0 = alle Häfen gleich teuer)
DEFAULT_ROAD_COST_PER_UNIT = 5.0  # € je Größeneinheit und Distanzeinheit

FEEDBACK_FILE = "feedback_log.csv"
