from __future__ import annotations

import httpx

from ..calibers import display_caliber
from ..models import Ammo
from .base import AdapterResult, DataSourceAdapter, FieldProvenance, SourceManifest, utc_now


class TarkovDevAdapter(DataSourceAdapter):
    name = "tarkov.dev"
    priority = 100
    url = "https://api.tarkov.dev/graphql"
    query = """
      query EftCalculatorAmmoBilingual {
        en: ammo(lang: en) {
          item { id name shortName iconLink wikiLink }
          caliber
          damage
          penetrationPower
          armorDamage
          projectileCount
          initialSpeed
          fragmentationChance
          ricochetChance
        }
        zh: ammo(lang: zh) {
          item { id name shortName }
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
        data = payload.get("data", {})
        records = data.get("en") or []
        chinese = {
            record["item"]["id"]: record["item"]
            for record in data.get("zh") or []
            if record.get("item", {}).get("id")
        }
        ammo: list[Ammo] = []
        provenance: dict[str, dict[str, FieldProvenance]] = {}
        for record in records:
            item = record.get("item") or {}
            item_id = item.get("id")
            if not item_id:
                continue
            localized_names = {"en": item.get("name") or item_id}
            aliases: list[str] = []
            translated = chinese.get(item_id)
            if translated and translated.get("name"):
                localized_names["zh"] = translated["name"]
                if translated.get("shortName") not in (
                    None,
                    "",
                    item.get("shortName"),
                ):
                    aliases.append(translated["shortName"])
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
                    aliases=tuple(aliases),
                    localized_names=localized_names,
                    image_url=item.get("iconLink"),
                    wiki_url=item.get("wikiLink"),
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
                    "localized_names",
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
    return display_caliber(value)


def _optional_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None
