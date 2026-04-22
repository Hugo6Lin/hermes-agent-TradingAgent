# Hermes 报告界面设计规范

**日期：** 2026-04-22
**阶段：** 报告界面设计
**状态：** 初稿

---

## 一、目的

Hermes 报告界面是 boss 做出投资决策的最终产物表面。它将完整的牛市决策流程转化为两种输出模式。第一种是海报视图，这是一张单页决策看板，优先保证 3 秒内理解完整决策内容，同时支持直接打印在单张 A4 或 Letter 纸上。第二种是 PDF 报告视图，这是一份多页 executive 报告，优先保证存档可查和投委会分发阅读。

本界面不替代幻灯片，因为幻灯片暗示演示节奏、内容密度不可控、打印效果差、不适合存档。海报加 PDF 的组合既给了 boss 一张无需导航的决策卡，也给了投委会一份可分页存档的完整记录。

---

## 二、目标读者

主要读者是 boss 或投委会主任，这两类人仅需要阅读海报即可做出判断。次要读者是操作员或分析师，这类人可以在需要时阅读完整的 PDF 报告以了解背后的研究深度。

boss 在 3 秒内必须看清：操作是什么（六个合法操作之一）、信心度是高还是中还是低、标的是哪只股票、目标价和目标窗口是什么、为何现在必须行动的最核心原因。

boss 在 30 秒内可以看清：为何选择这个工具而非其他备选、期权结构是什么（如有）、早期退出计划是什么、主要风险是什么、当前监控状态和验证结论是什么。

超过 60 秒才能理解的内容不在本表面范围，深度研究应归属分析师级视图。

---

## 三、设计原则

### 3.1 决策优先的信息层级

信息按重要性排序，依次为：操作加信心度（最主导）、代码加公司名、目标价加目标窗口、为何此时（前三条）、KPI 快照（当前价、市盈率、EPS 增长、分析师评级）、投资逻辑加催化剂、技术面摘要、工具选择（首选保守备选）、期权结构（如适用）、早期退出区间（如适用）、风险标签、监控状态、验证摘要。

### 3.2 中文优先的双语规则

所有区块标签以中文为主文本，英文作为次要标签写在同一元素上，格式统一为中文斜杠 English。主视图中不存在英文单独成行的情况。无乱码，所有字符串统一在 strings_zh.py 和 strings_en.py 中定义。

### 3.3 可打印的 Executive 摘要风格

海报和 PDF 均支持标准浏览器打印，颜色通过 print-color-adjust exact 保持不丢失，文字不超出页面边界，海报可完整打印在单页，PDF 使用 page-break 规则实现正确分页。

### 3.4 优质机构风格

不使用剪贴画、卡通或轻浮插图。布局采用清晰网格，区块之间边界分明。颜色语义固定：橙红色代表操作或警示，青绿色代表信心或支撑，深红色仅用于风险标签。正文采用清晰无衬线字体，通过字号差异建立层级。无任何原始数据无格式转储，所有数字均有对应标签。

### 3.5 紧凑监控支持

海报页脚（底部区块）概览监控状态和验证结论，一目了然。PDF 末页提供完整的监控列表和验证表格。条目数量较多时仍然可读。

### 3.6 无数据库转储感

每个表格行均有有意义的标签。空字段显示破折号而非空白。日期使用 YYYY-MM-DD 格式。百分比使用 XX% 格式。

---

## 四、海报结构

海报为单张 A4 或 Letter 纸，分成三个垂直堆叠的视觉区块。

### 区块一 — 决策主角（顶部约百分之五十五）

这个区块包含 boss 做 3 秒决策所需的全部信息，分为五个部分。

第一部分为操作区块，位于左侧主导位置。区块标签为操作 / Action，大号中文操作文字例如买入看涨，小号英文操作文字例如 Buy Call，下方附信心徽章如高信心 / HIGH CONVICTION。

