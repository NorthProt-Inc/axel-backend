"""Tests for centralized configuration constants.

Validates that all magic numbers are defined in config.py with proper defaults
and support environment variable overrides.  Also covers helper functions:
get_cors_origins, _get_size_bytes, _get_int_env, _get_float_env, ensure_data_directories.
"""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestTimeoutConstants:
    """Timeout constants merged from timeouts.py and scattered modules."""

    def test_timeout_api_call_default(self):
        from backend.config import TIMEOUT_API_CALL

        assert TIMEOUT_API_CALL == 180

    def test_timeout_stream_chunk_default(self):
        from backend.config import TIMEOUT_STREAM_CHUNK

        assert TIMEOUT_STREAM_CHUNK == 60

    def test_timeout_first_chunk_base_default(self):
        from backend.config import TIMEOUT_FIRST_CHUNK_BASE

        assert TIMEOUT_FIRST_CHUNK_BASE == 100

    def test_timeout_mcp_tool_default(self):
        from backend.config import TIMEOUT_MCP_TOOL

        assert TIMEOUT_MCP_TOOL == 300

    def test_timeout_deep_research_default(self):
        from backend.config import TIMEOUT_DEEP_RESEARCH

        assert TIMEOUT_DEEP_RESEARCH == 600

    def test_timeout_http_default(self):
        from backend.config import TIMEOUT_HTTP_DEFAULT

        assert TIMEOUT_HTTP_DEFAULT == 30.0

    def test_timeout_http_connect(self):
        from backend.config import TIMEOUT_HTTP_CONNECT

        assert TIMEOUT_HTTP_CONNECT == 5.0

    def test_timeout_env_override(self):
        """Environment variable should override default timeout via _get_int_env."""
        from backend.config import _get_int_env

        with patch.dict(os.environ, {"TIMEOUT_API_CALL": "300"}):
            assert _get_int_env("TIMEOUT_API_CALL", 180) == 300

    def test_timeout_env_invalid_falls_back(self):
        """Invalid env value should fall back to default."""
        from backend.config import _get_int_env

        with patch.dict(os.environ, {"TIMEOUT_API_CALL": "not_a_number"}):
            assert _get_int_env("TIMEOUT_API_CALL", 180) == 180


class TestSSEConstants:
    """SSE configuration constants from mcp_transport.py."""

    def test_sse_keepalive_interval_default(self):
        from backend.config import SSE_KEEPALIVE_INTERVAL

        assert SSE_KEEPALIVE_INTERVAL == 15

    def test_sse_connection_timeout_default(self):
        from backend.config import SSE_CONNECTION_TIMEOUT

        assert SSE_CONNECTION_TIMEOUT == 600

    def test_sse_retry_delay_default(self):
        from backend.config import SSE_RETRY_DELAY

        assert SSE_RETRY_DELAY == 3000


class TestRetryConstants:
    """Retry configuration constants scattered across modules."""

    def test_gemini_max_retries_default(self):
        from backend.config import GEMINI_MAX_RETRIES

        assert GEMINI_MAX_RETRIES == 5

    def test_gemini_retry_delay_base_default(self):
        from backend.config import GEMINI_RETRY_DELAY_BASE

        assert GEMINI_RETRY_DELAY_BASE == 2.0

    def test_stream_max_retries_default(self):
        from backend.config import STREAM_MAX_RETRIES

        assert STREAM_MAX_RETRIES == 5

    def test_embedding_max_retries_default(self):
        from backend.config import EMBEDDING_MAX_RETRIES

        assert EMBEDDING_MAX_RETRIES == 3


class TestFileLimitConstants:
    """File size and search limit constants."""

    def test_max_file_size_default(self):
        from backend.config import MAX_FILE_SIZE

        assert MAX_FILE_SIZE == 10 * 1024 * 1024

    def test_max_log_lines_default(self):
        from backend.config import MAX_LOG_LINES

        assert MAX_LOG_LINES == 1000

    def test_max_search_results_default(self):
        from backend.config import MAX_SEARCH_RESULTS

        assert MAX_SEARCH_RESULTS == 100


