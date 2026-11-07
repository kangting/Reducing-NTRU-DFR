"""Runtime-only controller binding; generated records are not paper datasets."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent


def controller_manifest():
    return {name:hashlib.sha256((HERE/name).read_bytes()).hexdigest()
            for name in ('environment.py', 'perf_counter.py', 'provenance.py')}
