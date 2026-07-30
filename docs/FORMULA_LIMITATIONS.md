# 公式限制

默认穿透函数用 `penetration - effective_class * 10` 的 Logistic 曲线；有效等级受
`current_durability / original_max_durability` 影响。该函数保证单调性与可解释性，但不是
Battlestate Games 公开或认可的精确公式。

耐久损伤综合弹药穿深、护甲等级、材料破坏系数和是否穿透。穿透后的肉伤/穿深衰减、钝伤及
距离衰减也属于近似。规则集中记录来源、版本和已知限制，后续可以替换而无需改动 UI 或数据库。

