# EFT Calculator v2.1.0

[中文](#中文说明) · [English](#english)

## 中文说明

Escape from Tarkov 分层护甲与弹药模拟器是一款面向游戏中快速查询的非官方 Windows 与 Android
工具。它离线优先搜索弹药，把弹丸依次送入任意数量的护甲层，并显示每层条件穿透率、累计穿透率、
停止概率、耐久损失、钝伤和连续射击结果。

> 当前数据快照：`eft-1.0.6.0-snapshot-2026-07-31`
> 默认规则：`community-approx-2026.07-v1`（**社区近似，不是官方精确公式**）
>
> 当前正式版本：`v2.1.0`

## 界面

Windows 2.0 使用顶部全局动作、左侧紧凑查询轨和右侧结果工作区。完整弹药列表和护甲编辑器只在
需要时打开；结果区包含醒目的首发穿透率、六项核心指标和一次一个的详情页签。

## 已支持

- 当前界面语言与英文名、简称、别名、口径的子串搜索；输入 `855` 即时联想 M855/M855A1
- 选中弹药后自动填入伤害、穿深、甲伤和弹丸数，仍可手动覆写
- Ctrl+K 本地弹药搜索面板、收藏/最近优先与弹药图标
- 首页护甲路径预设；独立编辑器按真实载具、插槽、具体插板自动填入等级、材质与耐久
- 自动值均可手动修改；每次确认追加一层，可继续添加第二层及后续层
- 分别重置弹药、护甲层或全部参数
- 护甲预设；任意层添加/删除；出厂、维修上限和当前耐久严格区分
- 快速解析；NumPy 批量蒙特卡洛；固定种子；后台线程、进度和取消旧任务
- 连续 1–100 发、每发穿透率、首次穿透分布、耐久时间线、胸部致死概率
- 分层条件/累计概率、停止概率、穿透后状态、钝伤与自然语言摘要
- 快速/实验室渐进模式；双区缩放；键盘快捷键
- 弹药对比表和 CSV/JSON 导出
- 离线启动、设置持久化、日志、pytest、ruff 和 PyInstaller 配置

## 快速启动

要求 Python 3.12 或更新版本。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m tarkov_armor_sim
```

应用首次启动会在 `%LOCALAPPDATA%\TarkovArmorSimulator\current.sqlite3` 创建离线数据库。断网不影响
搜索、护甲加载和模拟。日志位于用户目录 `.tarkov-armor-simulator\logs`。

## 数据更新

2.1 立即使用最后有效缓存，并后台从 tarkov.dev 分别取得英文和当前中文名称、按稳定 EFT 物品
ID 合并；服务不可用时退回 TarkovTracker 的结构化
数据。6 小时内跳过重复同步，48 小时标记过期。记录在写入前经过数量、唯一 ID、字段范围和
SHA-256 校验，JSON 与 SQLite 都使用原子切换；失败保留旧版。

## 公式可信度

游戏没有公开完整的当前穿透链路公式。默认规则将护甲等级、相对**出厂**耐久与弹药穿深映射到
单调 Logistic 近似；耐久损伤、穿透后伤害/穿深衰减、钝伤及距离衰减也属于近似。UI 永久显示
数据版本、规则版本和可信度，结果只显示有意义的精度。详细来源见
[调研记录](docs/RESEARCH.md) 与 [公式限制](docs/FORMULA_LIMITATIONS.md)。

碎裂、跳弹、技能、三维碰撞和全身黑部位传播仅保留模型接口，v0.1 默认禁用，避免输出未经验证
的结论。附带离线数据是演示所需的常用子集，并非全量当前物品库。

## 快捷键

| 快捷键 | 操作 |
|---|---|
| `Ctrl+K` / `Ctrl+1` | 聚焦弹药搜索 |
| `Ctrl+2` | 聚焦护甲 |
| `Ctrl+3` | 聚焦结果 |
| `Ctrl+D` | 收藏当前弹药 |
| `Ctrl+M` | 快速/实验室模式 |
| `Esc` | 清空搜索 |

## 开发与测试

```powershell
ruff check .
pytest
python -m tarkov_armor_sim
```

核心层无 Qt、Android、数据库或网络依赖；两个客户端共享 JSON API 和测试向量。项目结构：

```text
shared/tarkov_sim_core/  共享 Python 核心与 JSON API
shared/schemas/           跨端 JSON Schema
shared/test_vectors/      六组固定跨端向量
src/tarkov_armor_sim/     Windows 数据、同步、服务与 PySide6 双区 UI
android/                  Kotlin/Compose/Room/WorkManager/Chaquopy 原生应用
tests/                    单元、服务与 UI 测试
tools/                    Windows 构建与数据工具
```

## 国际化

- Windows 使用集中式 locale catalog，自动跟随系统语言，也可在“设置与数据管理”中即时切换
  `简体中文` / `English`。
- Android 使用标准资源国际化：`res/values/` 为英文默认资源，`res/values-zh/` 为中文资源，
  自动跟随系统语言。
- 新增界面文字必须进入对应 catalog/resource，禁止继续在业务逻辑中拼接中文或英文。

## Windows 云端构建

正式发布包由 `.github/workflows/windows-release.yml` 在 GitHub Actions 的
`windows-latest` 环境中构建。推送 `v*` 标签后，工作流会运行 lint、完整测试、PyInstaller
构建，生成 `EFT-Calculator-Windows-x64.zip` 并上传到 GitHub Release。用户数据库与设置写到
用户目录，不写入安装目录，目标电脑无需安装 Python。

## Android 构建

Android 原生工程位于 `android/`，要求 JDK 17 和 Android SDK 36.1：

```powershell
cd android
.\gradlew.bat testDebugUnitTest assembleDebugAndroidTest assembleDebug assembleRelease
```

`app-debug.apk` 可直接安装；正式标签构建会使用仓库 Secrets 中的稳定发布证书签名 release APK。
仓库的 `.github/workflows/android-build.yml` 在云端复跑单测和两个构建变体，并把可安装的正式
APK 上传到 GitHub Release。Android 最低 API 24，打包 `arm64-v8a` 与 `x86_64`，Chaquopy
17.0 嵌入 Python 3.13。

## 免责声明

本项目是非官方社区工具，与 Battlestate Games 无关联。游戏数据和机制可能随更新改变；结果取决
于标明版本的数据以及公开资料推导，不能视为官方结论。本软件不读取游戏内存、不修改或注入游戏
进程、不创建 DirectX Hook、不自动控制游戏，也不绕过反作弊。Escape from Tarkov 及相关名称和
资产归其权利人所有。

物品缩略图来源和逐文件记录见 [视觉素材来源](docs/ASSET_SOURCES.md)。这些游戏参考图片不属于
本项目 MIT 授权范围；原创应用图标不包含游戏 Logo、角色或原画。

---

## English

EFT Calculator is an unofficial Windows and Android utility for fast in-game reference. It searches
an offline-first ammunition database, sends each projectile through an arbitrary sequence of armor
layers, and reports conditional and cumulative penetration, stopping probability, durability loss,
blunt damage, and burst behavior.

> Current data snapshot: `eft-1.0.6.0-snapshot-2026-07-31`
> Default ruleset: `community-approx-2026.07-v1` (**community approximation, not an official formula**)
> Current stable release: `v2.1.0`

### Interface and workflow

Windows 2.0 uses a global action bar, a compact query rail on the left, and a result workspace on the
right. The full ammo browser and armor-path editor open only when needed. The main result area keeps
first-shot penetration, six core metrics, layered results, burst results, charts, and comparison close
at hand.

- Substring autocomplete over the active UI language and English; `855` suggests M855 and M855A1.
- Ammo presets auto-fill combat values while keeping every value manually editable.
- Real carrier → slot → plate presets auto-fill class, material, and durability; each confirmation appends a layer.
- Common armor presets plus independent Reset ammo, Reset armor, and Reset all actions.
- Numeric durability input and New / 75% / 50% / 25% / Broken shortcuts.
- Distance, 1–100 shots, quick analysis, seeded Monte Carlo, and cancellable background work.
- Layer probabilities, durability timeline, expected health/blunt damage, and thorax kill probability.
- CSV/JSON export, SQLite preferences, offline startup, logs, tests, and PyInstaller packaging.

### Quick start

Python 3.12 or newer is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m tarkov_armor_sim
```

The first launch creates `%LOCALAPPDATA%\TarkovArmorSimulator\current.sqlite3`. Search, armor loading,
and simulation continue to work without a network connection.

### Data synchronization

Version 2.1 opens the last valid cache immediately, then fetches English and Chinese names from
tarkov.dev and merges them by stable EFT item ID, with TarkovTracker/tarkovdata as a fallback. It
skips duplicate syncs for six hours and marks data stale
after 48 hours. Record count, unique IDs, value ranges, and SHA-256 are validated before atomic JSON and
SQLite replacement; any failure preserves the previous snapshot.

### Model trust and limitations

The game does not publish the complete current penetration pipeline. The default ruleset maps armor
class, original durability ratio, and penetration power through a monotonic logistic approximation.
Durability damage, post-penetration damage/penetration loss, blunt damage, and distance loss are also
approximations. Every result identifies its data and ruleset versions.

Fragmentation, ricochet, skills, 3D collision, and blacked-limb propagation are not enabled. The bundled
offline dataset is a useful subset, not a complete live item database.

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+K` / `Ctrl+1` | Open ammo search |
| `Ctrl+2` | Open the armor editor |
| `Ctrl+3` | Focus results |
| `Ctrl+D` | Favorite the current ammo |
| `Ctrl+M` | Toggle quick/laboratory mode |
| `Esc` | Clear search |

### Internationalization

- Windows uses a centralized locale catalog, follows the system locale by default, and can switch
  between Simplified Chinese and English from Settings.
- Android uses native resources: English in `res/values/` and Chinese in `res/values-zh/`.
- UI text belongs in catalogs/resources rather than business logic.

### Development and verification

```powershell
python -m ruff check .
python -m pytest -q
python tools/build_windows.py

cd android
.\gradlew.bat testDebugUnitTest assembleDebugAndroidTest assembleDebug assembleRelease
```

The shared Python core has no Qt, Android, database, or network dependency. Windows and Android consume
the same versioned JSON API, schemas, and fixed cross-platform vectors.

### Cloud releases

Pushing a `v*` tag triggers two GitHub Actions workflows. Windows runs lint, the full test suite, and
PyInstaller on `windows-latest`, then uploads a versioned x64 ZIP. Android runs JVM tests and the release
build on Ubuntu, signs the APK with the stable certificate stored only in GitHub Secrets, and uploads the
installable APK. Both artifacts are attached to the same GitHub Release.

### Disclaimer

This unofficial community project is not affiliated with Battlestate Games. It does not read game
memory, modify or inject into the game process, create a DirectX hook, automate gameplay, or bypass
anti-cheat. Escape from Tarkov and related names/assets belong to their respective rights holders.
Reference item images are outside this repository's MIT grant; the original application icon contains
no game logo, character, or key art.
