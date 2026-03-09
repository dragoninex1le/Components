"""Custom exceptions for Porth services."""

from __future__ import annotations


class AccessDeniedError(Exception):
    """Raised when a user does not have access to a tenant or resource.

    This exception is typically raised when:
    - No JWT claim matches any active claim-to-role mappings
    - No default roles are provided to fall back on
    - User authentication/authorization fails
    """

    def __init__(self, message: str = "User is not authorised for this tenant"):
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


class CompilationError(Exception):
    """Raised when claim mapping configuration compilation fails.

    This exception is raised when:
    - Operation configuration is invalid
    - Required fields are missing in operation config
    - Operation type is not supported
    - Example JWT validation fails during compilation
    """

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message
