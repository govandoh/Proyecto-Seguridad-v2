// Vistas de los frentes del datacenter: red, energía, ambiente y acceso físico.
import { api, aviso, el, estado as icono, hora, svg, vaciar } from "./comun.js";
import { E, puede, recargarEstado } from "./app.js";
import { lineaTiempo } from "./graficas.js";

// ------------------------------------------------------------------ gráficas persistentes
const G = { temp: null, bat: null, bufTemp: [], bufBat: [], cajaTemp: null, cajaBat: null };

export function iniciarGraficas() {
  G.cajaTemp = el("div", { clase: "grafica" }, el("canvas", { "aria-label": "Temperatura de entrada por rack" }));
  G.cajaBat = el("div", { clase: "grafica" }, el("canvas", { "aria-label": "Autonomía del UPS" }));
}

function asegurarTemp() {
  if (G.temp || !G.cajaTemp.isConnected) return;
  const u = E.estado.ambiente.umbrales;
  const sensores = [...new Set([...E.estado.ambiente.sensores.map((s) => s.sensor), "T-RACK-A", "T-RACK-B"])].slice(0, 2);
  G.temp = lineaTiempo(G.cajaTemp.querySelector("canvas"), {
    unidad: "°C", yMin: 15, yMax: 36,
    series: sensores.map((s, i) => ({ clave: s, etiqueta: s, color: i ? "--serie-2" : "--serie-1" })),
    umbrales: [
      { etiqueta: `Máx. permisible ${u.max_permisible} °C`, valor: u.max_permisible, color: "--crit" },
      { etiqueta: `Máx. recomendado ${u.max_recomendada} °C`, valor: u.max_recomendada, color: "--adv" },
      { etiqueta: `Mín. recomendado ${u.min_recomendada} °C`, valor: u.min_recomendada, color: "--tenue" },
    ],
  });
  for (const p of G.bufTemp) G.temp.agregar(p.s, p.x, p.y);
}

function asegurarBat() {
  if (G.bat || !G.cajaBat.isConnected) return;
  const d = E.estado.energia.diseno;
  G.bat = lineaTiempo(G.cajaBat.querySelector("canvas"), {
    unidad: "min simulados", yMin: 0, yMax: Math.ceil(d.autonomia_min / 10) * 10 + 5,
    series: [{ clave: "rt", etiqueta: "Autonomía restante", color: "--serie-1" }],
    umbrales: [
      { etiqueta: `Diseño ${d.autonomia_min} min`, valor: d.autonomia_min, color: "--tenue" },
      { etiqueta: `Batería baja ${d.umbral_bateria_baja_min} min`, valor: d.umbral_bateria_baja_min, color: "--crit" },
    ],
  });
  for (const p of G.bufBat) G.bat.agregar("rt", p.x, p.y);
}

export async function cargarHistoriales() {
  const [amb, en] = await Promise.all([api("/api/historial/ambiente?minutos=15"), api("/api/historial/energia?minutos=15")]);
  for (const r of amb) G.bufTemp.push({ s: r.sensor, x: Date.parse(r.ts), y: r.valor });
  for (const r of en) if (r.runtime_min !== null) G.bufBat.push({ x: Date.parse(r.ts), y: r.runtime_min });
}

export function agregarTemperatura(d) {
  const p = { s: d.sensor, x: Date.parse(d.ts), y: d.temp_c };
  G.bufTemp.push(p);
  if (G.bufTemp.length > 2000) G.bufTemp.splice(0, 500);
  if (G.temp) G.temp.agregar(p.s, p.x, p.y);
}

export function agregarEnergia(d) {
  const rt = d.telemetria && d.telemetria["battery.runtime"];
  if (rt === undefined || rt === null) return;
  const p = { x: Date.now(), y: rt / 60 };
  G.bufBat.push(p);
  if (G.bufBat.length > 2000) G.bufBat.splice(0, 500);
  if (G.bat) G.bat.agregar("rt", p.x, p.y);
}

function leyenda(items) {
  return el("div", { clase: "leyenda" }, items.map(([clase, texto]) => el("span", {}, el("i", { clase: `muestra ${clase}` }), texto)));
}

