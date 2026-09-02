# Omphalos Position Paper v0.1

## 從搜尋 API 到 AI 原生搜尋方法 Runtime：搜尋方法空間、可替換執行管道與自主方法組合

**English Title:** *Omphalos: From Search APIs to an AI-Native Search-Method Runtime — Search-Method Spaces, Replaceable Execution Channels, and Autonomous Method Composition*

**Codename:** Omphalos  
**Technical Name:** AUSI Runtime — AI-Native Unified Search Intelligence Runtime  
**Legacy Repository Name:** `ai-web-research`  
**Version:** v0.1  
**Date:** 2026-09-02  
**Status:** Canonical Position / Reframing Paper  
**Reference Implementation:** `kakon77777-commits/ai-web-research`

---

## 摘要

當代 AI 搜尋系統常被描述為「模型加搜尋 API」、「Agent 加工具」或「LLM 加 RAG」。這些描述雖然足以表達局部實作，卻容易把真正的搜尋智能誤縮成某個模型、搜尋引擎、API 或工具調用介面。當 Google Search、X Search、Brave Search、專利資料庫、學術資料庫、本地索引、Crawler、企業私有資料與未來的新型搜尋能力同時存在時，真正困難的問題已經不是「AI 能否呼叫一個 Search API」，而是：

> **AI 是否能把不同搜尋方法視為可操作的認知方法，依任務選擇、組合、切換、驗證、停止，並在 provider 改變時維持方法語義不變？**

本文重新定位 Omphalos / AUSI Runtime。Omphalos 是專案代號；AUSI Runtime 是技術名稱。其核心不再被定義為 Web crawler、search API aggregator 或單一 Deep Research Agent，而是：

> **一個 AI 原生搜尋方法 Runtime：將人類與機器已知的搜尋方法外顯成可註冊、可組合、可驗證的 Search Methods，讓 AI 自主選擇方法，再把方法綁定到可替換的模型、搜尋引擎、資料庫、API、Crawler 或本地資料來源。**

本文提出五層分離：

$$
\boxed{
\text{Search Method}
\neq
\text{Provider}
\neq
\text{Surface}
\neq
\text{Adapter}
\neq
\text{Credential}
}
$$

並將 provider 分成四種主要執行通道：

1. **Model-Native Search Provider**：例如 Gemini + Google Search、Grok + Web/X Search；
2. **Provider-Neutral Search Infrastructure**：例如 Brave Search；
3. **Domain-Specific Knowledge Provider**：例如 EPO OPS、Crossref、未來的經濟、氣象與專業資料服務；
4. **Local / Private Provider**：例如本地 corpus、Crawler、企業資料庫與私有索引。

在此架構下，Google API 免費額度到期、xAI 價格改變、Brave quota 改變、EPO OAuth 或 fair-use 改變，都只是：

$$
\operatorname{ProviderState}(t)
$$

的變化，而不是 Omphalos 架構本身的變化。

本文進一步提出 **Search-Method Primacy Principle**、**Provider Replaceability Principle**、**Method Coverage**、**Execution-Channel Diversity** 與 **Search Method Corpus**。Omphalos 的長期研究目標不是宣稱已經實作「所有搜尋法」，而是建立一個可持續擴張的搜尋方法空間，使 Boolean search、exact search、citation chasing、classification search、berrypecking、systematic-review search、counter-evidence search、identity search、temporal/version search、prior-art search、graph search、multilingual search 等已知方法，都可以逐步轉成 AI 能理解與調度的 typed operators。

最終，Omphalos 的核心式為：

$$
\boxed{
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
}
$$

因此，API 是管道；Provider 是能力載體；Method 才是搜尋智能的第一級物件。

**關鍵詞：** Omphalos、AUSI Runtime、AI-Native Search、Search Method Runtime、Search Method Ontology、Provider Routing、Gemini Search、Grok X Search、Brave Search、EPO OPS、Agentic Search、Search Intelligence

---

# 1. 為什麼需要重新定位

`ai-web-research` 最初從可靠 crawler 開始：

```text
robots
sitemap
BFS
fetch
parse
store
dedup
```

這個起點本身沒有問題。

問題在於系統後續逐漸加入：

```text
query divergence
LLM recall
identity search
semantic extraction
MCP
SearchMethodSpec
Provider Registry
Planner
Policy Runtime
Evidence Runtime
Gap Engine
Search Receipt
Patent Domain Pack
```

之後，若專案仍被描述為：

> 「一個比較強的 Web crawler」

就會產生 category error。

Crawler 現在只是：

$$
P_{\text{crawler}}
$$

