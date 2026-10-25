# 2026-10-25 审计交付与远端验收

完整发现、数据冲突和模型边界见 [主审计报告](AUDIT_2026-10-25.md)。

## 起点与修复提交

起点：v2.2.2 / `2e332e3541dd1818cdc74e2710c1bce4beb7f5ca`。
候选版本 2.2.3；没有新建正式 Release 或移动旧 Tag。

| 提交 | 内容 | 验收情况 |
|---|---|---|
| [`bea2fdf`](https://github.com/RICHARDwuxiaofei/eft-calculator/commit/bea2fdfd94dce0a773a7a79ddc761325e9411ed7) | 核心默认/校验、数据库保全、数据溯源、双端输入恢复、搜索与 UI 审计 | 本地通过，远端双流水线成功 |
| [`711fc02`](https://github.com/RICHARDwuxiaofei/eft-calculator/commit/711fc02c4ca94ca101a658d98fff91684a53d0f6) | 运行时翻译补全、图表/表头术语和指标换行 | 本地通过；远端发现 Linux 英文 360 像素布局超宽 4 像素，保留失败记录 |
| [`481c754`](https://github.com/RICHARDwuxiaofei/eft-calculator/commit/481c754b9e60961b23872082beb58f6ccf8cc157) | 缩短弹药卡片重复说明，保留完整“全部命中”模型提示；不修改尺寸断言 | 远端回归、verify、Windows、Android 编译均成功；后续新提交触发并发策略，旧模拟器运行被取消 |
| [`2fbde4f`](https://github.com/RICHARDwuxiaofei/eft-calculator/commit/2fbde4f83380e102bf07e237a32f4bfffa46e548) | 首次大窗口显示后按实际视口重新排布卡片，新增首帧回归；补充真实图表及 5.8×42 筛选截图 | 最终功能提交，本地与远端完整验收成功 |
| [`fbb3d92`](https://github.com/RICHARDwuxiaofei/eft-calculator/commit/fbb3d92efabfbf4661472308e70a381967867762) | 仅加固 pytest 缓存/日志目录隔离，并记录早期设置隔离边界；应用功能未变化 | 本地 231 项及远端全流水线再次成功 |

## 本地最终验收

- Ruff：通过；pytest：231/231 通过。
- 独立 Decimal 参考案例 92 组；Hypothesis 600 组；复杂案例各 10 万次固定种子抽样。
- Windows EXE：干净、旧版升级、物理损坏库三场景全部退出 0，并产生真实 1280×720 截图。
- Android JVM：4 项通过；API 36.1 x86_64 专用无窗口模拟器：5 项通过。
  这 5 项包含 Room 迁移、坏库原始字节保全、Compose 活动重建、6 个旧向量和 92 个独立案例。
- Android debug / release 编译通过；release 本地包未签名，不能当作正式安装包。
- 222 物品 ID 与 Wiki 逐页身份核对；222 在线原图与本地哈希一致；Windows/两种 APK 内资源逐一一致。
- 97 份审计证据逐项 SHA256 检查，无不符；文本强制 LF，避免 Windows/Git 换行破坏哈希。
- Qt 中英文五尺寸、Android 中英文四布局和深浅色均有实际截图。

## 远端最终提交

最终功能提交：`2fbde4f83380e102bf07e237a32f4bfffa46e548`。

- [Regression checks / 40133144446](https://github.com/RICHARDwuxiaofei/eft-calculator/actions/runs/40133144446)：成功，231 项测试通过。
- [双端构建与模拟器 / 40133144463](https://github.com/RICHARDwuxiaofei/eft-calculator/actions/runs/40133144463)：verify、Windows、Android、Android runtime 全部成功；publish 按设计跳过。

最终 CI 的 Windows 三类数据库真实启动均退出 0；Android API 35 模拟器 5 项测试通过，
随后安装并实际运行生产签名交付 APK，竖屏/横屏/宽屏均留存截图。
安装哈希与本地下载 APK 完全相同。本地 API 36.1 专用模拟器已停止，未操作或卸载个人设备应用。

最后的测试隔离提交也完成远端验收：
[Regression / 40160168954](https://github.com/RICHARDwuxiaofei/eft-calculator/actions/runs/40160168954) 和
[双端 / 40160169149](https://github.com/RICHARDwuxiaofei/eft-calculator/actions/runs/40160169149) 均成功。
下方下载收据明确对应最后功能变更 `2fbde4f`，不是将不同源提交的产物混称为同一哈希。

第一轮已成功的记录：[Regression 40131713304](https://github.com/RICHARDwuxiaofei/eft-calculator/actions/runs/40131713304)、
[双端 40131713294](https://github.com/RICHARDwuxiaofei/eft-calculator/actions/runs/40131713294)。
中间失败记录：[Linux 布局回归](https://github.com/RICHARDwuxiaofei/eft-calculator/actions/runs/40132358512)。
第一轮成功不代替最终提交成功。

## 产物与签名

本地 APK/EXE 哈希分别见 [打包报告](audits/2026-10-25/packaging.json) 和
[Windows 运行报告](audits/2026-10-25/windows-runtime/results.json)。
本地调试 APK 使用本机开发签名；远端若无生产密钥则交付明确标注的临时 debug-signed APK。
二者证书不同，不应覆盖个人设备的应用；本次仅使用专用模拟器，不改动个人设备。
Windows 没有 Authenticode 签名。SHA256 保证字节完整性，不认证发布者身份。

实际下载的远端 APK 使用**已配置的生产发布密钥**，APK v2 签名校验通过、签名者 1 个。
证书 SHA256：`e313537608ae44b884d91ef8198eeb824efe9ea0f5c9659be5c745694f7effce`。
这与本地未签名 release 编译包、开发签名 debug 包是不同产物，不能混称。

| 最终 CI 产物 | 字节数 | 下载文件 SHA256 |
|---|---:|---|
| EFT-Calculator-Android-2.2.3.apk | 35,939,561 | `d56687989b5ff7d9b81ec26ae4cb2529fe06ef2a514f7e6410e8c4ab74e7ddd7` |
| EFT-Calculator-Windows-2.2.3.zip | 78,496,976 | `a8a246a80fcda66c011fd4b44d0eeb5b5c02e57ae80580d3fdcc96a59c1aac9c` |

两份产物的构建说明均记录最终功能 SHA `2fbde4f83380e102bf07e237a32f4bfffa46e548`。
逐一核对包内 222 张图片和目录数据相同；Windows ZIP 内 EXE 哈希等于其三场景运行收据：
`42dfa99ce238bf5918aca867650dc3706b18ffe2a953394b95b2e7f309250aed`。

机器收据与运行证据：[ci-artifact-receipts.json](audits/2026-10-25/ci-artifact-receipts.json)、
[Android instrumentation](audits/2026-10-25/ci-runtime/android-instrumentation.txt)、
[Android JVM](audits/2026-10-25/ci-runtime/android-jvm.xml)、
[Windows 三场景](audits/2026-10-25/ci-runtime/windows-results.json)。
完整产物从上述最终工作流的 `release-windows` / `release-android` Artifacts 下载。
Artifacts 有保留期限，不是永久正式 Release 资产；本地下载副本保存在任务的 `artifacts/audit-2026-10-25/ci-final`。

## 为什么没有正式 Release

三项公开数值冲突、当前服务器公式精确性、完整头盔/整甲目录等边界仍未消除。
本轮交付代码、测试、离线证据和可审查构建，不把数学测试或模拟器测试当作游戏内实弹证据。
[既有 v2.2.2 Release](https://github.com/RICHARDwuxiaofei/eft-calculator/releases/tag/v2.2.2) 保持不动。
