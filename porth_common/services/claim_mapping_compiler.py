"""Claim mapping compiler for converting human-readable configs to typed operations."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from porth_common.services.exceptions import CompilationError


@dataclass
class CompilationResult:
    """Result of compilation operation."""

    compiled_ops: list[dict[str, Any]]
    compiled_hash: str
    validation_report: dict[str, Any] | None = None


class ClaimMappingCompiler:
    """Compiles human-readable JWT claim mapping configs into typed operations.

    Supported operation types:
    - direct: Map a single JWT claim path to a user field
    - concat: Concatenate multiple JWT claims
    - regex_extract: Extract via regex from a claim value
    - coalesce: Take first non-null from multiple sources
    - split: Split a claim and take an index
    - template: String template with placeholders
    - lowercase: Lowercase a claim value
    - uppercase: Uppercase a claim value
    """

    # Supported operation types
    SUPPORTED_OPS = {
        "direct",
        "concat",
        "regex_extract",
        "coalesce",
        "split",
        "template",
        "lowercase",
        "uppercase",
    }

    def compile(
        self, mapping_source: dict[str, Any], example_jwt: dict[str, Any] | None = None
    ) -> CompilationResult:
        """Compile a mapping configuration into typed operations.

        Args:
            mapping_source: Dict with 'operations' key containing list of operation configs
            example_jwt: Optional example JWT for validation against compiled ops

        Returns:
            CompilationResult with compiled_ops, compiled_hash, and optional validation_report

        Raises:
            CompilationError: If configuration is invalid
        """
        if not isinstance(mapping_source, dict):
            raise CompilationError("mapping_source must be a dictionary")

        if "operations" not in mapping_source:
            raise CompilationError("mapping_source must contain 'operations' key")

        operations = mapping_source["operations"]
        if not isinstance(operations, list):
            raise CompilationError("'operations' must be a list")

        # Validate and compile each operation
        compiled_ops = []
        for i, op_config in enumerate(operations):
            try:
                compiled_op = self._compile_operation(op_config)
                compiled_ops.append(compiled_op)
            except CompilationError as e:
                raise CompilationError(
                    f"Operation {i}: {e.message}",
                    details={"operation_index": i, **e.details},
                )

        # Calculate hash of compiled ops
        ops_json = str(compiled_ops)  # Deterministic string representation
        compiled_hash = hashlib.sha256(ops_json.encode()).hexdigest()

        # Validate against example JWT if provided
        validation_report = None
        if example_jwt is not None:
            validation_report = self._validate_against_example(
                compiled_ops, example_jwt
            )

        return CompilationResult(
            compiled_ops=compiled_ops,
            compiled_hash=compiled_hash,
            validation_report=validation_report,
        )

    def _compile_operation(self, op_config: dict[str, Any]) -> dict[str, Any]:
        """Compile and validate a single operation.

        Args:
            op_config: Operation configuration dict

        Returns:
            Compiled operation dict

        Raises:
            CompilationError: If operation config is invalid
        """
        if not isinstance(op_config, dict):
            raise CompilationError("Operation config must be a dictionary")

        op_type = op_config.get("type")
        if not op_type:
            raise CompilationError("Operation must have 'type' field")

        if op_type not in self.SUPPORTED_OPS:
            raise CompilationError(
                f"Unsupported operation type: {op_type}. Supported: {self.SUPPORTED_OPS}"
            )

        # Validate based on operation type
        if op_type == "direct":
            return self._compile_direct(op_config)
        elif op_type == "concat":
            return self._compile_concat(op_config)
        elif op_type == "regex_extract":
            return self._compile_regex_extract(op_config)
        elif op_type == "coalesce":
            return self._compile_coalesce(op_config)
        elif op_type == "split":
            return self._compile_split(op_config)
        elif op_type == "template":
            return self._compile_template(op_config)
        elif op_type == "lowercase":
            return self._compile_lowercase(op_config)
        elif op_type == "uppercase":
            return self._compile_uppercase(op_config)

    def _compile_direct(self, op_config: dict[str, Any]) -> dict[str, Any]:
        """Compile a direct mapping operation.

        Config: {"type": "direct", "source": "email", "target": "email"}
        """
        source = op_config.get("source")
        target = op_config.get("target")

        if not source:
            raise CompilationError("'direct' operation requires 'source' field")
        if not target:
            raise CompilationError("'direct' operation requires 'target' field")

        return {
            "type": "direct",
            "source": source,
            "target": target,
        }

    def _compile_concat(self, op_config: dict[str, Any]) -> dict[str, Any]:
        """Compile a concatenation operation.

        Config: {"type": "concat", "sources": ["given_name", "family_name"], "separator": " ", "target": "display_name"}
        """
        sources = op_config.get("sources")
        target = op_config.get("target")
        separator = op_config.get("separator", "")

        if not sources or not isinstance(sources, list):
            raise CompilationError("'concat' operation requires 'sources' list")
        if not target:
            raise CompilationError("'concat' operation requires 'target' field")

        return {
            "type": "concat",
            "sources": sources,
            "separator": separator,
            "target": target,
        }

    def _compile_regex_extract(self, op_config: dict[str, Any]) -> dict[str, Any]:
        """Compile a regex extraction operation.

        Config: {"type": "regex_extract", "source": "email", "pattern": "(.+)@(.+)", "group": 1, "target": "username"}
        """
        source = op_config.get("source")
        pattern = op_config.get("pattern")
        group = op_config.get("group")
        target = op_config.get("target")

        if not source:
            raise CompilationError("'regex_extract' operation requires 'source' field")
        if not pattern:
            raise CompilationError(
                "'regex_extract' operation requires 'pattern' field"
            )
        if group is None:
            raise CompilationError("'regex_extract' operation requires 'group' field")
        if not target:
            raise CompilationError("'regex_extract' operation requires 'target' field")

        # Validate regex pattern
        try:
            re.compile(pattern)
        except re.error as e:
            raise CompilationError(f"Invalid regex pattern: {e}")

        return {
            "type": "regex_extract",
            "source": source,
            "pattern": pattern,
            "group": group,
            "target": target,
        }

    def _compile_coalesce(self, op_config: dict[str, Any]) -> dict[str, Any]:
        """Compile a coalesce operation (first non-null).

        Config: {"type": "coalesce", "sources": ["preferred_username", "email", "sub"], "target": "display_name"}
        """
        sources = op_config.get("sources")
        target = op_config.get("target")

        if not sources or not isinstance(sources, list):
            raise CompilationError("'coalesce' operation requires 'sources' list")
        if not target:
            raise CompilationError("'coalesce' operation requires 'target' field")

        return {
            "type": "coalesce",
            "sources": sources,
            "target": target,
        }

    def _compile_split(self, op_config: dict[str, Any]) -> dict[str, Any]:
        """Compile a split operation.

        Config: {"type": "split", "source": "name", "delimiter": " ", "index": 0, "target": "first_name"}
        """
        source = op_config.get("source")
        delimiter = op_config.get("delimiter")
        index = op_config.get("index")
        target = op_config.get("target")

        if not source:
            raise CompilationError("'split' operation requires 'source' field")
        if delimiter is None:
            raise CompilationError("'split' operation requires 'delimiter' field")
        if index is None:
            raise CompilationError("'split' operation requires 'index' field")
        if not target:
            raise CompilationError("'split' operation requires 'target' field")

        return {
            "type": "split",
            "source": source,
            "delimiter": delimiter,
            "index": index,
            "target": target,
        }

    def _compile_template(self, op_config: dict[str, Any]) -> dict[str, Any]:
        """Compile a template operation.

        Config: {"type": "template", "template": "{given_name} {family_name}", "target": "display_name"}
        """
        template = op_config.get("template")
        target = op_config.get("target")

        if not template:
            raise CompilationError("'template' operation requires 'template' field")
        if not target:
            raise CompilationError("'template' operation requires 'target' field")

        return {
            "type": "template",
            "template": template,
            "target": target,
        }

    def _compile_lowercase(self, op_config: dict[str, Any]) -> dict[str, Any]:
        """Compile a lowercase operation.

        Config: {"type": "lowercase", "source": "email", "target": "email"}
        """
        source = op_config.get("source")
        target = op_config.get("target")

        if not source:
            raise CompilationError("'lowercase' operation requires 'source' field")
        if not target:
            raise CompilationError("'lowercase' operation requires 'target' field")

        return {
            "type": "lowercase",
            "source": source,
            "target": target,
        }

    def _compile_uppercase(self, op_config: dict[str, Any]) -> dict[str, Any]:
        """Compile an uppercase operation.

        Config: {"type": "uppercase", "source": "department", "target": "department"}
        """
        source = op_config.get("source")
        target = op_config.get("target")

        if not source:
            raise CompilationError("'uppercase' operation requires 'source' field")
        if not target:
            raise CompilationError("'uppercase' operation requires 'target' field")

        return {
            "type": "uppercase",
            "source": source,
            "target": target,
        }

    def _validate_against_example(
        self, compiled_ops: list[dict[str, Any]], example_jwt: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate compiled operations against an example JWT.

        Returns a report with success status and any warnings/errors.
        """
        from porth_common.services.claim_mapping_executor import ClaimMappingExecutor

        report = {
            "valid": True,
            "executed_ops": 0,
            "skipped_ops": 0,
            "errors": [],
            "warnings": [],
        }

        executor = ClaimMappingExecutor()
        try:
            result = executor.execute(compiled_ops, example_jwt)
            report["executed_ops"] = len(result)
            report["result_sample"] = result
        except Exception as e:
            report["valid"] = False
            report["errors"].append(str(e))

        return report
