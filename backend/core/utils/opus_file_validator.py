from pathlib import Path
from typing import Optional, Tuple

from backend.core.security.path_security import PathAccessType, get_path_security

AXEL_ROOT = Path(__file__).parent.parent.parent.parent.resolve()

OPUS_ALLOWED_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".md", ".txt", ".html", ".css", ".scss", ".sql", ".sh", ".bash",
    ".env.example", ".toml", ".cfg", ".ini",
})
OPUS_MAX_FILE_SIZE = 500 * 1024        # 500KB
OPUS_MAX_FILES = 20
OPUS_MAX_TOTAL_CONTEXT = 1024 * 1024   # 1MB


def validate_opus_file_path(file_path: str) -> Tuple[bool, Optional[Path], Optional[str]]:
    """Validate file path for Opus delegation.

    Returns:
        (valid, resolved_path, error_message)
    """
    psm = get_path_security()
    result = psm.validate(
        file_path,
        PathAccessType.OPUS_DELEGATE,
        must_exist=True,
        must_be_file=True,
        max_size=OPUS_MAX_FILE_SIZE,
        allowed_extensions=OPUS_ALLOWED_EXTENSIONS,
    )
    if result.valid:
        return True, result.resolved_path, None
    return False, None, result.error


def read_opus_file_content(file_path: Path) -> str:
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        return f"[Error reading file: {str(e)}]"
