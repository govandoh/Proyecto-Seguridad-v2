// Tablero principal: estado compartido, WebSocket, pestañas, resumen, bitácora e indicadores.
import { api, aviso, el, estado as icono, fechaHora, hora, NIVEL_SEVERIDAD, vaciar } from "./comun.js";
import * as dc from "./vistas-dc.js";
import * as control from "./vistas-control.js";

const PERMISOS = {
  acusar: ["operador", "administrador"],
  simular: ["operador", "administrador"],
  auditar: ["auditor", "administrador"],
  administrar: ["administrador"],
};

export const E = {
  yo: null,
  estado: null,
  eventos: [],
  pendientes: [],
  tab: "resumen",
  filtro: { modulo: "", severidad: "" },
  verificacion: null,
  ultimaActividad: Date.now(),
};

export const puede = (accion) => !!E.yo && PERMISOS[accion].includes(E.yo.rol);

// ------------------------------------------------------------------ arranque
async function iniciar() {
  E.yo = await api("/api/auth/yo");
  document.getElementById("chip-usuario").textContent = `${E.yo.nombre} · ${E.yo.rol}`;
  document.querySelectorAll("[data-permiso]").forEach((b) => b.classList.toggle("oculto", !puede(b.dataset.permiso)));
  document.getElementById("salir").addEventListener("click", salir);
  document.querySelectorAll(".pestanas button").forEach((b) => b.addEventListener("click", () => mostrar(b.dataset.tab)));
  ["click", "keydown"].forEach((ev) => document.addEventListener(ev, () => { E.ultimaActividad = Date.now(); }));
  setInterval(vigilarInactividad, 30000);

  await recargarEstado();
  E.eventos = await api("/api/eventos?limite=300");
  dc.iniciarGraficas();
  await dc.cargarHistoriales();
  const inicial = (location.hash || "#resumen").slice(1);
  mostrar(document.getElementById(`v-${inicial}`) ? inicial : "resumen");
  conectarWS();
  setInterval(() => recargarEstado(true).catch(() => {}), 20000);
}

export async function recargarEstado(fondo = false) {
  E.estado = await api("/api/estado", { fondo });
  E.pendientes = E.estado.pendientes;
  document.getElementById("chip-modo").textContent = modoRed();
  renderizar();
}

function modoRed() {
  const c = E.estado && E.estado.red.captura;
  if (!c || c.edad_s === null) return "Red: sin capturador";
  if (c.error) return `Red: error en ${c.iface}`;
  if (c.modo === "demo") return "Red: DEMO generada";
  return `Red: captura real ${c.iface}`;
}

async function salir() {
  try { await api("/api/auth/logout", { metodo: "POST" }); } finally { location.href = "/login"; }
}

function vigilarInactividad() {
  const limite = (E.yo.inactividad_min || 15) * 60 * 1000;
  if (Date.now() - E.ultimaActividad > limite) {
    aviso("Sesión cerrada por inactividad", "adv");
    salir();
  }
}