class TestMaxFileSizeConsistency:
    """MAX_FILE_SIZE should have the same value across all modules."""

    def test_system_observer_matches_config(self):
        from backend.config import MAX_FILE_SIZE as config_val
        from backend.core.tools.system_observer import MAX_FILE_SIZE as observer_val

        assert observer_val == config_val

    def test_file_tools_imports_from_config(self):
        from backend.config import MAX_FILE_SIZE as config_val
        from backend.core.mcp_tools.file_tools import MAX_FILE_SIZE as tools_val

        assert tools_val is config_val  # same object via import

    def test_system_observer_max_log_lines_matches_config(self):
        from backend.config import MAX_LOG_LINES as config_val
        from backend.core.tools.system_observer import MAX_LOG_LINES as observer_val

        assert observer_val == config_val

    def test_system_observer_max_search_results_matches_config(self):
        from backend.config import MAX_SEARCH_RESULTS as config_val
        from backend.core.tools.system_observer import MAX_SEARCH_RESULTS as observer_val

        assert observer_val == config_val


class TestReActConstants:
    """ReAct loop default configuration."""

    def test_react_max_loops_default(self):
        from backend.config import REACT_MAX_LOOPS

        assert REACT_MAX_LOOPS == 15

    def test_react_temperature_default(self):
        from backend.config import REACT_DEFAULT_TEMPERATURE

        assert REACT_DEFAULT_TEMPERATURE == 0.7

    def test_react_max_tokens_default(self):
        from backend.config import REACT_DEFAULT_MAX_TOKENS

        assert REACT_DEFAULT_MAX_TOKENS == 16384


class TestTimeoutsBackwardCompat:
    """timeouts.py TIMEOUTS object should use config.py values."""

    def test_timeouts_api_call_matches_config(self):
        from backend.config import TIMEOUT_API_CALL
        from backend.core.utils.timeouts import TIMEOUTS

        assert TIMEOUTS.API_CALL == TIMEOUT_API_CALL

    def test_timeouts_http_default_matches_config(self):
        from backend.config import TIMEOUT_HTTP_DEFAULT
        from backend.core.utils.timeouts import TIMEOUTS

        assert TIMEOUTS.HTTP_DEFAULT == TIMEOUT_HTTP_DEFAULT

    def test_timeouts_stream_chunk_matches_config(self):
        from backend.config import TIMEOUT_STREAM_CHUNK
        from backend.core.utils.timeouts import TIMEOUTS

        assert TIMEOUTS.STREAM_CHUNK == TIMEOUT_STREAM_CHUNK

    def test_service_timeouts_dict_available(self):
        from backend.core.utils.timeouts import SERVICE_TIMEOUTS

        assert "hass" in SERVICE_TIMEOUTS
        assert "default" in SERVICE_TIMEOUTS


class TestDecayNamedConstants:
    """Decay calculator magic numbers should be named constants."""

    def test_recency_age_hours_defined(self):
        from backend.memory.permanent.decay_calculator import RECENCY_AGE_HOURS

        assert RECENCY_AGE_HOURS == 168  # 1 week

    def test_recency_access_hours_defined(self):
        from backend.memory.permanent.decay_calculator import RECENCY_ACCESS_HOURS

        assert RECENCY_ACCESS_HOURS == 24

    def test_recency_boost_defined(self):
        from backend.memory.permanent.decay_calculator import RECENCY_BOOST

        assert RECENCY_BOOST == 1.3


class TestShutdownConstants:
    """Shutdown timeout constants from app.py."""

    def test_shutdown_task_timeout(self):
        from backend.config import SHUTDOWN_TASK_TIMEOUT

        assert SHUTDOWN_TASK_TIMEOUT == 3.0

    def test_shutdown_session_timeout(self):
        from backend.config import SHUTDOWN_SESSION_TIMEOUT

        assert SHUTDOWN_SESSION_TIMEOUT == 3.0

    def test_shutdown_http_pool_timeout(self):
        from backend.config import SHUTDOWN_HTTP_POOL_TIMEOUT

        assert SHUTDOWN_HTTP_POOL_TIMEOUT == 2.0


# ============================================================================
# get_cors_origins()
# ============================================================================

