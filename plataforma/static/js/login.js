import { crudo } from "./comun.js";
import * as webauthn from "./webauthn.js";

const $ = (id) => document.getElementById(id);
const error = (t) => { $("error").textContent = t || ""; };

if (!webauthn.soportado()) {
  error("Este navegador o esta dirección no permiten passkeys. Abra la plataforma por HTTPS con su nombre de host.");
}

$("f-pass").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  error("");
  try {
    await crudo("/api/auth/login", { metodo: "POST", cuerpo: { usuario: $("usuario").value, password: $("password").value } });
    $("password").value = "";
    $("f-pass").classList.add("oculto");
    $("paso-passkey").classList.remove("oculto");
    $("p1").classList.remove("activo");
    $("p2").classList.add("activo");
    await verificar();
  } catch (e) {
    error(e.message);
  }
});

$("f-passkey").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  await verificar();
});

async function verificar() {
  error("");
  try {
    const opciones = await crudo("/api/auth/passkey/login/opciones", { metodo: "POST" });
    const credencial = await webauthn.obtener(opciones);
    await crudo("/api/auth/passkey/login/verificar", { metodo: "POST", cuerpo: { credencial } });
    location.href = "/app";
  } catch (e) {
    if (e.estado === 401 && /desafío|contraseña/i.test(e.message)) {
      location.reload();
      return;
    }
    error(webauthn.mensajeError(e));
  }
}
