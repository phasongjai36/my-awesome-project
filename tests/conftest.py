"""pytest conftest — ทำให้ import โมดูลของโปรเจกต์ได้โดยไม่ต้องติดตั้งแพ็กเกจ"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
