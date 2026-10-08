"""Jalankan dari root: python -m contracts.export_schemas [--check]."""
import argparse
import json
from pathlib import Path

from contracts.models import AtcsStatus, Health, IntersectionConfig, SessionView, TrafficEvent, TrafficEvents
from contracts.traffic import TrafficView
from contracts.control import ControlStatus, CommandReceipt, OperatorControl, ControlCommand
from contracts.adaptive import AdaptiveStatus, MeasurementBatch
from contracts.video import VideoStatus
from contracts.model_quality import ModelQuality
from contracts.history import EventArchivePage
from contracts.analytics import AnalyticsView, ComparisonReport, ComparisonInput


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = Path(__file__).parent / "schemas"
    output.mkdir(exist_ok=True)
    for model in [AtcsStatus, Health, IntersectionConfig, TrafficEvent, TrafficEvents, SessionView, TrafficView,
                  ControlStatus, CommandReceipt, OperatorControl, ControlCommand, AdaptiveStatus, MeasurementBatch, VideoStatus, EventArchivePage, AnalyticsView, ComparisonReport, ComparisonInput, ModelQuality]:
        path = output / f"{model.__name__}.json"
        mode = 'validation' if model in (ControlCommand, OperatorControl, ComparisonInput) else 'serialization'
        content = json.dumps(model.model_json_schema(mode=mode), ensure_ascii=False, indent=2) + "\n"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"Kontrak belum sinkron: {path.name}")
        else:
            path.write_text(content, encoding="utf-8")
    print("Kontrak JSON Schema sinkron.")


if __name__ == "__main__":
    main()
