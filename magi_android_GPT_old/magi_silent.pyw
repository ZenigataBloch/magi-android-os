import os, sys, runpy

base = os.path.dirname(os.path.abspath(__file__))
os.chdir(base)
sys.path.insert(0, base)

log = open(os.path.join(base, "discord_magi.log"), "a", buffering=1, encoding="utf-8")
sys.stdout = log
sys.stderr = log

runpy.run_path(os.path.join(base, "discord_magi.py"), run_name="__main__")