第二部分为代码区块，位于右侧顶部。大号代码符号例如 NVDA，下方附公司名以小号文字呈现。

第三部分为目标加仓位区块，位于右侧中部。包括目标窗口 / Target Window 如 12个月，目标价 / Target Price 如 180 美元到 250 美元，建议仓位 / Suggested Size 如 15% Portfolio。

第四部分为为何此时，位于右侧中下。区块标签为为何此时 / Why Now，最多 3 条编号要点，每条含中文主文字加英文次要文字。

第五部分为风险标签行，位于区块一底部、全宽。水平排列风险标签，每个含中文主文字加英文次要文字，背景为半透明深红色。

### 区块二 — 详情卡片（中层约百分之三十五）

这个区块包含 30 秒深度阅读所需的分析内容，分五个部分。

第一部分为 KPI 卡片，4 列网格排列，分别是当前价 / Price、市盈率 / P/E、EPS增长 / EPS Growth、分析师评级 / Analyst Rating。

第二部分为投资逻辑加技术面，采用 2 列布局。左列为投资逻辑 / Thesis and Catalysts，最多 4 条编号要点。右列为技术分析 / Technical Analysis，展示支撑位、阻力位、趋势摘要。

第三部分为工具选择，5 列水平排列，每个格子显示一种工具类型。角色标签分别为首选 / PRIMARY、保守方案 / CONSERVATIVE、备选方案 / ALTERNATIVE，已拒绝的工具不显示。最多展示 3 种工具（首选加保守加备选）。

第四部分为期权结构，单个紧凑卡片，仅在实际为期权工具时显示。包含 5 列字段：到期日 / Expiry、行权价 / Strike、盈亏平衡 / Break-Even、Delta / Delta、提前退出 / Early Exit。

第五部分为早期退出，EarlyExitPlan 存在时显示。分为三个区间：首轮减仓 / First Trim、主要利润 / Main Profit、完全退出 / Full Exit。每个区间含操作加触发条件加目标收益率。

### 区块三 — 状态页脚（底部约百分之十）

这个区块包含监控上下文，轻量但始终可见，分三个部分。

第一部分为监控状态，位于左侧。状态徽章分别为持仓中 / Held、重点关注 / High Priority、研究进行中 / Research、被动跟踪 / Passive，另附操作倾向 / Action Bias 标签和对应值。

第二部分为验证摘要，位于中间。市场状态 / Regime 如趋势向上 / Trend Up，验证信心 / Validation Confidence 如 78%，颜色编码高等于青绿色、中等于橙红色。

第三部分为品牌加时间戳，位于右侧。显示 Hermes 研究台 / Hermes Research Desk、决策看板 / Decision Board，以及生成时间戳 YYYY-MM-DD HH:MM。

---

## 五、PDF 报告结构

PDF 报告为多页文档。

### 第 1 页 — 批次总览

报告页眉为批次总览 / Batch Overview，附日期和数量。然后是批次总览表格，含列：优先级、代码、公司、评级、信心度百分比、操作倾向、目标价。表格下方为执行摘要文本块。

### 第 2 页起 — 单个公司报告（每代码一页）

每个公司报告页面以决策对象为主结构，不以旧版交易计划为主结构。页面顺序严格固定如下。

第一区块为决策卡片摘要，这是页眉区块。内容依次为：代码加公司名（主导）、操作（大号中文主操作文字加英文，例如买入看涨 / Buy Call）、信心徽章（高信心 / HIGH CONVICTION）、核心结论框（深色背景，一行结论文字）。

第二区块为工具选择详情，这是首个主体区块。依次展示：首选 / PRIMARY（工具名称和理由）、保守方案 / CONSERVATIVE（工具名称和理由）、备选方案 / ALTERNATIVE（工具名称和理由），并附说明阐明为何首选该工具、保守方案作为备选的理由、以及其他方案被拒绝的原因。

