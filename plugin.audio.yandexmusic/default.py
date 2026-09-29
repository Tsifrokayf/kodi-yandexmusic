import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'resources', 'lib', 'vendor'))
sys.path.insert(0, os.path.join(BASE_DIR, 'resources', 'lib'))

from ymkodi.router import run  # noqa: E402

run(sys.argv)
