from __future__ import annotations

from ai_web_research.providers.registry import ProviderRegistrySnapshot

from .models import AuthorizedAction, ExecutionContext, ProviderObservation
from .registry import AdapterRegistry


class ExecutionRejected(RuntimeError):
    pass


class ExecutionRuntime:
    def __init__(
        self,
        adapters: AdapterRegistry,
        providers: ProviderRegistrySnapshot,
    ) -> None:
        self.adapters = adapters
        self.providers = providers

    async def execute(
        self,
        authorized: AuthorizedAction,
        context: ExecutionContext,
    ) -> ProviderObservation:
        if not authorized.authorization.is_executable:
            raise ExecutionRejected(
                f"action {authorized.action.action_id} is not executable: "
                f"{authorized.authorization.decision}"
            )

        action = authorized.action
        try:
            binding = self.providers.get_binding(action.binding_id)
        except KeyError as exc:
            raise ExecutionRejected(f"unknown binding: {action.binding_id}") from exc

        if not binding.enabled:
            raise ExecutionRejected(f"binding is disabled: {binding.binding_id}")

        if (
            binding.method_ref != action.method_ref
            or binding.provider_ref != action.provider_ref
            or binding.surface_id != action.surface_id
        ):
            raise ExecutionRejected(
                f"action {action.action_id} does not match binding {binding.binding_id}"
            )

        adapter = self.adapters.get(binding.adapter_id, binding.adapter_version)
        return await adapter.execute(authorized, context)