第三区块为期权结构详情，仅在工具为期权时显示。内容依次为期权类型 / Instrument（如牛市看涨价差 / Bull Call Spread）、标的合约 / Primary Contract（到期月、行权价、期权类型）、配对合约 / Short Contract（如适用，用于价差或备兑场景，到期月和行权价）、净 debit 或净 credit、盈亏平衡价 / Break-Even、最大盈利百分比 / Max Profit、最大亏损百分比 / Max Loss、Delta 估值、以及提前退出摘要（EarlyExitPlan 的三个区间）。

第四区块为支撑数据网格，这是旧 signal 和 report 字段的参考区域，不作为页面主结构。内容依次为：入场价 / Entry Price（来自 signal.entry_price）、止损价 / Stop Loss（来自 signal.stop_loss）、目标价 / Target Price（来自 signal.take_profit）、持仓周期 / Holding Horizon（来自 signal.holding_horizon）。这些字段作为支撑指标参考，不可作为页面主标题。

第五区块为看多逻辑，来自 decision_card.thesis_summary 和 bull_case，以编号要点形式呈现，最多 4 条。

第六区块为风险观察，来自 report.risk_watch，以列表形式呈现。

### 末页 — 监控列表加验证

报告页眉为监控状态 / Watchlist and 验证摘要 / Validation Summary。监控列表表格含列：代码、操作倾向、状态、逻辑状态、预警级别。验证表格含列：代码、市场状态、历史支持、环境匹配、主要失效模式、信心度。

---

## 六、数据映射

### decision_card（PositionDecisionCard）

primary_action 映射到海报区块一操作区块和 PDF 公司页决策卡片摘要。conviction 映射到海报区块一信心徽章。thesis_summary 映射到海报区块二投资逻辑和 PDF 公司页看多逻辑。why_now 映射到海报区块一为何此时要点。alternatives 映射到海报区块二工具选择已拒绝列。

### instrument_recommendation（InstrumentRecommendation）

primary_action 映射到海报区块二工具选择首选格子和 PDF 公司页工具选择首选。ranked_alternatives 映射到海报区块二工具选择保守方案和备选方案格子以及 PDF 公司页对应项。reason 映射到工具格子内理由文字和 PDF 公司页工具理由说明。

### options_structure（OptionsStructure）

instrument_action 映射到海报区块二期权结构卡片标签和 PDF 公司页期权类型。primary_contract.expiry_months 映射到海报区块二期权结构到期日和 PDF 公司页标的合约到期月。primary_contract.strike 映射到海报区块二期权结构行权价和 PDF 公司页标的合约行权价。primary_contract.option_type 映射到 PDF 公司页标的合约期权类型。short_contract（配对空头合约）映射到 PDF 公司页配对合约，用于价差或备兑场景。strategy_net_debit 映射到 PDF 公司页净 debit。strategy_net_credit 映射到 PDF 公司页净 credit。break_even_price 映射到海报区块二期权结构盈亏平衡和 PDF 公司页盈亏平衡价。max_profit_pct 映射到 PDF 公司页最大盈利百分比。max_loss_pct 映射到 PDF 公司页最大亏损百分比。primary_contract.delta_estimate 映射到海报区块二期权结构 Delta。early_exit_summary 映射到海报区块二期权结构提前退出。covered_by_shares 映射到 PDF 公司页备注，用于备兑看涨场景。assignment_strike 映射到 PDF 公司页配对行权价，用于备兑看涨场景。

### early_exit_plan（EarlyExitPlan）

primary_exit_trigger 映射到海报区块二早期退出区块和 PDF 公司页提前退出摘要。severity 映射到海报区块二早期退出严重性标签。primary_reason 映射到海报区块二早期退出理由文字。first_trim（含 zone_name、action、target_return_pct、trigger_condition）映射到海报区块二早期退出首轮减仓区间和 PDF 公司页三个区间。main_profit（含 zone_name、action、target_return_pct、trigger_condition）映射到海报区块二早期退出主要利润区间和 PDF 公司页三个区间。full_exit（含 zone_name、action、target_return_pct、trigger_condition）映射到海报区块二早期退出完全退出区间和 PDF 公司页三个区间。

