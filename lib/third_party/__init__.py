import os.path
import sys

# This bit of evil should inject third_party into the path for relative imports.
sys.path.append(os.path.dirname(__file__))
