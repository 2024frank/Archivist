import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("ARCHIVIST_API_TOKEN", "test-token")
os.environ.setdefault("ARCHIVIST_PUBLIC_BASE_URL", "https://example.test/archivist")
os.environ.setdefault("ARCHIVIST_STORAGE_ROOT", str(ROOT / ".test-storage"))
os.environ.setdefault("ARCHIVIST_MAX_UPLOAD_MB", "32")
os.environ.setdefault("ARCHIVIST_DATABASE_URL", "sqlite:///:memory:")
