// Conversión entre las opciones JSON del servidor (py_webauthn) y la API del navegador.
const b64u = {
  aBuffer(s) {
    const b = s.replace(/-/g, "+").replace(/_/g, "/");
    const bin = atob(b + "===".slice((b.length + 3) % 4));
    return Uint8Array.from(bin, (c) => c.charCodeAt(0)).buffer;
  },
  deBuffer(buf) {
    const bytes = new Uint8Array(buf);
    let bin = "";
    for (const x of bytes) bin += String.fromCharCode(x);
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  },
};

export function soportado() {
  return !!(window.PublicKeyCredential && navigator.credentials && window.isSecureContext);
}

function serializar(cred) {
  const r = cred.response;
  const salida = {
    id: cred.id,
    rawId: b64u.deBuffer(cred.rawId),
    type: cred.type,
    authenticatorAttachment: cred.authenticatorAttachment || null,
    clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
    response: { clientDataJSON: b64u.deBuffer(r.clientDataJSON) },
  };
  if (r.attestationObject) {
    salida.response.attestationObject = b64u.deBuffer(r.attestationObject);
    salida.response.transports = r.getTransports ? r.getTransports() : [];
  }
  if (r.authenticatorData) {
    salida.response.authenticatorData = b64u.deBuffer(r.authenticatorData);
    salida.response.signature = b64u.deBuffer(r.signature);
    if (r.userHandle) salida.response.userHandle = b64u.deBuffer(r.userHandle);
  }
  return salida;
}

export async function crear(opciones) {
  const publicKey = {
    ...opciones,
    challenge: b64u.aBuffer(opciones.challenge),
    user: { ...opciones.user, id: b64u.aBuffer(opciones.user.id) },
    excludeCredentials: (opciones.excludeCredentials || []).map((c) => ({ ...c, id: b64u.aBuffer(c.id) })),
  };
  const cred = await navigator.credentials.create({ publicKey });
  return serializar(cred);
}

export async function obtener(opciones) {
  const publicKey = {
    ...opciones,
    challenge: b64u.aBuffer(opciones.challenge),
    allowCredentials: (opciones.allowCredentials || []).map((c) => ({ ...c, id: b64u.aBuffer(c.id) })),
  };
  const cred = await navigator.credentials.get({ publicKey });
  return serializar(cred);
}

export function mensajeError(e) {
  if (!e) return "Error desconocido";
  if (e.name === "NotAllowedError") return "La operación se canceló o expiró. Intente de nuevo y confirme en su dispositivo.";
  if (e.name === "InvalidStateError") return "Este autenticador ya está registrado para su cuenta.";
  if (e.name === "SecurityError") return "El navegador rechazó el dominio: abra la plataforma por su nombre de host con HTTPS.";
  return e.message || String(e);
}
