"""Fail publication on private-network examples or accidentally tracked runtime data."""
import ipaddress,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ALLOWED={'192.168.4.1'} # Firmware's universal, temporary provisioning access point.
def private_literals(content):
    found=[]
    for candidate in set(re.findall(rb'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d./])',content)):
        try:address=ipaddress.ip_address(candidate.decode())
        except ValueError:continue
        if str(address) in ALLOWED:continue
        if any(address in ipaddress.ip_network(net) for net in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):found.append(str(address))
    return found
def main():
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    files=[ROOT/p for p in tracked if p]+[Path(p) for p in sys.argv[1:]]
    failed=False
    for file in files:
        if not file.is_file():continue
        relative=file.relative_to(ROOT).parts if file.is_relative_to(ROOT) else ()
        if file.name in ('credentials.json','setup-token','.env','.env.backup','gas.sqlite') or (relative and relative[0]=='data'):
            print('Runtime data must not be published:',file.name);failed=True
        found=private_literals(file.read_bytes())
        if found:print('Private LAN literal in',file.name,'(values withheld)');failed=True
    if failed:return 1
    print(f'Publication check passed: {len(files)} files; no private LAN literals (apart from the generic ESP setup AP).')
    return 0
if __name__=='__main__':raise SystemExit(main())
