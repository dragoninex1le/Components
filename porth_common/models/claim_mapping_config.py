"""ClaimMappingConfig entity model for JWT claim transformation pipelines.

ClaimMappingConfig stores compiled configurations for transforming JWT claims into
user profile data. It bridges human-readable YAML configurations with compiled operations
that execute efficiently at scale. Versioning enables audit trails and quick rollback
if a configuration breaks user provisioning.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ClaimMappingConfig(BaseModel):
    """Represents a compiled claim mapping configuration for JWT transformation.

    Why ClaimMappingConfig exists:
    - Define how to transform JWT claims into user profile fields (email, display_name, etc.)
    - Support complex claim transformations (concatenation, regex extraction, templating)
    - Enable compilation of human-readable configs into optimized operations
    - Maintain audit trail and enable rollback via versioning
    - Validate configurations against example JWTs before deployment

    Key relationships:
    - Many-to-one with Tenant (configs are tenant-scoped)
    - Many-to-one with application namespace (app_namespace)
    - One version per {tenant, namespace, version_number}

    Business rules:
    - mapping_source is human-readable YAML/JSON defining operations
    - compiled_ops are typed operation dicts ready for executor
    - compiled_hash enables integrity checking and change detection
    - version auto-increments (1, 2, 3, ...) on each save
    - Each save is immutable; updates create new versions
    - get_latest() returns the active version
    - rollback() creates new version from historical version without deleting current
    - example_jwt optional validation data used at compile time
    - validation_report captures any warnings/errors from example JWT test

    Typical workflow:
    1. Define mapping_source (human-readable operations)
    2. Compile it (creates compiled_ops, compiled_hash, optionally validates against example)
    3. Save as new version
    4. If issues, rollback() to previous version (creates new version from old)
    5. Executor uses latest compiled_ops to transform real JWTs at login time
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
