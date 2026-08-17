import sys
import unittest

sys.path.insert(0, r".\src")
suite = unittest.defaultTestLoader.discover(r".\tests", pattern="test_*.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
