"""Jobs package for scheduled tasks

This package historically tried to import from a module named
`check_expiration.py`. Some installs include a top-level module
`bot/jobs.py` instead of the `bot/jobs/check_expiration.py` file,
which caused imports like `from .jobs import check_expirations` to
fail. To be robust, try the package import first and fall back to
the sibling module if the package-level module is not present.
"""

try:
    # Preferred: package module implementation
    from .check_expiration import check_expirations, backup_and_send_to_admins
except ModuleNotFoundError:
    # Fallback: import from the legacy sibling module file `bot/jobs.py`.
    # Importing `bot.jobs` directly would recurse into this package while it
    # is still being initialised which results in a partially initialised
    # module.  Instead, load the legacy module under a distinct name using
    # importlib so we can safely access its attributes.
    import importlib.util
    from pathlib import Path

    _pkg_dir = Path(__file__).resolve().parent
    _legacy_path = _pkg_dir.parent / "jobs.py"

    spec = importlib.util.spec_from_file_location("bot._legacy_jobs", _legacy_path)
    if spec is None or spec.loader is None:
        raise ImportError("Unable to load legacy jobs module")

    _legacy_jobs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_legacy_jobs)

    check_expirations = _legacy_jobs.check_expirations
    backup_and_send_to_admins = _legacy_jobs.backup_and_send_to_admins

__all__ = ['check_expirations', 'backup_and_send_to_admins']
