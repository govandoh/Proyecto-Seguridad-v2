// Convierte un manual en Markdown (docs/MANUAL_SIMULACIONES*.md) en un documento Word con portada,
// índice y estilos. Requiere Node y el paquete docx 9 (npm install docx@9 en esta carpeta).
// Uso: node generar_manual.js <entrada.md> <salida.docx>
// Portada: variables SUBTITULO y VERSION. El PDF y el índice se actualizan abriendo el .docx en
// Word (Referencias > Actualizar tabla) y guardando como PDF.
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType,
  ShadingType, BorderStyle, AlignmentType, LevelFormat, Header, Footer, PageNumber,
  TableOfContents, PageBreak, TabStopType,
} = require("docx");

const [entrada, salida] = process.argv.slice(2);
const md = fs.readFileSync(entrada, "utf8").replace(/\r\n/g, "\n");

const AZUL = "1F3864", AZUL_CLARO = "D9E2F3", GRIS = "F2F2F2", BORDE = "A6A6A6";
const FUENTE = "Calibri", MONO = "Consolas";
const ANCHO = 12240 - 2 * 1080; // carta con márgenes de 0.75"

// ------------------------------------------------------------------ texto en línea
function runs(texto, base = {}) {
  const salida = [];
  // **negrita**, `código`, *cursiva*
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;
  let i = 0, m;
  while ((m = re.exec(texto))) {
    if (m.index > i) salida.push(new TextRun({ text: texto.slice(i, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("**")) salida.push(...runs(t.slice(2, -2), { ...base, bold: true }));
    else if (t.startsWith("`")) salida.push(new TextRun({ text: t.slice(1, -1), ...base, font: MONO, size: (base.size || 21) - 2, color: "7B2C2C" }));
    else salida.push(new TextRun({ text: t.slice(1, -1), ...base, italics: true }));
    i = m.index + t.length;
  }
  if (i < texto.length) salida.push(new TextRun({ text: texto.slice(i), ...base }));
  return salida;
}

// ------------------------------------------------------------------ tablas
const borde = { style: BorderStyle.SINGLE, size: 4, color: BORDE };
const bordes = { top: borde, bottom: borde, left: borde, right: borde };

function celdas(linea) {
  // Divide por | fuera de `código`
  const s = linea.trim().replace(/^\|/, "").replace(/\|$/, "");
  const out = []; let actual = "", enCodigo = false;
  for (const ch of s) {
    if (ch === "`") enCodigo = !enCodigo;
    if (ch === "|" && !enCodigo) { out.push(actual.trim()); actual = ""; } else actual += ch;
  }
  out.push(actual.trim());
  return out;
}

function anchos(filas) {
  const n = filas[0].length;
  const largo = Array.from({ length: n }, (_, c) =>
    Math.max(...filas.map((f) => (f[c] || "").replace(/[`*]/g, "").length)));
  const peso = largo.map((l) => Math.min(Math.max(l, 6), 70));
  const total = peso.reduce((a, b) => a + b, 0);
  const w = peso.map((p) => Math.floor((p / total) * ANCHO));
  w[w.length - 1] += ANCHO - w.reduce((a, b) => a + b, 0);
  return w;
}

function tabla(lineas) {
  const filas = lineas.filter((l, i) => i !== 1).map(celdas);
  const n = filas[0].length;
  filas.forEach((f) => { while (f.length < n) f.push(""); });
  // Tablas de "clave | valor" con encabezado vacío (| | |): sin fila de encabezado
  const sinEncabezado = filas[0].every((c) => c === "");
  const w = sinEncabezado && n === 2 ? [2400, ANCHO - 2400] : anchos(sinEncabezado ? filas.slice(1) : filas);
  const rows = (sinEncabezado ? filas.slice(1) : filas).map((f, r) => new TableRow({
    tableHeader: !sinEncabezado && r === 0,
    cantSplit: true,
    children: f.map((c, k) => new TableCell({
      width: { size: w[k], type: WidthType.DXA },
      borders: bordes,
      margins: { top: 60, bottom: 60, left: 100, right: 100 },
      shading: !sinEncabezado && r === 0 ? { type: ShadingType.CLEAR, fill: AZUL, color: "auto" }
        : sinEncabezado && k === 0 ? { type: ShadingType.CLEAR, fill: GRIS, color: "auto" }
        : r % 2 === 0 ? { type: ShadingType.CLEAR, fill: "F7F9FC", color: "auto" } : undefined,
      children: [new Paragraph({
        spacing: { before: 0, after: 0 },
        children: runs(c, !sinEncabezado && r === 0 ? { bold: true, color: "FFFFFF", size: 19 }
          : { size: 19, bold: sinEncabezado && k === 0 ? true : undefined }),
      })],
    })),
  }));
  return [new Table({ width: { size: ANCHO, type: WidthType.DXA }, columnWidths: w, rows }),
    new Paragraph({ spacing: { after: 80 }, children: [] })];
}

// ------------------------------------------------------------------ bloques
function codigo(lineas) {
  return lineas.map((l, i) => new Paragraph({
    shading: { type: ShadingType.CLEAR, fill: GRIS, color: "auto" },
    spacing: { before: i === 0 ? 80 : 0, after: i === lineas.length - 1 ? 160 : 0, line: 240 },
    indent: { left: 200, right: 200 },
    children: [new TextRun({ text: l.length ? l : " ", font: MONO, size: 17 })],
  }));
}

function convertir(texto) {
  const lineas = texto.split("\n");
  const out = [];
  let i = 0, parrafo = [];
  const volcar = () => {
    if (parrafo.length) { out.push(new Paragraph({ spacing: { after: 120 }, children: runs(parrafo.join(" ")) })); parrafo = []; }
  };
  while (i < lineas.length) {
    const l = lineas[i];
    if (/^```/.test(l)) {
      volcar(); const blq = []; i++;
      while (i < lineas.length && !/^```/.test(lineas[i])) blq.push(lineas[i++]);
      i++; out.push(...codigo(blq)); continue;
    }
    if (/^\|/.test(l)) {
      volcar(); const blq = [];
      while (i < lineas.length && /^\|/.test(lineas[i])) blq.push(lineas[i++]);
      out.push(...tabla(blq)); continue;
    }
    const h = /^(#{2,4}) (.*)$/.exec(l);
    if (h) {
      volcar();
      const nivel = { 2: HeadingLevel.HEADING_1, 3: HeadingLevel.HEADING_2, 4: HeadingLevel.HEADING_3 }[h[1].length];
      out.push(new Paragraph({ heading: nivel, keepNext: true, children: runs(h[2]) }));
      i++; continue;
    }
    const num = /^(\d+)\. (.*)$/.exec(l);
    const vin = /^- (.*)$/.exec(l);
    if (num || vin) {
      volcar();
      let txt = (num ? num[2] : vin[1]);
      i++;
      while (i < lineas.length && /^ {2,}\S/.test(lineas[i]) && !/^\s*```/.test(lineas[i])) txt += " " + lineas[i++].trim();
      out.push(new Paragraph({ numbering: { reference: num ? "numeros" : "vinetas", level: 0 }, spacing: { after: 60 }, children: runs(txt) }));
      // bloque de código sangrado dentro de un ítem
      if (i < lineas.length && /^\s+```/.test(lineas[i])) {
        const blq = []; i++;
        while (i < lineas.length && !/^\s*```/.test(lineas[i])) blq.push(lineas[i++].replace(/^ {3}/, ""));
        i++; out.push(...codigo(blq));
      }
      continue;
    }
    // Encabezado en negrita de escenario: **E1. ...**
    if (/^\*\*[^*]+\*\*$/.test(l.trim())) {
      volcar();
      out.push(new Paragraph({ keepNext: true, spacing: { before: 200, after: 80 },
        children: runs(l.trim().slice(2, -2), { bold: true, color: AZUL, size: 23 }) }));
      i++; continue;
    }
    if (!l.trim()) { volcar(); i++; continue; }
    parrafo.push(l.trim()); i++;
  }
  volcar();
  return out;
}

// El título y la línea institucional del Markdown pasan a la portada.
const cuerpo = md.split("\n").slice(4).join("\n");

const portada = [
  new Paragraph({ spacing: { before: 2400 }, children: [] }),
  new Paragraph({ alignment: AlignmentType.LEFT, border: { bottom: { style: BorderStyle.SINGLE, size: 18, color: AZUL, space: 8 } },
    children: [new TextRun({ text: "Manual de simulaciones y verificación normativa", bold: true, size: 52, color: AZUL })] }),
  new Paragraph({ spacing: { before: 240 }, children: [new TextRun({ text: "Plataforma de monitoreo y ciberresiliencia del datacenter del Operador Postal Designado", size: 28, color: "404040" })] }),
  new Paragraph({ spacing: { before: 120, after: 1600 }, children: [new TextRun({ text: process.env.SUBTITULO || "Documento para el equipo auditor · Ejecución local del laboratorio", italics: true, size: 26, color: "595959" })] }),
  ...[
    ["Curso", "Seguridad y Auditoría de Sistemas"],
    ["Institución", "Universidad Mariano Gálvez de Guatemala"],
    ["Autores", "Gerardo Antonio Ovando Hernández, Mario Andrés Culajay Roldán, Sergio Enrique Sánchez Sánchez"],
    ["Versión", process.env.VERSION || "1.0, ejecución local, octubre de 2026"],
    ["Marco normativo", "ISO/IEC 27001:2022, NFPA, IEEE, ASHRAE TC 9.9 y NIST"],
  ].map(([k, v]) => new Paragraph({ spacing: { after: 80 }, indent: { left: 2400, hanging: 2400 }, tabStops: [{ type: TabStopType.LEFT, position: 2400 }],
    children: [new TextRun({ text: k, bold: true, size: 22, color: AZUL }), new TextRun({ text: "\t" + v, size: 22 })] })),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: "Contenido", bold: true, size: 32, color: AZUL })] }),
  new TableOfContents("Contenido", { hyperlink: true, headingStyleRange: "1-2" }),
  new Paragraph({ children: [new PageBreak()] }),
];

