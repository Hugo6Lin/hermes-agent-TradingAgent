# Hermes 报告界面设计规范

**日期：** 2026-04-22
**阶段：** 报告界面重新设计
**状态：** 第三次修订版

---

## 一、目的

### 1.1 本报告界面用途

Hermes 报告界面是 boss 做出投资决策的核心产物表面。它将完整的牛市决策流程转化为两种阅读模式：

- 海报视图：单页决策看板，优先保证 3 秒内理解完整决策，支持打印在单张 A4 或 Letter 纸上
- PDF 报告视图：多页 executive 报告，优先保证存档和投委会分发

### 1.2 目标读者

- 主要读者：boss 或投委会主任，仅阅读海报即可
- 次要读者：操作员或分析师，可阅读完整 PDF 报告以了解研究深度

### 1.3 为何是海报加 PDF 而非幻灯片

幻灯片不适用，原因如下：

- 幻灯片暗示演示模式，有人向 boss 做汇报
- 幻灯片每页内容过多
- 幻灯片打印效果不可控
- 幻灯片不适合存档

海报加 PDF 是正确选择，原因如下：

- 海报给 boss 一张固定的决策卡，无需导航
- PDF 给投委会提供带完整深度的分页存档记录
- 两者均可打印，且无需特殊软件即可正确渲染
- 两者每次输出内容一致

---

## 二、目标读者要求

### Boss 或投委会

**3 秒内**，读者必须理解：

- 操作是什么？（买入股票、买入看涨、牛市看涨价差、卖出备兑看跌、备兑看涨、观望）
- 信心度是什么？（高信心、中信心、低信心）
- 标的是什么？（代码加公司名）
- 目标价和目标窗口是什么？
- 为何现在行动的最核心原因是什么？

**30 到 60 秒内**，读者可深入理解：

- 为何选择该工具而非其他备选方案
- 期权结构是什么（如适用）
- 早期退出计划是什么
- 主要风险是什么
- 监控状态和验证结论是什么

超过 60 秒的内容不在本表面范围。深度研究内容属于分析师级视图。

---

## 三、设计原则

### 3.1 决策优先的信息层级

最重要的信息放在最优先的视觉位置。信息层级顺序如下：

1. 操作加信心度，最主导的视觉元素
2. 代码加公司名
3. 目标价加目标窗口
4. 为何此时，前 3 条
5. KPI 快照，当前价、市盈率、EPS 增长、分析师评级
6. 投资逻辑加催化剂
7. 技术面摘要
8. 工具选择，首选、保守方案、备选方案
9. 期权结构，如适用
10. 早期退出区间，如适用
11. 风险标签
12. 监控状态
13. 验证摘要

### 3.2 中文优先的双语规则

- 所有区块标签以中文为主文本
- 英文翻译作为次要标签显示在同一元素上
- 所有标签均遵循中文斜杠 English 模式
- 主视图中无英文-only 标签
- 无乱码，所有字符串均定义在 strings_zh.py 和 strings_en.py 中，保持严格一一映射

### 3.3 可打印的 Executive 摘要风格

- 海报和 PDF 在标准浏览器打印时渲染正确
- 打印时颜色不丢失，使用 print-color-adjust exact
- 文字不超出页面边界
- 海报可在单张 A4 或 Letter 纸上完整打印
- PDF 分页规则正确，使用 page-break 规则

### 3.4 优质机构风格

- 无剪贴画、无卡通、无轻浮插图
- 清晰网格布局，区块边界分明
- 颜色语义：橙红色等于操作或警示，青绿色等于信心或支撑，深红色等于纯风险标签
- 排版：清晰无衬线字体的尺寸层级，大操作文字、小正文
- 无原始数据转储，每个显示数字均有标签

### 3.5 紧凑监控支持

- 海报页脚概览监控状态和验证，一目了然
- PDF 末页显示完整监控列表和验证表格
- 条目多时仍可阅读

### 3.6 无原始数据库转储感

- 每个表格行均有有意义的标签
- 空字段显示破折号而非空白
- 日期使用 YYYY-MM-DD 格式
- 百分比使用 XX% 格式，非小数

---

## 四、海报结构

海报为单张 A4 或 Letter 纸，分为三个视觉区块。

