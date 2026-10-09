# Topología GNS3

| Archivo | Contenido |
|---|---|
| `Topologia.gns3` | Proyecto de GNS3 2.2.61: nodos, enlaces, MAC de cada contenedor y posiciones. Copia de referencia del proyecto del laboratorio local |
| `configs/<nodo>.interfaces` | `/etc/network/interfaces` de cada Alpine: IP estática y latido (`ping -i 1 10.10.10.1`) |

| Nodo | IP | Conmutador | Inventario |
|---|---|---|---|
| SRV-TRAZA | 10.10.10.51 | SW-CIRC-A | autorizado |
| CAM-01 | 10.10.10.52 | SW-CIRC-A | autorizado |
| CAM-02 | 10.10.10.53 | SW-CIRC-A | autorizado |
| LECT-01 | 10.10.10.54 | SW-CIRC-B | autorizado |
| CAM-03 | 10.10.10.55 | SW-CIRC-B | autorizado |
| PC-NAVE (`alpine-1`) | 10.10.10.99 | SW-CIRC-B | autorizado |
| PC-INTRUSO | 10.10.10.66 | SW-CIRC-A | fuera del inventario, apagado hasta la prueba |

Cloud1 se conecta a SW-CIRC-A `eth4`. En la GNS3 VM local usa `eth2`; en la VM de Azure,
`lab-gns` (ver `docs/DESPLIEGUE_NUBE.md`).

Las MAC de los Alpine están fijadas en el proyecto (`properties.mac_address`) y coinciden
con las registradas en el inventario de la plataforma. Por eso la topología debe importarse
desde este proyecto y no recrearse a mano: un nodo nuevo tendría otra MAC y la plataforma lo
señalaría como sustitución.

Para mover el laboratorio a otro servidor GNS3, lo recomendado es la exportación desde la
interfaz (**File → Export portable project**) e importarla en el servidor nuevo. Si solo se
dispone de este directorio, se copia `Topologia.gns3` a `~/GNS3/projects/Topologia/` del
servidor, se reemplaza `"compute_id": "vm"` por `"compute_id": "local"` en esa copia (en el
laboratorio local los nodos corren en la GNS3 VM), se reinicia `gns3server` y se pega en cada
Alpine (clic derecho → *Edit config*) el archivo `configs/<nodo>.interfaces` correspondiente.
Este camino no está probado; la exportación portable es la opción preferida.