function dato(etiqueta, valor, sufijo = "") {
  return el("div", { clase: "dato" }, el("span", { clase: "etq", texto: etiqueta }),
    el("span", { clase: "val num" }, String(valor), sufijo ? el("small", { texto: ` ${sufijo}` }) : null));
}

// ------------------------------------------------------------------ red
const NIVEL_EQUIPO = { en_linea: "ok", caido: "crit", sin_trafico: "neutro" };
const TEXTO_EQUIPO = { en_linea: "En línea", caido: "Caído", sin_trafico: "Sin tráfico" };

// Un registro por IP del inventario: si alguna MAC de esa IP está en línea, el equipo está en línea;
// si la MAC en línea no es la registrada, se marca como sustituido.
export function porEquipo(equipos) {
  const m = new Map();
  for (const e of equipos) {
    const previo = m.get(e.ip);
    const sust = e.estado === "en_linea" && e.mac_registrada && e.mac && e.mac !== e.mac_registrada;
    if (!previo || (e.estado === "en_linea" && previo.estado !== "en_linea")) m.set(e.ip, { ...e, sustituido: sust || (previo && previo.sustituido) });
    else if (sust) previo.sustituido = true;
  }
  return [...m.values()];
}

function topologia(red) {
  const W = 960, H = 380;
  const rango = { "SW-CIRC-A": [30, W / 2 - 15], "SW-CIRC-B": [W / 2 + 15, W - 30] };
  const pos = { "SW-CIRC-A": (rango["SW-CIRC-A"][0] + rango["SW-CIRC-A"][1]) / 2, "SW-CIRC-B": (rango["SW-CIRC-B"][0] + rango["SW-CIRC-B"][1]) / 2 };
  const nodos = [], lineas = [];
  const caja = (x, y, w, h, clase, titulo, sub) => svg("g", { clase: `nodo ${clase}` },
    svg("rect", { x: x - w / 2, y, width: w, height: h, rx: 8 }),
    svg("text", { x, y: y + 18, "text-anchor": "middle", texto: titulo }),
    sub ? svg("text", { clase: "sub", x, y: y + 34, "text-anchor": "middle", texto: sub }) : null);

  const cap = red.captura;
  const capClase = red.visibilidad_perdida || !cap.activa ? "n-crit" : "n-ok";
  nodos.push(caja(W / 2, 12, 220, 44, capClase, "Punto de captura eth2", cap.activa ? `${cap.modo} · ${cap.paquetes} paq/s` : "sin datos"));
  lineas.push(svg("line", { x1: W / 2, y1: 56, x2: pos["SW-CIRC-A"], y2: 110, clase: red.visibilidad_perdida ? "caida" : "" }));
  lineas.push(svg("line", { x1: pos["SW-CIRC-A"] + 80, y1: 132, x2: pos["SW-CIRC-B"] - 80, y2: 132 }));
  for (const [sw, x] of Object.entries(pos)) {
    const propios = porEquipo(red.equipos.filter((e) => e.autorizado && e.switch === sw));
    const vistos = propios.filter((e) => e.estado !== "sin_trafico");
    const todosCaidos = vistos.length && vistos.every((e) => e.estado === "caido");
    nodos.push(caja(x, 110, 160, 44, todosCaidos ? "n-crit" : "n-switch", sw, todosCaidos ? "sin tráfico de sus equipos" : "Open vSwitch"));
    const [a, b] = rango[sw];
    const paso = propios.length > 1 ? Math.min(140, (b - a - 132) / (propios.length - 1)) : 0;
    const x0 = x - ((propios.length - 1) * paso) / 2;
    propios.forEach((e, i) => {
      const xi = x0 + i * paso;
      lineas.push(svg("line", { x1: x, y1: 154, x2: xi, y2: 230, clase: e.estado === "caido" ? "caida" : "" }));
      const clase = e.sustituido ? "n-crit" : `n-${NIVEL_EQUIPO[e.estado] || "neutro"}`;
      nodos.push(caja(xi, 230, 128, 44, clase, e.nombre, e.sustituido ? "MAC distinta" : `${e.ip} · ${TEXTO_EQUIPO[e.estado] || e.estado}`));
    });
  }
  const intrusos = red.equipos.filter((e) => !e.autorizado);
  intrusos.slice(0, 5).forEach((e, i) => {
    const xi = 140 + i * 170;
    lineas.push(svg("line", { x1: pos["SW-CIRC-A"], y1: 154, x2: xi, y2: 320, clase: "caida" }));
    nodos.push(caja(xi, 320, 150, 44, "n-intruso", "NO AUTORIZADO", `${e.ip} · ${TEXTO_EQUIPO[e.estado] || e.estado}`));
  });
  return el("div", { clase: "topologia" }, svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Topología de la red del laboratorio" }, ...lineas, ...nodos));
}

// Autorizar o retirar un equipo desde la vista de tráfico, como en la v1. El modal cuelga de
// <body> para que el repintado en vivo de la pestaña no borre lo que se está escribiendo.
function modalInventario(titulo, descripcion, campos, textoAccion, clase, accion) {
  const velo = el("div", { clase: "velo", role: "dialog", "aria-modal": "true" });
  const cerrar = () => velo.remove();
  const ejecutar = el("button", { clase: `boton ${clase}`, type: "button", texto: textoAccion });
  ejecutar.addEventListener("click", async () => {
    ejecutar.disabled = true;
    try {
      await accion();
      cerrar();
      await recargarEstado();
    } catch (e) { aviso(e.message, "crit"); ejecutar.disabled = false; }
  });
  velo.append(el("div", { clase: "modal" }, el("h2", { texto: titulo }), el("p", { clase: "sec", texto: descripcion }),
    campos ? el("div", { clase: "formulario seccion" }, campos) : null,
    el("footer", {}, el("button", { clase: "boton", type: "button", texto: "Cancelar", onclick: cerrar }), ejecutar)));
  velo.addEventListener("click", (ev) => { if (ev.target === velo) cerrar(); });
  document.body.append(velo);
  const primero = velo.querySelector("input");
  if (primero) primero.focus();
}

const campo = (etiqueta, control) => el("div", { clase: "campo" }, el("label", { texto: etiqueta }), control);

function autorizarEquipo(e) {
  const nombre = el("input", { type: "text", maxlength: "24", placeholder: "CAM-04", "aria-label": "Nombre" });
  const tipo = el("select", { "aria-label": "Tipo" }, ["camara", "lectora", "sensor", "servidor", "otro"].map((t) => el("option", { value: t, texto: t })));
  const sw = el("select", { "aria-label": "Conmutador" }, ["SW-CIRC-A", "SW-CIRC-B"].map((t) => el("option", { value: t, texto: t })));
  modalInventario(`Autorizar ${e.ip}`,
    `Se agrega al inventario autorizado con la MAC observada ${e.mac || "(sin MAC)"}; si luego cambia, se detectará como sustitución.`,
    [campo("Nombre", nombre), campo("Tipo", tipo), campo("Conmutador", sw)], "Autorizar", "primario",
    async () => {
      await api("/api/admin/inventario", { metodo: "POST", cuerpo: { ip: e.ip, nombre: nombre.value.trim(), tipo: tipo.value, switch: sw.value, mac: e.mac || null } });
      aviso(`${e.ip} agregado al inventario autorizado`);
    });
}

function retirarEquipo(e) {
  modalInventario(`Retirar ${e.nombre}`,
    `Se quita ${e.ip} del inventario autorizado. Si el equipo sigue emitiendo, aparecerá como no autorizado.`,
    null, "Retirar del inventario", "peligro",
    async () => {
      await api(`/api/admin/inventario/${encodeURIComponent(e.ip)}`, { metodo: "DELETE" });
      aviso(`${e.nombre} retirado del inventario`);
    });
}

export function renderRed() {
  const v = vaciar(document.getElementById("v-red"));
  const red = E.estado.red;
  const admin = puede("administrar");
  const filas = red.equipos.map((e) => el("tr", { clase: !e.autorizado ? "fila-crit" : e.estado === "caido" ? "fila-adv" : "" },
    el("td", { texto: e.nombre }), el("td", { clase: "mono", texto: e.ip }), el("td", { clase: "mono", texto: e.mac || "-" }),
    el("td", { texto: e.switch }),
    el("td", {}, !e.autorizado ? icono("crit", "No autorizado")
      : e.mac_registrada && e.mac && e.mac !== e.mac_registrada ? icono("crit", "MAC distinta a la registrada") : icono("ok", "Autorizado")),
    el("td", {}, icono(NIVEL_EQUIPO[e.estado] || "neutro", TEXTO_EQUIPO[e.estado] || e.estado)),
    el("td", { clase: "num", texto: e.visto_hace_s === null ? "-" : `${e.visto_hace_s} s` }),
    admin ? el("td", {}, !e.autorizado
      ? el("button", { clase: "boton primario", type: "button", texto: "Autorizar", onclick: () => autorizarEquipo(e) })
      : el("button", { clase: "boton peligro", type: "button", texto: "Retirar", onclick: () => retirarEquipo(e) })) : null));
  const columnas = ["Equipo", "IP", "MAC", "Conmutador", "Autorización", "Estado", "Último tráfico", ...(admin ? ["Acciones"] : [])];
  const aviso = red.visibilidad_perdida
    ? el("div", { clase: "aviso" }, icono("crit", "Pérdida de visibilidad: los eventos de red no son confiables hasta restablecer SW-CIRC-A o el enlace de captura."))
    : !red.captura.activa ? el("div", { clase: "aviso" }, icono("crit", red.captura.error
      ? `El capturador no puede leer ${red.captura.iface}: ${red.captura.error}`
      : "El capturador de red no publica. Revise el contenedor sensor-red.")) : null;
  v.append(
    aviso || "",
    el("div", { clase: "tarjeta seccion" }, el("header", {}, el("h2", { texto: "Topología y estado de los equipos" }), el("div", { clase: "espacio" }),
      el("span", { clase: "chip", texto: red.captura.modo === "demo" ? "Tráfico generado (demo)" : `Captura real en ${red.captura.iface || "eth2"}` })),
      topologia(red)),
    el("div", { clase: "tarjeta seccion" }, el("header", {}, el("h2", { texto: "Equipos observados e inventario autorizado" })),
      el("p", { clase: "sec", texto: "Esquema permisivo: todo equipo fuera del inventario se trata como no autorizado (IEEE 802.1X). La MAC queda registrada por primer uso y su cambio indica sustitución (IEEE 802.1AR)." }),
      el("div", { clase: "tabla-contenedor" }, el("table", {},
        el("thead", {}, el("tr", {}, columnas.map((c) => el("th", { texto: c })))),
        el("tbody", {}, filas)))));
}

// ------------------------------------------------------------------ energía
const PASOS = ["NORMAL", "CORTE_DETECTADO", "UPS_EN_BATERIA", "TRANSFERENCIA_GENERADOR", "BATERIA_BAJA", "APAGADO_CONTROLADO"];
const CRITICOS = ["CORTE_DETECTADO", "BATERIA_BAJA", "APAGADO_CONTROLADO"];

export function renderEnergia() {
  const v = vaciar(document.getElementById("v-energia"));
  const en = E.estado.energia;
  const t = en.telemetria || {};
  const p = t.planta || {};
  const fsm = el("div", { clase: "fsm" });
  PASOS.forEach((s, i) => {
    if (i) fsm.append(el("span", { clase: "flecha", "aria-hidden": "true", texto: "→" }));
    fsm.append(el("span", { clase: `paso ${en.estado === s ? "activo" : ""} ${en.estado === s && CRITICOS.includes(s) ? "crit" : ""}`, texto: s.replace(/_/g, " ") }));
  });
  const trans = en.transferencia_s;
  const nivelTrans = trans === null || trans === undefined ? "neutro" : trans <= en.tipo_nfpa110_s ? "ok" : "crit";
  const status = t["ups.status"] || "-";
  const nivelUps = !en.comunicacion ? "crit" : status.startsWith("OB") ? "adv" : status.startsWith("OFF") ? "crit" : "ok";
  const cargas = en.diseno.cargas.map((c) => el("tr", {}, el("td", { texto: c.equipo }), el("td", { clase: "num", texto: `${c.potencia_w} W` }),
    el("td", {}, c.critica ? icono("adv", "Crítica") : icono("neutro", "No crítica"))));
  v.append(
    el("div", { clase: "tarjeta" }, el("header", {}, el("h2", { texto: "Máquina de estados del incidente eléctrico" }), el("div", { clase: "espacio" }),
      icono(nivelUps, en.comunicacion ? `UPS ${status}` : "UPS sin comunicación")), fsm),
    el("div", { clase: "rejilla r-4 seccion" },
      el("div", { clase: "tarjeta" }, dato("Acometida", t.acometida ? "Presente" : "Ausente"), icono(t.acometida ? "ok" : "crit", t.acometida ? "Red pública" : "Sin red pública"),
        el("span", { clase: "sec", texto: `Entrada ${t["input.voltage"] ?? "-"} V${!t.acometida && t.ats === "planta" ? " desde la planta" : ""}` })),
      el("div", { clase: "tarjeta" }, dato("Carga de batería", t["battery.charge"] ?? "-", "%")),
      el("div", { clase: "tarjeta" }, dato("Autonomía restante", t["battery.runtime"] !== undefined ? (t["battery.runtime"] / 60).toFixed(1) : "-", "min"),
        el("span", { clase: "sec", texto: `tiempo acelerado x${t.factor_tiempo ?? "-"}` })),
      el("div", { clase: "tarjeta" }, dato("Planta de emergencia", (p.estado || "-").replace(/_/g, " ")), el("span", { clase: "sec", texto: `arranque configurado ${p.t_arranque_s ?? "-"} s · ATS: ${t.ats || "-"}` })),
      el("div", { clase: "tarjeta" }, dato("Última transferencia", trans ?? "-", "s"), icono(nivelTrans, `tipo ${en.tipo_nfpa110_s} de NFPA 110: ≤ ${en.tipo_nfpa110_s} s`)),
      el("div", { clase: "tarjeta" }, dato("Carga del UPS", t["ups.load"] ?? "-", "%"), el("span", { clase: "sec", texto: `${t["ups.realpower"] ?? "-"} W` }))),
    el("div", { clase: "rejilla r-2 seccion" },
      el("div", { clase: "tarjeta" }, el("header", {}, el("h2", { texto: "Autonomía del UPS" })), G.cajaBat,
        leyenda([["s1", "Autonomía restante"], ["lim-frio", "Autonomía de diseño"], ["lim-crit", "Umbral de batería baja"]])),
      el("div", { clase: "tarjeta" }, el("header", {}, el("h2", { texto: "Inventario de cargas y autonomía de diseño" })),
        el("p", { clase: "mono", texto: `t = 60 · E · η / P = 60 · ${en.diseno.energia_wh} · ${en.diseno.eficiencia} / ${en.diseno.carga_w} = ${en.diseno.autonomia_min} min` }),
        el("div", { clase: "tabla-contenedor" }, el("table", {}, el("thead", {}, el("tr", {}, ["Equipo", "Potencia", "Prioridad"].map((c) => el("th", { texto: c })))),
          el("tbody", {}, cargas))))));
  asegurarBat();
}

// ------------------------------------------------------------------ ambiente
const NIVEL_T = { normal: "ok", advertencia: "adv", frio: "adv", critico: "crit", mudo: "adv" };
const TEXTO_T = { normal: "En rango", advertencia: "Sobre 27 °C", frio: "Bajo 18 °C", critico: "Sobre 32 °C", mudo: "Sensor mudo" };

export function renderAmbiente() {
  const v = vaciar(document.getElementById("v-ambiente"));
  const a = E.estado.ambiente;
  const humo = a.alarma.humo === "activa";
  v.append(
    el("div", { clase: "rejilla r-4" },
      a.sensores.map((s) => el("div", { clase: "tarjeta" }, dato(s.sensor, s.temp_c.toFixed(1), "°C"),
        icono(NIVEL_T[s.estado] || "neutro", TEXTO_T[s.estado] || s.estado),
        el("span", { clase: "sec", texto: `HR ${s.humedad ?? "-"} % · hace ${s.edad_s} s` }))),
      el("div", { clase: "tarjeta" }, dato("Detección de humo", humo ? "ALARMA" : "Normal"), icono(humo ? "crit" : "ok", "Aspiración, NFPA 72")),
      el("div", { clase: "tarjeta" }, dato("Supresión por agente limpio", a.alarma.supresion), icono(a.alarma.supresion === "descargada" ? "crit" : a.alarma.supresion === "abortada" ? "adv" : "ok", "NFPA 2001"))),
    el("div", { clase: "tarjeta seccion" }, el("header", {}, el("h2", { texto: "Temperatura de entrada de aire por rack" }), el("div", { clase: "espacio" }),
      el("span", { clase: "sec", texto: "ASHRAE TC 9.9, clase A1" })), G.cajaTemp,
      leyenda([["s1", "T-RACK-A"], ["s2", "T-RACK-B"], ["lim-crit", `Máximo permisible ${a.umbrales.max_permisible} °C`],
               ["lim-adv", `Máximo recomendado ${a.umbrales.max_recomendada} °C`], ["lim-frio", `Mínimo recomendado ${a.umbrales.min_recomendada} °C`]])));
  asegurarTemp();
}

// ------------------------------------------------------------------ accesos
const MOTIVO_PUERTA = {
  latido: "Cerrada y supervisada", acceso_valido: "Abierta con acceso válido", forzada: "Forzada: sin acceso válido",
  cierre_automatico: "Cierre automático", tiempo_excedido: "Mantenida abierta", cierre_manual: "Cerrada",
};
const NIVEL_ACC = { autorizado: "ok", denegado: "adv", revocada: "crit", coaccion: "crit" };

export function renderAccesos() {
  const v = vaciar(document.getElementById("v-accesos"));
  const ac = E.estado.acceso;
  const puertas = Object.entries(ac.puertas);
  const lecturas = ac.recientes.map((r) => el("tr", { clase: r.resultado === "coaccion" || r.resultado === "revocada" ? "fila-crit" : "" },
    el("td", { clase: "num", texto: hora(r.ts) }), el("td", { texto: r.lectora }), el("td", { clase: "mono", texto: r.tarjeta }),
    el("td", { texto: r.titular }), el("td", {}, icono(NIVEL_ACC[r.resultado] || "neutro", r.resultado === "coaccion" ? "Coacción (alerta silenciosa)" : r.resultado))));
  const tarjetas = ac.tarjetas.map((t) => {
    const b = puede("administrar") && t.estado === "activa"
      ? el("button", { clase: "boton peligro", type: "button", texto: "Revocar", onclick: async () => {
        await api(`/api/admin/tarjetas/${encodeURIComponent(t.tarjeta)}/revocar`, { metodo: "POST" });
        t.estado = "revocada"; renderAccesos();
      } }) : null;
    return el("tr", {}, el("td", { clase: "mono", texto: t.tarjeta }), el("td", { texto: t.titular }),
      el("td", {}, icono(t.estado === "activa" ? "ok" : "crit", t.estado)), el("td", { texto: t.zonas }), el("td", {}, b));
  });
  v.append(
    el("div", { clase: "rejilla r-4" }, puertas.length ? puertas.map(([l, p]) => el("div", { clase: "tarjeta" },
      dato(`Puerta ${l}`, p.estado.replace(/_/g, " ")), icono(p.estado === "cerrada" ? "ok" : p.motivo === "forzada" || p.estado === "mantenida_abierta" ? "crit" : "adv", MOTIVO_PUERTA[p.motivo] || p.motivo || "")))
      : el("div", { clase: "tarjeta" }, dato("Puerta LECT-01", "sin datos"))),
    el("div", { clase: "rejilla r-2 seccion" },
      el("div", { clase: "tarjeta" }, el("header", {}, el("h2", { texto: "Lecturas recientes: tarjeta + PIN" })),
        el("div", { clase: "tabla-contenedor" }, el("table", {}, el("thead", {}, el("tr", {}, ["Hora", "Lectora", "Tarjeta", "Titular", "Resultado"].map((c) => el("th", { texto: c })))),
          el("tbody", {}, lecturas.length ? lecturas : el("tr", {}, el("td", { colspan: 5, texto: "Sin lecturas" })))))),
      el("div", { clase: "tarjeta" }, el("header", {}, el("h2", { texto: "Credenciales físicas" })),
        el("p", { clase: "sec", texto: "Revocar una tarjeta aplica de inmediato; su uso posterior genera una alerta crítica (ISO/IEC 27001 5.18)." }),
        el("div", { clase: "tabla-contenedor" }, el("table", {}, el("thead", {}, el("tr", {}, ["Tarjeta", "Titular", "Estado", "Zonas", ""].map((c) => el("th", { texto: c })))),
          el("tbody", {}, tarjetas))))));
}