而不是 architecture root。

---

# 2. 名稱分層

## 2.1 Omphalos

**Omphalos** 是專案代號與產品／研究代稱。

它代表整體研究方向：

> AI 如何把搜尋方法本身變成可調度的認知能力。

## 2.2 AUSI Runtime

**AI-Native Unified Search Intelligence Runtime** 是技術名稱。

它描述 runtime architecture：

```text
methods
providers
planning
policy
execution
evidence
gaps
experience
```

## 2.3 `ai-web-research`

這是歷史 repository 名稱。

它保留了專案早期的 Web research 起點，但已不能完整描述目前的系統範圍。

因此：

$$
\boxed{
\text{Repository Name}
\neq
\text{Technical Identity}
}
$$

---

# 3. API-Centric 思維的限制

最常見的搜尋 Agent 架構是：

```text
User
↓
LLM
↓
Search API
↓
Answer
```

這能工作。

但它把搜尋問題壓縮成：

> 「要不要 call search？」

如果未來同時存在：

```text
Google
X
Brave
Crossref
EPO
local vector index
crawler
enterprise database
```

問題就變成：

> 「call 哪一個？」

再往前一步又會發現：

> 「不是先選 provider，而是先選搜尋方法。」

例如「找反證」與「找更多相似結果」可能都使用 Brave。

「找 prior art」與「查專利法律狀態」可能都使用 EPO，但它們不是同一 Method。

因此：

$$
\boxed{
\text{Provider Selection}
\neq
\text{Search Strategy}
}
$$

---

# 4. Search-Method Primacy Principle

本文提出：

> **搜尋方法是第一級語義物件；Provider 與 API 是方法的執行通道。**

形式：

$$
M_i=\text{Search Method}
$$

$$
P_j=\text{Provider}
$$

$$
B_{ij}=\text{Binding}(M_i,P_j)
$$

實際執行：

$$
M_i\rightarrow B_{ij}\rightarrow P_j
$$

而不是：

$$
P_j\rightarrow\text{invent a search meaning}
$$

---

# 5. 五層分離

Omphalos 固定：

$$
\boxed{M\neq P\neq S\neq A\neq C}
$$

其中：

- $M$：Search Method；
- $P$：Provider；
- $S$：Surface；
- $A$：Adapter；
- $C$：Credential。

Search Method 回答「要做什麼搜尋認知操作」；Provider 回答「哪個能力來源可以做」；Surface 回答「從哪個介面做」；Adapter 負責 translation；Credential 只處理 execution authorization。

---

# 6. 四類 Provider

本文將 Omphalos Provider 分成四個主類。

## 6.1 Model-Native Search Provider

特色是搜尋工具與模型推理循環高度整合。

### Gemini / Google Search

Gemini API 的 `google_search` tool 可以讓模型自行分析 prompt、生成一或多個搜尋、執行 Google Search、處理結果並回傳 grounded response 與 citation / search-call metadata。

因此可視為：

$$
P_{\text{Gemini-Google}}
$$

### Grok / Web Search

xAI 的 `web_search` 是 server-side built-in tool，可即時搜尋 Web、瀏覽頁面並限制 domain。

### Grok / X Search

xAI 的 `x_search` 支援 keyword、semantic、user、thread、date/handle filtering，以及 image/video understanding。

因此 X 是一個具有不同 information topology 的 search surface，而不是普通 Web provider 的別名。

## 6.2 Provider-Neutral Search Infrastructure

例如 Brave Search。

Brave 提供獨立 Web index 與 REST Search API，也有為 Agent / LLM consumption 設計的 LLM Context surface。

這使：

```text
AI Planner
↓
Method
↓
Brave
```

可以作為不依附特定 model-native search 生態的 baseline。

## 6.3 Domain-Specific Knowledge Provider

例如 EPO OPS、Crossref。

EPO OPS 提供 REST/XML patent-data machine interface；Crossref 提供 scholarly metadata / DOI / NPL discovery。

這類 provider 不應被當 general Web Search。

## 6.4 Local / Private Provider

例如：

```text
crawler
local corpus
vector store
enterprise database
private index
```

它們讓搜尋不必預設所有資訊都要離開本機。

形式：

$$
\mathcal P=
\mathcal P_M
\cup
\mathcal P_N
\cup
\mathcal P_D
\cup
\mathcal P_L
$$

---

# 7. Search Method Space

Omphalos 的長期研究目標：

$$
\mathcal M_{\text{known}}=\{M_1,\ldots,M_n\}
$$

