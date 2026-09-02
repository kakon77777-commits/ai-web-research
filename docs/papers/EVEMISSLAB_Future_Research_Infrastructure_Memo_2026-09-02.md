# EVEMISSLAB Future Research Infrastructure Memo

**Date:** 2026-09-02  
**Status:** Internal / Local-AI Context Memo  
**Purpose:** 給 Neo.K、EVEMISSLAB 與本地端 AI 的長期方向備忘錄

---

# 0. 這份備忘錄要回答什麼？

這份文件主要回答三個問題：

1. **EVEMISSLAB 到底是一間什麼公司？**
2. **Omphalos / AUSI Runtime、經濟研究網站群、氣象研究網站群未來還需要什麼？**
3. **本地端 AI 接手後，應該把哪些能力視為長期基礎設施，而不是一次性專案？**

---

# 1. EVEMISSLAB 到底是什麼公司？

答案是：

> **它當然是一間企業，但不是只靠單一 SaaS、單一 App、單一 Agent 或單一模型活著的公司。**

目前更準確的定位應該是：

> **Research-Driven AI & Deep-Tech Company**
>
> **研究驅動的 AI／深科技企業**

或者更完整一點：

> **EVEMISSLAB 是一間以 AI-native research infrastructure、computational systems、research platforms 與跨領域技術研究為核心的獨立科技企業。**

它不是單純：

```text
AI SaaS 公司
模型公司
搜尋引擎公司
顧問公司
網站公司
資料公司
遊戲公司
```

但上述能力未來都可能成為它的產品／研究子系統。

更接近的結構是：

```text
EVEMISSLAB
│
├─ Core Research
│  ├─ AI / cognition
│  ├─ computation
│  ├─ information / search
│  ├─ mathematics
│  ├─ knowledge systems
│  └─ machine-native systems
│
├─ Research Infrastructure
│  ├─ Omphalos / AUSI Runtime
│  ├─ evidence / provenance systems
│  ├─ memory systems
│  ├─ agent/runtime systems
│  ├─ knowledge databases
│  └─ research automation
│
├─ Domain Research Platforms
│  ├─ Economic Research
│  ├─ Meteorological Research
│  ├─ Patent Intelligence
│  ├─ Academic / Scientific Research
│  └─ future specialist domains
│
├─ Products
│  ├─ B2B tools
│  ├─ enterprise research systems
│  ├─ AI-native applications
│  └─ public research websites
│
└─ Long-Term R&D
   ├─ AGI / individualized AI
   ├─ AI-native computation
   ├─ machine-native language / protocols
   └─ new computational / epistemic infrastructure
```

所以對外最乾淨的一句話可以是：

> **EVEMISSLAB is an independent AI-native research and technology company building research infrastructure, computational systems, and domain research platforms.**

中文：

> **EVEMISSLAB 是一間獨立的 AI 原生研究與科技企業，致力於建立研究基礎設施、計算系統，以及專業領域研究平台。**

---

# 2. Omphalos / AUSI Runtime 的真正角色

**Codename:** Omphalos  
**Technical Name:** AUSI Runtime — AI-Native Unified Search Intelligence Runtime

它不是搜尋 API 聚合器。

核心是：

> **讓 AI 能理解、選擇、組合、執行、驗證並學習搜尋方法。**

基本公式：

$$
\text{Task}
\rightarrow
\text{Search Strategy}
\rightarrow
\text{Search Method}
\rightarrow
\text{Provider Binding}
\rightarrow
\text{Authorized Execution}
\rightarrow
\text{Evidence}
\rightarrow
\text{Gap}
\rightarrow
\text{Replan}
$$

最重要的不變量：

$$
\text{Method} \neq \text{Provider} \neq \text{API}
$$

以及：

$$
\boxed{
\text{Method Stable}
\quad
\text{Provider Replaceable}
\quad
\text{API Disposable}
}
$$

---

# 3. 未來 Omphalos 的 Provider 版圖

## 3.1 Model-Native Search

### Gemini

主要角色：

```text
Google-native search
Google Search grounding
broad Web research
Google ecosystem grounding
```

### Grok

主要角色：

```text
X Search
Web Search
social / discourse / current signal
X-native information topology
```

---

## 3.2 Provider-Neutral Search

### Brave Search

Omphalos 自己控制 Search Method / Planner 時的重要 general-Web provider。

用途：

```text
general Web search
neutral search baseline
multi-provider verification
provider substitution
method-controlled search
```

---

## 3.3 Domain-Specific Providers

### Patent

```text
EPO OPS
future USPTO
future WIPO licensed / permitted surfaces
commercial patent providers if needed
```

### Academic

```text
Crossref
OpenAlex / scholarly providers if adopted
other academic indexes
```

### Economics

```text
FRED / ALFRED
World Bank
BEA
BLS
IMF
OECD
CBC
DGBAS
future commercial economic datasets
```

### Meteorology / Climate

```text
NOAA / NCEI
NWS
ECMWF Open Data
Copernicus CDS / ERA5
Taiwan CWA
future satellite / reanalysis / commercial feeds
```

