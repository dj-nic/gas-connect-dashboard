import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.flash import Port,new_ports,choose_port,verify_image,main

class FlashTests(unittest.TestCase):
    def test_existing_ports_are_not_new(self):
        port=Port('COM1','Existing adapter',1,2,'old')
        self.assertEqual(new_ports([port],[port]),[])
    def test_new_port_is_distinguishable(self):
        old=Port('COM1');new=Port('COM7','USB JTAG/serial',0x303A,0x1001,'demo')
        self.assertEqual(new_ports([old],[old,new]),[new])
    def test_changed_device_same_port_is_distinguishable(self):
        self.assertEqual(new_ports([Port('COM7',serial_number='before')],[Port('COM7',serial_number='after')]),[Port('COM7',serial_number='after')])
    def test_user_selects_port_instead_of_silent_guess(self):
        with patch('scripts.flash.scan_ports',return_value=[Port('COM1'),Port('COM7')]),patch('builtins.input',return_value='2'):
            self.assertEqual(choose_port(),'COM7')
    def test_cancel_never_flashes(self):
        with patch('scripts.flash.choose_port',return_value=None),patch('scripts.flash.subprocess.run') as run:
            self.assertEqual(main([]),0);run.assert_not_called()
    def test_hash_failure_never_flashes(self):
        with tempfile.TemporaryDirectory() as d:
            image=Path(d)/'factory.bin';image.write_bytes(b'firmware');checksum=Path(d)/'SHA256SUMS';checksum.write_text('0'*64+'  factory.bin\n')
            with patch('scripts.flash.subprocess.run') as run:
                with self.assertRaises(ValueError):main(['--port','COM7','--yes','--firmware',str(image)])
                run.assert_not_called()
    def test_valid_checksum(self):
        with tempfile.TemporaryDirectory() as d:
            image=Path(d)/'factory.bin';image.write_bytes(b'firmware');checksum=Path(d)/'SHA256SUMS';checksum.write_text(hashlib.sha256(b'firmware').hexdigest()+'  factory.bin\n')
            self.assertEqual(verify_image(image,checksum),hashlib.sha256(b'firmware').hexdigest())
if __name__=='__main__':unittest.main()