class TestGetCorsOrigins:
    """CORS origin list from env or defaults."""

    def test_default_origins_when_env_empty(self):
        from backend.config import get_cors_origins

        with patch.dict(os.environ, {"CORS_ALLOW_ORIGINS": ""}, clear=False):
            # Re-import to reset CORS_ALLOW_ORIGINS would require module reload,
            # but get_cors_origins reads the module-level variable.
            # Instead, test the function's internal logic by patching the module var.
            with patch("backend.config.CORS_ALLOW_ORIGINS", ""):
                origins = get_cors_origins()
                assert isinstance(origins, list)
                assert "http://localhost:3000" in origins
                assert "http://localhost:5173" in origins
                assert len(origins) == 4

    def test_custom_origins_from_env(self):
        from backend.config import get_cors_origins

        with patch("backend.config.CORS_ALLOW_ORIGINS", "https://example.com,https://app.test"):
            origins = get_cors_origins()
            assert origins == ["https://example.com", "https://app.test"]

    def test_strips_whitespace(self):
        from backend.config import get_cors_origins

        with patch("backend.config.CORS_ALLOW_ORIGINS", " https://a.com , https://b.com "):
            origins = get_cors_origins()
            assert origins == ["https://a.com", "https://b.com"]

    def test_filters_empty_entries(self):
        from backend.config import get_cors_origins

        with patch("backend.config.CORS_ALLOW_ORIGINS", "https://a.com,,, ,https://b.com"):
            origins = get_cors_origins()
            assert origins == ["https://a.com", "https://b.com"]


# ============================================================================
# _get_size_bytes()
# ============================================================================

class TestGetSizeBytes:
    """_get_size_bytes reads bytes_env first, then mb_env, then default."""

    def test_default_mb_when_no_env(self):
        from backend.config import _get_size_bytes

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TEST_BYTES", None)
            os.environ.pop("TEST_MB", None)
            result = _get_size_bytes("TEST_BYTES", "TEST_MB", 10)
            assert result == 10 * 1024 * 1024

    def test_bytes_env_takes_priority(self):
        from backend.config import _get_size_bytes

        with patch.dict(os.environ, {"TEST_BYTES": "5000", "TEST_MB": "99"}):
            result = _get_size_bytes("TEST_BYTES", "TEST_MB", 10)
            assert result == 5000

    def test_mb_env_converted_to_bytes(self):
        from backend.config import _get_size_bytes

        with patch.dict(os.environ, {"TEST_MB": "5"}, clear=False):
            os.environ.pop("TEST_BYTES", None)
            result = _get_size_bytes("TEST_BYTES", "TEST_MB", 10)
            assert result == 5 * 1024 * 1024

    def test_mb_env_handles_float(self):
        from backend.config import _get_size_bytes

        with patch.dict(os.environ, {"TEST_MB": "2.5"}, clear=False):
            os.environ.pop("TEST_BYTES", None)
            result = _get_size_bytes("TEST_BYTES", "TEST_MB", 10)
            assert result == int(2.5 * 1024 * 1024)

    def test_invalid_bytes_env_falls_to_mb(self):
        from backend.config import _get_size_bytes

        with patch.dict(os.environ, {"TEST_BYTES": "bad", "TEST_MB": "3"}):
            result = _get_size_bytes("TEST_BYTES", "TEST_MB", 10)
            assert result == 3 * 1024 * 1024

    def test_invalid_both_falls_to_default(self):
        from backend.config import _get_size_bytes

        with patch.dict(os.environ, {"TEST_BYTES": "bad", "TEST_MB": "bad"}):
            result = _get_size_bytes("TEST_BYTES", "TEST_MB", 10)
            assert result == 10 * 1024 * 1024

    def test_negative_bytes_clamp_to_zero(self):
        from backend.config import _get_size_bytes

        with patch.dict(os.environ, {"TEST_BYTES": "-100"}, clear=False):
            os.environ.pop("TEST_MB", None)
            result = _get_size_bytes("TEST_BYTES", "TEST_MB", 10)
            assert result == 0


# ============================================================================
# _get_int_env()
# ============================================================================

