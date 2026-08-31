from __future__ import annotations

from dataclasses import dataclass

from ai_web_research.methods.registry import MethodRegistrySnapshot
from ai_web_research.methods.spec import MethodAvailability, SearchMethodSpec
from ai_web_research.providers.registry import ProviderRegistrySnapshot
from .graph import ActionNode, EdgeKind, LoopNode, PlanNode, SearchPlan


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    node_id: str | None = None
    action_id: str | None = None
    severity: str = "error"


@dataclass(frozen=True)
class PlanValidationResult:
    valid: bool
    issues: tuple[ValidationIssue, ...]


class PlanValidator:
    def validate(
        self,
        plan: SearchPlan,
        methods: MethodRegistrySnapshot,
        providers: ProviderRegistrySnapshot,
    ) -> PlanValidationResult:
        issues: list[ValidationIssue] = []
        node_map: dict[str, PlanNode] = {}
        method_by_node: dict[str, SearchMethodSpec] = {}

        for node in plan.nodes:
            if node.node_id in node_map:
                issues.append(ValidationIssue("PLAN_DUPLICATE_NODE", f"duplicate node {node.node_id}", node.node_id))
            node_map[node.node_id] = node
            if isinstance(node, LoopNode) and node.max_iterations < 1:
                issues.append(ValidationIssue("PLAN_INVALID_LOOP", "loop max_iterations must be >= 1", node.node_id))

        for entry in plan.entry_node_ids:
            if entry not in node_map:
                issues.append(ValidationIssue("PLAN_UNKNOWN_NODE", f"unknown entry node {entry}", entry))

        for edge in plan.edges:
            if edge.source not in node_map:
                issues.append(ValidationIssue("PLAN_UNKNOWN_NODE", f"unknown edge source {edge.source}", edge.source))
            if edge.target not in node_map:
                issues.append(ValidationIssue("PLAN_UNKNOWN_NODE", f"unknown edge target {edge.target}", edge.target))

        for node in plan.nodes:
            if not isinstance(node, ActionNode):
                continue
            action = node.action
            try:
                method = methods.get(action.method_ref)
                method_by_node[node.node_id] = method
            except KeyError:
                issues.append(ValidationIssue("PLAN_UNKNOWN_METHOD", f"unknown method {action.method_ref}", node.node_id, action.action_id))
                continue

            if method.availability in {MethodAvailability.UNAVAILABLE, MethodAvailability.DEPRECATED}:
                issues.append(ValidationIssue("PLAN_METHOD_UNAVAILABLE", f"method {method.method_id} is {method.availability}", node.node_id, action.action_id))

            try:
                binding = providers.get_binding(action.binding_id)
            except KeyError:
                issues.append(ValidationIssue("PLAN_UNKNOWN_BINDING", f"unknown binding {action.binding_id}", node.node_id, action.action_id))
                continue

            if (
                binding.method_ref != action.method_ref
                or binding.provider_ref != action.provider_ref
                or binding.surface_id != action.surface_id
                or not binding.enabled
            ):
                issues.append(ValidationIssue("PLAN_UNKNOWN_BINDING", f"binding {action.binding_id} does not match action", node.node_id, action.action_id))
                continue

            try:
                surface = providers.surface(action.provider_ref, action.surface_id)
            except KeyError:
                issues.append(ValidationIssue("PLAN_UNKNOWN_PROVIDER", "provider surface does not resolve", node.node_id, action.action_id))
                continue

            missing = method.required_capabilities - surface.capabilities
            if missing:
                issues.append(ValidationIssue("PLAN_CAPABILITY_MISMATCH", f"missing capabilities: {sorted(missing)}", node.node_id, action.action_id))

            param_error = _validate_parameters(method.parameter_schema, action.parameters)
            if param_error:
                issues.append(ValidationIssue("PLAN_INVALID_PARAMETERS", param_error, node.node_id, action.action_id))

        for edge in plan.edges:
            source = node_map.get(edge.source)
            target = node_map.get(edge.target)
            if not isinstance(source, ActionNode) or not isinstance(target, ActionNode):
                continue
            source_method = method_by_node.get(edge.source)
            target_method = method_by_node.get(edge.target)
            if source_method is None or target_method is None:
                continue
            for kind in edge.artifact_kinds:
                if kind not in source_method.output_contract.produces or kind not in target_method.input_contract.accepts:
                    issues.append(
                        ValidationIssue(
                            "PLAN_ARTIFACT_TYPE_MISMATCH",
                            f"artifact {kind} is not compatible from {source_method.method_id} to {target_method.method_id}",
                            edge.target,
                            target.action.action_id,
                        )
                    )

        if _has_implicit_cycle(plan, node_map):
            issues.append(ValidationIssue("PLAN_UNBOUNDED_CYCLE", "plan contains a cycle without LOOP_BACK"))

        return PlanValidationResult(valid=not issues, issues=tuple(issues))


def _validate_parameters(schema: dict, parameters: dict) -> str | None:
    if not schema:
        return None
    if schema.get("type") == "object" and not isinstance(parameters, dict):
        return "parameters must be an object"
    required = schema.get("required", [])
    for name in required:
        if name not in parameters:
            return f"missing required parameter {name!r}"
    properties = schema.get("properties", {})
    for name, value in parameters.items():
        rule = properties.get(name)
        if not isinstance(rule, dict):
            continue
        expected = rule.get("type")
        if expected == "string" and not isinstance(value, str):
            return f"parameter {name!r} must be a string"
        if expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            return f"parameter {name!r} must be an integer"
        if expected == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            return f"parameter {name!r} must be a number"
        minimum = rule.get("minimum")
        if minimum is not None and isinstance(value, (int, float)) and value < minimum:
            return f"parameter {name!r} must be >= {minimum}"
    return None


def _has_implicit_cycle(plan: SearchPlan, node_map: dict[str, PlanNode]) -> bool:
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_map}
    for edge in plan.edges:
        if edge.kind is EdgeKind.LOOP_BACK:
            continue
        if edge.source in adjacency and edge.target in node_map:
            adjacency[edge.source].append(edge.target)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in visited:
            return False
        visiting.add(node_id)
        for nxt in adjacency[node_id]:
            if visit(nxt):
                return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    return any(visit(node_id) for node_id in adjacency if node_id not in visited)
