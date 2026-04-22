# Hermes 报告界面设计规范（Clean）

**日期：** 2026-04-22  
**阶段：** 报告界面重设计  
**状态：** 可实施版本

---

## 一、目标

### 1.1 这份规范解决什么问题

Hermes 现有报告输出更像技术导出页，而不是老板可直接阅读的决策简报。  
本规范定义一套新的报告界面系统，用于把 Hermes 已有的 bullish decision pipeline 结果，整理成：

1. 单页 Boss Poster
2. 可打印 PDF 报告
3. 后续可复用的固定 Web UI 模板

这套界面的目标不是展示“系统做了什么”，而是帮助老板快速回答：

- 现在该不该做
- 该做什么
- 为什么现在做
- 风险在哪里
- 如果做了，后续怎么观察和处理

### 1.2 面向谁

主要读者：

- 老板
- 投资委员会
- 负责执行和跟踪的操作人员

次要读者：

- 分析师
- 维护 Hermes 的开发者

### 1.3 为什么是 Poster + PDF，不是 PPT

PPT 不适合这个场景，原因如下：

- PPT 默认是演示逻辑，不是决策逻辑
- PPT 容易把内容切碎到很多页，降低“一眼看清”的能力
- PPT 打印效果不稳定
- PPT 不适合做标准化、批量化、自动化导出

Poster + PDF 更适合 Hermes：

- Poster 负责 3 秒钟决策理解
- PDF 负责 30 到 60 秒深读
- 两者都适合浏览器打印和归档
- 两者都能稳定模板化和自动生成

---

## 二、产品边界

### 2.1 这不是新交易逻辑

本规范只定义报告界面和信息呈现，不新增：

- 新的交易信号算法
- 新的 thesis 评分逻辑
- 新的 validation 评分逻辑
- 新的做空能力
- 自动交易
- 自动平仓

### 2.2 必须遵守的 Hermes 边界

报告界面必须完整继承 Hermes 已批准的边界：

- bullish-only
- alert-only
- equity thesis first
- options are derivative expression of equity thesis

### 2.3 正式动作集合

界面允许出现且必须被正确呈现的动作只有：

- 买入股票 / Buy Stock
- 买入看涨 / Buy Call
- 牛市看涨价差 / Bull Call Spread
- 卖出备兑看跌 / Sell Cash-Secured Put
- 备兑看涨 / Covered Call
- 观望 / Watchlist
- 不交易 / No Trade

界面不得退化为通用：

- BUY
- HOLD
- SELL

这些旧式词汇只能在遗留字段里作为兼容数据出现，不能成为主界面语言。

---

## 三、设计原则

### 3.1 决策优先

页面第一眼必须先给出结论，而不是先给数据。

优先级顺序如下：

1. 核心动作
2. 信心度
3. 标的代码与公司名
4. 目标价与时间窗
5. 为什么现在
6. 工具选择
7. 风险
8. 观察与验证

### 3.2 中文优先，英文辅助

所有主标签采用：

`中文 / English`

规则：

- 中文是主标题
- 英文是辅助说明
- 中文字号更大
- 英文字重更轻
- 不允许英文主导

### 3.3 老板可读

页面要像“决策简报”，不是“技术输出页”。

具体要求：

- 少表格堆砌
- 少技术缩写堆砌
- 少原始指标罗列
- 多卡片、多短句、多明确标签

### 3.4 可打印

页面从设计开始就要考虑：

- A4 / Letter 打印
- page-break 行为
- 卡片不跨页断裂
- 表头与首行不分离

### 3.5 稳定模板化

该界面必须适合：

- 用固定 HTML/CSS 模板实现
- 用固定数据映射自动填充
- 长期维护而不依赖人工排版

---

## 四、信息层级

### 4.1 老板 3 秒内必须看到

- 这只票的核心动作
- 这笔决策的信心度
- 建议仓位或动作倾向
- 目标价和时间窗
- 一句最核心的“为什么现在”

### 4.2 30 到 60 秒可读层

- Why Now 详细要点
- Thesis 与催化剂
- 技术面摘要
- 工具选择逻辑
- 期权结构
- 提前退出计划
- 监控状态
- 验证摘要

### 4.3 深层内容不放在首页

以下内容不应抢首页版面：

- 大段研究原文
- 多行 trade plan 原始字段
- 冗长表格
- 过多指标值

这些可作为 PDF 深层内容或附录。

---

## 五、Poster 结构

Poster 是单页、竖版、打印友好的决策板。

建议比例：

- 顶部：55%
- 中部：35%
- 底部：10%

### 5.1 顶部区：决策主区

目标：3 秒钟读懂。

包含：

1. 核心动作
2. 信心徽章
3. 标的代码
4. 公司名称
5. 目标价
6. 目标时间窗
7. 建议仓位或动作倾向
8. Why Now 三条
9. 风险标签

#### 动作主区

必须是页面最大视觉元素。

展示：

- 中文动作大字
- 英文动作副标题
- 信心徽章

示例：

- 买入看涨 / Buy Call
- 高信心 / High Conviction

#### 目标与仓位区

展示：

