"""
Structured error types for MCP tools.

Provides consistent error classification and handling across all tools.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class ErrorCode(Enum):
    """
    Categorized error codes for MCP tools.

    Ranges:
    - E00x: Input validation
    - E10x: Home Assistant
    - E20x: Research/Web
    - E30x: Memory
    - E40x: System/General
    """

    # Input validation (E00x)
    INVALID_PARAMETER = "E001"
    MISSING_PARAMETER = "E002"
    PARAMETER_OUT_OF_RANGE = "E003"
    INVALID_FORMAT = "E004"

    # Home Assistant (E10x)
    HASS_UNREACHABLE = "E101"
    HASS_AUTH_FAILED = "E102"
    HASS_ENTITY_NOT_FOUND = "E103"
    HASS_SERVICE_FAILED = "E104"
    HASS_CIRCUIT_OPEN = "E105"

    # Research/Web (E20x)
    BROWSER_TIMEOUT = "E201"
    PAGE_LOAD_FAILED = "E202"
    SEARCH_NO_RESULTS = "E203"
    SEARCH_PROVIDER_ERROR = "E204"
    INVALID_URL = "E205"
    CONTENT_TOO_LARGE = "E206"

    # Memory (E30x)
    MEMORY_STORE_FAILED = "E301"
    MEMORY_RETRIEVE_FAILED = "E302"
    EMBEDDING_FAILED = "E303"
    GRAPH_QUERY_FAILED = "E304"
    MEMORY_NOT_FOUND = "E305"

    # System (E40x)
    RATE_LIMITED = "E401"
    CIRCUIT_OPEN = "E402"
    TIMEOUT = "E403"
    COMMAND_FAILED = "E404"
    FILE_NOT_FOUND = "E405"
    PERMISSION_DENIED = "E406"
    INTERNAL_ERROR = "E499"


# Error codes that are safe to retry
RETRYABLE_ERRORS = {
    ErrorCode.HASS_UNREACHABLE,
    ErrorCode.BROWSER_TIMEOUT,
    ErrorCode.PAGE_LOAD_FAILED,
    ErrorCode.SEARCH_PROVIDER_ERROR,
    ErrorCode.EMBEDDING_FAILED,
    ErrorCode.RATE_LIMITED,
    ErrorCode.TIMEOUT,
}


@dataclass
class ToolError:
    """
    Structured error for MCP tool responses.

    Attributes:
        code: Error classification code
        message: Human-readable error message
        details: Optional additional context
        retryable: Whether the operation can be retried
    """

    code: ErrorCode
    message: str
    details: Optional[dict[str, Any]] = None
    retryable: bool = False

    def __post_init__(self):
        # Auto-set retryable based on error code if not explicitly set
        if self.code in RETRYABLE_ERRORS and not self.retryable:
            self.retryable = True

    def to_response(self) -> str:
        """Format error for MCP tool response."""
        prefix = "[RETRYABLE] " if self.retryable else ""
        return f"{prefix}[{self.code.value}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
            "retryable": self.retryable,
        }


class ToolException(Exception):
    """
    Exception wrapper for ToolError.

    Can be raised in tool handlers and caught for consistent error handling.
    """

    def __init__(self, error: ToolError):
        self.error = error
        super().__init__(error.to_response())
