# Omphalos / AUSI Runtime v1.0 Roadmap Technical Whitepaper v0.1

## 從模型原生搜尋到可替換、可驗證、可學習的 AI Search Method Runtime

**Codename:** Omphalos  
**Technical Name:** AUSI Runtime — AI-Native Unified Search Intelligence Runtime  
**Document Type:** Canonical Technical Roadmap Whitepaper  
**Version:** v0.1  
**Date:** 2026-09-03  
**Status:** Canonical Engineering Roadmap toward v1.0  
**Reference Repository:** `kakon77777-commits/ai-web-research`  
**Recommended Future Repository Name:** `omphalos`

---

# 0. 文件目的

本文件不是功能清單，也不是市場 Roadmap。

它的目的，是固定 Omphalos / AUSI Runtime 從目前狀態推進到 **v1.0** 的工程邊界、版本順序、驗收條件與 release discipline，避免未來因新 Provider、新搜尋法、新 Domain Pack 或新研究題目不斷插入，導致 Runtime 永遠停留在 0.x。

本文件從 2026-09-03 起應視為：

> **Omphalos v1.0 的 Canonical Engineering Roadmap。**

若後續沒有正式修訂本文件，任何新功能、Provider、Domain Pack、搜尋方法或研究想法，都不應自動改變 v1.0 主路線。

---

# 1. v1.0 的正式定義

Omphalos v1.0 不代表：

- 已實作人類歷史上所有搜尋方法；
- 已接入所有搜尋 API；
- 已完成所有 Domain Pack；
- 已完成經濟研究平台；
- 已完成氣象研究平台；
- 已完成所有 Patent Intelligence 能力；
- 已經達到 AGI 等級自主研究。

v1.0 的正式定義是：

> **第一個真正可長期使用、Provider 可替換、Policy-aware、Evidence-grounded、Auditable、Replayable、Gap-directed 且具有基礎 Experience Learning 的 AI-native Search Method Runtime。**

---

# 2. v1.0 核心閉環

```text
Task
↓
Search State
↓
Search Strategy / Planner
↓
Search Method
↓
Provider Binding
↓
Provider State / Routing
↓
Policy / Authorization
↓
Execution
↓
Provider Observation
↓
Acquisition / Evidence
↓
Gap Analysis
↓
Continue / Switch Method / Switch Provider / Stop
↓
Search Receipt
↓
Experience
↓
Future Planner Prior
```

形式化：

$$
\boxed{
T
\rightarrow
S_t
\rightarrow
\Pi_t
\rightarrow
M_i
\rightarrow
B_{ij}
\rightarrow
P_j
\rightarrow
A
\rightarrow
O
\rightarrow
E
\rightarrow
G
\rightarrow
\Pi_{t+1}
}
$$

---

# 3. 永久架構不變量

從現在到 v1.0，以下規則不得破壞：

```text
Method != Provider
Provider != Surface
Provider != API
Spec != Implementation
CapabilityMatch != BindingExists
Planning != Authorization
UNKNOWN != ALLOW
Retrieved != Verified
Citation != Support
QuoteMatch != SemanticSupport
NotFound != False
Saturation != CompleteRecall
SearchReceipt != ChainOfThought
Learning != SelfAuthorization
ProviderObservation != VerifiedEvidence
Access != Acquisition != Usage
EvidenceQuality != UsageRights
```

最核心的工程原則：

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

# 4. Scope Discipline

從本文件生效後採用：

> **Release-Driven Development**

而不是：

> **Idea-Driven Development**

新的研究想法、搜尋法、Provider 與 Domain 能力，預設先進：

```text
Backlog
Search Method Corpus
Provider Candidate Registry
Experimental Domain Pack
```

只有符合目前 milestone 的項目才進 Runtime 主線。

---

# 5. 當前基礎

截至本 Roadmap 建立時，Omphalos 已具備或已開始具備：

```text
SearchMethodSpec
Search Method Registry
ProviderSpec
Provider Registry
ProviderTopology
MethodBinding
Search Graph AST
Plan validation
ExecutionRuntime
TrustedExecutionRuntime
Policy Registry
UsageEnvelope
ProviderObservation
AcquiredAsset
CandidateEvidence
EvidenceAnchor
VerificationResult
Evidence Ledger
GapProjection
Search Receipt
Brave Search provider
Crossref provider
EPO OPS provider
Grok Web provider
Grok X provider
Gemini Google Search provider
Patent Domain contracts
Source lineage / reverse tracing
```