// ------------------------------------------------------------------ pestañas
export function mostrar(tab) {
  E.tab = tab;
  history.replaceState(null, "", `#${tab}`);
  document.querySelectorAll(".pestanas button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
  document.querySelectorAll("main > section").forEach((s) => s.classList.toggle("oculto", s.id !== `v-${tab}`));
  pintar();
  if (tab === "indicadores") renderIndicadores();
  if (tab === "admin") control.renderAdmin();
  if (tab === "simulacion") control.renderSimulacion();
}

// Los mensajes en vivo llegan varias veces por segundo; se agrupan en un repintado cada 700 ms.
let programado = null;
export function renderizar() {
  if (programado) return;
  programado = setTimeout(() => { programado = null; pintar(); }, 700);
}

function pintar() {
  if (!E.estado) return;
  const n = E.pendientes.length;
  document.getElementById("cnt-pend").textContent = n ? ` (${n})` : "";
  switch (E.tab) {
    case "resumen": renderResumen(); break;
    case "red": dc.renderRed(); break;
    case "energia": dc.renderEnergia(); break;
    case "ambiente": dc.renderAmbiente(); break;
    case "accesos": dc.renderAccesos(); break;
    case "bitacora": renderBitacora(); break;
    default: break;
  }
}

// ------------------------------------------------------------------ WebSocket
let reintentos = 0;
function conectarWS() {
  const chip = document.getElementById("chip-ws");
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  let latido;
  ws.onopen = () => {
    reintentos = 0;
    chip.textContent = "En vivo";
    sincronizarEventos();
    latido = setInterval(() => ws.readyState === 1 && ws.send("latido"), 20000);
  };
  ws.onclose = (ev) => {
    clearInterval(latido);
    chip.textContent = "Reconectando…";
    if (ev.code === 4401) { location.href = "/login"; return; }
    setTimeout(conectarWS, Math.min(10000, 1000 * 2 ** reintentos++));
  };
  ws.onmessage = (m) => {
    let msg;
    try { msg = JSON.parse(m.data); } catch { return; }
    recibir(msg.tipo, msg.datos);
  };
}

// Recupera los eventos ocurridos entre la carga inicial (o una reconexión) y la apertura del WebSocket.
async function sincronizarEventos() {
  const ultimo = E.eventos.length ? E.eventos[0].id : 0;
  try {
    const nuevos = await api(`/api/eventos?limite=500&desde_id=${ultimo}`, { fondo: true });
    const vistos = new Set(E.eventos.map((e) => e.id));
    for (const e of nuevos.reverse()) if (!vistos.has(e.id)) E.eventos.unshift(e);
    E.eventos.sort((a, b) => b.id - a.id);
    await recargarEstado(true);
  } catch { /* se reintenta en la siguiente reconexión */ }
}

function recibir(tipo, d) {
  const est = E.estado;
  if (!est) return;
  switch (tipo) {
    case "evento":
      if (E.eventos.length && E.eventos[0].id >= d.id) break;
      E.eventos.unshift(d);
      if (E.eventos.length > 1000) E.eventos.pop();
      if (d.tipo === "acuse") E.pendientes = E.pendientes.filter((p) => p.id !== d.ref_id);
      else if (d.severidad === "critico") {
        E.pendientes.unshift(d);
        aviso(`${d.descripcion}`, "crit");
      }
      break;
    case "red": est.red = d; document.getElementById("chip-modo").textContent = modoRed(); break;
    case "energia": est.energia = d; dc.agregarEnergia(d); break;
    case "ambiente_lectura": {
      const s = est.ambiente.sensores.find((x) => x.sensor === d.sensor);
      if (s) Object.assign(s, { temp_c: d.temp_c, estado: d.estado, humedad: d.humedad, edad_s: 0 });
      else est.ambiente.sensores.push({ sensor: d.sensor, temp_c: d.temp_c, estado: d.estado, humedad: d.humedad, edad_s: 0 });
      dc.agregarTemperatura(d);
      break;
    }
    case "ambiente_alarma": est.ambiente.alarma = d; break;
    case "acceso_lectura": est.acceso.recientes.unshift(d); est.acceso.recientes.length = Math.min(20, est.acceso.recientes.length); break;
    case "acceso_puerta": est.acceso.puertas[d.lectora] = { estado: d.estado, motivo: d.motivo, ts: Date.now() / 1000 }; break;
    default: return;
  }
  renderizar();
}

// ------------------------------------------------------------------ alertas y procedimientos
export async function abrirAlerta(evento) {
  const proc = await api(`/api/procedimientos/${encodeURIComponent(evento.tipo)}`);
  const nota = el("input", { type: "text", maxlength: "300", placeholder: "Nota del operador (opcional)" });
  const velo = el("div", { clase: "velo", role: "dialog", "aria-modal": "true" });
  const cerrar = () => velo.remove();
  const acusar = el("button", { clase: "boton primario", type: "button", texto: "Registrar acuse" });
  acusar.addEventListener("click", async () => {
    acusar.disabled = true;
    try {
      await api(`/api/eventos/${evento.id}/acuse`, { metodo: "POST", cuerpo: { nota: nota.value } });
      aviso("Acuse registrado en la bitácora");
      cerrar();
    } catch (e) { aviso(e.message, "crit"); acusar.disabled = false; }
  });
  velo.append(el("div", { clase: "modal" },
    el("h2", { texto: proc.titulo }),
    icono("crit", evento.descripcion),
    el("div", { clase: "sec", texto: `#${evento.id} · ${fechaHora(evento.ts)} · control ${evento.control_iso || "-"} · ${evento.norma || proc.norma}` }),
    el("h3", { clase: "seccion", texto: `Procedimiento de respuesta (${proc.norma})` }),
    el("ol", {}, proc.pasos.map((p) => el("li", { texto: p }))),
    puede("acusar") ? el("div", { clase: "campo" }, el("label", { texto: "Nota del acuse" }), nota) : el("div", { clase: "aviso", texto: "Su rol puede consultar el procedimiento, pero no registrar el acuse." }),
    el("footer", {}, el("button", { clase: "boton", type: "button", texto: "Cerrar", onclick: cerrar }), puede("acusar") ? acusar : null),
  ));
  velo.addEventListener("click", (ev) => { if (ev.target === velo) cerrar(); });
  document.body.append(velo);
}

function listaAlertas() {
  if (!E.pendientes.length) return el("div", {}, icono("ok", "Sin alertas críticas pendientes de acuse"));
  return el("div", { clase: "alertas" }, E.pendientes.slice(0, 8).map((p) =>
    el("div", { clase: "alerta" },
      icono("crit", ""),
      el("div", { clase: "texto" }, el("div", { texto: p.descripcion }),
        el("div", { texto: `${hora(p.ts)} · ${p.modulo} · ${p.norma || ""}` })),
      el("button", { clase: "boton", type: "button", texto: "Atender", onclick: () => abrirAlerta(p) }))));
}

// ------------------------------------------------------------------ resumen
function mosaico(tab, titulo, nivel, etiqueta, valor, detalle) {
  return el("div", { clase: "tarjeta mosaico", role: "button", tabindex: "0", onclick: () => mostrar(tab),
                     onkeydown: (ev) => ev.key === "Enter" && mostrar(tab) },
    el("div", { clase: "titulo", texto: titulo }), icono(nivel, etiqueta),
    el("div", { clase: "valor num", texto: valor }), el("div", { clase: "detalle", texto: detalle }));
}

function renderResumen() {
  const v = vaciar(document.getElementById("v-resumen"));
  const { red, energia, ambiente, acceso } = E.estado;

  const aut = dc.porEquipo(red.equipos.filter((e) => e.autorizado));
  const enLinea = aut.filter((e) => e.estado === "en_linea").length;
  const intrusos = red.equipos.filter((e) => !e.autorizado && e.estado === "en_linea").length;
  const caidos = aut.filter((e) => e.estado === "caido").length;
  const nRed = red.visibilidad_perdida || intrusos || !red.captura.activa ? "crit" : caidos ? "adv" : "ok";
  const tRed = red.visibilidad_perdida ? "Sin visibilidad" : !red.captura.activa ? "Capturador detenido" : intrusos ? `${intrusos} no autorizado(s)` : caidos ? `${caidos} caído(s)` : "Normal";

  const fsm = energia.estado;
  const nEn = { NORMAL: "ok", TRANSFERENCIA_GENERADOR: "adv", UPS_EN_BATERIA: "adv", CORTE_DETECTADO: "crit", BATERIA_BAJA: "crit", APAGADO_CONTROLADO: "crit" }[fsm] || "neutro";
  const rt = energia.telemetria && energia.telemetria["battery.runtime"];

  const sens = ambiente.sensores;
  const peor = sens.reduce((a, s) => ((s.temp_c || 0) > (a ? a.temp_c : -99) ? s : a), null);
  const hayMudo = sens.some((s) => s.estado === "mudo");
  const nAmb = ambiente.alarma.humo === "activa" || sens.some((s) => s.estado === "critico") ? "crit" : sens.some((s) => ["advertencia", "frio"].includes(s.estado)) || hayMudo ? "adv" : "ok";
  const tAmb = ambiente.alarma.humo === "activa" ? "Alarma de humo" : { crit: "Temperatura crítica", adv: hayMudo ? "Sensor mudo" : "Fuera de rango", ok: "En rango" }[nAmb];

  const puerta = acceso.puertas["LECT-01"] || { estado: "sin datos" };
  const ult = acceso.recientes[0];
  const nAcc = ["abierta", "mantenida_abierta"].includes(puerta.estado) ? "adv" : "ok";

  v.append(
    el("div", { clase: "rejilla r-5" },
      mosaico("red", "Red", nRed, tRed, `${enLinea}/${aut.length}`, "equipos autorizados en línea"),
      mosaico("energia", "Energía", nEn, fsm.replace(/_/g, " "), rt !== undefined ? `${(rt / 60).toFixed(1)} min` : "-",
              `autonomía; diseño ${energia.diseno.autonomia_min} min`),
      mosaico("ambiente", "Ambiente", nAmb, tAmb, peor ? `${peor.temp_c.toFixed(1)} °C` : "-", peor ? `máxima, ${peor.sensor}` : "sin sensores"),
      mosaico("accesos", "Acceso físico", nAcc, `Puerta ${puerta.estado.replace(/_/g, " ")}`, String(acceso.recientes.length),
              ult ? `último: ${ult.titular} (${ult.resultado})` : "sin lecturas"),
      mosaico("bitacora", "Alertas", E.pendientes.length ? "crit" : "ok", E.pendientes.length ? "Pendientes de acuse" : "Sin pendientes",
              String(E.pendientes.length), "críticas sin acuse"),
    ),
    el("div", { clase: "rejilla r-2 seccion" },
      el("div", { clase: "tarjeta" }, el("header", {}, el("h2", { texto: "Alertas críticas pendientes" })), listaAlertas()),
      el("div", { clase: "tarjeta" }, el("header", {}, el("h2", { texto: "Últimos eventos" })), tablaEventos(E.eventos.slice(0, 12), true)),
    ),
  );
}

// ------------------------------------------------------------------ bitácora
export function tablaEventos(lista, compacta = false) {
  const cab = compacta ? ["Hora", "Severidad", "Descripción"] : ["#", "Fecha y hora", "Módulo", "Tipo", "Severidad", "Descripción", "Control", "Norma", "Actor", "Hash"];
  const filas = lista.map((e) => {
    const nivel = NIVEL_SEVERIDAD[e.severidad] || "neutro";
    const clase = e.severidad === "critico" ? "fila-crit" : "";
    const sev = icono(nivel, e.severidad);
    if (compacta) return el("tr", { clase }, el("td", { clase: "num", texto: hora(e.ts) }), el("td", {}, sev), el("td", { texto: e.descripcion }));
    return el("tr", { clase },
      el("td", { clase: "num", texto: e.id }), el("td", { clase: "num", texto: fechaHora(e.ts) }), el("td", { texto: e.modulo }),
      el("td", { clase: "mono", texto: e.tipo }), el("td", {}, sev), el("td", { texto: e.descripcion }),
      el("td", { texto: e.control_iso }), el("td", { texto: e.norma }), el("td", { clase: "mono", texto: e.actor }),
      el("td", { clase: "mono tenue", title: e.hash, texto: `${e.hash.slice(0, 10)}…` }));
  });
  return el("div", { clase: "tabla-contenedor" }, el("table", {}, el("thead", {}, el("tr", {}, cab.map((c) => el("th", { texto: c })))),
    el("tbody", {}, filas.length ? filas : el("tr", {}, el("td", { colspan: cab.length, texto: "Sin eventos" })))));
}

function renderBitacora() {
  const v = vaciar(document.getElementById("v-bitacora"));
  const modulos = ["", "red", "energia", "ambiente", "acceso", "auth", "bitacora", "simulacion", "sistema"];
  const sevs = ["", "critico", "advertencia", "informativo"];
  const selMod = el("select", { "aria-label": "Módulo" }, modulos.map((m) => el("option", { value: m, texto: m || "Todos los módulos" })));
  const selSev = el("select", { "aria-label": "Severidad" }, sevs.map((m) => el("option", { value: m, texto: m || "Todas las severidades" })));
  selMod.value = E.filtro.modulo;
  selSev.value = E.filtro.severidad;
  const alCambiar = () => { E.filtro = { modulo: selMod.value, severidad: selSev.value }; renderBitacora(); };
  selMod.addEventListener("change", alCambiar);
  selSev.addEventListener("change", alCambiar);
  const r = E.verificacion;
  const resultado = el("span", { clase: "sec" }, r ? (r.integra
    ? icono("ok", `Íntegra: ${r.total} eventos encadenados (${hora(r.cuando)})`)
    : icono("crit", `Rota en el evento #${r.primer_error_id} (${hora(r.cuando)})`)) : null);
  const verificar = el("button", { clase: "boton", type: "button", texto: "Verificar cadena de hash" });
  verificar.addEventListener("click", async () => {
    E.verificacion = { ...(await api("/api/bitacora/verificar")), cuando: new Date().toISOString() };
    renderBitacora();
  });
  const exportar = puede("auditar") ? el("a", { clase: "boton", href: "/api/bitacora/exportar.csv", texto: "Exportar CSV" }) : null;
  const lista = E.eventos.filter((e) => (!E.filtro.modulo || e.modulo === E.filtro.modulo) && (!E.filtro.severidad || e.severidad === E.filtro.severidad));
  v.append(el("div", { clase: "tarjeta" },
    el("header", {}, el("h2", { texto: "Bitácora auditable" }), el("div", { clase: "espacio" }), resultado),
    el("div", { clase: "formulario" }, selMod, selSev, verificar, exportar),
    el("p", { clase: "sec", texto: "Solo inserción. Cada evento guarda el hash del anterior; un acuse es un evento nuevo que referencia a la alerta (ISO/IEC 27001 8.15)." }),
    tablaEventos(lista.slice(0, 300))));
}

// ------------------------------------------------------------------ indicadores
async function renderIndicadores() {
  const v = vaciar(document.getElementById("v-indicadores"));
  const datos = await api("/api/indicadores");
  const filas = datos.map((k) => el("tr", {},
    el("td", { texto: k.nombre }),
    el("td", { clase: "num", texto: k.valor === null || k.valor === undefined ? "sin datos" : `${k.valor} ${k.unidad}` }),
    el("td", { texto: k.meta }),
    el("td", {}, k.cumple === null || k.cumple === undefined ? icono("neutro", "sin evaluar") : k.cumple ? icono("ok", "Cumple") : icono("crit", "No cumple")),
    el("td", { clase: "sec", texto: [k.muestras !== null && k.muestras !== undefined ? `${k.muestras} muestras` : "", k.extra || ""].filter(Boolean).join(" · ") })));
  v.append(el("div", { clase: "tarjeta" },
    el("header", {}, el("h2", { texto: "Indicadores de verificación" }), el("div", { clase: "espacio" }),
      el("button", { clase: "boton", type: "button", texto: "Recalcular", onclick: renderIndicadores })),
    el("p", { clase: "sec", texto: "Calculados sobre la bitácora, no sobre declaraciones (Tabla 22 del Entregable 2)." }),
    el("div", { clase: "tabla-contenedor" }, el("table", {},
      el("thead", {}, el("tr", {}, ["Indicador", "Valor", "Meta", "Resultado", "Base"].map((c) => el("th", { texto: c })))),
      el("tbody", {}, filas)))));
}

iniciar().catch((e) => {
  if (e && e.estado === 401) location.href = "/login";
  else aviso(`No se pudo cargar el tablero: ${e.message}`, "crit");
});