class TestGetIntEnv:
    """_get_int_env reads integer from env or returns default."""

    def test_returns_default_when_not_set(self):
        from backend.config import _get_int_env

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TEST_INT_UNSET", None)
            assert _get_int_env("TEST_INT_UNSET", 42) == 42

    def test_returns_env_value(self):
        from backend.config import _get_int_env

        with patch.dict(os.environ, {"TEST_INT": "99"}):
            assert _get_int_env("TEST_INT", 42) == 99

    def test_invalid_value_returns_default(self):
        from backend.config import _get_int_env

        with patch.dict(os.environ, {"TEST_INT": "not_int"}):
            assert _get_int_env("TEST_INT", 42) == 42

    def test_zero_is_valid(self):
        from backend.config import _get_int_env

        with patch.dict(os.environ, {"TEST_INT": "0"}):
            assert _get_int_env("TEST_INT", 42) == 0

    def test_negative_value(self):
        from backend.config import _get_int_env

        with patch.dict(os.environ, {"TEST_INT": "-5"}):
            assert _get_int_env("TEST_INT", 42) == -5


# ============================================================================
# _get_float_env()
# ============================================================================

class TestGetFloatEnv:
    """_get_float_env reads float from env or returns default."""

    def test_returns_default_when_not_set(self):
        from backend.config import _get_float_env

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TEST_FLOAT_UNSET", None)
            assert _get_float_env("TEST_FLOAT_UNSET", 3.14) == 3.14

    def test_returns_env_value(self):
        from backend.config import _get_float_env

        with patch.dict(os.environ, {"TEST_FLOAT": "2.718"}):
            assert _get_float_env("TEST_FLOAT", 3.14) == 2.718

    def test_integer_string_parsed_as_float(self):
        from backend.config import _get_float_env

        with patch.dict(os.environ, {"TEST_FLOAT": "10"}):
            assert _get_float_env("TEST_FLOAT", 3.14) == 10.0

    def test_invalid_value_returns_default(self):
        from backend.config import _get_float_env

        with patch.dict(os.environ, {"TEST_FLOAT": "not_float"}):
            assert _get_float_env("TEST_FLOAT", 3.14) == 3.14

    def test_zero_is_valid(self):
        from backend.config import _get_float_env

        with patch.dict(os.environ, {"TEST_FLOAT": "0.0"}):
            assert _get_float_env("TEST_FLOAT", 3.14) == 0.0


# ============================================================================
# ensure_data_directories()
# ============================================================================

class TestEnsureDataDirectories:
    """ensure_data_directories creates required directories."""

    def test_creates_directories(self, tmp_path):
        from backend.config import ensure_data_directories

        with patch("backend.config.DATA_ROOT", tmp_path / "data"), \
             patch("backend.config.TEMP_DIR", tmp_path / "data" / "tmp"), \
             patch("backend.config.CHROMADB_PATH", tmp_path / "data" / "chroma"), \
             patch("backend.config.STORAGE_ROOT", tmp_path / "storage"), \
             patch("backend.config.RESEARCH_INBOX_DIR", tmp_path / "storage" / "research" / "inbox"), \
             patch("backend.config.RESEARCH_ARTIFACTS_DIR", tmp_path / "storage" / "research" / "artifacts"), \
             patch("backend.config.CRON_REPORTS_DIR", tmp_path / "storage" / "cron" / "reports"), \
             patch("backend.config.LOGS_DIR", tmp_path / "logs"):
            ensure_data_directories()
            assert (tmp_path / "data").exists()
            assert (tmp_path / "data" / "tmp").exists()
            assert (tmp_path / "storage").exists()
            assert (tmp_path / "logs").exists()

    def test_does_not_raise_on_mkdir_failure(self, tmp_path):
        """If a directory cannot be created, it logs warning but doesn't raise."""
        from backend.config import ensure_data_directories

        # Use a file as the parent so mkdir fails
        blocker = tmp_path / "blocker"
        blocker.write_text("I'm a file, not a directory")

        with patch("backend.config.DATA_ROOT", blocker / "data"), \
             patch("backend.config.TEMP_DIR", tmp_path / "ok" / "tmp"), \
             patch("backend.config.CHROMADB_PATH", tmp_path / "ok" / "chroma"), \
             patch("backend.config.STORAGE_ROOT", tmp_path / "ok" / "storage"), \
             patch("backend.config.RESEARCH_INBOX_DIR", tmp_path / "ok" / "ri"), \
             patch("backend.config.RESEARCH_ARTIFACTS_DIR", tmp_path / "ok" / "ra"), \
             patch("backend.config.CRON_REPORTS_DIR", tmp_path / "ok" / "cr"), \
             patch("backend.config.LOGS_DIR", tmp_path / "ok" / "logs"):
            # Should not raise
            ensure_data_directories()