### 区块一 — 决策主角（顶部约百分之五十五）

作用：包含 3 秒决策所需的全部信息。

**操作区块**（左侧，主导）：

- 区块标签：操作 / Action
- 大号中文操作文字，如买入看涨
- 小号英文操作文字，如 Buy Call
- 下方信心徽章，如高信心 / HIGH CONVICTION

**代码区块**（右侧，顶部）：

- 大号代码符号，如 NVDA
- 下方公司名，小号文字

**目标加仓位区块**（右侧，中部）：

- 目标窗口 / Target Window，如 12个月
- 目标价 / Target Price，如 180 美元箭头 250 美元
- 建议仓位 / Suggested Size，如 15% Portfolio

**为何此时**（右侧，中下）：

- 区块标签：为何此时 / Why Now
- 最多 3 条编号要点
- 每条要点有中文主文字加英文次要文字

**风险标签行**（区块一底部，全宽）：

- 水平排列的风险标签行
- 每个标签：中文风险主文字加英文次要文字
- 背景：半透明深红色

### 区块二 — 详情卡片（中层约百分之三十五）

作用：包含 30 秒阅读所需的分析深度。

**KPI 卡片**（4 列网格）：

- 当前价 / Price
- 市盈率 / P/E
- EPS增长 / EPS Growth
- 分析师评级 / Analyst Rating

**投资逻辑加技术面**（2 列布局）：

- 左：投资逻辑 / Thesis and Catalysts，最多 4 条编号要点
- 右：技术分析 / Technical Analysis，支撑位、阻力位、趋势摘要

**工具选择**（5 列水平排列）：

- 每个格子显示一种工具类型
- 角色标签：首选 / PRIMARY、保守方案 / CONSERVATIVE、备选方案 / ALTERNATIVE
- 仅显示 3 种工具，首选加保守加备选，不显示全部 5 种

**期权结构**（单个紧凑卡片，仅在适用时显示）：

- 字段：到期日 / Expiry、行权价 / Strike、盈亏平衡 / Break-Even、Delta / Delta、提前退出 / Early Exit
- 5 列布局

**早期退出**（EarlyExitPlan 存在时显示）：

- 三个区间：首轮减仓 / First Trim、主要利润 / Main Profit、完全退出 / Full Exit
- 每个区间：操作加触发条件加目标收益率

### 区块三 — 状态页脚（底部约百分之十）

作用：包含监控上下文，轻量但始终显示。

**监控状态**（左侧）：

- 状态徽章：持仓中 / Held、重点关注 / High Priority、研究进行中 / Research、被动跟踪 / Passive
- 操作倾向 / Action Bias 标签和值

**验证摘要**（中间）：

- 市场状态 / Regime，如趋势向上 / Trend Up
- 验证信心 / Validation Confidence，如 78%
- 颜色编码：高等于青绿色，中等于橙红色

**品牌加时间戳**（右侧）：

- Hermes 研究台 / Hermes Research Desk
- 决策看板 / Decision Board
- 生成时间戳：YYYY-MM-DD HH:MM

---

## 五、PDF 报告结构

PDF 报告为多页文档。

### 第 1 页 — 批次总览

- 报告页眉：批次总览 / Batch Overview 加日期加数量
- 批次总览表格，列：优先级、代码、公司、评级、信心度百分比、操作倾向、目标价
- 表格下方为执行摘要文本块

### 第 2 页起 — 单个公司报告（每个代码一页）

每个公司报告页面以决策对象为主结构，不以旧交易计划为主结构。

页面主结构顺序如下：

**第一区块 — 决策卡片摘要**（页眉区块）：

- 代码加公司名（主导）
- 操作：大号中文主操作文字加英文，如买入看涨 / Buy Call
- 信心徽章：高信心 / HIGH CONVICTION
- 核心结论框（深色背景）：一行结论文字

**第二区块 — 工具选择详情**（首个主体区块）：

- 首选 / PRIMARY：工具名称、理由
- 保守方案 / CONSERVATIVE：工具名称、理由
- 备选方案 / ALTERNATIVE：工具名称、理由
- 阐明为何首选该工具、保守方案作为备选、其他方案被拒绝的原因

**第三区块 — 期权结构详情**（工具为期权时显示）：

