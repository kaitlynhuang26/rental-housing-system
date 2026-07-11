from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ALL_LOCATION_ID = "all"


class RentalLocation(BaseModel):
    location_id: str
    name: str
    excel_file: str

    @property
    def excel_path(self) -> Path:
        return (PROJECT_ROOT / self.excel_file).resolve()


LOCAL_LOCATIONS = [
    RentalLocation(
        location_id="gedung_panjang",
        name="Kos Gedung Panjang",
        excel_file="data/Kos Gedung Panjang (1).xlsx",
    ),
    RentalLocation(
        location_id="pluit_kencana",
        name="Kos Pluit Kencana",
        excel_file="data/Kos Pluit Kencana.xlsx",
    ),
    RentalLocation(
        location_id="putra_satu",
        name="Kos Putra Satu",
        excel_file="data/Kos Putra Satu.xlsx",
    ),
]

DEMO_LOCATIONS = [
    RentalLocation(
        location_id="gedung_panjang",
        name="Kos Gedung Panjang",
        excel_file="data/public_demo/Kos_Gedung_Panjang_PUBLIC_DEMO_LOCKED.xlsx",
    ),
    RentalLocation(
        location_id="pluit_kencana",
        name="Kos Pluit Kencana",
        excel_file="data/public_demo/Kos_Pluit_Kencana_PUBLIC_DEMO_LOCKED.xlsx",
    ),
    RentalLocation(
        location_id="putra_satu",
        name="Kos Putra Satu",
        excel_file="data/public_demo/Kos_Putra_Satu_PUBLIC_DEMO_LOCKED.xlsx",
    ),
]


def _active_locations() -> list[RentalLocation]:
    if os.getenv("RENTAL_DEMO_MODE", "").lower() in {"1", "true", "yes"}:
        return DEMO_LOCATIONS
    return LOCAL_LOCATIONS


LOCATIONS = _active_locations()
LOCATION_BY_ID = {location.location_id: location for location in LOCATIONS}


def list_locations() -> list[RentalLocation]:
    return LOCATIONS


def get_location(location_id: str | None) -> RentalLocation:
    key = location_id or "gedung_panjang"
    if key == ALL_LOCATION_ID:
        key = "gedung_panjang"
    try:
        return LOCATION_BY_ID[key]
    except KeyError as error:
        available = ", ".join(location.location_id for location in LOCATIONS)
        raise ValueError(f"Unknown location_id {key!r}. Available: {available}") from error


def is_all_locations(location_id: str | None) -> bool:
    return location_id == ALL_LOCATION_ID
