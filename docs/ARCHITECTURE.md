# 架构

`models.py` 定义不可依赖 UI/数据库的数据模型；`rulesets.py` 是可替换公式边界；
`engine.py` 提供快速解析与 NumPy 蒙特卡洛；`data.py` 管理 SQLite 离线快照与用户状态；
`services.py` 负责摘要和导出；`worker.py` 把模拟放进 Qt 线程池；`ui.py` 仅收集输入并展示结果。

命中路径始终是 `Projectile -> ArmorLayer[0..N] -> BodyPart`，没有“外甲+内衬”硬编码。

