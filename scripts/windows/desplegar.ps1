# Despliega la plataforma v2 en la GNS3 VM local (modo localhost) o en la VM de Azure (modo nube).
# Uso (desde PowerShell, en cualquier carpeta):
#   .\scripts\windows\desplegar.ps1
#   .\scripts\windows\desplegar.ps1 -VM gns3@192.168.56.101 -Destino plataforma
#   .\scripts\windows\desplegar.ps1 -VM gns3@dcim -Modo nube -Dominio dcim.<tailnet>.ts.net
# Requiere llave SSH sin contraseña hacia la VM (ssh -o BatchMode=yes gns3@192.168.56.101 "echo ok").
# No sobrescribe el .env de la VM: solo lo crea en el primer despliegue, con -Modo y -Dominio.
param(
    [string]$VM = "gns3@192.168.56.101",
    [string]$Destino = "plataforma",
    [ValidateSet("localhost", "nube")][string]$Modo = "localhost",
    [string]$Dominio = ""
)
$ErrorActionPreference = "Stop"
if ($Modo -eq "nube" -and -not $Dominio) { Write-Error "El modo nube requiere -Dominio, p. ej. dcim.<tailnet>.ts.net" }
if ($Dominio -notmatch '^[a-z0-9.-]*$') { Write-Error "Dominio inválido: $Dominio" }

$raiz = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$paquete = Join-Path $env:TEMP "plataforma-dcim.tgz"

ssh -o BatchMode=yes -o ConnectTimeout=5 $VM "true"
if ($LASTEXITCODE -ne 0) {
    Write-Error "No hay acceso SSH sin contraseña a $VM. Configure la llave antes de desplegar."
}

Write-Host "Empaquetando $raiz ..."
tar -czf $paquete `
    --exclude=./datos --exclude=./capturas --exclude=./.env `
    --exclude=__pycache__ --exclude=*.pyc --exclude=./venv --exclude=./.venv `
    --exclude=*.db --exclude=root.crt --exclude=./evidencia `
    -C $raiz .
if ($LASTEXITCODE -ne 0) { Write-Error "tar falló" }

Write-Host "Copiando a ${VM}:~/$Destino ..."
scp -q $paquete "${VM}:~/plataforma-dcim.tgz"
if ($LASTEXITCODE -ne 0) { Write-Error "scp falló" }
Remove-Item $paquete

# Script remoto: se envía en base64 con finales LF. Enviarlo por tubería no sirve, porque
# PowerShell agrega CRLF al final y bash recibe "docker compose ps\r".
$remoto = @"
set -e
mkdir -p ~/$Destino
tar -xzf ~/plataforma-dcim.tgz -C ~/$Destino
rm -f ~/plataforma-dcim.tgz
cd ~/$Destino
sed -i 's/\r$//' broker/entrypoint.sh scripts/*.sh scripts/nube/*.sh
chmod +x scripts/*.sh scripts/nube/*.sh
if [ ! -f .env ]; then
  ./scripts/generar_env.sh $Modo $Dominio
  sed -i 's/^MODO_RED=.*/MODO_RED=captura/' .env
fi
docker compose up -d --build
docker compose ps
"@ -replace "`r", ""

Write-Host "Construyendo y levantando el stack en la VM ..."
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoto))
ssh $VM "echo $b64 | base64 -d | bash"
if ($LASTEXITCODE -ne 0) { Write-Error "El despliegue remoto falló (código $LASTEXITCODE)" }

Write-Host ""
Write-Host "Listo. Código de alta del administrador:"
ssh $VM "cd ~/$Destino && docker compose logs plataforma 2>/dev/null | grep -a 'CÓDIGO DE ALTA' | tail -1"
if ($Modo -eq "nube") { Write-Host "Entre a https://$Dominio (requiere Tailscale conectado)" }
else { Write-Host "Abra el túnel con .\scripts\windows\tunel.ps1 y entre a http://localhost:8000/alta" }
