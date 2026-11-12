"""Compile and exercise the same mode-1 controller used by the L CPU."""
import subprocess
import tempfile
import unittest
from pathlib import Path


class DiagnoseTests(unittest.TestCase):
    def test_priority_protocol(self):
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(prefix='hp1000-diagnose-') as directory:
            binary = Path(directory) / 'diagnose'
            build = subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                                    '-I', str(root / 'HP2100'),
                                    str(root / 'tests/hp1000/test_l_diagnose.c'),
                                    '-o', str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('diagnose-controller checks', result.stdout)


if __name__ == '__main__':
    unittest.main()
