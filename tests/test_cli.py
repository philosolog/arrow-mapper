"""Exercise the public CLI with generated artwork and no local project data."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw


SCRIPT = Path(__file__).resolve().parents[1] / 'constructor.py'


class CliTests(unittest.TestCase):
    def test_detect_and_build_without_project_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            sheet = Image.new('RGBA', (100, 100))
            ImageDraw.Draw(sheet).rectangle((10, 10, 89, 89), fill='red')
            sheet.save(root / 'sheet.png')
            Image.new('RGBA', (20, 20), 'white').save(root / 'arrow.png')

            def run(*args):
                return subprocess.run(
                    [sys.executable, str(SCRIPT), *args], cwd=root,
                    capture_output=True, text=True,
                )

            args = ('detect', '--sheet', 'sheet.png', '--source', 'arrow.png',
                    '--recipe', 'recipe.json')
            detected = run(*args)
            self.assertEqual(detected.returncode, 0, detected.stderr)
            recipe = json.loads((root / 'recipe.json').read_text())
            self.assertEqual(recipe['sources'], [str(root / 'arrow.png')])
            self.assertEqual(len(recipe['regions']), 1)
            self.assertTrue(recipe['regions'][0]['replace'])
            self.assertNotEqual(run(*args).returncode, 0)

            built = run('build', '--recipe', 'recipe.json', '--output', 'out/atlas.png')
            self.assertEqual(built.returncode, 0, built.stderr)
            for suffix in ('.png', '.xml', '.preview.png', '.overlay.png', '.matches.json'):
                self.assertTrue((root / f'out/atlas{suffix}').is_file())
            atlas = ET.parse(root / 'out/atlas.xml').getroot()
            self.assertEqual(len(atlas), 1)
            self.assertEqual(atlas[0].attrib['name'], 'sprite_000')
            self.assertNotEqual(run('build').returncode, 0)