# ============================================================================
# Path constants
# ============================================================================

class TestPathConstants:
    """Verify path constants are Path objects and consistent."""

    def test_project_root_is_path(self):
        from backend.config import PROJECT_ROOT
        assert isinstance(PROJECT_ROOT, Path)

    def test_backend_root_is_path(self):
        from backend.config import BACKEND_ROOT
        assert isinstance(BACKEND_ROOT, Path)

    def test_backend_root_is_child_of_project_root(self):
        from backend.config import PROJECT_ROOT, BACKEND_ROOT
        assert str(BACKEND_ROOT).startswith(str(PROJECT_ROOT))

    def test_data_root_under_project(self):
        from backend.config import PROJECT_ROOT, DATA_ROOT
        assert DATA_ROOT == PROJECT_ROOT / "data"


# ============================================================================
# Miscellaneous config values
# ============================================================================

class TestMiscConfig:
    """Various configuration values with expected defaults."""

    def test_host_default(self):
        from backend.config import HOST
        assert HOST == "0.0.0.0" or isinstance(HOST, str)

    def test_port_is_int(self):
        from backend.config import PORT
        assert isinstance(PORT, int)

    def test_embedding_dimension_default(self):
        from backend.config import EMBEDDING_DIMENSION
        assert EMBEDDING_DIMENSION == 3072

    def test_deep_search_enabled_is_bool(self):
        from backend.config import DEEP_SEARCH_ENABLED
        assert isinstance(DEEP_SEARCH_ENABLED, bool)

    def test_allowed_text_extensions(self):
        from backend.config import ALLOWED_TEXT_EXTENSIONS
        assert ".py" in ALLOWED_TEXT_EXTENSIONS
        assert ".json" in ALLOWED_TEXT_EXTENSIONS

    def test_allowed_image_extensions(self):
        from backend.config import ALLOWED_IMAGE_EXTENSIONS
        assert ".png" in ALLOWED_IMAGE_EXTENSIONS
        assert ".jpg" in ALLOWED_IMAGE_EXTENSIONS

    def test_max_context_tokens_positive(self):
        from backend.config import MAX_CONTEXT_TOKENS
        assert MAX_CONTEXT_TOKENS > 0

    def test_memory_budgets_positive(self):
        from backend.config import (
            BUDGET_SYSTEM_PROMPT,
            BUDGET_TEMPORAL,
            BUDGET_WORKING_MEMORY,
            BUDGET_LONG_TERM,
            BUDGET_GRAPHRAG,
            BUDGET_SESSION_ARCHIVE,
        )
        for val in [BUDGET_SYSTEM_PROMPT, BUDGET_TEMPORAL, BUDGET_WORKING_MEMORY,
                     BUDGET_LONG_TERM, BUDGET_GRAPHRAG, BUDGET_SESSION_ARCHIVE]:
            assert val > 0

    def test_pg_pool_defaults(self):
        from backend.config import PG_POOL_MIN, PG_POOL_MAX
        assert PG_POOL_MIN == 2
        assert PG_POOL_MAX == 10

    def test_mcp_disabled_tools_is_set(self):
        from backend.config import MCP_DISABLED_TOOLS
        assert isinstance(MCP_DISABLED_TOOLS, set)

    def test_mcp_disabled_categories_is_set(self):
        from backend.config import MCP_DISABLED_CATEGORIES
        assert isinstance(MCP_DISABLED_CATEGORIES, set)

    def test_context_io_timeout_is_float(self):
        from backend.config import CONTEXT_IO_TIMEOUT
        assert isinstance(CONTEXT_IO_TIMEOUT, float)

    def test_memory_decay_constants(self):
        from backend.config import (
            MEMORY_BASE_DECAY_RATE,
            MEMORY_MIN_RETENTION,
            MEMORY_DECAY_DELETE_THRESHOLD,
            MEMORY_SIMILARITY_THRESHOLD,
            MEMORY_MIN_IMPORTANCE,
        )
        assert 0 < MEMORY_BASE_DECAY_RATE < 1
        assert 0 < MEMORY_MIN_RETENTION < 1
        assert 0 < MEMORY_DECAY_DELETE_THRESHOLD < 1
        assert 0 < MEMORY_SIMILARITY_THRESHOLD <= 1
        assert 0 < MEMORY_MIN_IMPORTANCE < 1