---

## 3.4 Local / Private

```text
crawler
local corpus
local vector index
private databases
enterprise files
local models
tenant-private search
```

---

# 4. 目前建議要準備的 API / Account / Credential

以下是未來真的會用到的，不需要一次全部買商業方案。

## 經濟

### 建議現在申請

- FRED / ALFRED API key
- BEA API key
- BLS v2 registration key

### 不一定需要 key

- World Bank Indicators API
- IMF public APIs（依實際 endpoint）
- 台灣公開政府資料 endpoint（依 adapter 實作逐一確認）

---

## 氣象 / 氣候

### 建議現在申請

- NOAA CDO / NCEI token
- Copernicus Climate Data Store account + API token
- Taiwan CWA Open Data Authorization key

### 可直接使用或另依服務條件

- NWS API
- ECMWF Open Data

---

## AI / Search

- xAI API — 已具備
- Google / Gemini API — 持續維護可用 billing / credit
- Brave Search API — 建議作 Omphalos provider-neutral general search credential

---

## Patent

- EPO OPS account / OAuth credentials
- 未來如果真的需要：
  - USPTO account / ODP
  - WIPO commercial / licensed data products
  - commercial patent intelligence providers

---

# 5. 經濟研究網站群不能只是「API + AI 解釋」

未來 EVEMISSLAB Economic Research Platform 至少要有六層。

```text
Official / Scientific Data
↓
Canonical Economic Data Layer
↓
Research Method Layer
↓
Interpretation / Structural Analysis
↓
Forecast / Nowcast / Scenario
↓
Verification / Backtesting
```

---

# 6. 經濟資料 Canonical Identity

每個 observation 至少保存：

```text
provider
dataset
series_id
value
unit
frequency
observation_time
publication_time
retrieval_time
revision_time
vintage
seasonal_adjustment
transformation
source evidence
usage envelope
```

重要：

$$
\text{Latest Revised Data}
\neq
\text{Data Known At Historical Forecast Time}
$$

所以做預測驗證時必須 **vintage-aware**。

不能用今天修訂後的 GDP 去回測去年模型，假裝模型當時已知道。

---

# 7. 經濟研究需要的方法層

未來至少要逐步具備：

```text
trend decomposition
seasonality
structural break detection
regime detection
lead-lag analysis
cross-series dependency
revision analysis
nowcasting
forecasting
scenario analysis
uncertainty intervals
causal hypotheses
counter-evidence search
policy-event analysis
cross-country comparison
```

此外可逐步引入 EVEMISSLAB 自有方法與其他前沿統合模型。

---

# 8. 經濟預測層

不能只讓 LLM 寫一句「經濟可能成長」。

至少需要：

```text
baseline statistical models
time-series models
machine-learning models
structural / econometric models
ensemble
scenario models
AI synthesis layer
```

最後由：

```text
model outputs
+
research methods
+
evidence
+
event/news/search state
```

產生正式 forecast。

---

# 9. 經濟 Forecast Ledger

每次預測一旦發布：

```text
forecast_id
timestamp
information_cutoff
data_vintage
model_version
prediction
interval
scenario
method
```

應保存。

等真實數值公布後再計分。

不能偷偷回改歷史預測。

---

# 10. 經濟驗證指標

可逐步使用：

```text
MAE
RMSE
MAPE / sMAPE
directional accuracy
interval coverage
calibration
revision-aware forecast error
benchmark-relative skill
```

---

# 11. 氣象網站群也不能只是顯示 ECMWF / NOAA

EVEMISSLAB Meteorological Research Platform：

```text
Observations
+
NWP Models
+
Reanalysis
+
Satellite / Radar
+
Local Calibration
+
AI / Statistical Postprocessing
↓
Our Forecast
↓
Verification
```

---

# 12. 氣象資料層

至少考慮：

```text
CWA station observations
NOAA observations
NWS forecasts
ECMWF forecasts
ECMWF AIFS / IFS where available
ERA5 / Copernicus
radar
satellite
reanalysis
historical climatology
```

---

# 13. 氣象研究方法

```text
bias correction
ensemble weighting
model blending
downscaling
local calibration
station correction
extreme-event detection
probabilistic forecasting
spatial verification
forecast regime classification
model disagreement analysis
uncertainty estimation
```

---

# 14. 我們自己的氣象預測

EVEMISSLAB 不應只說：

> ECMWF 說多少。

而應該輸出：

```text
ECMWF forecast
NOAA forecast
CWA forecast
other model outputs
↓
EVEMISSLAB synthesis / calibration
↓
EVEMISSLAB forecast
```

而且要保留：

```text
why models disagree
which model historically performs better in this regime
what local bias exists
what uncertainty remains
```

---

# 15. 氣象 Forecast Ledger

每次發布：

```text
forecast_id
issue_time
valid_time
location
variable
forecast value
probability
model inputs
model versions
method
uncertainty
```

固定保存。

---

# 16. 氣象驗證

逐步建立：