- 目标价 / Target Price
- 目标时间窗 / Target Window
- 建议仓位 / Suggested Size

#### Why Now

最多 3 条：

- 每条一句话
- 中文在前
- 英文在后
- 不写成长段落

#### 风险标签

展示方式：

- 小 chip
- 不与核心动作争主视觉
- 只展示 2 到 4 个最重要风险

### 5.2 中部区：研究卡片区

目标：30 秒内读懂支撑逻辑。

包含：

1. Executive Snapshot
2. Thesis & Catalysts
3. Technical View
4. Instrument Choice
5. Options Structure
6. Early Exit

#### Executive Snapshot

推荐 4 张 KPI 卡片：

- 当前价格 / Price
- 上行空间 / Upside
- 估值位置 / Valuation
- 验证信心 / Validation Confidence

#### Thesis & Catalysts

内容来源：

- `decision_card`
- `report.bull_case`
- `report.why_now`

规则：

- 3 到 5 条要点
- 每条短句
- 不要大段研究散文

#### Technical View

必须是老板可读摘要，不是指标堆。

允许展示：

- 趋势 / Trend
- 支撑位 / Support
- 阻力位 / Resistance
- 动能摘要 / Momentum Summary

不允许展示：

- RSI 原始值
- MACD 原始值
- 多时间框架指标列表
- 大段技术指标说明

#### Instrument Choice

只显示三层：

- 首选 / Primary
- 保守方案 / Conservative
- 备选方案 / Alternative

不把所有工具做成等权按钮墙。

#### Options Structure

仅当动作涉及期权时显示。

最少显示：

- 期权类型
- 到期
- 行权价
- Break-Even
- Delta
- Debit / Credit

#### Early Exit

仅当 `early_exit` 存在时显示。

显示三段：

- 首轮减仓 / First Trim
- 主要利润 / Main Profit
- 完全退出 / Full Exit

每段包括：

- 建议动作
- 触发条件
- 目标收益区间

### 5.3 底部区：监控与验证区

目标：提供辅助决策上下文，但不抢主视觉。

包含：

1. Watchlist State
2. Alert Level
3. Validation Summary
4. Main Failure Mode
5. 时间戳

展示形式：

- 小型状态卡
- badge / chip
- 低视觉权重

---

## 六、PDF 结构

PDF 是多页正式报告，服务于存档和深读。

### 6.1 第 1 页：批次概览

包含：

- 报告标题
- 生成日期
- 本次研究对象数量
- 批次总览表
- 简要执行摘要

总览表建议列：

- 排名
- 代码
- 公司
- 核心动作
- 信心度
- 目标价
- 时间窗

### 6.2 第 2 页起：单票报告页

每只标的一页或一页半，按以下主结构顺序：

1. 决策卡片摘要
2. 工具选择详情
3. 期权结构详情（仅期权时）
4. 支撑数据网格（仅参考）
5. 看多逻辑
6. 风险观察

#### 决策卡片摘要

这是单票页的主标题区。

包含：

- 代码
- 公司名
- 核心动作
- 信心度
- 目标价
- 时间窗
- 一句话底线结论

#### 工具选择详情

必须基于真实对象：

- `instrument_recommendation`
- `decision_card`

展示：

- 首选工具及理由
- 保守方案及理由
- 备选方案及理由

#### 期权结构详情

仅当动作为期权相关时显示。

必须基于真实对象：

- `options_structure`
- `early_exit`

展示：

- 主合约
- 配对合约（如有）
- 到期
- 行权价
- 净 debit / 净 credit
- break-even
- 最大收益 / 最大损失
- 退出区间摘要

#### 支撑数据网格

这是遗留字段区，只能是辅助，不是主体。

允许展示：

- 入场价
- 止损价
- 目标价
- 持有周期

来源：

- legacy `signal`
- legacy `report`

但必须明确标注：

**仅供参考，不构成页面主结构**

#### 看多逻辑

来源：

- `decision_card.thesis_summary`
- `report.bull_case`
- `report.why_now`

形式：

- 条列式
- 最多 4 条主点

#### 风险观察

来源：

- `report.risk_watch`
- `validation.main_failure_mode`
- `watchlist_entry.alert_level`

形式：

- 风险标签
- 观察点列表

### 6.3 末页：监控与验证摘要

包含两张表：

1. Watchlist 表
2. Validation 表

#### Watchlist 表建议列

- Ticker
- Action Bias
- Status
- Thesis State
- Alert Level

#### Validation 表建议列

- Ticker
- Regime
- Historical Support
- Environment Fit
- Main Failure Mode
- Validation Confidence

---

## 七、数据映射

### 7.1 主对象映射

#### `decision_card`

用于：

- Poster 顶部核心动作
- Poster Why Now
- PDF 单票页决策卡片摘要
- PDF 单票页看多逻辑

#### `instrument_recommendation`

用于：

- Poster Instrument Choice
- PDF 工具选择详情

#### `options_structure`

用于：

- Poster Options Structure
- PDF 期权结构详情

#### `early_exit`

用于：

- Poster Early Exit
- PDF 期权结构详情中的退出区间