### watchlist_entry（WatchlistEntry）

ticker 映射到海报区块三监控状态和 PDF 末页。status 映射到海报区块三状态徽章。thesis_state 映射到海报区块三逻辑状态标签和 PDF 末页。alert_level 映射到海报区块三预警标签和 PDF 末页。current_action_bias 映射到海报区块三操作倾向标签。

### validation（ValidationResult）

regime 映射到海报区块三验证区块市场状态和 PDF 末页。validation_confidence 映射到海报区块三验证区块信心度百分比和 PDF 末页。historical_support 映射到 PDF 末页验证表格。environment_fit 映射到 PDF 末页验证表格。main_failure_mode 映射到 PDF 末页验证表格。

### Legacy 支撑字段（仅作支撑数据，不可作为页面主结构）

signal.ticker 用于所有页面标识公司。signal.entry_price 作为支撑数据网格入场价。signal.stop_loss 作为支撑数据网格止损价。signal.take_profit 作为支撑数据网格目标价。signal.holding_horizon 作为支撑数据网格持仓周期。report.company_name 用于所有页面显示公司全称。report.executive_summary 用于 PDF 第 1 页执行摘要文本块。

---

## 七、双语规则

### 中文优先，英文为辅

所有标签格式统一为中文斜杠 English。示例标签包括：操作 / Action、为何此时 / Why Now、核心结论 / Bottom Line、看多逻辑 / Bull Case、风险观察 / Risk Watch、期权结构 / Options Structure、提前退出 / Early Exit、监控状态 / Watchlist、验证摘要 / Validation。

### 术语一致性

术语表固定，全系统统一，不可出现同义词或不同译法。

操作类：买入股票 / Buy Stock、买入看涨 / Buy Call、牛市看涨价差 / Bull Call Spread、卖出备兑看跌 / Sell Cash-Secured Put、备兑看涨 / Covered Call、观望 / Watchlist、不交易 / No Trade。

信心度类：高信心 / HIGH CONVICTION、中信心 / MEDIUM CONVICTION、低信心 / LOW CONVICTION。

工具角色类：首选 / PRIMARY、保守方案 / CONSERVATIVE、备选方案 / ALTERNATIVE。

监控状态类：持仓中 / Held、重点关注 / High Priority、研究进行中 / Research In Progress、被动跟踪 / Passive Watch。

逻辑状态类：逻辑强化 / Strengthening、逻辑稳定 / Stable、逻辑弱化 / Weakening、逻辑破坏 / Broken。

市场状态类：趋势向上 / Trend Up、区间震荡 / Range Bound、高波动 / High Volatility、风险规避 / Risk Off。

### 无混合编码

所有字符串统一在 strings_zh.py（中文）和 strings_en.py（英文）中定义，渲染时加载两者并一一映射。无任何字符串通过字节拼接组装。所有 HTML 文件声明 meta charset 等于 utf-8，并保存为 UTF-8 编码。

---

## 八、视觉系统

### 色彩方案

橙红色为主要操作色，代码为 #E85A3C，用于操作和警示。青绿色为正面色，代码为 #2DD4A8，用于信心度、支撑和正面指标。深红色为纯风险色，代码为 #C0392B，仅用于风险标签。暖白色为主背景，代码为 #FAF8F5。白色为卡片和面板背景，代码为 #FFFFFF。深炭色为页眉和页脚背景，代码为 #1C1C1E。深中性色为正文，代码为 #1A1A1A。灰色为次要和辅助文字，代码为 #6B7280。白色为深色背景上文字，代码为 #FFFFFF。

### 排版

