# Extrae eventos de la bitácora de la VM y verifica la cadena de hash.
# Sirve para registrar la evidencia de cada paso del ensayo (docs/VALIDACION_DEMO.md).
# Uso:
#   .\scripts\windows\evidencia.ps1                    últimos 20 eventos
#   .\scripts\windows\evidencia.ps1 -Desde 120         eventos con id mayor que 120
#   .\scripts\windows\evidencia.ps1 -Desde 120 -Csv    además guarda evidencia\eventos_<fecha>.csv
# Solo lee: no modifica la bitácora.
param(
    [int]$Desde = 0,
    [int]$Ultimos = 20,
    [switch]$Csv,
    [string]$VM = "gns3@192.168.56.101"
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$py = @"
import json, sys
from app import bitacora, db
desde, limite = int(sys.argv[1]), int(sys.argv[2])
if desde:
    filas = db.consultar("SELECT id, ts, modulo, tipo, severidad, actor, ref_id, control_iso, norma, descripcion, hash FROM eventos WHERE id > ? ORDER BY id LIMIT 2000", (desde,))
else:
    filas = db.consultar("SELECT id, ts, modulo, tipo, severidad, actor, ref_id, control_iso, norma, descripcion, hash FROM eventos ORDER BY id DESC LIMIT ?", (limite,))[::-1]
print(json.dumps({"cadena": bitacora.verificar(), "eventos": filas}))
"@ -replace "`r", ""

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($py))
$salida = ssh $VM "cd ~/plataforma && echo $b64 | base64 -d | docker compose exec -T plataforma python - $Desde $Ultimos"
if ($LASTEXITCODE -ne 0) { Write-Error "No se pudo leer la bitácora (código $LASTEXITCODE)" }
$r = ($salida -join "`n") | ConvertFrom-Json

$c = $r.cadena
if ($c.integra) { Write-Host "Cadena de hash ÍNTEGRA: $($c.total) eventos encadenados" -ForegroundColor Green }
else { Write-Host "Cadena ROTA en el evento $($c.primer_error_id): $($c.detalle)" -ForegroundColor Red }

$r.eventos | ForEach-Object {
    [pscustomobject]@{
        id = $_.id; hora = ([datetime]$_.ts).ToLocalTime().ToString("HH:mm:ss"); severidad = $_.severidad
        tipo = $_.tipo; actor = $_.actor; iso = $_.control_iso; descripcion = $_.descripcion
    }
} | Format-Table -AutoSize -Wrap

if ($Csv) {
    $dir = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..")) "evidencia"
    New-Item -ItemType Directory -Force $dir | Out-Null
    $archivo = Join-Path $dir ("eventos_{0}.csv" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
    $r.eventos | Export-Csv -Path $archivo -NoTypeInformation -Encoding UTF8
    Write-Host "Guardado: $archivo"
}
