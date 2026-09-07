import os
import sys

# Make the in-tree `exconverter` package importable when running tests
# without installing the project.
sys.path.insert(0, os.path.dirname(__file__))
