"""Assemble ESP32-C3 flash segments at their partition-table offsets."""
import argparse,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--boot-app0',type=Path,required=True);args=p.parse_args()
root=Path(__file__).resolve().parents[1];build=root/'.pio/build/gas-c3'
segments=[(0,build/'bootloader.bin'),(0x8000,build/'partitions.bin'),(0xe000,args.boot_app0),(0x10000,build/'firmware.bin')]
image=bytearray()
for i,(offset,path) in enumerate(segments):
    data=path.read_bytes()
    if i in (0,3):assert data[0]==0xe9,'Invalid ESP image'
    assert len(image)<=offset,'Segments overlap'
    image.extend(b'\xff'*(offset-len(image)));image.extend(data)
assert len(image)<0x170000,'Firmware exceeds app0 partition'
dest=root/'dist';dest.mkdir(exist_ok=True)
(dest/'factory.bin').write_bytes(image)
(dest/'SHA256SUMS').write_text(hashlib.sha256(image).hexdigest()+'  factory.bin\n')
print(f'Factory image: {len(image)} bytes; SHA-256 recorded')
