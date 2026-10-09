// Consola de simulación (inyección de eventos) y administración (usuarios, inventario, passkeys).
import { api, aviso, el, estado as icono, fechaHora, vaciar } from "./comun.js";
import { E, recargarEstado } from "./app.js";
import * as webauthn from "./webauthn.js";

async function enviar(dispositivo, cuerpo, mensaje) {
  try {
    await api(`/api/sim/${dispositivo}`, { metodo: "POST", cuerpo });
    aviso(mensaje || `Evento inyectado: ${cuerpo.accion}`);
  } catch (e) {
    aviso(e.message, "crit");
  }
}

const boton = (texto, fn, clase = "") => el("button", { clase: `boton ${clase}`, type: "button", texto, onclick: fn });
const campo = (etiqueta, control) => el("div", { clase: "campo" }, el("label", { texto: etiqueta }), control);

function grupo(titulo, descripcion, ...contenido) {
  return el("div", { clase: "tarjeta" }, el("header", {}, el("h2", { texto: titulo })),
    el("p", { clase: "sec", texto: descripcion }), ...contenido);
}

// ------------------------------------------------------------------ simulación
export function renderSimulacion() {
  const v = vaciar(document.getElementById("v-simulacion"));
  const demo = E.estado && E.estado.red.captura.modo === "demo";

  const tarjeta = el("select", { "aria-label": "Tarjeta" },
    [["C-1001", "C-1001 · Técnico de turno A"], ["C-1002", "C-1002 · Custodio de la sala"], ["C-1003", "C-1003 · Exempleado (revocada)"],
     ["C-9999", "C-9999 · Tarjeta desconocida"]].map(([v2, t]) => el("option", { value: v2, texto: t })));
  const pin = el("input", { type: "password", inputmode: "numeric", maxlength: "8", placeholder: "PIN", "aria-label": "PIN", autocomplete: "off" });
  const leer = (accion) => enviar("puerta", { accion, tarjeta: tarjeta.value, pin: pin.value }, `Lectura enviada a LECT-01 (${tarjeta.value})`);

  const redDemo = demo
    ? el("div", { clase: "botonera" },
      boton("Apagar SW-CIRC-B", () => enviar("red", { accion: "apagar_switch", switch: "SW-CIRC-B" })),
      boton("Encender SW-CIRC-B", () => enviar("red", { accion: "encender_switch", switch: "SW-CIRC-B" })),
      boton("Apagar SW-CIRC-A", () => enviar("red", { accion: "apagar_switch", switch: "SW-CIRC-A" })),
      boton("Encender SW-CIRC-A", () => enviar("red", { accion: "encender_switch", switch: "SW-CIRC-A" })),
      boton("Conectar intruso", () => enviar("red", { accion: "conectar_intruso" })),
      boton("Desconectar intruso", () => enviar("red", { accion: "desconectar_intruso" })),
      boton("Sustituir CAM-02", () => enviar("red", { accion: "sustituir", nombre: "CAM-02" })),
      boton("Restaurar red", () => enviar("red", { accion: "restaurar" })))
    : el("div", { clase: "tabla-contenedor" }, el("table", {},
      el("thead", {}, el("tr", {}, ["Evento", "Acción en GNS3"].map((c) => el("th", { texto: c })))),
      el("tbody", {}, [
        ["Equipo no autorizado", "Encender PC-INTRUSO (10.10.10.66, fuera del inventario)"],
        ["Sustitución de equipo", "Cambiar la MAC de un Alpine: ip link set eth0 address 02:42:de:ad:be:ef"],
        ["Cascada PoE", "Detener SW-CIRC-B, que alimenta a LECT-01 y CAM-03"],
        ["Pérdida de visibilidad", "Detener SW-CIRC-A, donde cuelga el nodo Cloud"],
      ].map(([a, b]) => el("tr", {}, el("td", { texto: a }), el("td", { texto: b }))))));

  v.append(
    el("div", { clase: "aviso" }, "Cada evento inyectado queda en la bitácora con su actor, para que el auditor distinga una prueba de un incidente real."),
    el("div", { clase: "rejilla r-2 seccion" },
      grupo("Energía: UPS, transferencia y planta", "La descarga de la batería está acelerada; el arranque de la planta corre en segundos reales para medir el tipo 10 de NFPA 110.",
        el("div", { clase: "botonera" },
          boton("Cortar acometida", () => enviar("ups", { accion: "corte_acometida" }), "peligro"),
          boton("Restablecer acometida", () => enviar("ups", { accion: "retorno_acometida" })),
          boton("Falla de planta", () => enviar("ups", { accion: "falla_planta" }), "peligro"),
          boton("Reparar planta", () => enviar("ups", { accion: "reparar_planta" })),
          boton("Arranque lento, 14 s", () => enviar("ups", { accion: "fijar_arranque", segundos: 14 })),
          boton("Arranque normal, 7 s", () => enviar("ups", { accion: "fijar_arranque", segundos: 7 })),
          boton("Ejercicio mensual", () => enviar("ups", { accion: "prueba_mensual" })))),
      grupo("Ambiente: climatización, humo y sensores", "Sin acometida ni planta, la climatización se apaga y la sala se calienta.",
        el("div", { clase: "botonera" },
          boton("Falla de climatización", () => enviar("ambiente", { accion: "falla_clima" }), "peligro"),
          boton("Restaurar climatización", () => enviar("ambiente", { accion: "restaurar_clima" })),
          boton("T-RACK-A a 29 °C", () => enviar("ambiente", { accion: "fijar", sensor: "T-RACK-A", valor: 29 })),
          boton("T-RACK-A a 34 °C", () => enviar("ambiente", { accion: "fijar", sensor: "T-RACK-A", valor: 34 }), "peligro"),
          boton("Liberar sensores", () => enviar("ambiente", { accion: "liberar" })),
          boton("Silenciar T-RACK-B", () => enviar("ambiente", { accion: "silenciar", sensor: "T-RACK-B" })),
          boton("Reactivar T-RACK-B", () => enviar("ambiente", { accion: "reactivar", sensor: "T-RACK-B" })),
          boton("Detectar humo", () => enviar("ambiente", { accion: "humo" }), "peligro"),
          boton("Abortar descarga", () => enviar("ambiente", { accion: "abortar_supresion" })),
          boton("Restablecer detección", () => enviar("ambiente", { accion: "restablecer_humo" })))),
      grupo("Puerta de la sala: tarjeta + PIN", "PIN de demostración: C-1001 → 1357, C-1002 → 2468. El PIN de coacción es el mismo con el último dígito + 1, por ejemplo 1358.",
        el("div", { clase: "formulario" }, tarjeta, pin,
          boton("Presentar tarjeta y PIN", () => leer("leer"), "primario"),
          boton("Entrar y dejar abierta", () => leer("mantener")),
          boton("Forzar la puerta", () => enviar("puerta", { accion: "forzar" }), "peligro"))),
      grupo("Red", demo ? "El capturador está en modo demostración: el tráfico es generado." : "Captura real: los eventos de red se provocan desde GNS3.", redDemo)));
}