主 UI 字体采用 CJK 兼容无衬线字体栈：Noto Sans SC、PingFang SC、Microsoft YaHei、Helvetica Neue、Arial、sans-serif。数字和金融数据采用 SF Pro Display、Helvetica Neue、Arial、sans-serif。等宽字体用于代码和代码符号：SF Mono、Consolas、monospace。

字号层级：操作文字大号为 56px、font-weight 800，操作副文字为 28px、font-weight 300，代码符号为 28px、font-weight 700，区块标签中文为 13px、font-weight 700，区块标签英文为 10px、font-weight 400，正文为 12px，小标签为 10px。

### 间距系统

间距常数定义如下：--space-xs 为 4px、--space-sm 为 8px、--space-md 为 16px、--space-lg 为 24px、--space-xl 为 32px。

### 标签徽章卡片样式

状态徽章用于监控状态。Held（持仓中）使用青绿色背景百分之十五透明度配实色青绿文字。High Priority（重点关注）使用橙红色背景百分之十五透明度配实色橙红文字。Research（研究进行中）使用琥珀色背景百分之十五透明度配实色琥珀文字。Passive（被动跟踪）使用灰色背景百分之十透明度配实色灰色文字。

信心徽章用于海报区块一，使用 2px solid 边框颜色为 --color-positive，透明背景，中文加英文双层文字。

风险标签用于海报区块一，深红色边框配半透明深红色背景，中文主文字加英文次要文字。

KPI 卡片用于海报区块二，白色背景，顶部 3px 边框颜色为 --color-positive，4px 圆角配轻阴影。

区块卡片用于海报区块二，白色背景，左侧 3px --color-action 垂直强调线，中文加粗标签配浅色英文标签。

### 工具层级规则

工具行最多显示 3 种工具，按优先级排序。首选 / PRIMARY 使用橙红色边框、浅橙红色背景 tint、橙红色角色标签。保守方案 / CONSERVATIVE 使用青绿色边框、浅青绿色背景 tint、青绿色角色标签。备选方案 / ALTERNATIVE 使用灰色边框、无背景 tint、灰色角色标签。已拒绝的工具不在海报工具行中显示。

---

## 九、技术分析渲染规则

### 仅 boss 可读

技术分析区块是摘要，而非指标数据转储。

### 应显示的内容

支撑位：单一价格水平或区间，例如 165 到 170 美元。阻力位：单一价格水平或区间，例如 220 到 225 美元。趋势：简短方向短语，例如上升趋势 / Uptrend 或区间震荡 / Range Bound。动能（如有）：简短短语，例如动能较强 / Strong Momentum。

### 不应显示的内容

不显示原始指标值（RSI、MACD、布林线值等）。不显示超出单一趋势标签的图表描述。不显示多时间周期分析（除非压缩为一句短语）。

### 渲染模式

格式为三行文字：支撑位 / Support 加数字，阻力位 / Resistance 加数字，趋势 / Trend 加短语。

---

## 十、分页和打印规则

### 海报

固定宽高比为 3 比 4（竖向）。按 A4 或 Letter 尺寸渲染（视地区而定）。使用 overflow hidden 防止内容溢出页面。使用 page size A4 portrait margin 0 消除浏览器默认边距。

### PDF 报告

页面尺寸为 A4 竖向，标准边距 15mm。每个报告页（非末页）使用 page-break-after always。公司报告卡片使用 page-break-inside avoid 防止中途分页。末页使用 page-break-after auto。

### 整体规则

以下元素不可跨页分隔：公司报告卡片（尽量保持在同一页）、监控列表表头（与首行一起保留）、验证表格表头（与首行一起保留）、核心结论框（整体保留）。

### 分隔约束

批次总览表格允许在行间分页。交易计划网格（4 列）仅在绝对必要时才在列间分页。工具行不可在行中分隔。

---

## 十一、非目标