- 期权类型 / Instrument，如牛市看涨价差 / Bull Call Spread
- 标的合约 / Primary Contract：到期月、行权价、期权类型
- 配对合约 / Short Contract（如适用）：到期月、行权价，如为价差或备兑场景
- 净 debit 或净 credit
- 盈亏平衡价 / Break-Even
- 最大盈利百分比 / Max Profit
- 最大亏损百分比 / Max Loss
- Delta 估值
- 提前退出摘要，EarlyExitPlan 的三个区间

**第四区块 — 支撑数据网格**（旧 signal 和 report 字段，仅作参考）：

- 入场价 / Entry Price，来自 signal.entry_price
- 止损价 / Stop Loss，来自 signal.stop_loss
- 目标价 / Target Price，来自 signal.take_profit
- 持仓周期 / Holding Horizon
- 以上字段作为支撑指标显示，不可作为页面主标题

**第五区块 — 看多逻辑**（来自 decision_card.thesis_summary 和 bull_case）：

- 编号要点形式，最多 4 条

**第六区块 — 风险观察**（来自 report.risk_watch）：

- 列表形式

### 末页 — 监控列表加验证

- 报告页眉：监控状态 / Watchlist and 验证摘要 / Validation Summary
- 监控列表表格，列：代码、操作倾向、状态、逻辑状态、预警级别
- 验证表格，列：代码、市场状态、历史支持、环境匹配、主要失效模式、信心度

---

## 六、数据映射

本节将 Hermes 规范对象映射到 UI 区块。

### decision_card（PositionDecisionCard）

| 字段 | UI 目标 |
|------|---------|
| primary_action | 海报区块一操作区块；PDF 公司页决策卡片摘要 |
| conviction | 海报区块一信心徽章 |
| thesis_summary | 海报区块二投资逻辑；PDF 公司页看多逻辑 |
| why_now | 海报区块一为何此时要点 |
| alternatives | 海报区块二工具选择已拒绝列 |

### instrument_recommendation（InstrumentRecommendation）

| 字段 | UI 目标 |
|------|---------|
| primary_action | 海报区块二工具选择首选格子；PDF 公司页工具选择首选 |
| ranked_alternatives | 海报区块二工具选择保守方案和备选方案格子；PDF 公司页对应项 |
| reason | 工具格子内理由文字；PDF 公司页工具理由说明 |

### options_structure（OptionsStructure）

| 字段 | UI 目标 |
|------|---------|
| instrument_action | 海报区块二期权结构卡片标签；PDF 公司页期权类型 |
| primary_contract.expiry_months | 海报区块二期权结构到期日；PDF 公司页标的合约到期月 |
| primary_contract.strike | 海报区块二期权结构行权价；PDF 公司页标的合约行权价 |
| primary_contract.option_type | PDF 公司页标的合约期权类型 |
| short_contract | PDF 公司页配对合约，价差或备兑场景 |
| strategy_net_debit | PDF 公司页净 debit |
| strategy_net_credit | PDF 公司页净 credit |
| break_even_price | 海报区块二期权结构盈亏平衡；PDF 公司页盈亏平衡价 |
| max_profit_pct | PDF 公司页最大盈利百分比 |
| max_loss_pct | PDF 公司页最大亏损百分比 |
| primary_contract.delta_estimate | 海报区块二期权结构 Delta |
| early_exit_summary | 海报区块二期权结构提前退出 |
| covered_by_shares | PDF 公司页备注，备兑看涨场景 |
| assignment_strike | PDF 公司页配对行权价，备兑看涨场景 |

### early_exit_plan（EarlyExitPlan）

| 字段 | UI 目标 |
|------|---------|
| primary_exit_trigger | 海报区块二早期退出区块；PDF 公司页提前退出摘要 |
| severity | 海报区块二早期退出严重性标签 |
| primary_reason | 海报区块二早期退出理由文字 |
| first_trim | 海报区块二早期退出首轮减仓区间；PDF 公司页三个区间 |
| main_profit | 海报区块二早期退出主要利润区间；PDF 公司页三个区间 |
| full_exit | 海报区块二早期退出完全退出区间；PDF 公司页三个区间 |

### watchlist_entry（WatchlistEntry）

