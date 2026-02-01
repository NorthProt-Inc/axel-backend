"""
Circuit Breaker pattern implementation for external service calls.

Protects system from cascading failures when external services are down.

States:
- CLOSED: Normal operation, requests go through
- OPEN: Service is failing, requests fail immediately
- HALF_OPEN: Testing if service recovered
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

from backend.core.logging import get_logger

_log = get_logger("circuit_breaker")

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitConfig:
    """Configuration for a circuit breaker."""
    failure_threshold: int = 5        # Failures before opening
    success_threshold: int = 2        # Successes in HALF_OPEN before closing
    timeout_seconds: float = 60.0     # Time to stay OPEN before trying HALF_OPEN
    half_open_max_calls: int = 3      # Max concurrent calls in HALF_OPEN


@dataclass
class CircuitStats:
    """Statistics for a circuit breaker."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0  # Calls rejected due to OPEN state
    state_changes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "state_changes": self.state_changes,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
        }


class CircuitOpenError(Exception):
    """Raised when circuit is open and request is rejected."""

    def __init__(self, circuit_name: str, timeout_remaining: float):
        self.circuit_name = circuit_name
        self.timeout_remaining = timeout_remaining
        super().__init__(
            f"Circuit '{circuit_name}' is OPEN. "
            f"Retry after {timeout_remaining:.1f}s"
        )


class CircuitBreaker:
    """
    Circuit breaker for protecting external service calls.

    Usage:
        circuit = CircuitBreaker.get("hass", CircuitConfig(failure_threshold=3))

        if circuit.can_execute():
            try:
                result = await external_call()
                circuit.record_success()
            except Exception as e:
                circuit.record_failure()
                raise
        else:
            raise CircuitOpenError(...)
    """

    _instances: Dict[str, "CircuitBreaker"] = {}

    def __init__(self, name: str, config: Optional[CircuitConfig] = None):
        self.name = name
        self.config = config or CircuitConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
        self.stats = CircuitStats()

    @classmethod
    def get(cls, name: str, config: Optional[CircuitConfig] = None) -> "CircuitBreaker":
        """Get or create a named circuit breaker."""
        if name not in cls._instances:
            cls._instances[name] = cls(name, config)
        return cls._instances[name]

    @classmethod
    def get_all(cls) -> Dict[str, "CircuitBreaker"]:
        """Get all circuit breakers."""
        return cls._instances.copy()

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state

    def can_execute(self) -> bool:
        """
        Check if a request can proceed.

        Returns:
            True if request can proceed, False if circuit is open
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if timeout has passed
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.config.timeout_seconds:
                self._transition_to(CircuitState.HALF_OPEN)
                self._success_count = 0
                self._half_open_calls = 0
                return True
            return False

        # HALF_OPEN: allow limited calls
        if self._half_open_calls < self.config.half_open_max_calls:
            return True
        return False

    def record_success(self) -> None:
        """Record a successful call."""
        self.stats.total_calls += 1
        self.stats.successful_calls += 1
        self.stats.last_success_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            self._half_open_calls -= 1
            if self._success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
                self._failure_count = 0
        else:
            # Reset failure count on success in CLOSED state
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self.stats.total_calls += 1
        self.stats.failed_calls += 1
        self.stats.last_failure_time = time.time()

        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # Any failure in HALF_OPEN goes back to OPEN
            self._transition_to(CircuitState.OPEN)
            self._half_open_calls = 0
        elif self._failure_count >= self.config.failure_threshold:
            self._transition_to(CircuitState.OPEN)

    def record_rejected(self) -> None:
        """Record a rejected call (circuit was open)."""
        self.stats.total_calls += 1
        self.stats.rejected_calls += 1

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            self.stats.state_changes += 1
            _log.info(
                "circuit state change",
                name=self.name,
                old_state=old_state.value,
                new_state=new_state.value,
                failure_count=self._failure_count,
            )

    def get_timeout_remaining(self) -> float:
        """Get remaining timeout before HALF_OPEN (0 if not OPEN)."""
        if self._state != CircuitState.OPEN:
            return 0.0
        elapsed = time.time() - self._last_failure_time
        remaining = self.config.timeout_seconds - elapsed
        return max(0.0, remaining)

    def reset(self) -> None:
        """Manually reset circuit to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        _log.info("circuit manually reset", name=self.name)

    def get_status(self) -> dict:
        """Get full circuit status."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "timeout_remaining": self.get_timeout_remaining(),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout_seconds": self.config.timeout_seconds,
            },
            "stats": self.stats.to_dict(),
        }


# Pre-configured circuit breakers for common services
HASS_CIRCUIT = CircuitBreaker.get(
    "hass",
    CircuitConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=30.0,
    )
)

RESEARCH_CIRCUIT = CircuitBreaker.get(
    "research",
    CircuitConfig(
        failure_threshold=5,
        success_threshold=2,
        timeout_seconds=60.0,
    )
)

EMBEDDING_CIRCUIT = CircuitBreaker.get(
    "embedding",
    CircuitConfig(
        failure_threshold=3,
        success_threshold=1,
        timeout_seconds=30.0,
    )
)


def get_all_circuit_status() -> Dict[str, dict]:
    """Get status of all circuit breakers."""
    return {name: cb.get_status() for name, cb in CircuitBreaker.get_all().items()}
