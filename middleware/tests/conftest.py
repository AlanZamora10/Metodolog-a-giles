import sys
import os

# Asegurar que el directorio de middleware esté en sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MIDDLEWARE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "../.."))

if MIDDLEWARE_DIR not in sys.path:
    sys.path.insert(0, MIDDLEWARE_DIR)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
