# Omphalos / AUSI Runtime Quickstart — v1.0.0

Omphalos `1.0.0` is the first final release of the frozen v1 public API.

## Install

From a source checkout:

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e ".[dev]"
```

## Verify the package

```bash
omphalos version
omphalos doctor --json
omphalos api --json
```

These three commands are offline package/public-contract checks. They do not contact a Provider and do not require API credentials.

## Import the stable facade

```python
import omphalos

print(omphalos.__version__)
print(omphalos.PUBLIC_API_VERSION)

task_type = omphalos.SearchTask
method_type = omphalos.SearchMethodSpec
provider_type = omphalos.ProviderSpec
receipt_type = omphalos.SearchReceipt
```

Applications targeting v1 should prefer `import omphalos` for frozen public contracts. The implementation packages remain `ai_web_research` and `crawler` for compatibility.

## Runtime boundary

The facade does not authorize execution. Normal runtime flow remains:

```text
Task
→ Planner
→ Search Method
→ Provider routing
→ Policy authorization
→ Execution
→ Evidence / Gap
→ Stop / Receipt / Experience
```

The public API version is `1.0`. Provider/API churn remains an adapter/routing concern and does not by itself change Search Method identity.
