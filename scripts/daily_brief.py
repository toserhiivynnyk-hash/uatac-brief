# -*- coding: utf-8 -*-
"""UATAC Daily Sales Brief — оркестратор: fetch → analyze → render.
Запуск: python3 scripts/daily_brief.py [--days 125] [--no-fetch]
KeyCRM = READ-ONLY (тільки GET).
"""
import subprocess, sys, os
D = os.path.dirname(os.path.abspath(__file__))
days = sys.argv[sys.argv.index("--days") + 1] if "--days" in sys.argv else "125"
steps = []
if "--no-fetch" not in sys.argv:
    steps.append([sys.executable, os.path.join(D, "fetch.py"), "--days", days])
steps += [[sys.executable, os.path.join(D, "analyze.py")],
          [sys.executable, os.path.join(D, "render.py")]]
for cmd in steps:
    print("→", " ".join(cmd[1:]), flush=True)
    r = subprocess.run(cmd)
    if r.returncode: sys.exit(r.returncode)
print("ГОТОВО: index.html зібрано.")
