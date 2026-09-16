# EFT Calculator 2.2.0

Offline Chinese/English desktop and Android calculator for a selected Escape from
Tarkov armor hit path. The two frontends share one Python calculation core.

**Accuracy status:** Wiki-reviewed item facts, independently tested mathematics,
and a versioned community armor model. This is not a verified replica of current
closed-source EFT server code. Read [the research and limitations](docs/RESEARCH.md).

## This release

184 cartridges, 38 individual plates, four 5.8x42 cartridges, and 222 item-ID-keyed
images. Shotguns always resolve ALL pellets sequentially against updated armor.
Current, repaired maximum and original factory durability are separate. First-trigger,
conditional penetrating and entire-burst damage are separately labeled. Exact
single-projectile expectations and sampled multi-shot trajectories are distinguished.

Desktop supports narrow/tall and wide layouts; Android supports portrait, landscape
and resizable multi-window layouts. Layer editing updates rather than appends.
Online-sync failure retains the verified snapshot and does not fall back to stale
numbers. Missing exact images show a placeholder, not a different item.

## Run and test

Desktop requires Python 3.12 or newer:

```sh
python -m pip install -e '.[dev]'
python -m tarkov_armor_sim.main
ruff check .
pytest
```

Headless Linux checks use `QT_QPA_PLATFORM=offscreen`. Run `python tools/verify_ui.py`
to capture actual Qt layouts at widths 360, 390, 800 and 1440. On Windows run
`python tools/build_windows.py`; the built executable supports `--smoke-test`.

Android uses Java 17, Python 3.13/Chaquopy, Android SDK 36.1 and the checked-in Gradle
wrapper. From `android`, run `./gradlew testDebugUnitTest assembleDebug`. The native
instrumentation suite compares all six shared regression vectors on the device.

## Releases

GitHub Actions runs tests before packaging. Release assets distinguish the Windows
portable ZIP, Android signed-release APK (when signing secrets are configured), and
explicitly labeled debug-signed APK. Debug builds are not production-store builds;
the signing certificate can differ between builds, so installation over an existing
build with a different certificate may require removal of the older build first.
SHA256SUMS and validation artifacts accompany releases. Existing version tags are
never force-moved to a different source commit.

See [the repair review](docs/REVIEW_2026-09-16.md) and [CHANGELOG.md](CHANGELOG.md).
Original game imagery remains owned by its respective rights holders; image/source
provenance is retained in the bundled catalog and image manifest.
