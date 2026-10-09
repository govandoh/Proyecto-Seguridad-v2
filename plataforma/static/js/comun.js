// Utilidades compartidas: cliente de la API, construcción segura del DOM e iconos de estado.
// Todo el texto que viene del servidor se inserta con textContent, nunca como HTML (hallazgo V1).
import * as webauthn from "./webauthn.js";

export class ErrorApi extends Error {
  constructor(estado, detalle) {
    super(typeof detalle === "string" ? detalle : (detalle && detalle.mensaje) || `Error ${estado}`);
    this.estado = estado;
    this.detalle = detalle;
  }
}

async function crudo(ruta, { metodo = "GET", cuerpo, fondo = false } = {}) {
  const r = await fetch(ruta, {
    method: metodo,
    credentials: "same-origin",
    headers: { "X-Plataforma": "1", ...(fondo ? { "X-Fondo": "1" } : {}), ...(cuerpo !== undefined ? { "Content-Type": "application/json" } : {}) },
    body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
  });
  const tipo = r.headers.get("content-type") || "";
  const datos = tipo.includes("application/json") ? await r.json() : null;
  if (!r.ok) throw new ErrorApi(r.status, datos && datos.detail);
  return datos;
}

export async function reautenticar() {
  const opciones = await crudo("/api/auth/passkey/login/opciones", { metodo: "POST" });
  const credencial = await webauthn.obtener(opciones);
  await crudo("/api/auth/passkey/login/verificar", { metodo: "POST", cuerpo: { credencial } });
}

// Llama a la API; si el servidor pide reautenticación, firma un desafío y reintenta una vez.
export async function api(ruta, opciones = {}) {
  try {
    return await crudo(ruta, opciones);
  } catch (e) {
    if (e.estado === 401 && e.detalle && e.detalle.reauth && !opciones._reintento) {
      await reautenticar();
      return api(ruta, { ...opciones, _reintento: true });
    }
    if (e.estado === 401 && !(e.detalle && e.detalle.reauth)) {
      location.href = "/login";
    }
    throw e;
  }
}

export { crudo };

export function el(etiqueta, atributos = {}, ...hijos) {
  const n = document.createElement(etiqueta);
  for (const [k, v] of Object.entries(atributos || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "clase") n.className = v;
    else if (k === "texto") n.textContent = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const h of hijos.flat()) {
    if (h === null || h === undefined || h === false) continue;
    n.append(h instanceof Node ? h : document.createTextNode(String(h)));
  }
  return n;
}

export function vaciar(n) {
  while (n.firstChild) n.removeChild(n.firstChild);
  return n;
}

const NS = "http://www.w3.org/2000/svg";
export function svg(etiqueta, atributos = {}, ...hijos) {
  const n = document.createElementNS(NS, etiqueta);
  for (const [k, v] of Object.entries(atributos)) {
    if (k === "clase") n.setAttribute("class", v);
    else if (k === "texto") n.textContent = v;
    else n.setAttribute(k, v);
  }
  for (const h of hijos.flat()) if (h) n.append(h);
  return n;
}

// Iconos de estado: la forma distingue el estado además del color.
const ICONOS = {
  ok: "M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13Zm3.1 4.6-3.8 4.6a.75.75 0 0 1-1.1.05L4.3 8.9a.75.75 0 1 1 1.06-1.06l1.3 1.3 3.3-4a.75.75 0 1 1 1.14.96Z",
  adv: "M8.9 1.9a1 1 0 0 0-1.8 0L1.2 12.6A1 1 0 0 0 2.1 14h11.8a1 1 0 0 0 .9-1.4L8.9 1.9ZM8 5a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 8 5Zm0 7.25a.9.9 0 1 1 0-1.8.9.9 0 0 1 0 1.8Z",
  crit: "M5.2 1h5.6L15 5.2v5.6L10.8 15H5.2L1 10.8V5.2L5.2 1Zm.9 4.1a.75.75 0 0 0-1 1L6.9 8l-1.8 1.9a.75.75 0 1 0 1 1L8 9.1l1.9 1.8a.75.75 0 0 0 1-1L9.1 8l1.8-1.9a.75.75 0 0 0-1-1L8 6.9 6.1 5.1Z",
  neutro: "M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM5 7.25h6a.75.75 0 0 1 0 1.5H5a.75.75 0 0 1 0-1.5Z",
};

export function estado(nivel, etiqueta) {
  const n = ICONOS[nivel] ? nivel : "neutro";
  const icono = svg("svg", { viewBox: "0 0 16 16", "aria-hidden": "true" }, svg("path", { d: ICONOS[n], fill: "currentColor" }));
  return el("span", { clase: `estado ${n}` }, icono, etiqueta);
}

export const NIVEL_SEVERIDAD = { critico: "crit", advertencia: "adv", informativo: "neutro" };

export function hora(ts) {
  if (!ts) return "";
  const d = typeof ts === "number" ? new Date(ts * 1000) : new Date(ts);
  return d.toLocaleTimeString("es-GT", { hour12: false });
}

export function fechaHora(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  return `${d.toLocaleDateString("es-GT")} ${d.toLocaleTimeString("es-GT", { hour12: false })}`;
}

export function aviso(texto, nivel = "") {
  let caja = document.querySelector(".toast");
  if (!caja) {
    caja = el("div", { clase: "toast", role: "status", "aria-live": "polite" });
    document.body.append(caja);
  }
  const m = el("div", { clase: nivel, texto });
  caja.prepend(m);
  setTimeout(() => m.remove(), 7000);
  while (caja.children.length > 4) caja.lastChild.remove();
}
