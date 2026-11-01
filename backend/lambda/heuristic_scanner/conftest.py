import sys
from pathlib import Path

LAMBDA_DIR = Path(__file__).resolve().parent
if str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))
