"""Interactive, cross-platform USB flashing. No serial writes before confirmation."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION=(ROOT/'VERSION').read_text().strip() if (ROOT/'VERSION').exists() else '0.2.0'
REPO='dj-nic/gas-connect-dashboard'

@dataclass(frozen=True)
class Port:
    device:str
    description:str=''
    vid:int|None=None
    pid:int|None=None
    serial_number:str|None=None
    manufacturer:str|None=None

def scan_ports():
    from serial.tools import list_ports
    return sorted([Port(p.device,p.description,p.vid,p.pid,p.serial_number,p.manufacturer) for p in list_ports.comports()],key=lambda p:p.device)

def new_ports(before,after):
    old={p.device:p for p in before}
    return [p for p in after if p.device not in old or old[p.device]!=p]

def show_ports(ports,new=()):
    names={p.device for p in new}
    print('\nNr.  Anschluss          USB-ID       Gerät / Seriennummer')
    print('-'*78)
    for index,p in enumerate(ports,1):
        usb=f'{p.vid:04X}:{p.pid:04X}' if p.vid is not None and p.pid is not None else '—'
        print(f'{index:>2}.  {p.device:<17} {usb:<12} {p.description}  {p.serial_number or ""}'+('  <- NEU' if p.device in names else ''))
    if not ports: print('Keine seriellen Ports erkannt. Datenkabel, BOOT-Modus und Treiber prüfen.')

def choose_port(detect=False):
    fresh=[]
    while True:
        if detect:
            input('\nNur den ESP abziehen, dann Enter drücken. ')
            before=scan_ports()
            input('ESP mit gehaltenem BOOT einstecken, BOOT lösen, dann Enter drücken. ')
            ports=scan_ports();fresh=new_ports(before,ports);detect=False
        else:ports=scan_ports()
        show_ports(ports,fresh)
        answer=input('\nNummer wählen · [r] erneut scannen · [d] Abziehen/Einstecken vergleichen · [q] abbrechen: ').strip().lower()
        if answer=='q':return None
        if answer=='r':fresh=[];continue
        if answer=='d':detect=True;continue
        if answer.isdecimal() and 1<=int(answer)<=len(ports):return ports[int(answer)-1].device
        print('Bitte eine angezeigte Nummer wählen.')

def verify_image(image,checksums):
    image=Path(image);checksums=Path(checksums)
    if not image.is_file() or not checksums.is_file():raise ValueError('Firmware oder SHA256SUMS fehlt.')
    expected=None
    for line in checksums.read_text().splitlines():
        parts=line.split()
        if len(parts)>=2 and Path(parts[-1].lstrip('*')).name==image.name:expected=parts[0].lower()
    actual=hashlib.sha256(image.read_bytes()).hexdigest()
    if expected is None or actual!=expected:raise ValueError('Firmware-Prüfsumme stimmt nicht. Abbruch vor dem Zugriff auf den ESP.')
    return actual

def release_image(version):
    if not version or any(c not in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-' for c in version):raise ValueError('Ungültige Release-Version')
    dest=ROOT/'.flash-cache'/version;dest.mkdir(parents=True,exist_ok=True)
    if (dest/'factory.bin').is_file() and (dest/'SHA256SUMS').is_file():
        try:verify_image(dest/'factory.bin',dest/'SHA256SUMS');return dest/'factory.bin',dest/'SHA256SUMS'
        except ValueError:pass
    base=f'https://github.com/{REPO}/releases/download/v{version}/'
    for name in ('factory.bin','SHA256SUMS'):
        request=urllib.request.Request(base+name,headers={'User-Agent':'Gas-Connect-Flasher'})
        with urllib.request.urlopen(request,timeout=60) as response:content=response.read(4*1024*1024+1)
        if len(content)>4*1024*1024:raise ValueError('Unerwartet großer Download')
        temporary=dest/(name+'.part');temporary.write_bytes(content);temporary.replace(dest/name)
    return dest/'factory.bin',dest/'SHA256SUMS'

def main(argv=None):
    parser=argparse.ArgumentParser(description='Gas Connect USB-Flash-Assistent für ESP32-C3 (4 MB)')
    parser.add_argument('--list-ports',action='store_true');parser.add_argument('--json',action='store_true')
    parser.add_argument('--detect',action='store_true',help='USB-Abziehen/Einstecken vergleichen')
    parser.add_argument('--port');parser.add_argument('--erase',action='store_true',help='Alle ESP-Daten vor dem Flashen löschen')
    parser.add_argument('--yes',action='store_true',help='Explizit nichtinteraktiv; nur mit --port')
    parser.add_argument('--firmware',type=Path);parser.add_argument('--checksums',type=Path)
    parser.add_argument('--version',default=VERSION)
    args=parser.parse_args(argv)
    if args.list_ports:
        ports=scan_ports()
        if args.json:print(json.dumps([asdict(p) for p in ports]))
        else:show_ports(ports)
        return 0
    if args.yes and not args.port:parser.error('--yes erfordert einen expliziten --port')
    port=args.port or choose_port(args.detect)
    if not port:print('Abgebrochen.');return 0
    if args.firmware:image=args.firmware;checks=args.checksums or image.parent/'SHA256SUMS'
    elif (ROOT/'firmware/factory.bin').exists():image=ROOT/'firmware/factory.bin';checks=image.parent/'SHA256SUMS'
    elif (ROOT/'factory.bin').exists():image=ROOT/'factory.bin';checks=ROOT/'SHA256SUMS'
    else:
        print(f'Öffentliche Firmware v{args.version} wird heruntergeladen …')
        image,checks=release_image(args.version)
    digest=verify_image(image,checks)
    print(f'\nZiel: {port}\nFirmware: {image.name} · ESP32-C3 · 4 MB\nSHA-256: {digest}')
    if args.erase:print('ACHTUNG: --erase löscht WLAN, Geräteeinstellungen und gespeicherte Messwerte.')
    confirmation='LOESCHEN' if args.erase else 'FLASH'
    if not args.yes and input(f'Zum Fortfahren {confirmation} eingeben: ').strip()!=confirmation:
        print('Abgebrochen. Keine Flash-Schreiboperation ausgeführt.');return 0
    command=[sys.executable,'-m','esptool','--chip','esp32c3','--port',port]
    if args.erase:subprocess.run(command+['erase_flash'],check=True)
    subprocess.run(command+['write_flash','0x0',str(image.resolve())],check=True)
    print('\nFertig. USB abziehen und ohne BOOT wieder einstecken. Danach Gas-Setup-WLAN zur Einrichtung öffnen.')
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,subprocess.CalledProcessError) as e:print(f'Fehler: {e}',file=sys.stderr);raise SystemExit(1)
    except (KeyboardInterrupt,EOFError):print('\nAbgebrochen.');raise SystemExit(130)
