"""테스트에서 server/ 를 import 루트로 사용 — 앱 코드의 sys.path 관례와 동일."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