其中 $M_i$ 來自人類資訊搜尋、IR、圖書資訊、科學研究、法律研究、專利研究、資料庫、Graph、Web 與 AI-native search。

「讓 AI 可以調用人類已知搜尋法」不是宣稱今天已經枚舉完成，而是一個持續擴張的 research program：

> **任何已知且可明確描述的搜尋方法，都應有機會被外顯成 typed Search Method。**

---

# 8. Search Method Corpus

除了 Method Registry，Omphalos 應建立 **Search Method Corpus**。

每個方法至少保存：

```text
name
history
domain
goal
input
output
preconditions
strengths
failure modes
composition rules
provider requirements
references
implementation status
```

可能逐步外顯的方法包括：

```text
Boolean Search
Exact Search
Phrase Search
Faceted Search
Classification Search
Citation Chasing
Backward Search
Forward Search
Snowballing
Berrypicking
Exploratory Search
Systematic Review Search
Counter-Evidence Search
Prior-Art Search
Identity Search
Temporal Search
Graph Search
Cross-Language Search
```

---

# 9. Berrypicking、Exploratory Search 與 Systematic Search

Bates 的 berrypicking 強調 query 會隨新資訊逐步演化：

$$
S_t\rightarrow M_t\rightarrow E_t\rightarrow S_{t+1}
$$

Marchionini 的 Exploratory Search 強調 learning / investigation / comparison，而不是只做 known-item lookup。

PRISMA-S 等 systematic-search 方法則要求 sources、queries、dates、iterations、citation searching 與 reproducibility。

這些方法論共同說明：

> **搜尋是一個可組合的研究程序，而不是一次 API request。**

---

# 10. Search-Method Coverage

Omphalos 應區分：

$$
Coverage_{\text{provider}}
$$

與：

$$
Coverage_{\text{method}}
$$

Provider Coverage 回答「查了哪些來源」。

Method Coverage 回答「用了哪些搜尋方法」。

查五個搜尋引擎但全部使用同一 query，Provider Coverage 可以很高，Method Coverage 仍然很低。

---

# 11. Search Strategy

Search Strategy 是 Method composition：

$$
\Pi=M_1\triangleright(M_2\parallel M_3)\triangleright M_4
$$

它不是 Provider list。

執行時才把 Method 綁到 Provider：

$$
B:(M,S)\rightarrow(P,Surface,Adapter)
$$

---

# 12. Provider Replaceability Principle

若 Method semantic contract 不變，Provider 可以替換：

$$
(M,P_a)\rightarrow(M,P_b)
$$

而不必重新定義 Method。

例如 Gemini 企業額度到期時，變化的是：

$$
Cost(P_{Gemini})\uparrow
$$

或：

$$
Quota(P_{Gemini})\downarrow
$$

不是：

$$
M_{web-search}\text{ disappears}
$$

---

# 13. ProviderState

Provider State 應包含：

```text
available
quota
cost
latency
health
auth
policy freshness
```

它是一個會隨時間改變的 runtime state。

因此：

$$
\operatorname{ProviderState}(t_1)
\neq
\operatorname{ProviderState}(t_2)
$$

完全不要求 Method identity 也跟著改。

---

# 14. Dynamic Routing

Planner 可以估：

$$
U(M_i,P_j,S_t)
$$

例如 deployment profile：

```text
Google-native web grounding → Gemini / google_search
X / discourse / social      → Grok / x_search
general neutral Web         → Brave
academic / NPL              → Crossref
patent machine data         → EPO OPS
site acquisition            → crawler
local corpus                → local index
```

這只是 deployment profile，不是 architecture law。

---

# 15. Model 的多重角色

同一 Gemini / Grok 可以扮演：

```text
Planner
Provider
Synthesizer
```

但 Runtime identity 必須分開。

Model-as-Planner 只提出 plan。

Model-as-Provider 執行 native search tool。

Model-as-Synthesizer 根據 Evidence 產生 synthesis。

---

# 16. Search Result 與 Evidence

無論 Provider 是 Gemini、Grok、Brave、EPO 或 Crossref：

$$
\boxed{Retrieved\neq Verified}
$$

Model-native grounded response 可以提供很好的 citations 與 search traces，但高風險研究仍應把來源轉成 Evidence Objects，再做 task-relative verification。

---

# 17. Search Receipt 與 Search Strategy Memory

每次 execution 留下：

```text
method
provider
surface
query
policy
cost
latency
result count
evidence gain
gap change
stop reason
```

累積：

$$
H_{search}
$$

形成 Search Strategy Memory。

但：

$$
\boxed{
PastExecution
\not\Rightarrow
CurrentAuthorization
}
$$

