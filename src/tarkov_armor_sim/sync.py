from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from .data_sources import DataSourceAdapter, TarkovDevAdapter, TarkovTrackerAdapter
from .models import Ammo

LOGGER = logging.getLogger(__name__)
SYNC_INTERVAL = timedelta(hours=6)
STALE_AFTER = timedelta(hours=48)


@dataclass(frozen=True)
class SyncReport:
    ok: bool
    status: str
    source: str
    record_count: int
    snapshot_id: str | None
    message: str
    conflicts: int = 0


class SnapshotStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.current_path = directory / "snapshot.json"
        self.backup_path = directory / "snapshot.backup.json"

    def read(self) -> dict | None:
        if not self.current_path.exists():
            return None
        return json.loads(self.current_path.read_text(encoding="utf-8"))

    def status(self) -> str:
        snapshot = self.read()
        if not snapshot:
            return "内置数据"
        created = datetime.fromisoformat(snapshot["created_at"])
        if datetime.now(UTC) - created > STALE_AFTER:
            return "数据已过期"
        return "数据已更新"

    def should_sync(self, *, force: bool = False) -> bool:
        if force:
            return True
        snapshot = self.read()
        if not snapshot:
            return True
        return datetime.now(UTC) - datetime.fromisoformat(
            snapshot["created_at"]
        ) >= SYNC_INTERVAL

    def atomic_write(self, payload: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temp_path = self.directory / "snapshot.pending.json"
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        temp_path.write_text(encoded, encoding="utf-8")
        # Parse and hash the exact staged bytes before the switch.
        staged = json.loads(temp_path.read_text(encoding="utf-8"))
        canonical = json.dumps(
            staged["ammo"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != staged.get("sha256"):
            raise ValueError("暂存快照 SHA-256 校验失败")
        if self.current_path.exists():
            shutil.copy2(self.current_path, self.backup_path)
        os.replace(temp_path, self.current_path)


class DataSynchronizer:
    def __init__(
        self,
        store: SnapshotStore,
        adapters: tuple[DataSourceAdapter, ...] | None = None,
    ) -> None:
        self.store = store
        self.adapters = adapters or (TarkovDevAdapter(), TarkovTrackerAdapter())

    async def sync(self, *, force: bool = False) -> SyncReport:
        if not self.store.should_sync(force=force):
            current = self.store.read() or {}
            return SyncReport(
                True,
                "跳过",
                current.get("sources", [{}])[0].get("source", "缓存"),
                len(current.get("ammo", [])),
                current.get("snapshot_id"),
                "距离上次成功同步不足 6 小时",
            )
        failures: list[str] = []
        results = []
        adapters = sorted(self.adapters, key=lambda item: item.priority, reverse=True)
        for attempt, adapter in enumerate(
            adapters
        ):
            try:
                result = await adapter.fetch()
                self._validate(result.ammo)
                results.append(result)
            except (httpx.HTTPError, OSError, RuntimeError, TypeError, ValueError) as exc:
                failures.append(f"{adapter.name}: {exc}")
                LOGGER.warning("Data source %s failed: %s", adapter.name, exc)
                if attempt + 1 < len(adapters):
                    await asyncio.sleep(min(2**attempt, 4))
        if results:
            payload = self._snapshot_payload(results)
            self.store.atomic_write(payload)
            source_names = " + ".join(item.manifest.source for item in results)
            return SyncReport(
                True,
                "成功",
                source_names,
                len(payload["ammo"]),
                payload["snapshot_id"],
                f"已验证并原子切换 {len(payload['ammo'])} 条弹药数据",
                len(payload["conflicts"]),
            )
        old = self.store.read()
        return SyncReport(
            False,
            "失败，保留旧数据",
            " / ".join(adapter.name for adapter in self.adapters),
            len(old.get("ammo", [])) if old else 0,
            old.get("snapshot_id") if old else None,
            "; ".join(failures),
        )

    @staticmethod
    def _validate(ammo: list[Ammo]) -> None:
        if len(ammo) < 20:
            raise ValueError(f"记录数异常：{len(ammo)}")
        ids = [item.id for item in ammo]
        if len(set(ids)) != len(ids):
            raise ValueError("弹药 ID 重复")
        for item in ammo:
            if not item.name or not item.caliber:
                raise ValueError(f"{item.id}: 名称或口径为空")
            if not 0 <= item.damage <= 1000:
                raise ValueError(f"{item.id}: 伤害越界")
            if not 0 <= item.penetration_power <= 200:
                raise ValueError(f"{item.id}: 穿深越界")

    @staticmethod
    def _snapshot_payload(results) -> dict:
        ordered = sorted(results, key=lambda item: item.manifest.priority, reverse=True)
        chosen: dict[str, Ammo] = {}
        chosen_provenance = {}
        conflicts = []
        compared_fields = (
            "name",
            "short_name",
            "caliber",
            "damage",
            "penetration_power",
            "armor_damage_percent",
            "projectile_count",
        )
        for result in ordered:
            for ammo in result.ammo:
                if ammo.id not in chosen:
                    chosen[ammo.id] = ammo
                    chosen_provenance[ammo.id] = result.provenance.get(ammo.id, {})
                    continue
                winner = chosen[ammo.id]
                for field in compared_fields:
                    selected = getattr(winner, field)
                    candidate = getattr(ammo, field)
                    if selected != candidate:
                        conflict = {
                            "id": ammo.id,
                            "field": field,
                            "chosen": selected,
                            "chosen_source": chosen_provenance[ammo.id]
                            .get(field, {})
                            .source
                            if chosen_provenance[ammo.id].get(field)
                            else ordered[0].manifest.source,
                            "rejected": candidate,
                            "rejected_source": result.manifest.source,
                        }
                        conflicts.append(conflict)
                        LOGGER.info("Data conflict kept by priority: %s", conflict)
        records = []
        for ammo in sorted(chosen.values(), key=lambda item: item.id):
            item = asdict(ammo)
            item["aliases"] = list(ammo.aliases)
            item["provenance"] = {
                field: asdict(value)
                for field, value in chosen_provenance.get(ammo.id, {}).items()
            }
            records.append(item)
        canonical = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return {
            "schema_version": 1,
            "snapshot_id": f"eft-online-{digest[:12]}",
            "created_at": ordered[0].manifest.fetched_at,
            "sources": [asdict(result.manifest) for result in ordered],
            "conflicts": conflicts,
            "ammo": records,
            "sha256": digest,
        }


def run_sync(store: SnapshotStore, *, force: bool = False) -> SyncReport:
    return asyncio.run(DataSynchronizer(store).sync(force=force))
