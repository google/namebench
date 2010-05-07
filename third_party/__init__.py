import os.path
import sys

# This bit of evil should inject third_party into the path for relative imports.
sys.path.insert(1, os.path.dirname(__file__))