歷史成功不能學成今天仍被允許。

---

# 18. Omphalos Control Loop

正式：

$$
\boxed{
T
\rightarrow
S_0
\rightarrow
\Pi_0
\rightarrow
M
\rightarrow
B
\rightarrow
A
\rightarrow
O
\rightarrow
E
\rightarrow
G
\rightarrow
\Pi_1
}
$$

其中：

- $T$：Task；
- $S$：State；
- $\Pi$：Plan；
- $M$：Method；
- $B$：Binding；
- $A$：Authorized Action；
- $O$：Observation；
- $E$：Evidence；
- $G$：Gap。

---

# 19. Omphalos 不是什麼

Omphalos 不是 Meta Search Engine：

```text
query → many engines → merge results
```

Omphalos 是：

```text
task
→ method selection
→ method composition
→ provider selection
→ evidence
→ gap
→ replan
```

它也不是單純 RAG pipeline、Browser Agent 或 MCP server。

RAG、Browser、MCP 都只是 Omphalos 可以使用的 execution / protocol capabilities。

---

# 20. Method Coverage 與 Execution-Channel Diversity

本文提出 execution-channel diversity：

$$
D_E=D(model-native,neutral,domain,local)
$$

它不等於 source independence。

Gemini、Grok、Brave 可能都找到同一篇 Reuters，因此：

$$
ProviderDiversity\not\Rightarrow SourceIndependence
$$

Evidence Runtime 仍需 origin resolution。

---

# 21. Cost / Quota-Aware Routing

Provider Utility：

$$
U(P)=w_qQ+w_fF+w_aA-w_cC-w_lL-w_rR
$$

其中：

- $Q$：expected quality；
- $F$：freshness；
- $A$：authority / appropriateness；
- $C$：cost；
- $L$：latency；
- $R$：risk。

Quota：

$$
q_j(t)
$$

是 Provider State，不是 Search Method property。

---

# 22. Provider Failure 與 Method Portability

如果：

```text
quota exhausted
policy stale
API outage
credential unavailable
```

Planner 可以重新 binding。

因此：

$$
ProviderDown\not\Rightarrow MethodUnavailable
$$

只要還有其他 binding。

---

# 23. Domain Methods 與 Core Methods

Method Space 可以分成：

$$
\mathcal M=
\mathcal M_{core}
\cup
\mathcal M_{domain}
$$

例如：

```text
lexical_search
semantic_search
identity_search
```

是 core。

```text
patent.family_resolve
patent.classification_search
```

是 domain-specific。

---

# 24. Omphalos / AUSI 的正式表述

本文正式建議：

> **Omphalos is the codename of the reference implementation and research program; AUSI Runtime is the technical architecture.**

中文：

> **Omphalos 是研究／實作代號；AUSI Runtime 是技術架構名稱。**

---

# 25. Repository 與 Package Identity

歷史 repository：

```text
ai-web-research
```

已不足以完整表達系統。

較合理的新 repository name 候選：

```text
omphalos
omphalos-runtime
omphalos-search
omphalos-ausi
```

其中最乾淨的是：

```text
omphalos
```

但 Python package `ai_web_research` 已承載大量既有 imports，因此 repo rebrand 與 package rename 不必同步。

---

# 26. 遷移策略

Phase R1：

```text
README → Omphalos-first
pyproject description → AUSI-first
project identity constants
provider taxonomy
```

Phase R2：

```text
repository rename → omphalos
```

Phase R3：

視需要提供：

```text
omphalos
```

Python facade package，而不是 Big-Bang rename。

---

# 27. Provider Taxonomy Contract

新的 provider taxonomy：

```text
MODEL_NATIVE
PROVIDER_NEUTRAL
DOMAIN_SPECIFIC
LOCAL_PRIVATE
```

這是 execution topology，不是品質 ranking。

同一 Provider 也可以有不同 surfaces；Provider class 不應改變 Method semantics。

---

# 28. Search Method Corpus 的工程方向

未來可加入：

```text
methods/corpus/
    exact_search
    boolean_search
    citation_search
    berrypicking
    systematic_search
    counter_evidence
    classification
    graph
    temporal
    multilingual
```

每個 method corpus entry 可以先作文獻／方法描述，再視成熟度升成 executable SearchMethodSpec。

---

# 29. 自動吸收新搜尋法

未來可以研究：

> AI 能否閱讀一個新的搜尋方法論，產生 candidate SearchMethodSpec？

但不能直接 auto-promote。

流程：

```text
discover
extract
formalize
test
review
register
```

---

