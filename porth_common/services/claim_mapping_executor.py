"""Claim mapping executor for running compiled operations against JWT claims."""

from __future__ import annotations

import re
from typing import Any


class ClaimMappingExecutor:
    """Executes compiled claim mapping operations against JWT claims.

    Target performance: < 5ms for typical payloads.
    On any operation error, the field is skipped and execution continues (graceful degradation).
    """

    def execute(self, compiled_ops: list[dict[str, Any]], jwt_claims: dict) -> dict[str, Any]:
        """Execute compiled operations against JWT claims.

        Args:
            compiled_ops: List of compiled operation dicts
            jwt_claims: Raw JWT claims dictionary

        Returns:
            Dictionary of {target_field: extracted_value}
            Supports nested paths via dot notation (e.g., "address.street")

        Note:
            On any operation error, that field is skipped and execution continues.
        """
        result: dict[str, Any] = {}

        for op in compiled_ops:
            try:
                op_type = op.get("type")

                if op_type == "direct":
                    self._execute_direct(op, jwt_claims, result)
                elif op_type == "concat":
                    self._execute_concat(op, jwt_claims, result)
                elif op_type == "regex_extract":
                    self._execute_regex_extract(op, jwt_claims, result)
                elif op_type == "coalesce":
                    self._execute_coalesce(op, jwt_claims, result)
                elif op_type == "split":
                    self._execute_split(op, jwt_claims, result)
                elif op_type == "template":
                    self._execute_template(op, jwt_claims, result)
                elif op_type == "lowercase":
                    self._execute_lowercase(op, jwt_claims, result)
                elif op_type == "uppercase":
                    self._execute_uppercase(op, jwt_claims, result)
            except Exception:
                # Graceful degradation: skip this field on any error
                pass

        return result

    def _get_nested_value(self, obj: Any, path: str) -> Any:
        """Get a value from an object using dot notation.

        Args:
            obj: Object to traverse
            path: Dot-separated path (e.g., "address.street")

        Returns:
            The value at the path, or None if not found
        """
        if not isinstance(path, str):
            return None

        parts = path.split(".")
        current = obj

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

            if current is None:
                return None

        return current

    def _execute_direct(
        self, op: dict[str, Any], jwt_claims: dict, result: dict[str, Any]
    ) -> None:
        """Execute direct mapping: copy claim to target."""
        source = op.get("source")
        target = op.get("target")

        value = self._get_nested_value(jwt_claims, source)
        if value is not None:
            result[target] = value

    def _execute_concat(
        self, op: dict[str, Any], jwt_claims: dict, result: dict[str, Any]
    ) -> None:
        """Execute concatenation: join multiple claims."""
        sources = op.get("sources", [])
        separator = op.get("separator", "")
        target = op.get("target")

        parts = []
        for source in sources:
            value = self._get_nested_value(jwt_claims, source)
            if value is not None:
                parts.append(str(value))

        if parts:
            result[target] = separator.join(parts)

    def _execute_regex_extract(
        self, op: dict[str, Any], jwt_claims: dict, result: dict[str, Any]
    ) -> None:
        """Execute regex extraction."""
        source = op.get("source")
        pattern = op.get("pattern")
        group = op.get("group")
        target = op.get("target")

        value = self._get_nested_value(jwt_claims, source)
        if value is None:
            return

        match = re.search(pattern, str(value))
        if match:
            try:
                extracted = match.group(group)
                if extracted is not None:
                    result[target] = extracted
            except IndexError:
                # Group index out of range
                pass

    def _execute_coalesce(
        self, op: dict[str, Any], jwt_claims: dict, result: dict[str, Any]
    ) -> None:
        """Execute coalesce: take first non-null value."""
        sources = op.get("sources", [])
        target = op.get("target")

        for source in sources:
            value = self._get_nested_value(jwt_claims, source)
            if value is not None:
                result[target] = value
                break

    def _execute_split(
        self, op: dict[str, Any], jwt_claims: dict, result: dict[str, Any]
    ) -> None:
        """Execute split: split claim and take an index."""
        source = op.get("source")
        delimiter = op.get("delimiter")
        index = op.get("index")
        target = op.get("target")

        value = self._get_nested_value(jwt_claims, source)
        if value is None:
            return

        parts = str(value).split(delimiter)
        try:
            if 0 <= index < len(parts):
                result[target] = parts[index]
        except (IndexError, TypeError):
            pass

    def _execute_template(
        self, op: dict[str, Any], jwt_claims: dict, result: dict[str, Any]
    ) -> None:
        """Execute template: format string with placeholders."""
        template = op.get("template")
        target = op.get("target")

        # Extract placeholder names from template
        # Look for {name} patterns
        placeholders = re.findall(r"\{(\w+)\}", template)

        # Build a dictionary for string formatting
        format_dict = {}
        for placeholder in placeholders:
            value = self._get_nested_value(jwt_claims, placeholder)
            if value is not None:
                format_dict[placeholder] = str(value)

        # Only format if we have at least some values
        if format_dict:
            try:
                # Use partial formatting - missing keys won't cause errors
                formatted = template.format_map(format_dict)
                # Only set result if template was actually substituted
                if formatted != template or not placeholders:
                    result[target] = formatted
            except (KeyError, ValueError):
                pass

    def _execute_lowercase(
        self, op: dict[str, Any], jwt_claims: dict, result: dict[str, Any]
    ) -> None:
        """Execute lowercase transformation."""
        source = op.get("source")
        target = op.get("target")

        value = self._get_nested_value(jwt_claims, source)
        if value is not None:
            result[target] = str(value).lower()

    def _execute_uppercase(
        self, op: dict[str, Any], jwt_claims: dict, result: dict[str, Any]
    ) -> None:
        """Execute uppercase transformation."""
        source = op.get("source")
        target = op.get("target")

        value = self._get_nested_value(jwt_claims, source)
        if value is not None:
            result[target] = str(value).upper()
