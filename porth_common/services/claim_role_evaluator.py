"""JWT claim-to-role evaluation engine for Porth.

Evaluates JWT claims against claim-to-role mappings to automatically assign roles
to users during authentication. Used during JIT (just-in-time) provisioning to
determine which roles a user should have based on their identity provider attributes.

Supports both list and scalar claim matching, priority-based evaluation, and fallback
to default roles when no mappings match.
"""

from __future__ import annotations

from porth_common.models.claim_role_mapping import ClaimRoleMapping
from porth_common.services.exceptions import AccessDeniedError


class ClaimRoleEvaluator:
    """Evaluates JWT claims against claim-to-role mappings to determine assigned roles.

    Used during user login to automatically assign internal roles based on JWT claims
    (typically from identity provider groups, departments, or custom attributes).

    Evaluation algorithm:
    1. Filter to active mappings only
    2. Sort by priority descending (higher priority evaluated first)
    3. For each mapping, check if JWT claim matches
    4. Collect all matched role IDs (may have multiple matches)
    5. Return deduplicated, sorted role IDs
    6. If no matches and default_role_ids provided, return defaults
    7. If no matches and no defaults, raise AccessDeniedError (deny login)

    Claim matching:
    - For list claims (e.g., "groups": ["admin", "users"]): check if mapping value in list
    - For scalar claims: check if mapping value equals claim value
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
