from __future__ import annotations

import httpx

from ..models import Ammo
from .base import AdapterResult, DataSourceAdapter, FieldProvenance, SourceManifest, utc_now
from .tarkov_dev import _clean_caliber, _optional_float


class TarkovTrackerAdapter(DataSourceAdapter):
    """Structured GitHub fallback maintained by the Tarkov community tool ecosystem."""

    name = "TarkovTracker/tarkovdata"
    priority = 60
    url = "https://raw.githubusercontent.com/TarkovTracker/tarkovdata/master/ammunition.json"

    async def fetch(self) -> AdapterResult:
        fetched_at = utc_now()
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(self.url)
            response.raise_for_status()
            records = response.json()
        ammo: list[Ammo] = []
        provenance: dict[str, dict[str, FieldProvenance]] = {}
        for item_id, record in records.items():
            ballistics = record.get("ballistics") or {}
            ammo.append(
                Ammo(
                    id=item_id,
                    name=record.get("name") or item_id,
                    short_name=record.get("shortName") or record.get("name") or item_id,
                    caliber=_clean_caliber(record.get("caliber") or ""),
                    damage=float(ballistics.get("damage") or 0),
                    penetration_power=float(ballistics.get("penetrationPower") or 0),
                    armor_damage_percent=float(ballistics.get("armorDamage") or 0),
                    projectile_count=int(record.get("projectileCount") or 1),
                    muzzle_velocity=_optional_float(ballistics.get("initialSpeed")),
                    fragmentation_chance=_optional_float(ballistics.get("fragmentationChance")),
                    ricochet_chance=_optional_float(ballistics.get("ricochetChance")),
                    source_version=f"tarkovdata-{fetched_at[:10]}",
                )
            )
            provenance[item_id] = {
                field: FieldProvenance(self.name, fetched_at, f"{item_id}.{field}")
                for field in (
                    "name",
                    "short_name",
                    "caliber",
                    "damage",
                    "penetration_power",
                    "armor_damage_percent",
                )
            }
        return AdapterResult(
            SourceManifest(
                self.name,
                self.url,
                fetched_at,
                self.priority,
                len(ammo),
                response.headers.get("etag"),
            ),
            ammo,
            provenance,
        )
