"""Regression tests for symlink-based bypass of _check_sensitive_path.

W3-S6: Before the fix, _check_sensitive_path compared raw (un-resolved) path
strings against sensitive prefixes.  A symlink in a non-sensitive directory
pointing into /etc/ would pass the guard unchallenged.

After the fix the function calls Path.resolve(strict=False) first, so:
* symlinks that ultimately point into sensitive directories are rejected,
* dot-dot traversal paths are rejected,
* symlink loops are rejected (fail-safe / deny).
"""

import tempfile
from pathlib import Path  # used in tests directly and in _can_symlink helper

import pytest

from tools.file_tools import _check_sensitive_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _can_symlink() -> bool:
    """Return True if the OS allows creating symlinks (needs admin on Windows)."""
    try:
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src.txt"
            src.write_text("x")
            lnk = Path(d) / "lnk"
            lnk.symlink_to(src)
            return True
    except OSError:
        return False


requires_symlinks = pytest.mark.skipif(
    not _can_symlink(), reason="Symlinks require elevated privileges on this OS"
)


# ---------------------------------------------------------------------------
# Core tests
# ---------------------------------------------------------------------------

@requires_symlinks
def test_check_sensitive_path_resolves_symlink_into_etc(tmp_path):
    """A symlink in /tmp pointing at /etc/passwd must be rejected.

    This is the exact vulnerability class being fixed: without resolve(),
    the raw path (inside /tmp) passes the sensitive-prefix guard even though
    the symlink target is in /etc/.
    """
    # /etc/passwd must exist for the symlink target to be meaningful on the
    # host.  On macOS the canonical sensitive path is /private/etc so we
    # check both.
    etc_passwd_candidates = ["/etc/passwd", "/private/etc/passwd"]
    target = next((p for p in etc_passwd_candidates if Path(p).exists()), None)
    if target is None:
        pytest.skip("/etc/passwd not found on this system")

    symlink = tmp_path / "innocent_looking_file.txt"
    symlink.symlink_to(target)

    # The symlink itself lives in /tmp (not sensitive), but must be rejected.
    result = _check_sensitive_path(str(symlink))
    assert result is not None, (
        f"Expected _check_sensitive_path to reject symlink {symlink} "
        f"-> {target}, but it returned None (allowed)."
    )


def test_check_sensitive_path_passes_clean_path():
    """A path under the user home directory must NOT be flagged as sensitive.

    Note: on macOS, pytest's tmp_path resolves to /private/var/... which IS
    in _SENSITIVE_PATH_PREFIXES, so we use a home-directory path instead.
    """
    clean = Path.home() / "hermes_test_workfile.txt"
    result = _check_sensitive_path(str(clean))
    assert result is None, (
        f"Expected _check_sensitive_path to allow {clean}, "
        f"but it returned: {result!r}"
    )


def test_check_sensitive_path_resolves_relative_with_dotdot():
    """/tmp/../etc/passwd resolves to /etc/passwd and must be rejected.

    On macOS /tmp is a symlink to /private/tmp, so
    Path('/tmp/../etc/passwd').resolve(strict=False) yields /private/etc/passwd,
    which is in _SENSITIVE_PATH_PREFIXES.  On Linux it resolves to /etc/passwd.
    Either way the function must reject it.

    Note: /tmp/foo/../etc/passwd does NOT work here because strict=False only
    resolves existing ancestors — since /tmp/foo doesn't exist, the ..
    traversal stays inside /private/tmp giving /private/tmp/etc/passwd.
    Using /tmp directly (which exists and is a symlink on macOS) ensures the
    full resolution chain is traversed correctly.
    """
    tricky = "/tmp/../etc/passwd"
    result = _check_sensitive_path(tricky)
    assert result is not None, (
        f"Expected _check_sensitive_path to reject dot-dot path {tricky!r}, "
        "but it returned None (allowed)."
    )


@requires_symlinks
def test_check_sensitive_path_loop_rejected(tmp_path):
    """A symlink loop must be rejected (fail-safe deny).

    Path.resolve(strict=False) on CPython raises RuntimeError for loops on
    POSIX.  The function must catch that and treat the path as sensitive.
    """
    loop_a = tmp_path / "loop_a"
    loop_b = tmp_path / "loop_b"
    loop_a.symlink_to(loop_b)
    loop_b.symlink_to(loop_a)

    result = _check_sensitive_path(str(loop_a))
    assert result is not None, (
        f"Expected _check_sensitive_path to reject symlink loop {loop_a}, "
        "but it returned None (allowed)."
    )