#### `watchlist_entry`

用于：

- Poster 底部监控区
- PDF 末页 Watchlist 表

#### `validation`

用于：

- Poster 底部验证区
- PDF 末页 Validation 表

### 7.2 遗留支撑字段

以下字段只能作为辅助信息：

- `signal.entry_price`
- `signal.stop_loss`
- `signal.take_profit`
- `signal.holding_horizon`
- `signal.confidence`
- `report.company_name`
- `report.executive_summary`

这些字段不允许重新成为页面主结构。

---

## 八、双语与术语规则

### 8.1 固定术语

| 中文 | English |
|---|---|
| 买入股票 | Buy Stock |
| 买入看涨 | Buy Call |
| 牛市看涨价差 | Bull Call Spread |
| 卖出备兑看跌 | Sell Cash-Secured Put |
| 备兑看涨 | Covered Call |
| 观望 | Watchlist |
| 不交易 | No Trade |
| 高信心 | High Conviction |
| 中信心 | Medium Conviction |
| 低信心 | Low Conviction |
| 首选 | Primary |
| 保守方案 | Conservative |
| 备选方案 | Alternative |
| 持仓中 | Held |
| 重点关注 | High Priority |
| 研究进行中 | Research In Progress |
| 被动跟踪 | Passive Watch |
| 强化 | Strengthening |
| 稳定 | Stable |
| 弱化 | Weakening |
| 破坏 | Broken |

### 8.2 空状态

空状态统一使用：

- 暂无数据 / Not Available

不得使用乱码或空白。

### 8.3 编码规则

- 所有模板文件必须保存为 UTF-8
- HTML 必须声明 `meta charset="utf-8"`
- 不允许通过错误 decode / encode 链拼装中文

---

## 九、视觉系统

### 9.1 色彩

- 主动作色：橘红 `#E85A3C`
- 正向色：青绿 `#2DD4A8`
- 风险色：深红 `#C0392B`
- 背景色：暖白 `#FAF8F5`
- 卡片色：白色 `#FFFFFF`
- 文字色：深灰黑 `#1A1A1A`

### 9.2 字体

中文优先字体栈：

- Noto Sans SC
- PingFang SC
- Microsoft YaHei
- Helvetica Neue
- Arial

### 9.3 卡片与标签

- 决策主卡最大
- KPI 卡片次级
- 风险 chip 小而明确
- 底部监控 badge 最轻

### 9.4 工具层级

工具区只允许：

- 首选：高强调
- 保守方案：次强调
- 备选方案：弱强调

Rejected 工具不在 Poster 主区展示。

---

## 十、技术面渲染规则

技术面摘要只能服务于老板判断，不能变成分析师指标页。

允许：

- 支撑位
- 阻力位
- 趋势
- 动能摘要

不允许：

- 指标列表转储
- 多行技术说明长文
- 原始 MACD / RSI 数值墙

推荐渲染格式：

- 支撑位 / Support：165–170 美元
- 阻力位 / Resistance：220–225 美元
- 趋势 / Trend：上升趋势 / Uptrend
- 动能 / Momentum：较强 / Strong

---

## 十一、分页与打印规则

### 11.1 Poster

- 竖版
- 3:4 比例
- 单页打印
- 不允许滚动依赖

### 11.2 PDF

- A4 竖版
- 标准边距
- 单票主卡尽量不跨页
- 表头不与首行分离
- Options 与 Early Exit 尽量保持同页

### 11.3 Keep Together 规则

以下内容必须避免拆散：

- 决策卡片摘要
- 工具选择详情
- 期权结构详情
- Watchlist 表头与首行
- Validation 表头与首行

---

## 十二、非目标

本规范不包括：

- 新的交易算法
- 新的信号逻辑
- 新的 validation 逻辑
- 自动交易
- 实时看盘大屏
- 做空能力
- 营销 landing page
- PPT 幻灯片系统

---

## 十三、验收标准

### 13.1 内容正确性

- 页面主动作来自真实 decision objects
- 不退回 BUY / HOLD / SELL 表达
- legacy 字段只是辅助

### 13.2 中文可读性

- 所有中文正常显示
- 无 mojibake
- 空状态显示“暂无数据”

### 13.3 Poster

- 单页可打印
- 顶部区 3 秒可读
- 中部区 30 秒可读
- 底部区只作支持

### 13.4 PDF

- 批次概览清晰
- 单票页是 decision-object-first
- 末页 watchlist / validation 完整

### 13.5 实现边界

- 不修改业务决策逻辑
- 不新增交易功能
- 不改变 bullish-only / alert-only

---

## 十四、实施目标文件

后续实现主要作用于：

- `agent/research_v1/report_pdf.py`
- `agent/research_v1/report_templates/renderer.py`
- `agent/research_v1/report_templates/boss_poster_base.html`
- `agent/research_v1/report_templates/boss_report_base.html`
- `agent/research_v1/report_templates/boss_report_pdf.css`
- `agent/research_v1/report_templates/strings_zh.py`
- `agent/research_v1/report_templates/strings_en.py`

本规范本身不要求在这一轮修改以上实现文件。
