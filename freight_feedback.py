"""
Feedback-Logging für die Frage "War diese Demo hilfreich?" - identisches
Muster wie in den anderen drei Demos.
"""

import csv
import os
import time

from freight_constants import FEEDBACK_FILE


def log_feedback(vote, feedback_file=FEEDBACK_FILE):
    try:
        file_exists = os.path.exists(feedback_file)
        with open(feedback_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "vote"])
            writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), vote])
        return True
    except Exception:
        return False


def get_feedback_counts(feedback_file=FEEDBACK_FILE):
    try:
        if not os.path.exists(feedback_file):
            return 0, 0
        up, down = 0, 0
        with open(feedback_file, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("vote") == "up":
                    up += 1
                elif row.get("vote") == "down":
                    down += 1
        return up, down
    except Exception:
        return 0, 0