| 字段 | UI 目标 |
|------|---------|
| ticker | 海报区块三监控状态；PDF 末页 |
| status | 海报区块三状态徽章 |
| thesis_state | 海报区块三逻辑状态标签；PDF 末页 |
| alert_level | 海报区块三预警标签；PDF 末页 |
| current_action_bias | 海报区块三操作倾向标签 |

### validation（ValidationResult）

| 字段 | UI 目标 |
|------|---------|
| regime | 海报区块三验证区块市场状态；PDF 末页 |
| validation_confidence | 海报区块三验证区块信心度百分比；PDF 末页 |
| historical_support | PDF 末页验证表格 |
| environment_fit | PDF 末页验证表格 |
| main_failure_mode | PDF 末页验证表格 |

### Legacy 支撑字段（仅作支撑数据，不可作为页面主结构）

| 字段 | 用途说明 |
|------|---------|
| signal.ticker | 所有页面用于标识公司 |
| signal.entry_price | 支撑数据网格入场价 |
| signal.stop_loss | 支撑数据网格止损价 |
| signal.take_profit | 支撑数据网格目标价 |
| signal.holding_horizon | 支撑数据网格持仓周期 |
| report.company_name | 所有页面显示公司全称 |
| report.executive_summary | PDF 第 1 页执行摘要文本块 |

---

## 七、双语规则

### 中文优先，英文为辅

所有标签遵循中文斜杠 English 模式。

示例：

- 操作 / Action
- 为何此时 / Why Now
- 核心结论 / Bottom Line
- 看多逻辑 / Bull Case
- 风险观察 / Risk Watch
- 期权结构 / Options Structure
- 提前退出 / Early Exit
- 监控状态 / Watchlist
- 验证摘要 / Validation

### 术语一致性

以下术语固定，不可跨 UI 使用不同译法：

| 中文 | English | 应用场景 |
|------|---------|---------|
| 买入股票 | Buy Stock | 操作 |
| 买入看涨 | Buy Call | 工具 |
| 牛市看涨价差 | Bull Call Spread | 工具 |
| 卖出备兑看跌 | Sell Cash-Secured Put | 工具 |
| 备兑看涨 | Covered Call | 工具 |
| 观望 | Watchlist | 操作 |
| 不交易 | No Trade | 操作 |
| 高信心 | HIGH CONVICTION | 信心度 |
| 中信心 | MEDIUM CONVICTION | 信心度 |
| 低信心 | LOW CONVICTION | 信心度 |
| 首选 | PRIMARY | 工具角色 |
| 保守方案 | CONSERVATIVE | 工具角色 |
| 备选方案 | ALTERNATIVE | 工具角色 |
| 持仓中 | Held | 监控状态 |
| 重点关注 | High Priority | 监控状态 |
| 研究进行中 | Research In Progress | 监控状态 |
| 被动跟踪 | Passive Watch | 监控状态 |
| 逻辑强化 | Strengthening | 逻辑状态 |
| 逻辑稳定 | Stable | 逻辑状态 |
| 逻辑弱化 | Weakening | 逻辑状态 |
| 逻辑破坏 | Broken | 逻辑状态 |
| 趋势向上 | Trend Up | 市场状态 |
| 区间震荡 | Range Bound | 市场状态 |
| 高波动 | High Volatility | 市场状态 |
| 风险规避 | Risk Off | 市场状态 |

### 无混合编码

- 所有字符串定义在 strings_zh.py（中文）和 strings_en.py（英文）
- 渲染时加载两者并一一映射
- 无任何字符串通过拼接字节组装
- 所有 HTML 文件声明 meta charset 等于 utf-8，保存为 UTF-8

---

## 八、视觉系统

### 色彩方案

```css
/* 主要操作色，橙红色 */
--color-action: #E85A3C;

/* 正面、信心度、支撑，青绿色 */
--color-positive: #2DD4A8;

/* 纯风险色，深红色 */
--color-risk: #C0392B;

/* 主背景，暖白 */
--color-bg: #FAF8F5;

/* 卡片和面板背景，白色 */
--color-panel: #FFFFFF;

/* 页眉和页脚背景，深炭色 */
--color-header: #1C1C1E;
--color-footer: #1C1C1E;

/* 正文，深中性色 */
--color-text: #1A1A1A;

/* 次要和辅助文字，灰色 */
--color-text-secondary: #6B7280;

/* 深色背景上文字，白色 */
--color-text-inverse: #FFFFFF;
```