因此 v1.0 Roadmap 是收斂與完成，不是從零開始。

---

# 6. Version Strategy

```text
v0.2 Provider State & Dynamic Routing
v0.3 Search Method Corpus + Core Method Set
v0.4 Autonomous Search Planner
v0.5 Stopping / Coverage / Saturation
v0.6 Evidence / Provenance Closure
v0.7 Search Receipt / Experience Learning
v0.8 Evaluation / Benchmark Suite
v0.9 API Freeze / Hardening / Release Candidate
v1.0 Final Release Gate
```

原則上每一版完成前，不開始下一版核心工作。

---

# 7. v0.2 — Provider State & Dynamic Routing

## Goal

讓 Omphalos 證明：

> **同一 Search Method 可以依 runtime state 動態切換不同 Provider，而不改變 Method identity。**

## ProviderState

新增 typed contract：

```text
provider_ref
surface_id
available
healthy
credential_available
quota_remaining
quota_reset_at
estimated_cost
estimated_latency
policy_freshness
runtime_capabilities
model_available
last_checked_at
```

## BindingSelector / ProviderRouter

輸入：

```text
SearchMethod
SearchTask
SearchState
ProviderState[]
RoutingPolicy
```

輸出：

```text
MethodBinding
```

## Routing Examples

```text
Google-native grounding → Gemini
X / social discourse    → Grok X
General neutral Web     → Brave
Academic / NPL          → Crossref
Patent machine data     → EPO OPS
```

## Provider Degradation

若：

```text
quota exhausted
credential missing
API down
policy stale
model unavailable
```

Runtime 應重新選 Binding，而不是讓 Search Method 消失。

## 必須證明

```text
method.lexical_search
↓
Brave unavailable
↓
Grok Web selected
↓
Grok unavailable
↓
Gemini selected
```

Method identity 不變。

## Exit Gate

- [ ] ProviderState typed contract
- [ ] health / availability state
- [ ] credential presence state
- [ ] quota / cost / latency state
- [ ] deterministic routing
- [ ] provider preference
- [ ] fallback
- [ ] same-method provider substitution test
- [ ] routing decision enters Receipt
- [ ] no credential leakage

---

# 8. v0.3 — Search Method Corpus + Core Method Set

## Goal

建立真正的：

> **Search Method Space**

而不是只增加 Provider。

## Search Method Corpus

每個方法至少記：

```text
method_id
canonical_name
aliases
history
domain
goal
representation
direction
interaction_mode
input_contract
output_contract
strengths
failure_modes
preconditions
provider_requirements
composition_rules
references
implementation_status
validation_status
```

## Method Lifecycle

```text
DOCUMENTED
EXPERIMENTAL
EXECUTABLE
VALIDATED
DEPRECATED
```

