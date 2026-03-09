"""JWT claim-to-role evaluation engine for Porth."""

from __future__ import annotations

from porth_common.models.claim_role_mapping import ClaimRoleMapping
from porth_common.services.exceptions import AccessDeniedError


class ClaimRoleEvaluator:
    """Evaluates JWT claims against claim-to-role mappings to determine assigned roles.

    The evaluator:
    1. Sorts mappings by priority (descending — higher priority first)
    2. Checks each mapping to see if the JWT claim matches
    3. Collects all matched role IDs and deduplicates them
    4. Falls back to default roles if no matches are found
    5. Raises AccessDeniedError if no roles are matched and no defaults provided
    """

    @staticmethod
    def evaluate(
        jwt_claims: dict,
        mappings: list[ClaimRoleMapping],
        default_role_ids: list[str] | None = None,
    ) -> list[str]:
        """Evaluate JWT claims against mappings to determine roles.

        Args:
            jwt_claims: Dictionary of JWT claims (e.g., {"groups": ["admin", "users"], "roles": "editor"})
            mappings: List of ClaimRoleMapping objects to evaluate
            default_role_ids: Optional list of role IDs to use if no mappings match

        Returns:
            List of matched role IDs (deduplicated)

        Raises:
            AccessDeniedError: If no roles are matched and no default_role_ids provided
        """
        # Filter and sort active mappings by priority (descending)
        active_mappings = [m for m in mappings if m.is_active]
        sorted_mappings = sorted(
            active_mappings, key=lambda m: m.priority, reverse=True
        )

        matched_role_ids = set()

        # Evaluate each mapping
        for mapping in sorted_mappings:
            if ClaimRoleEvaluator._matches_mapping(jwt_claims, mapping):
                matched_role_ids.add(mapping.role_id)

        # If we have matches, return them
        if matched_role_ids:
            return sorted(list(matched_role_ids))

        # If no matches and we have defaults, return them
        if default_role_ids:
            return sorted(list(set(default_role_ids)))

        # No matches and no defaults — deny access
        raise AccessDeniedError("User is not authorised for this tenant")

    @staticmethod
    def _matches_mapping(jwt_claims: dict, mapping: ClaimRoleMapping) -> bool:
        """Check if a JWT claim matches the given mapping.

        Args:
            jwt_claims: Dictionary of JWT claims
            mapping: ClaimRoleMapping to check against

        Returns:
            True if the mapping matches, False otherwise
        """
        # Check if the claim key exists in the JWT claims
        if mapping.claim_key not in jwt_claims:
            return False

        claim_value = jwt_claims[mapping.claim_key]

        # If claim value is a list, check if mapping value is in the list
        if isinstance(claim_value, list):
            return mapping.claim_value in claim_value

        # Otherwise, compare directly
        return claim_value == mapping.claim_value