### 排版

```css
/* 主 UI 字体，CJK 兼容无衬线 */
--font-main: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;

/* 数字和金融数据 */
--font-numbers: "SF Pro Display", "Helvetica Neue", Arial, sans-serif;

/* 等宽字体，代码和代码符号 */
--font-mono: "SF Mono", "Consolas", monospace;
```

字号层级：

- 操作文字大号，56px，font-weight 800
- 操作副文字，28px，font-weight 300
- 代码符号，28px，font-weight 700
- 区块标签中文，13px，font-weight 700
- 区块标签英文，10px，font-weight 400
- 正文，12px
- 小标签，10px

### 间距系统

```css
--space-xs: 4px;
--space-sm: 8px;
--space-md: 16px;
--space-lg: 24px;
--space-xl: 32px;
```

### 标签徽章卡片样式

**状态徽章**（用于监控状态）：

- Held（持仓中），青绿色背景百分之十五透明度，实色青绿文字
- High Priority（重点关注），橙红色背景百分之十五透明度，实色橙红文字
- Research（研究进行中），琥珀色背景百分之十五透明度，实色琥珀文字
- Passive（被动跟踪），灰色背景百分之十透明度，实色灰色文字

**信心徽章**（海报区块一）：

- 2px solid 边框，颜色为 --color-positive
- 透明背景
- 中文信心文字加英文副文字

**风险标签**（海报区块一）：

- 深红色边框
- 半透明深红色背景
- 中文风险主文字加英文次要文字

**KPI 卡片**（海报区块二）：

- 白色背景
- 顶部 3px 边框，颜色为 --color-positive
- 4px 圆角
- 轻阴影

**区块卡片**（海报区块二）：

- 白色背景
- 左侧强调线，3px --color-action 垂直线
- 中文区块标签加粗加英文区块标签浅色

### 工具层级规则

工具行最多按优先级显示 3 种工具：

1. 首选 / PRIMARY：橙红色边框，浅橙红色背景 tint，橙红色角色标签
2. 保守方案 / CONSERVATIVE：青绿色边框，浅青绿色背景 tint，青绿色角色标签
3. 备选方案 / ALTERNATIVE：灰色边框，无背景 tint，灰色角色标签

已拒绝的工具不在海报工具行中显示。

---

## 九、技术分析渲染规则

### 仅 boss 可读

技术分析区块是摘要，而非指标转储。

### 应显示的内容

- 支撑位：单一价格水平或区间，如 165 到 170 美元
- 阻力位：单一价格水平或区间，如 220 到 225 美元
- 趋势：简短方向短语，如上升趋势 / Uptrend 或区间震荡 / Range Bound
- 动能（如有）：简短短语，如动能较强 / Strong Momentum

### 不应显示的内容

- 无原始指标值，RSI、MACD、布林线值等
- 无超出单一趋势标签的图表描述
- 无多时间周期分析，除非可压缩为一句短语

### 渲染模式

```
支撑位 / Support: 165-170 美元
阻力位 / Resistance: 220-225 美元
趋势 / Trend: 上升趋势 / Uptrend
```

---

## 十、分页和打印规则

### 海报

- 固定宽高比，3 比 4，竖向
- 按 A4 或 Letter 尺寸渲染，视地区而定
- overflow hidden 防止内容溢出页面
- page size A4 portrait margin 0 消除浏览器边距

### PDF 报告

- 页面尺寸，A4 竖向，标准边距 15mm
- 每个报告页非末页使用 page-break-after always
- 公司报告卡片使用 page-break-inside avoid 防止中途分页
- 末页使用 page-break-after auto

### 整体规则

以下元素不可跨页分隔：

- 公司报告卡片，尽量保持在同一页
- 监控列表表头，与首行一起保留
- 验证表格表头，与首行一起保留
- 核心结论框，整体保留

### 分隔约束

- 批次总览表格允许在行间分页
- 交易计划网格 4 列仅在绝对必要时才在列间分页
- 工具行不可在行中分隔

