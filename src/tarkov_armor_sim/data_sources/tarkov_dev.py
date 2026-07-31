from __future__ import annotations

import httpx

from ..models import Ammo
from .base import AdapterResult, DataSourceAdapter, FieldProvenance, SourceManifest, utc_now


class TarkovDevAdapter(DataSourceAdapter):
    name = "tarkov.dev"
    priority = 100
    url = "https://api.tarkov.dev/graphql"
    query = """
      query EftCalculatorAmmo {
        ammo(lang: en) {
          item { id name shortName }
          caliber
          damage
          penetrationPower
          armorDamage
          projectileCount
          initialSpeed
          fragmentationChance
          ricochetChance
        }
      }
    """

    async def fetch(self) -> AdapterResult:
        fetched_at = utc_now()
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            response = await client.post(self.url, json={"query": self.query})
            response.raise_for_status()
            payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(f"tarkov.dev GraphQL error: {payload['errors'][0]['message']}")
        records = payload.get("data", {}).get("ammo") or []
        ammo: list[Ammo] = []
        provenance: dict[str, dict[str, FieldProvenance]] = {}
        for record in records:
            item = record.get("item") or {}
            item_id = item.get("id")
            if not item_id:
                continue
            ammo.append(
                Ammo(
                    id=item_id,
                    name=item.get("name") or item_id,
                    short_name=item.get("shortName") or item.get("name") or item_id,
                    caliber=_clean_caliber(record.get("caliber") or ""),
                    damage=float(record.get("damage") or 0),
                    penetration_power=float(record.get("penetrationPower") or 0),
                    armor_damage_percent=float(record.get("armorDamage") or 0),
                    projectile_count=int(record.get("projectileCount") or 1),
                    muzzle_velocity=_optional_float(record.get("initialSpeed")),
                    fragmentation_chance=_optional_float(record.get("fragmentationChance")),
                    ricochet_chance=_optional_float(record.get("ricochetChance")),
                    source_version=f"tarkov.dev-{fetched_at[:10]}",
                )
            )
            provenance[item_id] = {
                field: FieldProvenance(self.name, fetched_at, f"ammo.{field}")
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


def _clean_caliber(value: str) -> str:
    return value.removeprefix("Caliber").replace("NATO", "").replace("mm", "")


def _optional_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None
