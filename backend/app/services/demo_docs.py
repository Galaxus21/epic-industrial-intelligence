"""
EPIC — The demo's sample documents, written for the user to upload through the document pipeline.

Three files that tell the same story as the seeded records (demoTimeline dates all of them):
  PDF — P-101 vibration analysis report (demoReportP101)
  PDF — K-401 incident investigation report (demoReportK401)
  TXT — night-shift handover notes (demoHandover)
Called by the demo seed (app/services/demoSeed.py).
"""
from __future__ import annotations

import os
from datetime import datetime

from app.services import demoTimeline as timeline
from app.services.demoHandover import buildNightShiftHandover
from app.services.demoReportK401 import buildK401IncidentReport
from app.services.demoReportP101 import buildP101VibrationReport

UPLOADS_DIR = os.path.join("uploads", "demo_samples")


def generate_demo_documents(now: datetime | None = None) -> list[dict]:
    """
    Write the sample documents to UPLOADS_DIR and return {"id", "name"} for each.

    Nothing is written to the database: the files are there for the user to upload through the normal
    document pipeline. When a generator fails a short text note naming
    the error is written under the same file name, so every listed file exists. Safe to call repeatedly;
    the files are overwritten.
    """
    now = now or timeline.seedMoment()
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    records: list[dict] = []
    for docId, name, generate in _demoFiles(now):
        try:
            content = generate(now)
        except Exception as exc:
            content = f"[Demo document placeholder — generation error: {exc}]\nDocument: {name}\n"
        _writeDemoFile(name, content)
        records.append({"id": docId, "name": name})
    return records


def _demoFiles(now: datetime) -> tuple:
    """(document ID, file name, generator) for each sample file."""
    handoverDate = timeline.daysAgo(now, 0).strftime(timeline.FILE_DATE_FORMAT)
    incidentFileTag = timeline.k401IncidentId(now).removeprefix("INC-")
    return (
        ("DOC-DEMO-PDF-01", "P101_Vibration_Analysis_Report_MR-P101-033.pdf", buildP101VibrationReport),
        ("DOC-DEMO-PDF-02", f"K401_Incident_Investigation_Report_INC{incidentFileTag}.pdf", buildK401IncidentReport),
        ("DOC-DEMO-TXT-01", f"Night_Shift_Handover_CDU_{handoverDate}.txt", buildNightShiftHandover),
    )


def _writeDemoFile(name: str, content: bytes | str) -> None:
    path = os.path.join(UPLOADS_DIR, name)
    if isinstance(content, bytes):
        with open(path, "wb") as demoFile:
            demoFile.write(content)
    else:
        with open(path, "w", encoding="utf-8") as demoFile:
            demoFile.write(content)