## 長期 Corpus

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
Entity Search
Temporal Search
Version Search
Graph Search
Cross-Language Search
Federated Search
Adversarial Search
```

v1.0 不要求全部 executable。

## Core Executable Method Set Target

至少：

```text
lexical_search
exact_search / phrase_search
query_divergence
identity_search
entity_search
classification_search
backward_citation
forward_citation
counter_evidence_search
temporal_version_search
relation / family resolve
fetch_document
extract_candidate_evidence
```

## Method Coverage

新增：

```text
MethodCoverage
```

與 ProviderCoverage 分開。

## Exit Gate

- [ ] Search Method Corpus schema
- [ ] Method lifecycle
- [ ] documented/executable distinction
- [ ] Core Method Set
- [ ] MethodCoverage metric
- [ ] provider requirements
- [ ] composition metadata
- [ ] no provider-branded method IDs

---

# 9. v0.4 — Autonomous Search Planner v1

## Goal

從 deterministic baseline 進入：

> **Task / Evidence / Gap / ProviderState-aware autonomous planning**

## Planner Input

```text
SearchTask
SearchState
EvidenceState
GapState
ProviderState
MethodRegistrySnapshot
ProviderRegistrySnapshot
Budget
```

## Planner Output

```text
SearchPlan
```

包含：

```text
ActionNode
BranchNode
JoinNode
LoopNode
StopNode
```

## AI Proposes, Runtime Validates

```text
AI / planner proposes plan
↓
PlanValidator
↓
PolicyEvaluator
↓
ExecutionRuntime
```

AI 不得越過 validator / policy。

## Planner 能力

至少：

```text
branching
parallel methods
join
bounded loops
fallback
provider substitution
method substitution
gap-directed continuation
budget-aware planning
```

## Exit Gate

- [ ] autonomous plan proposal
- [ ] validator remains authoritative
- [ ] multi-method plan
- [ ] branch / join
- [ ] bounded loop
- [ ] fallback
- [ ] method substitution
- [ ] provider substitution
- [ ] budget awareness
- [ ] gap-directed replanning
- [ ] planner metadata enters Receipt
- [ ] no persisted planner CoT

---

# 10. v0.5 — Stopping / Coverage / Saturation

## Goal

回答：

> **AI 到底什麼時候應該停止搜尋？**

## Contracts

```text
StopCondition
SearchBudget
CoverageState
SaturationState
UncertaintyState
```

## Canonical Stop Reasons

```text
NO_MATERIAL_GAP_REMAINS
COVERAGE_TARGET_MET
MARGINAL_GAIN_BELOW_THRESHOLD
SATURATION_REACHED
BUDGET_EXHAUSTED
PROVIDER_UNAVAILABLE
POLICY_BLOCKED
HUMAN_REVIEW_REQUIRED
TIME_LIMIT_REACHED
```

## Saturation

只表示：

> 在目前 method/provider/budget 下，新增資訊的 marginal gain 已下降。

不得解讀為完整 recall。

## Coverage Axes

```text
Method Coverage
Provider Coverage
Source Coverage
Evidence Coverage
Jurisdiction Coverage
Language Coverage
Temporal Coverage
Domain-specific Coverage
```

## Exit Gate

- [ ] typed StopCondition
- [ ] typed SearchBudget
- [ ] CoverageState
- [ ] SaturationState
- [ ] UncertaintyState
- [ ] marginal-gain stop logic
- [ ] human-review stop
- [ ] budget stop
- [ ] Receipt stop reason
- [ ] Saturation != CompleteRecall tests

---

# 11. v0.6 — Evidence / Provenance Closure

## Goal

收斂現有 evidence / source-lineage 元件，形成穩定 v1 Evidence Boundary。

## Canonical Pipeline

```text
Discovery Candidate
↓
Fetched Source
↓
AcquiredAsset
↓
CandidateEvidence
↓
EvidenceAnchor
↓
Verification
↓
Claim Link
↓
Corroboration / Contradiction
↓
Evidence Ledger
```

## 禁止捷徑

下列都不能直接成為 Verified Evidence：

```text
Brave rank
Grok citation
Gemini grounding citation
Crossref rank
EPO search rank
```

## Model-Native Boundary

```text
Gemini grounded answer != Verified Evidence
Grok synthesis != Verified Evidence
```

只使用可驗證 source references 作 discovery / acquisition frontier。

## Provenance Identity

至少追：

```text
source identity
work identity
version identity
content hash
retrieval time
publication time
origin relation
source family
independent root
```

## Exit Gate

- [ ] stable Candidate → Evidence pipeline
- [ ] provenance identity
- [ ] source-family / origin tracing
- [ ] independent source roots
- [ ] anchor verification
- [ ] semantic support separate
- [ ] contradiction support
- [ ] version identity
- [ ] append-only Evidence Ledger
- [ ] policy metadata travels downstream

---

# 12. v0.7 — Search Receipt & Experience Runtime

## Goal

把 Search Receipt 從 audit artifact 提升成：

> **Search Experience Dataset**

## Search Receipt 必須記

```text
task
epoch
action
method
provider
surface
binding
provider state
routing decision
policy result
query/input refs
observation
result count
latency
cost
candidate gain
evidence gain
gap reduction
failure
stop reason
```

## 禁止保存

```text
hidden chain-of-thought
private reasoning
provider hidden reasoning
raw credentials
secret tokens
```

## Experience Metrics

```text
MethodSuccess(method, task_class)
ProviderSuccess(provider, method)
GapResolution(method, gap_type)
EvidenceYield
CostEfficiency
LatencyEfficiency
ProviderFailureRate
MethodFailureRate
```

## Planner Prior

歷史 experience 可以形成 planner prior，但不能形成 authorization。

## Exit Gate

- [ ] complete action receipts
- [ ] final SearchReceipt
- [ ] replay metadata
- [ ] failure receipts
- [ ] provider substitution history
- [ ] method substitution history
- [ ] gap reduction metrics
- [ ] cost / latency metrics
- [ ] planner prior interface
- [ ] Learning != Authorization test

---

# 13. v0.8 — Evaluation / Benchmark Suite

## Goal

Omphalos 必須能回答：

> **比直接讓模型搜尋有什麼改善？**

## Provider Substitution Benchmark

比較：

```text
Brave-only
Grok Web-only
Gemini-only
Hybrid routing
```

Metrics：

```text
Verified Evidence Yield
Independent Source Coverage
Gap Reduction
Cost
Latency
Failure Rate
```

## Method Diversity Benchmark

比較：

```text
lexical only
```

vs.

```text
lexical
+ exact
+ classification
+ citation
+ counter evidence
```

## Planner Benchmark

```text
fixed plan
vs
gap-directed adaptive plan
```

## Provenance Benchmark

```text
raw source mentions
vs
independent source roots
```

## Replay Benchmark

同一：

```text
Task
Registry Snapshot
Provider Fixture
Policy Snapshot
```

應能 deterministic replay。

## Exit Gate

- [ ] provider benchmark
- [ ] method benchmark
- [ ] planner benchmark
- [ ] provenance benchmark
- [ ] replay benchmark
- [ ] machine-readable outputs
- [ ] baseline comparisons
- [ ] reproducibility artifacts
- [ ] benchmark docs

---

# 14. v0.9 — API Freeze / Hardening / RC

## Goal

停止新增大功能。

只做：

```text
stability
migration
security
packaging
documentation
release validation
```

## Freeze Candidate Interfaces

至少：

```text
SearchMethodSpec v1
ProviderSpec v1
ProviderState v1
MethodBinding v1
SearchTask v1
SearchState v1
SearchPlan v1
AuthorizedAction v1
ProviderObservation v1
Evidence interfaces v1
Gap interfaces v1
SearchReceipt v1
```

## Error Taxonomy

統一：

```text
policy rejection
credential failure
provider failure
binding failure
validation failure
quota failure
timeout
rate limit
malformed response
evidence verification failure
replay mismatch
```

## Packaging

Python package 暫時保留：

```text
ai_web_research
```

避免 Big-Bang rename。

可考慮新增：

```python
import omphalos
```

作 stable facade。

## Documentation

至少：

```text
Quickstart
Architecture
Provider authoring
Method authoring
Policy authoring
Domain Pack authoring
Evidence model
Search Receipt
Security / credentials
Benchmarking
Migration
```

## Exit Gate

- [ ] public API freeze
- [ ] schema/version freeze
- [ ] migration rules
- [ ] error taxonomy
- [ ] clean install
- [ ] fresh environment
- [ ] CLI/API quickstart
- [ ] example workflows
- [ ] security scan
- [ ] credential leak scan
- [ ] package reproducibility
- [ ] Release Candidate tag

---

# 15. v1.0 — Final Release Gate

v1.0 不以功能很多判定。

必須通過九個 Gate。

## G1 — Method Gate

- Search Method 是 first-class；
- 有 versioned Method Registry；
- 有 Core Method Set；
- Method 與 Provider 分離。

## G2 — Provider Gate

至少有四種 topology 實例：

```text
MODEL_NATIVE
PROVIDER_NEUTRAL
DOMAIN_SPECIFIC
LOCAL_PRIVATE
```

## G3 — Replaceability Gate

必須證明：

```text
same Method
→ provider A
→ provider A unavailable
→ provider B
```

Method identity 不變。

## G4 — Planner Gate

AI 可以：

```text
select
compose
branch
fallback
switch method
switch provider
replan
```

Runtime validator 仍具最後權威。

## G5 — Policy Gate

必須證明：

```text
UNKNOWN != ALLOW
DENY blocks execution
credentials never persist
rights metadata travels downstream
```

## G6 — Evidence Gate

必須證明：

```text
Retrieved != Verified
Citation != Support
QuoteMatch != SemanticSupport
ProviderGrounding != VerifiedEvidence
```

## G7 — Gap / Stop Gate

Runtime 必須能：

```text
identify gaps
continue search
switch methods
switch providers
stop with explicit reason
```

## G8 — Receipt Gate

每次 research execution 必須：

```text
auditable
replayable
versioned
non-CoT
credential-safe
```

## G9 — Evaluation Gate

至少有：

```text
provider substitution benchmark
method diversity benchmark
planner benchmark
provenance benchmark
replay benchmark
```

---

# 16. v1.0 Reference Workflows

v1.0 不能只靠 unit tests。

至少需要四條完整 E2E。

## 16.1 General Web Research

```text
Task
↓
Planner
↓
Brave / Grok / Gemini routing
↓
multiple methods
↓
evidence
↓
counter evidence
↓
gap analysis
↓
stop
```

## 16.2 X / Current Discourse Research

```text
Grok X
+
Grok Web / Brave
↓
candidate sources
↓
fetch / provenance verification
↓
independent source analysis
```

## 16.3 Academic / NPL Research

```text
Crossref
+
general Web
+
identity
+
citation
+
counter-evidence
```

## 16.4 Patent Prior-Art

```text
EPO
+
Crossref NPL
+
classification
+
family
+
priority
+
claims
+
coverage gaps
```

Patent Intelligence 作為 v1.0 第一個正式 Domain Pack reference implementation。

---

# 17. 不屬於 v1.0 Blocker

以下項目重要，但不得阻塞 Omphalos v1.0。

## Economic Research Platform

應作為：

```text
Omphalos-compatible Economic Domain Pack
```

獨立演進。

## Meteorological Research Platform

應作為：

```text
Omphalos-compatible Meteorological Domain Pack
```

獨立演進。

## 所有人類已知搜尋方法全部 executable

不屬於 v1.0 blocker。

v1.0 只要求：

```text
Search Method Corpus exists
+
Core Executable Method Set exists
```

---

# 18. Domain Pack Boundary

Omphalos Runtime 負責：

```text
search methods
planning
providers
policy
execution
evidence
gaps
receipts
experience
```

Domain Pack 負責：

```text
domain concepts
domain methods
domain identifiers
domain validation
domain forecasts
domain benchmarks
```

---

# 19. Backlog Policy

任何新功能先分類：

## A. Runtime Blocker
直接進目前 milestone。

## B. Runtime Enhancement
排到 v1.x。

## C. Search Method Corpus
先 documented，不一定 executable。

## D. Provider Candidate
先記 Provider Profile。

## E. Domain Pack
獨立版本管理。

## F. Research Experiment
不得直接污染 stable runtime contract。

---

# 20. Version Discipline

每一 milestone 必須：

```text
Design
↓
TDD
↓
Fresh verification
↓
Source diff
↓
PR
↓
Review
↓
Merge
↓
Version checkpoint
```

禁止：

```text
implementation half done
↓
version number changed
↓
old plan forgotten
```

---

# 21. Branch / PR Discipline

建議：

```text
integration/omphalos-v0.2-provider-state
integration/omphalos-v0.3-method-corpus
integration/omphalos-v0.4-planner
...
```

每個 milestone 原則上一個 review boundary。

避免無限疊一個巨大 PR。

---

# 22. Verification Discipline

任何「完成」宣稱前至少執行：

```text
pytest
compileall
import smoke
source diff
branch compare
secret scan
artifact verification
```

v0.9 / v1.0 再增加：

```text
clean install
reproducibility
benchmark replay
```

---

# 23. Credential Discipline

所有 Provider credentials：

```text
xAI API key
Gemini API key
Brave API key
EPO OAuth
future economic API keys
future meteorological tokens
```

只能存在：

```text
runtime secret store
environment
execution context
credential manager
```

不能出現在：

```text
GitHub source
Search Receipt
ProviderObservation
Evidence object
logs
fixtures
release bundle
```

---

# 24. Provider / API Change Discipline

若 API 改版：

```text
Provider Adapter Version
↓
Binding Version
↓
ProviderState
```

不應直接修改 Search Method identity，除非 Method semantics 本身真的改變。

---

# 25. Search Method Governance

新 Search Method 進 Executable Registry 前，至少需要：

```text
canonical definition
input contract
output contract
failure modes
provider requirements
test fixture
at least one implementation
method-level validation
```

---

# 26. Domain Governance

Domain-specific Method 不應硬塞進 core。

例如：

```text
patent.family_resolve
meteorology.station_bias_correction
economics.vintage_revision_analysis
```

應保持 Domain Pack identity。

---

# 27. v1.0 Public Identity

建議正式對外描述：

> **Omphalos / AUSI Runtime is a provider-replaceable, policy-aware, evidence-grounded, auditable AI-native Search Method Runtime.**

中文：

> **Omphalos / AUSI Runtime 是一個 Provider 可替換、具 Policy 邊界、以 Evidence 為基礎、可審計的 AI 原生搜尋方法 Runtime。**

---

# 28. v1.0 不應宣稱

```text
solves all search
complete recall
all human search methods implemented
all evidence verified
AGI research system
fully autonomous science
perfect forecasting
complete patent recall
```

---

# 29. Release Artifact

v1.0 Final Release 至少產生：

```text
source tree
canonical docs
API reference
examples
benchmark artifacts
release manifest
dependency lock / reproducibility metadata
FINAL ZIP
SHA-256
Git tag
GitHub Release
```

---

# 30. Final v1.0 Verification Procedure

```text
1. source-diff verification
2. final HEAD verification
3. clean-environment installation
4. full Runtime test suite
5. Reference Workflow verification
6. Benchmark replay
7. credential / secret scan
8. policy fixture verification
9. reproducible package build
10. FINAL ZIP
11. SHA-256
12. release tag
```

---

# 31. Canonical Roadmap Summary

```text
CURRENT
│
├─ Grok Web / X
├─ Gemini Google Search
├─ Brave
├─ Crossref
├─ EPO
├─ Policy
├─ Evidence
└─ Search Receipt foundations
│
▼
v0.2
ProviderState + Dynamic Routing
│
▼
v0.3
Search Method Corpus + Core Method Set
│
▼
v0.4
Autonomous Search Planner
│
▼
v0.5
Stopping + Coverage + Saturation
│
▼
v0.6
Evidence + Provenance Closure
│
▼
v0.7
Receipt + Experience Learning
│
▼
v0.8
Benchmarks + Evaluation
│
▼
v0.9
API Freeze + Hardening + RC
│
▼
v1.0
Provider-replaceable
Policy-aware
Evidence-grounded
Auditable
Replayable
Gap-directed
AI-native Search Method Runtime
```

---

# 32. Local AI Canonical Instruction

給任何後續接手 Omphalos 的 AI：

> **不要為了新 API 偏離 v1.0 Roadmap。**

> **不要把 Provider 新增誤認成 Search Intelligence 增長。**

> **不要為了完成 Omphalos v1.0，先去完成整個經濟研究院、氣象研究院或所有 Domain Pack。**

> **不要因為某個新搜尋法很有趣，就跳過目前 milestone。**

> **新方法先進 Search Method Corpus。**

> **新 Provider 先進 Provider Candidate / Binding。**

> **新 Domain 能力進 Domain Pack。**

> **主 Runtime 只按照本 Roadmap 往 v1.0 推進。**

---

# 33. 最終原則

Omphalos 的 v1.0 不是 API 數量競賽，也不是功能數量競賽。

它要證明的是：

$$
\boxed{
\text{AI}
+
\text{Search Method Space}
+
\text{Provider Replaceability}
+
\text{Policy}
+
\text{Evidence}
+
\text{Gap-Directed Planning}
+
\text{Receipt}
+
\text{Learning}
}
$$

可以形成一個穩定、可擴張的 Runtime。

最終仍回到：

$$
\boxed{
\text{Method Stable}
\quad
\text{Provider Replaceable}
\quad
\text{API Disposable}
}
$$

而 v1.0 的真正完成標準是：

> **Omphalos 已經能把「搜尋方法」本身當成 AI 可以自主組合與執行的第一級計算／認知物件。**

---

# End of Canonical Roadmap