# 30. Research Hypotheses

## O.1 — Method Primacy Hypothesis

Method-aware Planner 應比 provider-first router 更容易跨 provider 遷移。

## O.2 — Provider Replaceability Hypothesis

Provider pricing/quota/availability 改變時，typed Method/Binding architecture 應降低 planning rewrite 成本。

## O.3 — Method Coverage Hypothesis

Method Coverage 應比單純 Provider Coverage 更能發現搜尋 blind spot。

## O.4 — Model-Native vs Neutral Complementarity Hypothesis

Model-native search 與 provider-neutral search 在 query planning、control、auditability 與 cost 上應存在可測量差異。

## O.5 — Search Method Corpus Hypothesis

把專業搜尋方法明確註冊成 operators，應提高 AI 在 unfamiliar domain 中的策略多樣性與可審計性。

---

# 31. Benchmark

可建立：

```text
same task
same evidence criteria
different provider topology
```

比較：

```text
Gemini-native
Grok-native
Brave-neutral
hybrid
```

Metrics：

$$
\text{Verified Evidence Yield}
$$

$$
\text{Method Coverage}
$$

$$
\text{Provider Coverage}
$$

$$
\text{Independent Source Coverage}
$$

$$
\text{Gap Reduction}
$$

$$
\text{Cost}
$$

$$
\text{Latency}
$$

$$
\text{Provider Substitution Success}
$$

---

# 32. 結論

Omphalos 的重新定位可以濃縮成一句：

> **Omphalos 不是多搜尋 API 聚合器，而是一個 AI 原生搜尋方法 Runtime。**

它的核心不是 Google、Grok、Brave、EPO，而是：

```text
Search Methods
```

模型、搜尋引擎、資料庫、API、Crawler 與本地資料只是：

$$
\boxed{ExecutionChannels(M)}
$$

完整架構：

$$
\boxed{
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
\rightarrow
\text{Receipt}
\rightarrow
\text{Learning}
}
$$

Crawler 沒有被否定，它只是從「專案本身」回到其中一個 execution capability。

同樣地，今天新增 Grok、Gemini、Brave、EPO，也不會再次改變 Omphalos 的核心身份。

因為：

$$
\boxed{
\text{Method Stable}
\quad
\text{Provider Replaceable}
\quad
\text{API Disposable}
}
$$

真正需要長期累積的是：

> **AI 對搜尋方法空間的理解、組合與使用能力。**

這就是 Omphalos。

---

# References

[1] Bates, M. J. (1989). *The Design of Browsing and Berrypicking Techniques for the Online Search Interface*. Online Review, 13(5), 407–424.

[2] Marchionini, G. (2006). *Exploratory Search: From Finding to Understanding*. Communications of the ACM, 49(4), 41–46.

[3] Rethlefsen, M. L., Kirtley, S., Waffenschmidt, S., et al. (2021). *PRISMA-S: an Extension to the PRISMA Statement for Reporting Literature Searches in Systematic Reviews*. Systematic Reviews, 10, 39.

[4] Google AI for Developers. *Grounding with Google Search — Gemini API*. Current documentation accessed 2026-09-02.

[5] xAI. *Web Search — xAI API Tools*. Current documentation accessed 2026-09-02.

[6] xAI. *X Search — xAI API Tools*. Current documentation accessed 2026-09-02.

[7] xAI. *Tools Overview*. Current documentation accessed 2026-09-02.

[8] Brave Search API. *Web Search API / Authentication / LLM Context*. Current documentation accessed 2026-09-02.

[9] European Patent Office. *Open Patent Services (OPS)*. Current documentation accessed 2026-09-02.

[10] European Patent Office. *OPS RESTful Web Services Reference Guide v3.2*. Version 1.3.20.

[11] Thorne, J., Vlachos, A., Christodoulopoulos, C., & Mittal, A. (2018). *FEVER: a Large-scale Dataset for Fact Extraction and VERification*. NAACL-HLT 2018.

[12] Moreau, L., Missier, P., et al. (2013). *PROV-DM: The PROV Data Model*. W3C Recommendation.

---

# Canonical Project Identity

```text
Codename:
    Omphalos

Technical architecture:
    AUSI Runtime
    AI-Native Unified Search Intelligence Runtime

Core identity:
    AI-native Search Method Runtime

Legacy repository name:
    ai-web-research
```

Recommended public one-line description:

> **Omphalos / AUSI Runtime — an AI-native search-method runtime that lets AI select, compose, execute, verify, and learn search strategies across replaceable models, search engines, APIs, databases, crawlers, and local corpora.**