const doc = new Document({
  creator: "Gerardo Ovando, Mario Culajay, Sergio Sánchez",
  title: "Manual de simulaciones y verificación normativa",
  description: "Plataforma DCIM del Operador Postal Designado. Documento para el equipo auditor.",
  styles: {
    default: { document: { run: { font: FUENTE, size: 21 }, paragraph: { spacing: { line: 276 } } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, color: AZUL, font: FUENTE },
        paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: AZUL_CLARO, space: 4 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, color: "2E5597", font: FUENTE },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 23, bold: true, color: "2E5597", font: FUENTE },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "vinetas", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "numeros", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
  ] },
  sections: [{
    properties: {
      page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1080, left: 1080, right: 1080 } },
      titlePage: true,
    },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: AZUL_CLARO, space: 4 } },
      children: [new TextRun({ text: "Manual de simulaciones y verificación normativa · Plataforma DCIM", size: 16, color: "7F7F7F" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
      new TextRun({ text: "Página ", size: 16, color: "7F7F7F" }),
      new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "7F7F7F" }),
      new TextRun({ text: " de ", size: 16, color: "7F7F7F" }),
      new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: "7F7F7F" }),
    ] })] }) },
    children: [...portada, ...convertir(cuerpo)],
  }],
});

Packer.toBuffer(doc).then((b) => { fs.writeFileSync(salida, b); console.log("escrito", salida, b.length, "bytes"); });