```text
temperature MAE / RMSE
wind error
precipitation error
Brier score
CRPS
probability calibration
hit rate
miss rate
false alarm rate
extreme-event skill
spatial verification
```

---

# 17. 公開 Verification 是研究品牌資產

EVEMISSLAB 如果真的想成為研究機構型企業，不應只公開「我們預測」。

更有價值的是公開：

> **我們過去到底預測得多準。**

例如：

```text
Model A
Model B
Official Forecast
EVEMISSLAB Forecast
```

長期 skill comparison。

這會形成很難靠 UI 套皮抄走的研究資產。

---

# 18. Omphalos 與研究網站群的關係

Omphalos 不負責替經濟學家或氣象學家做所有 domain mathematics。

它負責：

```text
data discovery
search methods
provider routing
policy
provenance
evidence
gap detection
research orchestration
search receipt
learning
```

Domain Packs 負責：

```text
economic methods
meteorological methods
forecast models
verification rules
domain-specific state
```

---

# 19. 本地端 AI 接下來要知道的「未來仍缺什麼」

## A. Omphalos / AUSI

尚需逐步完成：

```text
Grok Web provider
Grok X provider
Gemini Google provider
Brave Search provider

ProviderState
cost / quota-aware routing
model-native search receipts
Search Method Corpus
method coverage metrics
provider substitution
more search-method operators
strategy learning
```

---

## B. Economic Research Domain Pack

需要：

```text
FRED/ALFRED connector
BEA connector
BLS connector
World Bank connector
IMF connector
CBC connector
DGBAS connector

canonical economic series model
vintage/revision model
transformation lineage
nowcast runtime
forecast ensemble
scenario engine
forecast ledger
backtesting
public verification dashboard
```

---

## C. Meteorological Domain Pack

需要：

```text
CWA connector
NOAA/NCEI connector
NWS connector
ECMWF connector
Copernicus/ERA5 connector

station identity
variable identity
unit normalization
quality flags
forecast-run identity
lead-time identity
spatial identity

bias correction
ensemble blending
local calibration
probability layer
extreme-event engine
forecast ledger
verification dashboard
```

---

## D. Patent Intelligence

目前已開始：

```text
EPO OPS
patent identifiers
classification
family
priority
claims
NPL via Crossref
coverage/gaps
```

仍需：

```text
official legal-value claim manifestation
more jurisdictions/providers
USPTO
better citation graph
legal-status monitoring
review workspace
```

---

## E. Research Institution Layer

長期還需要：

```text
research publication system
dataset/version registry
forecast registry
experiment registry
benchmark suite
reproducibility artifacts
research review process
public methodology docs
correction/retraction policy
model cards
data provenance pages
```

---

# 20. EVEMISSLAB 未來不只是在「做產品」

更合理的方向是形成：

```text
Research
↓
Infrastructure
↓
Methods
↓
Products
↓
Public Research
↓
Enterprise Services
```

所以公司真正累積的核心資產不是某一個 App。

而是：

```text
methods
runtime
datasets
evidence
models
benchmarks
forecast history
research corpus
software
domain expertise
```

---

# 21. 公司類型的最終答案

如果一定要分類：

**它是一間企業。**

但更準確：

> **Research-Driven Deep-Tech Enterprise**

再更完整：

> **AI-Native Research Infrastructure & Deep-Tech Company**

它未來可以同時：

```text
做 B2B
做 SaaS
做 API
做研究網站
做專業研究
做預測
做開源
做 whitepaper
做模型
做 infrastructure
```

而不互相矛盾。

因為最上層的共同核心是：

> **研究與計算能力本身。**

---

# 22. Local AI Canonical Instruction

給未來任何接手 EVEMISSLAB repository / research task 的本地 AI：

> 不要把 EVEMISSLAB 理解成一個單一產品公司。
>
> 不要把 Omphalos 理解成搜尋 API aggregator。
>
> 不要把 Economic / Meteorological sites 理解成資料套皮網站。
>
> 不要把 forecast 理解成 LLM opinion。
>
> 不要把 API provider 當成 architecture center。
>
> 不要因為有資料就宣稱有研究。
>
> 不要因為有 prediction 就宣稱有 forecasting capability，除非有 timestamped forecasts、out-of-sample verification 與 benchmark。
>
> 優先累積可重用的 methods、runtime contracts、provenance、evidence、models、benchmarks、receipts 與 domain packs。

Canonical mental model：

$$
\boxed{
\text{EVEMISSLAB}
=
\text{Research}
+
\text{Infrastructure}
+
\text{Methods}
+
\text{Domain Systems}
+
\text{Products}
}
$$

---

# 23. 一句話備忘

如果未來又有人問：

> 「EVEMISSLAB 到底在幹嘛？」

可以回答：

> **我們不是只做 AI 產品。我們在建立讓 AI、資料、搜尋方法、計算方法與專業研究可以真正被組合成研究能力的基礎設施，然後把這些能力做成產品與研究平台。**

嗯。

所以答案是：

> **對，它是企業。只是這間企業長得有點像研究院、軟體公司、AI Lab、資料研究機構和未來研究基礎設施公司疊在一起。**
