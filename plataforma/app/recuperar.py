"""Recuperación de una cuenta desde la consola del servidor (procedimiento de emergencia).

Hace lo mismo que "Restablecer" en Administración: revoca las passkeys, borra la
contraseña, cierra las sesiones y emite un código de alta nuevo. Sirve cuando ningún
administrador puede entrar, por ejemplo si su única passkey era el autenticador
virtual de Chrome. Exige acceso a la GNS3 VM y queda registrado en la bitácora.

    docker compose exec plataforma python -m app.recuperar admin
"""

import json
import sqlite3
import sys

from . import bitacora, config
from .auth import seguridad
from .util import iso


def recuperar(usuario: str) -> str:
    con = sqlite3.connect(config.DB_PATH, timeout=10, isolation_level=None)
    con.row_factory = sqlite3.Row
    try:
        # BEGIN IMMEDIATE toma el bloqueo de escritura antes de leer el último hash,
        # para que un evento de la plataforma no se intercale y rompa la cadena.
        con.execute("BEGIN IMMEDIATE")
        u = con.execute("SELECT * FROM usuarios WHERE usuario = ? AND activo = 1", (usuario,)).fetchone()
        if not u:
            con.execute("ROLLBACK")
            raise SystemExit(f"No existe un usuario activo llamado {usuario}")
        codigo = seguridad.generar_codigo_alta()
        n = con.execute("UPDATE credenciales SET revocada = 1 WHERE usuario_id = ? AND revocada = 0",
                        (u["id"],)).rowcount
        con.execute("""UPDATE usuarios SET password_hash = NULL, codigo_alta_hash = ?, codigo_alta_expira = ?,
                       intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = ?""",
                    (seguridad.hash_codigo(codigo), seguridad.expiracion_codigo(), u["id"]))
        con.execute("DELETE FROM sesiones WHERE usuario_id = ?", (u["id"],))
        evento = {
            "ts": iso(), "modulo": "auth", "tipo": "usuario_restablecido", "severidad": "advertencia",
            "descripcion": f"Se restableció el alta de {usuario} desde la consola del servidor: "
                           f"{n} passkeys revocadas y nuevo código emitido",
            "control_iso": "5.18", "norma": "NIST SP 800-63B-4", "actor": "consola:recuperacion",
            "ref_id": None,
            "datos": json.dumps({"usuario": usuario, "credenciales_revocadas": n, "via": "consola"},
                                ensure_ascii=False, sort_keys=True),
        }
        fila = con.execute("SELECT hash FROM eventos ORDER BY id DESC LIMIT 1").fetchone()
        evento["hash_anterior"] = fila["hash"] if fila else bitacora.GENESIS
        evento["hash"] = bitacora._calcular_hash(evento["hash_anterior"], evento)
        con.execute("""INSERT INTO eventos (ts, modulo, tipo, severidad, descripcion, control_iso, norma,
                                           actor, ref_id, datos, hash_anterior, hash)
                       VALUES (:ts,:modulo,:tipo,:severidad,:descripcion,:control_iso,:norma,
                               :actor,:ref_id,:datos,:hash_anterior,:hash)""", evento)
        con.execute("COMMIT")
        return codigo
    except Exception:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python -m app.recuperar <usuario>")
    nombre = sys.argv[1].strip().lower()
    print(f"usuario={nombre}  código={recuperar(nombre)}  (vence en {config.CODIGO_ALTA_HORAS} h)")
