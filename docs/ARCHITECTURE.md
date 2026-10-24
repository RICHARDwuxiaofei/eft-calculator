# 架构（2026-10-25）

## 两端共用计算，不复制方程

`shared/tarkov_sim_core/src/tarkov_sim_core/` 是纯 Python 核心：

- `models/`：弹药、护甲层、场景、结果和输入校验。
- `rulesets/`：穿透/磨损/穿后损失/钝伤的版本化模型边界。
- `engine/`：单弹丸解析、`random.Random` 随机轨迹与统计区间（不是 NumPy 引擎）。
- `serialization/`、`validation/`、`api.py`：JSON 输入输出、结构化错误、工作量限制。

Windows 的兼容模块转出共享核心；Android 通过 Chaquopy 的 `PythonSimulationEngine.kt`
调用同一个 JSON API。六组旧共享向量不改期望值；新增 92 组独立 Decimal 向量同时喂给
桌面 Python API 和真实 Android Python 桥。两端默认护甲/发数不同，必须用相同完整输入比对。

## 桌面

`ui.py` 是应用初始化/图表范围保护入口，`ui_v2.py` 是当前界面。`worker.py` 在 Qt 线程池
执行模拟；代际编号丢弃旧参数结果。`services.py` 做摘要和 JSON/CSV 导出。
`data.py` 管理 SQLite：目录、收藏、预设、上次输入和来源水位；`legacy_db.py` 在迁移前保全旧库。
损坏物理文件改名留存，坏行备份/隔离，不能以重新建库掩盖原数据丢失。
Qt 设置负责语言/窗口位置；测试通过 `EFT_TEST_SETTINGS_DIRECTORY` 使用独立 INI，不写真实设置。

## Android

`MainActivity.kt` 使用 Compose Material 3；`MainViewModel.kt` 处理输入、防抖、协程和结果代际。
Room 保存弹药与收藏；`MIGRATION_1_2` 添加中文名称而不破坏旧数据。
DataStore 保存同步状态和 `SessionCodec` 编码的输入；恢复后重新计算，不保存陈旧结果。
Room 的损坏回调先完整复制数据库及旁路文件，再允许平台恢复。
`DataSyncWorker.kt` 只接受有效当前 API，不使用历史 Tracker 数值兜底；失败保留目录。

## 数据与图片

唯一离线目录是 `src/tarkov_armor_sim/resources/items/catalog.json`，Android 构建从这里复制资产。
`image-manifest.json` 以稳定 Item ID 绑定图片路径、原 URL 和 SHA256。当前离线范围为
184 弹药、38 插板；软甲、头盔支持手动层模型，不等于拥有完整装备物品库。
缺少精确物品图片显示问号，不能拿其他弹药图顶替。新增在线物品尚无离线图时也是如此。

桌面在线快照含时间、内容哈希、来源和冲突；缓存暂存校验后原子替换、保留有效备份、拒绝回退；
数据库按记录来源水位保护新数据和人工覆盖。快照 SHA256 是完整性校验，不是发布者数字签名。
Android 事务合并当前 API 并保留手工覆盖；服务端未提供逐物品修改时间时，不能据抓取时间证明数值更新。

命中路径始终为 `弹丸 → 启用护甲层（外到内） → 所选身体部位`。
载具/前后左右选择是编辑便利工具，不是覆盖所有当前游戏兼容规则的验证器。
前后插板不能自动叠成同一命中路径；材质、层类型和系数的作用以 [公式边界](FORMULA_LIMITATIONS.md) 为准。

