const ports=document.getElementById('ports');
function hex(value){return value==null?'unbekannt':value.toString(16).padStart(4,'0').toUpperCase();}
async function refreshPorts(){
  if(!('serial' in navigator)){ports.textContent='Web Serial ist hier nicht verfügbar. Nutze Desktop-Chrome/Edge oder den lokalen Flash-Assistenten.';return;}
  const allowed=await navigator.serial.getPorts();
  ports.textContent=allowed.length?'Von dir freigegeben: '+allowed.map(p=>{const i=p.getInfo();return `USB ${hex(i.usbVendorId)}:${hex(i.usbProductId)}`;}).join(' · '):'Noch kein USB-Gerät freigegeben. Die Geräteauswahl zeigt die verfügbaren seriellen Anschlüsse.';
}
document.getElementById('choose').addEventListener('click',async()=>{
  if(!('serial' in navigator)){await refreshPorts();return;}
  try{const p=await navigator.serial.requestPort();const i=p.getInfo();ports.textContent=`Ausgewählt: USB ${hex(i.usbVendorId)}:${hex(i.usbProductId)}. Dieses Gerät beim Installieren erneut auswählen. Eine Seriennummer bzw. der COM-Name ist über diese Browser-API nicht zuverlässig verfügbar.`;}
  catch(error){ports.textContent=error.name==='NotFoundError'?'Auswahl abgebrochen. Es wurde nichts geflasht.':`USB-Auswahl fehlgeschlagen: ${error.message}`;}
});
if('serial' in navigator){navigator.serial.addEventListener('connect',refreshPorts);navigator.serial.addEventListener('disconnect',refreshPorts);}
refreshPorts().catch(()=>{});
