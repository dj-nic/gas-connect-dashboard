import json,unittest
from pathlib import Path
from scripts.privacy_check import private_literals
ROOT=Path(__file__).resolve().parents[1]
class PublicationTests(unittest.TestCase):
    def test_manifest_matches_project_and_supported_chip(self):
        manifest=json.loads((ROOT/'docs/manifest.json').read_text())
        self.assertEqual(manifest['version'],(ROOT/'VERSION').read_text().strip())
        self.assertEqual([build['chipFamily'] for build in manifest['builds']],['ESP32-C3'])
        self.assertEqual(manifest['builds'][0]['parts'][0]['offset'],0)
    def test_private_network_examples_are_detected(self):
        example='.'.join(str(x) for x in (192,168,90,12)).encode()
        self.assertTrue(private_literals(example))
    def test_generic_provisioning_and_loopback_are_allowed(self):
        self.assertEqual(private_literals(b'http://192.168.4.1 and 127.0.0.1'),[])