---

## 十一、非目标

本规范明确不包含：

- 新交易逻辑，无新的买入或卖出或等待决策算法
- 新验证逻辑，无新的验证引擎实现
- 流程重新设计，编排器、子代理执行器、证据库不在范围内
- 新数据源，Futu 仍为主要市场数据提供方
- 自动执行，无券商集成或下单功能
- 熊市表面，系统保持牛市 only 和预警 only
- 营销落地页，本界面非营销文档
- PPT 演示，幻灯片不是目标产出
- 实时流 UI，本规范仅覆盖打印和导出表面，不含实时 Web 看板

---

## 十二、验收标准

### 通用标准

- 所有文字中文优先、英文辅佐，遵循中文斜杠 English 模式
- 无乱码，所有字符串来自 strings_zh.py 和 strings_en.py
- 无原始数据库转储或无格式数字
- 空字段显示破折号而非空白
- 屏幕和打印颜色渲染正确

### 海报标准

- 海报在 A4 竖向尺寸下正确渲染，无溢出
- 区块一包含 3 秒决策所需的全部信息
- 区块二包含 KPI、投资逻辑、技术面、工具、期权、早期退出
- 区块三包含监控状态和验证摘要
- 工具行最多显示 3 种工具，首选加保守方案加备选方案
- 风险标签出现在区块一，可读
- 打印海报可在单页完整呈现

### PDF 报告标准

- 第 1 页显示批次总览表格和执行摘要
- 第 2 页起每个代码单独一页
- 末页显示监控列表表格和验证表格
- 公司报告主结构顺序为决策卡片摘要、工具选择详情、期权结构详情（仅期权时）、支撑数据网格、看多逻辑、风险观察
- 旧版交易计划网格不在公司页主结构中
- Table headers repeat on page break if table continues
- page-break CSS 规则在 Edge headless PDF 导出中正确生效

### 数据映射标准

- PositionDecisionCard 字段正确填充对应海报区块
- InstrumentRecommendation 正确标记首选、保守方案、备选方案
- OptionsStructure 正确渲染期权类型、标的合约、配对合约、盈亏平衡、最大盈利、最大亏损、Delta
- EarlyExitPlan 以三个区间正确渲染早期退出区块
- WatchlistEntry 正确填充海报页脚状态徽章和报告末页表格
- ValidationResult 正确填充海报页脚验证标签和报告末页表格
- Legacy signal 和 report 字段作为支撑数据，不可作为页面主结构

### 双语标准

- 所有区块标签中文优先、英文辅佐
- 工具名称使用固定术语表，无同义词
- 监控状态使用固定术语表
- 日期使用 YYYY-MM-DD 格式
- 百分比使用 XX% 格式

### 视觉标准

- 操作色 #E85A3C 仅用于主要操作和强调
- 正面色 #2DD4A8 仅用于信心度、支撑和正面指标
- 风险色 #C0392B 仅用于风险标签和亏损指标
- 字体栈包含 Noto Sans SC 以支持 CJK
- 所有交互和装饰色通过 print-color-adjust exact 验证

### 技术标准

- export_poster_pdf 正确接收所有决策对象
- export_batch_report_pdf 正确接收所有决策对象
- render_boss_poster 正确接收所有决策对象
- render_batch_report 正确接收所有决策对象
- Edge headless PDF 导出生成有效 PDF 文件
- 现有 export_task_pdf 函数无回归

---

## 附录：文件目标

本规范管理以下文件的更改：

| 文件 | 职责 |
|------|------|
| agent/research_v1/report_templates/renderer.py | 海报和批次报告渲染逻辑 |
| agent/research_v1/report_templates/boss_poster_base.html | 海报 HTML 模板 |
| agent/research_v1/report_templates/boss_report_base.html | 批次报告 HTML 模板 |
| agent/research_v1/report_templates/boss_report_pdf.css | 海报和报告共享 CSS |
| agent/research_v1/report_templates/strings_zh.py | 中文字符串常量 |
| agent/research_v1/report_templates/strings_en.py | 英文字符串常量 |
| agent/research_v1/report_pdf.py | PDF 导出函数，无业务逻辑更改 |

agent/research_v1 下其他文件不在本次重新设计范围内。