// ------------------------------------------------------------------ administración
function mostrarCodigo(usuario, codigo) {
  const caja = document.getElementById("res-usuarios");
  if (!caja) return;
  vaciar(caja).append(el("div", { clase: "aviso" },
    `Código de alta de ${usuario}. Entréguelo por un canal separado; se muestra una sola vez y vence en 24 h.`,
    el("div", { clase: "codigo-alta", texto: codigo })));
}

export async function renderAdmin() {
  const v = vaciar(document.getElementById("v-admin"));
  const [usuarios, inventario, yo] = await Promise.all([api("/api/admin/usuarios"), api("/api/admin/inventario"), api("/api/auth/yo")]);

  const resultado = el("div");
  const fUsuario = el("input", { type: "text", placeholder: "usuario", maxlength: "30", "aria-label": "Usuario" });
  const fNombre = el("input", { type: "text", placeholder: "Nombre completo", maxlength: "60", "aria-label": "Nombre" });
  const fRol = el("select", { "aria-label": "Rol" }, ["operador", "auditor", "administrador"].map((r) => el("option", { value: r, texto: r })));
  const crear = async () => {
    try {
      const r = await api("/api/admin/usuarios", { metodo: "POST", cuerpo: { usuario: fUsuario.value.trim().toLowerCase(), nombre: fNombre.value, rol: fRol.value } });
      await renderAdmin();
      mostrarCodigo(r.usuario, r.codigo_alta);
    } catch (e) { aviso(e.message, "crit"); }
  };

  const filasUsuarios = usuarios.map((u) => el("tr", { clase: u.activo ? "" : "tenue" },
    el("td", { clase: "mono", texto: u.usuario }), el("td", { texto: u.nombre }), el("td", { texto: u.rol }),
    el("td", {}, !u.activo ? icono("neutro", "Baja") : u.alta_pendiente ? icono("adv", "Alta pendiente") : icono("ok", "Activa")),
    el("td", { clase: "num", texto: String(u.passkeys) }),
    el("td", {}, u.activo && u.usuario !== yo.usuario ? el("div", { clase: "botonera" },
      boton("Restablecer", async () => {
        try { const r = await api(`/api/admin/usuarios/${u.id}/restablecer`, { metodo: "POST" }); await renderAdmin(); mostrarCodigo(r.usuario, r.codigo_alta); }
        catch (e) { aviso(e.message, "crit"); }
      }),
      boton("Dar de baja", async () => {
        try { const r = await api(`/api/admin/usuarios/${u.id}/baja`, { metodo: "POST" }); aviso(`Baja aplicada; ${r.credenciales_revocadas} passkeys revocadas`); renderAdmin(); }
        catch (e) { aviso(e.message, "crit"); }
      }, "peligro")) : null)));

  const iIp = el("input", { type: "text", placeholder: "10.10.10.56", maxlength: "15", "aria-label": "IP" });
  const iNombre = el("input", { type: "text", placeholder: "CAM-04", maxlength: "24", "aria-label": "Nombre" });
  const iTipo = el("select", { "aria-label": "Tipo" }, ["camara", "lectora", "sensor", "servidor", "otro"].map((t) => el("option", { value: t, texto: t })));
  const iSw = el("select", { "aria-label": "Conmutador" }, ["SW-CIRC-A", "SW-CIRC-B"].map((t) => el("option", { value: t, texto: t })));
  const iMac = el("input", { type: "text", placeholder: "MAC opcional", maxlength: "17", "aria-label": "MAC" });
  const agregar = async () => {
    try {
      await api("/api/admin/inventario", { metodo: "POST", cuerpo: { ip: iIp.value, nombre: iNombre.value, tipo: iTipo.value, switch: iSw.value, mac: iMac.value || null } });
      aviso("Equipo agregado al inventario autorizado");
      await recargarEstado();
      renderAdmin();
    } catch (e) { aviso(e.message, "crit"); }
  };
  const filasInv = inventario.map((d) => el("tr", {},
    el("td", { texto: d.nombre }), el("td", { clase: "mono", texto: d.ip }), el("td", { clase: "mono", texto: d.mac || "por primer uso" }),
    el("td", { texto: d.switch }), el("td", { texto: d.tipo }), el("td", { texto: d.poe ? "Sí" : "No" }),
    el("td", {}, boton("Retirar", async () => {
      try { await api(`/api/admin/inventario/${encodeURIComponent(d.ip)}`, { metodo: "DELETE" }); await recargarEstado(); renderAdmin(); }
      catch (e) { aviso(e.message, "crit"); }
    }, "peligro"))));

  const nombrePk = el("input", { type: "text", maxlength: "40", placeholder: "Nombre, p. ej. Llave FIDO2", "aria-label": "Nombre de la passkey" });
  const registrarPk = async () => {
    try {
      const opciones = await api("/api/auth/passkey/registro/opciones", { metodo: "POST" });
      const credencial = await webauthn.crear(opciones);
      await api("/api/auth/passkey/registro/verificar", { metodo: "POST", cuerpo: { credencial, nombre: nombrePk.value } });
      aviso("Passkey adicional registrada");
      renderAdmin();
    } catch (e) { aviso(webauthn.mensajeError(e), "crit"); }
  };
  const filasPk = yo.passkeys.map((p) => el("tr", {}, el("td", { texto: p.nombre }), el("td", { texto: p.tipo_disp === "multi_device" ? "sincronizada" : "ligada al dispositivo" }),
    el("td", { texto: JSON.parse(p.transports || "[]").join(", ") || "-" }), el("td", { texto: fechaHora(p.creada) }), el("td", { texto: fechaHora(p.ultimo_uso) || "-" })));

  v.append(
    el("div", { clase: "aviso" }, "Las acciones de esta pestaña piden confirmar su identidad con la passkey si no lo hizo en los últimos minutos."),
    el("div", { clase: "tarjeta seccion" }, el("header", {}, el("h2", { texto: "Usuarios y roles" })),
      el("div", { clase: "formulario" }, fUsuario, fNombre, fRol, boton("Crear y emitir código de alta", crear, "primario")),
      el("div", { id: "res-usuarios", clase: "seccion" }, resultado),
      el("div", { clase: "tabla-contenedor seccion" }, el("table", {},
        el("thead", {}, el("tr", {}, ["Usuario", "Nombre", "Rol", "Estado", "Passkeys", "Acciones"].map((c) => el("th", { texto: c })))),
        el("tbody", {}, filasUsuarios)))),
    el("div", { clase: "tarjeta seccion" }, el("header", {}, el("h2", { texto: "Inventario autorizado de la red" })),
      el("p", { clase: "sec", texto: "Formulario para agregar un equipo o actualizar uno existente con la misma IP; no filtra la tabla. Los equipos no autorizados también se pueden autorizar desde la pestaña Red." }),
      el("div", { clase: "formulario" }, campo("IP", iIp), campo("Nombre", iNombre), campo("Tipo", iTipo), campo("Conmutador", iSw),
        campo("MAC (opcional)", iMac), boton("Agregar equipo", agregar, "primario")),
      el("div", { clase: "tabla-contenedor seccion" }, el("table", {},
        el("thead", {}, el("tr", {}, ["Equipo", "IP", "MAC registrada", "Conmutador", "Tipo", "PoE", ""].map((c) => el("th", { texto: c })))),
        el("tbody", {}, filasInv)))),
    el("div", { clase: "tarjeta seccion" }, el("header", {}, el("h2", { texto: "Mis passkeys" })),
      el("p", { clase: "sec", texto: "Registre una segunda passkey, por ejemplo una llave FIDO2 de respaldo, para no quedar fuera si pierde el teléfono." }),
      el("div", { clase: "formulario" }, nombrePk, boton("Registrar otra passkey", registrarPk)),
      el("div", { clase: "tabla-contenedor seccion" }, el("table", {},
        el("thead", {}, el("tr", {}, ["Nombre", "Tipo", "Transportes", "Creada", "Último uso"].map((c) => el("th", { texto: c })))),
        el("tbody", {}, filasPk)))));
}
