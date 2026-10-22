import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "../.."))

if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
