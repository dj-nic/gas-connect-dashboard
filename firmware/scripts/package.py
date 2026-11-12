"""Package PlatformIO output using Espressif's merger, without host-specific paths."""
import hashlib,os,shutil,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
core=Path(os.environ.get('PLATFORMIO_CORE_DIR',str(Path.home()/'.platformio')))
build=root/'.pio/build/gas-c3';dest=root/'dist';dest.mkdir(exist_ok=True)
tool=core/'packages/tool-esptoolpy/esptool.py'
boot=core/'packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin'
subprocess.run([sys.executable,str(tool),'--chip','esp32c3','merge_bin','-o',str(dest/'factory.bin'),'--flash_mode','dio','--flash_size','4MB','0x0',str(build/'bootloader.bin'),'0x8000',str(build/'partitions.bin'),'0xe000',str(boot),'0x10000',str(build/'firmware.bin')],check=True)
(dest/'SHA256SUMS').write_text(hashlib.sha256((dest/'factory.bin').read_bytes()).hexdigest()+'  factory.bin\n')
shutil.copy2(dest/'factory.bin',root/'factory.bin');shutil.copy2(dest/'SHA256SUMS',root/'SHA256SUMS')
