# -*- coding: utf-8 -*-
import os, sys, traceback, importlib.util

here = os.path.dirname(os.path.abspath(__file__))
target = os.path.join(here, "aggregate_e04.py")
log = os.path.join(here, "_trace.txt")

spec = importlib.util.spec_from_file_location("agg", target)
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
    mod.main()
    with open(log, "w", encoding="utf-8") as f:
        f.write("OK\n")
except Exception:
    with open(log, "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
