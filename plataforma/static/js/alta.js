import { crudo } from "./comun.js";
import * as webauthn from "./webauthn.js";

const $ = (id) => document.getElementById(id);
const error = (t) => { $("error").textContent = t || ""; };

if (!webauthn.soportado()) {
  error("Este navegador o esta dirección no permiten passkeys. Abra la plataforma por HTTPS con su nombre de host.");
}

$("f-alta").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  error("");
  if ($("password").value !== $("password2").value) {
    error("Las contraseñas no coinciden");
    return;
  }
  try {
    await crudo("/api/auth/alta", {
      metodo: "POST",
      cuerpo: { usuario: $("usuario").value, codigo: $("codigo").value, password: $("password").value },
    });
    $("password").value = $("password2").value = "";
    $("f-alta").classList.add("oculto");
    $("f-passkey").classList.remove("oculto");
    $("p1").classList.remove("activo");
    $("p2").classList.add("activo");
  } catch (e) {
    error(e.message);
  }
});

$("f-passkey").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  error("");
  try {
    const opciones = await crudo("/api/auth/passkey/registro/opciones", { metodo: "POST" });
    const credencial = await webauthn.crear(opciones);
    await crudo("/api/auth/passkey/registro/verificar", { metodo: "POST", cuerpo: { credencial, nombre: $("nombre").value } });
    location.href = "/app";
  } catch (e) {
    error(webauthn.mensajeError(e));
  }
});
