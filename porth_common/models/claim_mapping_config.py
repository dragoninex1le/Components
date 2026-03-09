"""ClaimMappingConfig model for compiled JWT claim transformation pipelines."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ClaimMappingConfig(BaseModel):
    """Represents a compiled claim mapping configuration for JWT transformation.

    This model stores both the human-readable mapping configuration and the compiled
    operations that can be executed against JWT claims. It supports versioning to
    enable rollback and audit trails.
    """

    id: str = Field(description="Unique configuration identifier (UUID)")
    tenant_id: str = Field(description="Tenant identifier")
    app_namespace: str = Field(
        description="Application namespace, e.g. 'cart-agent', 'ops-agent'"
    )
    version: int = Field(
        description="Configuration version, auto-incremented on save"
    )
    mapping_source: dict[str, Any] = Field(
        description="Human-readable JSON mapping configuration"
    )
    compiled_ops: list[dict[str, Any]] = Field(
        description="Compiled operations list for execution"
    )
    compiled_hash: str = Field(
        description="SHA256 hash of compiled_ops for integrity checking"
    )
    example_jwt: Optional[dict[str, Any]] = Field(
        default=None,
        description="Example JWT used for compile-time validation",
    )
    validation_report: Optional[dict[str, Any]] = Field(
        default=None,
        description="Validation results when compiled against example JWT",
    )
    compiled_at: str = Field(description="ISO 8601 datetime when config was compiled")
    created_at: str = Field(description="ISO 8601 datetime when config was created")
    updated_at: str = Field(description="ISO 8601 datetime when config was last updated")

    model_config = {"extra": "allow"}