本规范明确不包含以下内容：不增加新交易逻辑（无新的买入、卖出、等待决策算法）；不增加新验证逻辑（无新的验证引擎实现）；不重新设计流程（编排器、子代理执行器、证据库不在范围内）；不引入新数据源（Futu 仍为主要市场数据提供方）；不实现自动执行（无券商集成或下单功能）；不支持熊市表面（系统保持牛市 only 和预警 only）；不制作营销落地页（本界面非营销文档）；不制作 PPT 演示（幻灯片不是目标产出）；不支持实时流 UI（本规范仅覆盖打印和导出表面，不含实时 Web 看板）。

---

## 十二、验收标准

### 通用标准

所有文字中文优先、英文辅佐，遵循中文斜杠 English 模式。无乱码，所有字符串来自 strings_zh.py 和 strings_en.py。无原始数据库转储或无格式数字。空字段显示破折号而非空白。屏幕和打印颜色渲染正确。

### 海报标准

海报在 A4 竖向尺寸下正确渲染无溢出。区块一包含 3 秒决策所需的全部信息。区块二包含 KPI、投资逻辑、技术面、工具、期权、早期退出。区块三包含监控状态和验证摘要。工具行最多显示 3 种工具（首选加保守加备选）。风险标签出现在区块一且可读。打印海报可在单页完整呈现。

### PDF 报告标准

第 1 页显示批次总览表格和执行摘要。第 2 页起每个代码单独一页。末页显示监控列表表格和验证表格。公司报告主结构顺序固定为：决策卡片摘要、工具选择详情、期权结构详情（仅期权时）、支撑数据网格、看多逻辑、风险观察。旧版交易计划网格不在公司页主结构中。表格跨页时表头重复显示。page-break CSS 规则在 Edge headless PDF 导出中正确生效。

### 数据映射标准

PositionDecisionCard 字段正确填充对应海报区块。InstrumentRecommendation 正确标记首选、保守方案、备选方案。OptionsStructure 正确渲染期权类型、标的合约、配对合约、盈亏平衡、最大盈利、最大亏损、Delta。EarlyExitPlan 以三个区间正确渲染早期退出区块。WatchlistEntry 正确填充海报页脚状态徽章和报告末页表格。ValidationResult 正确填充海报页脚验证标签和报告末页表格。Legacy signal 和 report 字段作为支撑数据，不可作为页面主结构。

### 双语标准

所有区块标签中文优先、英文辅佐。工具名称使用固定术语表，无同义词。监控状态使用固定术语表。日期使用 YYYY-MM-DD 格式。百分比使用 XX% 格式。

### 视觉标准

操作色 #E85A3C 仅用于主要操作和强调。正面色 #2DD4A8 仅用于信心度、支撑和正面指标。风险色 #C0392B 仅用于风险标签和亏损指标。字体栈包含 Noto Sans SC 以支持 CJK。所有交互和装饰色通过 print-color-adjust exact 验证。

### 技术标准

export_poster_pdf 正确接收所有决策对象。export_batch_report_pdf 正确接收所有决策对象。render_boss_poster 正确接收所有决策对象。render_batch_report 正确接收所有决策对象。Edge headless PDF 导出生成有效 PDF 文件。现有 export_task_pdf 函数无回归。

---

## 附录：文件目标

本规范管理以下文件的更改：agent/research_v1/report_templates/renderer.py 负责海报和批次报告渲染逻辑；agent/research_v1/report_templates/boss_poster_base.html 负责海报 HTML 模板；agent/research_v1/report_templates/boss_report_base.html 负责批次报告 HTML 模板；agent/research_v1/report_templates/boss_report_pdf.css 负责海报和报告共享 CSS；agent/research_v1/report_templates/strings_zh.py 负责中文字符串常量；agent/research_v1/report_templates/strings_en.py 负责英文字符串常量；agent/research_v1/report_pdf.py 负责 PDF 导出函数（无业务逻辑更改）。

agent/research_v1 下其他文件不在本次重新设计范围内。
