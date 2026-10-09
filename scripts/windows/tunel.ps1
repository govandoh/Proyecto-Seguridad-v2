# Abre el túnel SSH para usar la plataforma en http://localhost:8000.
# La plataforma solo escucha en 127.0.0.1:8000 dentro de la GNS3 VM; nada queda expuesto a otra red.
# Uso: .\scripts\windows\tunel.ps1      (Ctrl+C para cerrar el túnel)
param(
    [string]$VM = "gns3@192.168.56.101",
    [int]$Puerto = 8000
)

$ocupado = Get-NetTCPConnection -LocalPort $Puerto -State Listen -ErrorAction SilentlyContinue
if ($ocupado) {
    $proc = Get-Process -Id $ocupado[0].OwningProcess -ErrorAction SilentlyContinue
    Write-Warning "El puerto $Puerto de Windows ya está en uso por '$($proc.ProcessName)' (PID $($ocupado[0].OwningProcess))."
    Write-Warning "Si es un túnel anterior, ciérrelo o use: Stop-Process -Id $($ocupado[0].OwningProcess)"
    exit 1
}

Write-Host "Túnel activo: http://localhost:$Puerto  ->  $VM 127.0.0.1:8000"
Write-Host "Deje esta ventana abierta; Ctrl+C para cerrar."
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L "${Puerto}:127.0.0.1:8000" $VM
