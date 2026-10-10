# Acceso para el equipo auditor

El laboratorio y la plataforma están en una VM de Azure que solo es visible dentro de una
red privada de Tailscale. No hay servicios publicados en Internet.

## 1. Unirse a la red

1. Crear una cuenta gratuita en tailscale.com e instalar Tailscale en el equipo desde el que
   se auditará.
2. Enviar al equipo del proyecto el correo de esa cuenta. Recibirán una invitación para
   compartir la máquina **`dcim`**; al aceptarla, aparece en la lista de Tailscale.
3. Comprobar: abrir `https://dcim.taila9c375.ts.net/salud`. Debe responder
   `{"estado":"ok","mqtt":true}` con un certificado válido.

## 2. Cuentas de la plataforma

Cada auditor recibe dos cuentas, porque la plataforma separa funciones:

| Cuenta | Rol | Para qué |
|---|---|---|
| `op-<apellido>` (o `operador-ext`) | operador | Ejecutar las simulaciones y registrar acuses |
| `aud-<apellido>` (o `auditor-ext`) | auditor | Verificar la cadena, exportar la bitácora, comprobar el mínimo privilegio |

El equipo del proyecto entrega por **mensaje directo**, separado de este documento, el
usuario y el **código de alta** de cada cuenta, y la clave del servidor GNS3. El código sirve
una sola vez y vence en 24 horas; si vence, se pide uno nuevo.

1. Abrir `https://dcim.taila9c375.ts.net/alta`, escribir el usuario, el código y una
   contraseña de al menos 12 caracteres.
2. Registrar la passkey. En el diálogo del navegador elegir "Usar un teléfono o tableta"
   (o "Guardar de otra forma → iPhone, iPad o dispositivo Android"), escanear el QR y
   confirmar con la huella o el rostro. También sirven Windows Hello o una llave FIDO2.
3. Cerrar sesión y volver a entrar con contraseña y passkey.

## 3. Topología GNS3

| Opción | Cómo |
|---|---|
| Navegador | `http://dcim.taila9c375.ts.net:3080`, con el usuario y la clave del servidor GNS3 que entrega el equipo del proyecto. Permite ver la topología, encender y detener nodos y abrir consolas web |
| Cliente GNS3 2.2.61 | Edit → Preferences → Server: desmarcar *Enable local server*, host `dcim.taila9c375.ts.net`, puerto 3080 y las mismas credenciales. Debe ser exactamente la versión 2.2.61 |

Abrir el proyecto **Topologia**. PC-INTRUSO está apagado a propósito: encenderlo es la
prueba de equipo no autorizado.

## 4. Qué auditar

Los escenarios, el marco normativo y la matriz de trazabilidad están en
`docs/MANUAL_SIMULACIONES.md`. La bitácora ya contiene la evidencia del ensayo del equipo del
proyecto, migrada desde el laboratorio local con su cadena de hash; los eventos que genere
la auditoría se encadenan a continuación. El primer `plataforma_iniciada` con
`RP_ID=dcim...` marca el paso a la nube.

Recomendaciones:

- Anotar el último `id` de la bitácora antes de empezar.
- Ejecutar las simulaciones con la cuenta de operador, para que cada prueba quede con el
  actor en el evento `comando_simulado`.
- Al terminar, con la cuenta de auditor: Bitácora → Verificar cadena y Exportar CSV.

## 5. Reglas de uso

- No cambiar la topología (enlaces, nodos, configuraciones) salvo lo que indique un escenario.
- No redesplegar ni reiniciar contenedores durante una prueba.
- La VM se apaga sola cada noche; si no responde, pedir al equipo del proyecto que la encienda.
