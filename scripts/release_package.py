import argparse,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--artifacts',type=Path,required=True);args=parser.parse_args()
version=(ROOT/'VERSION').read_text().strip();dest=args.artifacts
with zipfile.ZipFile(dest/f'Gas-Connect-ESP32C3-v{version}.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for name in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0'):
        if name and (ROOT/name).is_file():archive.write(ROOT/name,name)
    archive.write(dest/'factory.bin','firmware/factory.bin');archive.write(dest/'SHA256SUMS','firmware/SHA256SUMS')
