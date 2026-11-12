import os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.name=='posix','Bash installer targets Linux')
class InstallerTests(unittest.TestCase):
    def run_installer(self,*args):return subprocess.run(['bash',str(ROOT/'install.sh'),*args],capture_output=True,text=True)
    def test_dry_run_does_not_create_target(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'new'
            result=self.run_installer('--dry-run','--non-interactive','--bind','203.0.113.10','--dir',str(target))
            self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(target.exists())
    def test_invalid_address_rejected(self):
        result=self.run_installer('--dry-run','--non-interactive','--bind','999.1.1.1')
        self.assertNotEqual(result.returncode,0)
    def test_existing_foreign_directory_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            marker=Path(directory)/'unrelated';marker.write_text('keep')
            result=self.run_installer('--dry-run','--bind','203.0.113.10','--dir',directory)
            self.assertNotEqual(result.returncode,0);self.assertEqual(marker.read_text(),'keep')
