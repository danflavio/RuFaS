const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType,
  AlignmentType, BorderStyle, ImageRun, Header, Footer, PageNumber, LevelFormat,
  TableLayoutType, VerticalAlign,
} = require("docx");

const FIG = "/Users/guilhermemartins/Projetos/IFG/Modulo 3/Modelagem e Otimização Aplicada/trabalho-final/RuFaS/GO_campo_dourado/otimizacao_dieta";
const OUT = path.join(FIG, "relatorios_alunos");
fs.mkdirSync(OUT, { recursive: true });

const FONT = "Times New Roman";
const BLACK = "000000";
const TEXT_W = 9071; // A4 com margens 3 cm (esq.) e 2 cm (dir.)

// ---------- helpers ----------
const runs = (text, base = {}) => {
  // **negrito** e ~itálico~ simples
  const parts = text.split(/(\*\*[^*]+\*\*|~[^~]+~)/g).filter(Boolean);
  return parts.map((p) => {
    if (p.startsWith("**")) return new TextRun({ ...base, text: p.slice(2, -2), bold: true });
    if (p.startsWith("~") && p.endsWith("~")) return new TextRun({ ...base, text: p.slice(1, -1), italics: true });
    return new TextRun({ ...base, text: p });
  });
};
const P = (text, opts = {}) =>
  new Paragraph({
    alignment: opts.align ?? AlignmentType.JUSTIFIED,
    spacing: { after: opts.after ?? 100, before: opts.before ?? 0, line: opts.line ?? 276 },
    indent: opts.noIndent ? undefined : { firstLine: 709 },
    keepNext: opts.keepNext,
    children: runs(text, opts.run || {}),
  });
const H1 = (text) =>
  new Paragraph({
    spacing: { before: 200, after: 100 }, keepNext: true,
    children: [new TextRun({ text: text.toUpperCase(), bold: true })],
  });
const H2 = (text) =>
  new Paragraph({
    spacing: { before: 120, after: 80 }, keepNext: true,
    children: [new TextRun({ text, bold: true })],
  });
const B = (text) =>
  new Paragraph({
    numbering: { reference: "bul", level: 0 }, alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 40, line: 276 }, children: runs(text),
  });
const N = (text, ref) =>
  new Paragraph({
    numbering: { reference: ref, level: 0 }, alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 40, line: 276 }, children: runs(text),
  });
const EQ = (text) =>
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 40 },
    children: [new TextRun({ text, italics: true })],
  });
const caption = (text) =>
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
    children: runs(text, { size: 20 }),
  });
const fonte = (text = "Fonte: elaborado pelo autor (2026).") =>
  new Paragraph({
    alignment: AlignmentType.LEFT, spacing: { before: 40, after: 160 },
    children: [new TextRun({ text, size: 18 })],
  });

const line = { style: BorderStyle.SINGLE, size: 8, color: BLACK };
const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
function table(headers, rows, widths, leftCols = [0]) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (t, i, isHead, isLastRow) =>
    new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      verticalAlign: VerticalAlign.CENTER,
      margins: { top: 30, bottom: 30, left: 80, right: 80 },
      borders: {
        top: isHead ? line : none,
        bottom: isHead || isLastRow ? line : none,
        left: none, right: none,
      },
      children: [
        new Paragraph({
          alignment: leftCols.includes(i) ? AlignmentType.LEFT : AlignmentType.CENTER,
          children: runs(String(t), isHead ? { size: 20, bold: true } : { size: 20 }),
        }),
      ],
    });
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: widths,
    layout: TableLayoutType.FIXED,
    alignment: AlignmentType.CENTER,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, i, true, false)) }),
      ...rows.map((r, ri) =>
        new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, i, false, ri === rows.length - 1)) })),
    ],
  });
}
function figure(file, w) {
  const [pw, ph] = sizes[file];
  return new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 0 },
    children: [new ImageRun({
      type: "png", data: fs.readFileSync(path.join(FIG, file)),
      transformation: { width: w, height: Math.round((w * ph) / pw) },
    })],
  });
}
const sizes = {
  "fig_custo.png": [1307, 677], "fig_dieta.png": [1412, 656],
  "fig_sobol_custo.png": [1247, 647], "fig_validacao.png": [1367, 831],
  "fig_break_even.png": [1247, 647],
};

// ---------- cabeçalho institucional ----------
function blocoInstitucional(titulo, subtitulo) {
  const c = (t, o = {}) =>
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: o.after ?? 0 },
      children: [new TextRun({ text: t, bold: o.bold, size: o.size ?? 22, allCaps: o.caps })],
    });
  return [
    c("INSTITUTO FEDERAL DE GOIÁS – IFG", { bold: true, size: 24 }),
    c("Pós-Graduação em Inteligência Artificial Aplicada"),
    c("Disciplina: Modelagem e Otimização Aplicada"),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 240 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: BLACK, space: 6 } },
      children: [new TextRun({ text: "Professor: Eduardo Noronha", size: 22 })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: subtitulo ? 60 : 200 },
      children: [new TextRun({ text: titulo.toUpperCase(), bold: true, size: 26 })],
    }),
    ...(subtitulo
      ? [new Paragraph({
          alignment: AlignmentType.CENTER, spacing: { after: 200 },
          children: [new TextRun({ text: subtitulo, italics: true, size: 22 })],
        })]
      : []),
    new Paragraph({
      alignment: AlignmentType.RIGHT, spacing: { after: 0 },
      children: [new TextRun({ text: "Aluno(a): [Nome completo do aluno]" })],
    }),
    new Paragraph({
      alignment: AlignmentType.RIGHT, spacing: { after: 240 },
      children: [new TextRun({ text: "Outubro de 2026" })],
    }),
  ];
}

function resumo(texto, palavras, titulo = "RESUMO") {
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 80 },
      children: [new TextRun({ text: titulo, bold: true })],
    }),
    new Paragraph({
      alignment: AlignmentType.JUSTIFIED, spacing: { after: 80, line: 240 },
      children: runs(texto, { size: 22 }),
    }),
    new Paragraph({
      alignment: AlignmentType.JUSTIFIED, spacing: { after: 200 },
      children: [new TextRun({ text: "Palavras-chave: ", bold: true, size: 22 }), new TextRun({ text: palavras, size: 22 })],
    }),
  ];
}

function build(file, children, font, size = 24) {
  const numbering = {
    config: [
      { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 709, hanging: 284 } } } }] },
      ...["n1", "n2", "n3", "n4"].map((r) => ({
        reference: r, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 709, hanging: 360 } } } }],
      })),
    ],
  };
  const runningHeader = new Header({
    children: [new Paragraph({
      alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: "IFG – Pós-Graduação em IA Aplicada – Modelagem e Otimização Aplicada", size: 18 })],
    })],
  });
  const doc = new Document({
    creator: "IFG – Pós-Graduação em IA Aplicada",
    styles: { default: { document: { run: { font, size, color: BLACK } } } },
    numbering,
    sections: [{
      properties: {
        titlePage: true,
        page: { size: { width: 11906, height: 16838 }, margin: { top: 1418, left: 1701, bottom: 1134, right: 1134, header: 709, footer: 567 } },
      },
      headers: { default: runningHeader, first: new Header({ children: [new Paragraph("")] }) },
      footers: {
        default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ children: [PageNumber.CURRENT], size: 20 })] })] }),
        first: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ children: [PageNumber.CURRENT], size: 20 })] })] }),
      },
      children,
    }],
  });
  return Packer.toBuffer(doc).then((buf) => fs.writeFileSync(path.join(OUT, file), buf));
}

// =====================================================================
// MODELO 1 — Artigo científico (Times New Roman)
// =====================================================================
const m1 = [
  ...blocoInstitucional("Formulação de dieta de mínimo custo para vacas leiteiras por programação linear integrada ao simulador RuFaS"),
  ...resumo(
    "Este trabalho apresenta um módulo de programação linear integrado ao simulador de fazendas leiteiras RuFaS para formular, ao menor custo, a ração de vacas em lactação de uma fazenda sintética de Goiás. As exigências nutricionais foram obtidas do calculador NASEM do próprio simulador e os preços, do CEPEA e de cotações regionais. O problema, com 19 alimentos e 38 restrições, foi resolvido pelo método dual simplex. A dieta recomendada custou R$ 26,07/vaca/dia, contra R$ 32,17 da dieta basal (−19,0%), com economia estimada de R$ 197 mil por ano. A análise de Sobol indicou a silagem de milho como principal fonte de variação do custo e o preço do leite como determinante da margem. Na simulação de um ano no RuFaS, a produção de leite manteve-se estável e a intensidade de metano entérico caiu 8,8%.",
    "programação linear; problema da dieta; simplex; análise de sensibilidade; RuFaS."
  ),
  H1("1 Introdução"),
  P("A alimentação é o maior custo variável da pecuária leiteira e, no cenário estudado, consome 27% da receita do leite. O problema estudado pode ser enunciado assim: **dada uma fazenda com um número conhecido de vacas em lactação, com exigências nutricionais definidas, e um conjunto de ingredientes com composição e preço conhecidos, qual mistura atende às exigências ao menor custo?** Trata-se do clássico problema da dieta da pesquisa operacional, que, por ter objetivo e restrições lineares, pode ser resolvido de forma exata pelo método simplex."),
  P("O RuFaS (~Ruminant Farm Systems~) é um simulador de código aberto que representa a fazenda leiteira de forma integrada (rebanho, nutrição, dejetos, solo e lavouras). Embora calcule exigências nutricionais, o simulador recebe a ração pronta do usuário e não otimiza seu custo. O objetivo deste trabalho foi desenvolver um módulo de otimização da dieta acoplado ao RuFaS, avaliar o efeito econômico da dieta resultante e analisar a sensibilidade da solução aos preços."),
  H1("2 Material e métodos"),
  H2("2.1 Cenário de estudo"),
  P("Utilizou-se o cenário ~GO_campo_dourado~ do RuFaS 1.0.5: fazenda sintética de 100 vacas, com média de 88,56 vacas em lactação, produção de 41,3 kg de leite/vaca/dia e consumo de 25,3 kg de matéria seca (MS)/vaca/dia. A dieta basal foi a ração da vaca em lactação definida no arquivo ~feed.json~ do cenário, avaliada com os mesmos preços de Goiás usados na otimização (milho, soja e leite do CEPEA; demais itens de cotações regionais)."),
  H2("2.2 Modelo de otimização"),
  P("As variáveis de decisão xᵢ representam a quantidade (kg MS/dia) de cada um dos 19 alimentos candidatos. O modelo minimiza o custo diário da ração:", { keepNext: true }),
  EQ("min Z = Σ cᵢ xᵢ   sujeito a   Σ xᵢ = 25,3;   Σ aᵢⱼ xᵢ ≥ bⱼ (ou ≤ bⱼ);   lᵢ ≤ xᵢ ≤ uᵢ"),
  P("em que cᵢ é o preço do alimento (R$/kg MS), aᵢⱼ o teor do nutriente j e bⱼ a exigência. As restrições incluem energia (TDN ≥ 72,12% da MS, igual ao da dieta basal), proteína bruta ≥ 17,5%, proteína não degradável no rúmen (RUP) digestível ≥ 1,2 kg/dia, fibra em detergente neutro (FDN) entre 28% e 33%, amido entre 25% e 35%, extrato etéreo entre 3% e 6%, cálcio e fósforo absorvíveis e limites práticos de inclusão. O modelo foi resolvido com o método dual simplex do pacote HiGHS (~scipy.optimize.linprog~). Também foram avaliados cenários alternativos: energia NASEM integral (TDN 76,99%), inclusão mínima de 15% de milho, 5% de linhaça e ausência de sorgo."),
  H2("2.3 Sensibilidade e validação"),
  P("A sensibilidade local foi obtida do quadro final do simplex; a global, pelo método de Sobol, com dez preços variando ±30% e o preço do leite ±20% (512 amostras). Os cenários foram comparados de forma pareada sob 256 choques de preço comuns (teste de Wilcoxon). A dieta ótima foi então simulada no RuFaS por um ano, com três sementes aleatórias."),
  H1("3 Resultados e discussão"),
  H2("3.1 Dieta ótima"),
  P("O milho grão foi excluído da solução: aos preços de outubro de 2026, o sorgo e o glúten de milho fornecem energia a menor custo. O farelo de soja foi parcialmente substituído por farelo de algodão e ureia, e a mistura mineral caiu de 3% para 0,5%, complementada por calcário (Tabela 1).", { keepNext: true }),
  caption("Tabela 1 – Composição da dieta basal e da dieta otimizada (% da MS)"),
  table(["Alimento", "Basal", "Otimizada"], [
    ["Silagem de milho", "30,0", "48,6"], ["Milho grão", "24,0", "–"], ["Silagem de leguminosa", "18,0", "–"],
    ["Sorgo grão", "–", "23,2"], ["Glúten de milho", "–", "12,6"], ["Farelo de soja", "16,0", "9,2"],
    ["Caroço / farelo de algodão", "9,0", "4,3"], ["Mistura mineral + calcário", "3,0", "1,7"], ["Ureia", "–", "0,4"],
  ], [4500, 2000, 2000]),
  fonte(),
  H2("3.2 Efeito econômico"),
  P("A redução de custo foi de R$ 6,10/vaca/dia (Tabela 2), o que eleva a receita sobre o custo da ração (IOFC, ~income over feed cost~) em 7,0% e reduz o peso da ração na receita de 27,0% para 21,9%. Para as 88,56 vacas em lactação, a economia anual estimada é de R$ 197 mil. Cerca de 61% dessa diferença decorre da correção da mistura mineral da dieta basal; o restante, da reformulação dos demais ingredientes.", { keepNext: true }),
  caption("Tabela 2 – Indicadores econômicos por vaca em lactação"),
  table(["Indicador", "Basal", "Otimizada"], [
    ["Custo da ração (R$/vaca/dia)", "32,17", "26,07"], ["Custo por kg de leite (R$)", "0,779", "0,631"],
    ["IOFC (R$/vaca/dia)", "86,89", "92,99"], ["Ração / receita do leite (%)", "27,0", "21,9"],
    ["Economia anual – 88,56 vacas (R$)", "–", "197.199"],
  ], [4500, 2000, 2000]),
  fonte(),
  P("A Figura 1 compara os cenários. Atender integralmente a energia NASEM custa R$ 5,53/vaca/dia a mais que a dieta recomendada; manter 15% de milho, R$ 0,65; incluir 5% de linhaça, R$ 1,21."),
  caption("Figura 1 – Custo diário da ração por cenário"),
  figure("fig_custo.png", 500),
  fonte(),
  H2("3.3 Análise de sensibilidade"),
  P("O quadro final do simplex indicou que a restrição mais cara é a de RUP digestível (preço sombra de R$ 6,41 por kg) e que cada ponto de TDN custa R$ 0,63/vaca/dia. O milho só entra na dieta com queda de 13,2% no preço (cerca de R$ 56/saca); a linhaça, com queda de 34,4%. Na análise de Sobol, a silagem de milho (ST = 0,39), o farelo de soja (0,23) e o sorgo (0,19) explicaram a maior parte da variância do custo, enquanto o preço do leite explicou 98% da variância do IOFC. A vantagem da dieta recomendada manteve-se nos 256 choques de preço (p < 0,001)."),
  H2("3.4 Validação no simulador"),
  P("No RuFaS, a produção média do lote foi de 3.720 kg/dia com a dieta otimizada, contra 3.707 kg/dia com a basal; o consumo de MS caiu 1,2% e o metano entérico por kg de leite caiu 8,8%. Com três repetições, a diferença não é estatisticamente significativa (p = 0,25)."),
  H1("4 Considerações finais"),
  P("A programação linear integrada ao RuFaS produziu uma dieta 19% mais barata que a basal, com produção de leite estável e menor intensidade de metano na simulação. Do ponto de vista do aprendizado, o trabalho mostrou que um problema real de nutrição animal pode ser traduzido em um modelo linear simples, com poucas dezenas de restrições, e que o valor da pesquisa operacional não está só na solução ótima: os preços sombra e os custos reduzidos respondem a perguntas práticas, como a partir de que preço vale a pena voltar a comprar milho."),
  P("Aprendeu-se também a ler os resultados com cautela. Parte relevante da economia veio de uma premissa da dieta basal (3% de mistura mineral), e não apenas da troca de grãos; o modelo linear é uma aproximação das exigências não lineares do NASEM, o que justificou validar a dieta no simulador; e a análise de sensibilidade mostrou que, para a margem da fazenda, o preço do leite pesa mais que o ajuste fino da ração. Como continuidade, recomenda-se simular a fazenda completa por cinco anos com preços reais."),
];

// =====================================================================
// MODELO 2 — Ênfase em Pesquisa Operacional (Arial)
// =====================================================================
const m2 = [
  ...blocoInstitucional("O problema da dieta de vacas leiteiras como programação linear", "Modelagem, método simplex e leitura econômica do quadro ótimo"),
  ...resumo(
    "O trabalho modela a formulação da ração de vacas em lactação como um problema de programação linear e interpreta a solução ótima sob a ótica da gestão. Os dados de rebanho e as exigências nutricionais foram extraídos do simulador RuFaS e os preços, do CEPEA. O problema foi resolvido pelo método dual simplex e o quadro final foi reconstruído para obter preços sombra, custos reduzidos e intervalos de estabilidade da base. A solução ótima reduziu o custo da ração de R$ 32,17 para R$ 26,07 por vaca/dia. A sensibilidade foi avaliada pelo quadro final, pelo método de Sobol e por testes pareados.",
    "pesquisa operacional; programação linear; simplex; preço sombra; Sobol."
  ),
  H1("1 Introdução"),
  P("Uma fazenda leiteira precisa alimentar diariamente dezenas de vacas de alta produção. Cada vaca exige quantidades mínimas de energia, proteína, fibra e minerais, mas não tolera excesso de amido ou gordura. A fazenda pode comprar diversos ingredientes (milho, sorgo, farelos, subprodutos, minerais), cada um com composição e preço próprios. **O problema é decidir quanto usar de cada ingrediente para atender a todas as exigências gastando o mínimo possível.**"),
  P("Esse é o problema da dieta, um dos primeiros resolvidos pelo método simplex. Neste trabalho ele é aplicado à ração das vacas em lactação de uma fazenda sintética de Goiás, representada no simulador RuFaS, que fornece os dados do rebanho, as exigências nutricionais e o ambiente de validação. O foco é a modelagem matemática e a interpretação do último quadro do simplex como ferramenta de decisão."),
  H1("2 Modelo matemático"),
  P("**Conjuntos e parâmetros.** I = conjunto de 19 alimentos candidatos; J = conjunto de nutrientes; cᵢ = preço do alimento i (R$/kg MS); aᵢⱼ = teor do nutriente j no alimento i; bⱼ = exigência; lᵢ, uᵢ = limites de inclusão; D = 25,3 kg MS/dia (consumo previsto pelo RuFaS)."),
  P("**Variáveis de decisão.** xᵢ ≥ 0, quantidade do alimento i na ração (kg MS/vaca/dia)."),
  P("**Função objetivo e restrições:**", { keepNext: true }),
  EQ("min Z = Σᵢ cᵢ xᵢ"),
  EQ("Σᵢ xᵢ = D                         (consumo de matéria seca)"),
  EQ("Σᵢ aᵢⱼ xᵢ ≥ bⱼ D  ou  ≤ bⱼ D     (limites em % da MS, linearizados)"),
  EQ("lᵢ D ≤ xᵢ ≤ uᵢ D                  (limites de inclusão)"),
  P("Restrições em porcentagem da MS tornam-se lineares ao multiplicar o limite pelo consumo fixo D. O modelo tem 19 variáveis, 37 restrições de desigualdade e uma de igualdade (Tabela 1).", { keepNext: true }),
  caption("Tabela 1 – Principais restrições do modelo"),
  table(["Restrição", "Tipo", "Limite"], [
    ["Energia (TDN)", "≥", "72,12% da MS"], ["Proteína bruta", "≥", "17,5% da MS"],
    ["RUP digestível", "≥", "1,20 kg/dia"], ["FDN", "≥ e ≤", "28% a 33% da MS"],
    ["Amido", "≥ e ≤", "25% a 35% da MS"], ["Extrato etéreo", "≥ e ≤", "3% a 6% da MS"],
    ["Ca e P absorvíveis", "≥", "66,8 g/d e 64,1 g/d"], ["Relação Ca:P", "≥ e ≤", "1,5 a 2,5"],
  ], [4000, 1500, 3000]),
  fonte("Fonte: exigências do módulo NASEM do RuFaS; limites práticos definidos pelo autor (2026)."),
  H1("3 Solução pelo método simplex"),
  P("O simplex é aplicável porque objetivo e restrições são lineares e as variáveis são contínuas. Partindo de uma solução básica viável, o algoritmo troca variáveis na base enquanto houver um ingrediente com custo reduzido negativo, isto é, cuja entrada diminua o custo. Utilizou-se a variante dual simplex do HiGHS. A solução ótima está na Tabela 2.", { keepNext: true }),
  caption("Tabela 2 – Variáveis básicas da solução ótima"),
  table(["Alimento", "kg MS/dia", "% MS", "R$/dia"], [
    ["Silagem de milho", "12,29", "48,6", "7,65"], ["Sorgo grão", "5,88", "23,2", "5,95"],
    ["Glúten de milho", "3,18", "12,6", "3,92"], ["Farelo de soja 48%", "2,34", "9,2", "5,29"],
    ["Farelo de algodão", "1,08", "4,3", "2,16"], ["Calcário", "0,32", "1,2", "0,09"],
    ["Mistura mineral", "0,13", "0,5", "0,76"], ["Ureia", "0,10", "0,4", "0,25"],
    ["**Total**", "**25,30**", "**100,0**", "**26,07**"],
  ], [3700, 1600, 1600, 1600]),
  fonte(),
  H1("4 Leitura do quadro final na perspectiva do negócio"),
  P("O último quadro do simplex contém, além da solução, duas informações de valor gerencial. Os **preços sombra** indicam quanto o custo diário varia se uma restrição for apertada em uma unidade. Os **custos reduzidos** indicam quanto o preço de um alimento fora da base precisa cair para que ele entre na dieta (Tabela 3).", { keepNext: true }),
  caption("Tabela 3 – Preços sombra e custos reduzidos selecionados"),
  table(["Elemento do quadro", "Valor", "Interpretação"], [
    ["Preço sombra – RUP digestível", "R$ 6,41/kg", "Exigência mais cara da dieta"],
    ["Preço sombra – TDN", "R$ 0,63/p.p.", "Custo de 1 ponto a mais de energia"],
    ["Preço sombra – proteína bruta", "R$ 0,15/p.p.", "Proteína barata na margem"],
    ["Custo reduzido – milho grão", "−13,2%", "Entra abaixo de ≈ R$ 56/saca"],
    ["Custo reduzido – farelo de linhaça", "−34,4%", "Não compete por nutrição"],
  ], [3500, 1800, 3200], [0, 2]),
  fonte(),
  P("Os preços sombra valem apenas no intervalo em que a base ótima se mantém. Elevar o TDN de 72,12% para 76,99% (exigência NASEM) custaria R$ 3,04 pelo preço sombra, mas a reotimização mostrou acréscimo real de R$ 5,53, pois a base muda e o custo marginal cresce. Para o gestor, o quadro final define uma zona de negociação: dentro das faixas, a fórmula não precisa ser refeita."),
  H1("5 Efeito econômico"),
  P("A Tabela 4 compara a dieta basal do RuFaS, avaliada com os mesmos preços, com a solução ótima e com a alternativa que atende integralmente à energia NASEM.", { keepNext: true }),
  caption("Tabela 4 – Indicadores econômicos por vaca em lactação"),
  table(["Indicador", "Basal", "Ótima", "NASEM"], [
    ["Custo da ração (R$/vaca/dia)", "32,17", "26,07", "31,60"],
    ["Custo por kg de leite (R$)", "0,779", "0,631", "0,765"],
    ["IOFC (R$/vaca/dia)", "86,89", "92,99", "87,45"],
    ["Economia anual – 88,56 vacas (R$)", "–", "197.199", "18.206"],
  ], [4000, 1500, 1500, 1500]),
  fonte(),
  P("A solução ótima reduz o custo em 19,0% e eleva o IOFC (receita do leite menos custo da ração) em 7,0%. Cerca de 61% da economia vem da substituição da mistura mineral da dieta basal; o restante, da troca de milho e farelo de soja por sorgo, glúten de milho e farelo de algodão."),
  H1("6 Análise de sensibilidade"),
  P("Variando simultaneamente dez preços (±30%) e o preço do leite (±20%), o método de Sobol mostrou que o custo da ração depende principalmente da silagem de milho (ST = 0,39), do farelo de soja (0,23) e do sorgo (0,19) (Figura 1), enquanto a margem depende quase só do preço do leite (ST = 0,98). Em testes pareados sob 256 choques de preço comuns, a solução ótima foi mais barata que as alternativas com energia NASEM (+R$ 5,94), com 15% de milho (+R$ 0,73) e com 5% de linhaça (+R$ 1,30), todas com p < 0,001.", { keepNext: true }),
  caption("Figura 1 – Índices de Sobol para o custo da ração"),
  figure("fig_sobol_custo.png", 430),
  fonte(),
  H1("7 Considerações finais"),
  P("O trabalho permitiu aplicar, em um problema real, os conceitos centrais da disciplina: formulação de variáveis, função objetivo e restrições; resolução pelo simplex; e interpretação do quadro final. O principal aprendizado foi que o quadro ótimo é tão útil quanto a própria solução. Os preços sombra mostram quanto custa cada exigência nutricional e os custos reduzidos mostram a partir de que preço um ingrediente passa a valer a pena, o que transforma o modelo em uma ferramenta de compra."),
  P("Aprendeu-se também que essas informações têm limites: valem apenas dentro das faixas de estabilidade da base, como mostrou o caso da energia NASEM, e dependem de uma aproximação linear de exigências que, na realidade, são não lineares. Por isso foi importante validar a solução no simulador RuFaS, onde a dieta manteve a produção de leite, e complementar a análise local com a análise global de Sobol."),
];

// =====================================================================
// MODELO 3 — Estudo de caso: integração com o RuFaS (Georgia)
// =====================================================================
const m3 = [
  ...blocoInstitucional("Integração de um módulo de otimização da dieta ao simulador RuFaS", "Estudo de caso da Fazenda Campo Dourado (GO)"),
  ...resumo(
    "Este estudo de caso descreve a investigação do simulador de fazendas leiteiras RuFaS e o desenvolvimento de um módulo externo de otimização da dieta que se comunica com ele. O módulo reutiliza o calculador de exigências NASEM e a biblioteca de alimentos do simulador, resolve um problema de programação linear com preços de Goiás e devolve uma ração no formato de entrada do RuFaS. Aplicado ao cenário Campo Dourado, gerou uma dieta 19% mais barata. A simulação de um ano mostrou leite estável e redução de 8,8% na intensidade de metano.",
    "RuFaS; simulação; otimização da dieta; integração de modelos; estudo de caso."
  ),
  H1("1 Introdução"),
  P("Uma fazenda de leite de Goiás, com cerca de 89 vacas em lactação produzindo 41,3 kg de leite por dia cada, gasta mais de R$ 30 por vaca por dia com ração. **A pergunta do estudo é se é possível montar uma ração mais barata, que atenda às mesmas exigências nutricionais, e qual seria o efeito disso na produção e na margem da fazenda.**"),
  P("Para responder, usou-se o RuFaS (~Ruminant Farm Systems~), simulador que modela rebanho, nutrição, leite, dejetos, solo e emissões em passos diários. O simulador descreve o que acontece com a fazenda, mas recebe a dieta pronta do usuário e não indica qual é a melhor. Os objetivos foram: (i) entender a estrutura do RuFaS no ponto em que a dieta é definida; (ii) construir um módulo de otimização integrado a ele; e (iii) avaliar o efeito econômico e a sensibilidade da dieta obtida."),
  H1("2 Investigação do repositório"),
  P("O RuFaS 1.0.5 tem cerca de 214 arquivos e 82 mil linhas de código Python. A investigação concentrou-se nos componentes do Quadro 1, que ligam a definição da dieta à simulação do rebanho.", { keepNext: true }),
  caption("Quadro 1 – Componentes do RuFaS utilizados no trabalho"),
  table(["Componente", "Função no trabalho"], [
    ["animal/nutrients/", "Calculador de exigências NASEM (energia, proteína, Ca, P), chamado diretamente pelo módulo"],
    ["animal/ration/", "Verificação da ração; a dieta otimizada entra como ração do usuário (user_input)"],
    ["animal/pen.py", "Organização do rebanho; vacas em lactação no pen LAC_COW_PEN_3"],
    ["input_manager.py", "Leitura do farm_metadata.json e dos arquivos feed.json e config.json"],
    ["task_manager.py, main.py", "Execução das simulações de validação"],
  ], [2900, 6100], [0, 1]),
  fonte(),
  P("Um achado relevante foi que o cenário contém dois arquivos de alimentos. O metadado da fazenda aponta para ~feed.json~, baseado na biblioteca do Nordeste dos EUA e com preços em dólar; o ~feed_goias.json~ existe, mas não é usado pela simulação. Adotou-se, portanto, a dieta do ~feed.json~ como basal, avaliada com preços de Goiás."),
  H1("3 Desenvolvimento do módulo"),
  P("O módulo ~diet_optimization~ foi implementado como pacote Python independente, sem alterar o código do simulador. O fluxo segue cinco etapas:", { keepNext: true }),
  N("**Entrada:** composição dos alimentos do RuFaS e preços do CEPEA e de cotações regionais (19 candidatos).", "n1"),
  N("**Exigências:** cálculo pelo NASEM do RuFaS, somado a limites práticos de fibra, amido e gordura.", "n1"),
  N("**Otimização:** programação linear de mínimo custo, resolvida pelo dual simplex (HiGHS).", "n1"),
  N("**Análise:** indicadores econômicos e sensibilidade (quadro final, Sobol e testes pareados).", "n1"),
  N("**Integração:** geração de ~feed_otimizado.json~ e dos metadados para simular a dieta no RuFaS.", "n1"),
  H1("4 Dieta obtida"),
  P("A dieta ótima é composta por silagem de milho (48,6% da MS), sorgo grão (23,2%), glúten de milho (12,6%), farelo de soja (9,2%), farelo de algodão (4,3%), calcário (1,2%), mistura mineral (0,5%) e ureia (0,4%). O milho grão saiu da dieta e a mistura mineral caiu de 3% para 0,5% (Figura 1).", { keepNext: true }),
  caption("Figura 1 – Composição da dieta basal e da dieta otimizada"),
  figure("fig_dieta.png", 500),
  fonte(),
  H1("5 Efeito econômico"),
  P("Atendendo à orientação de testar ingredientes, foram simulados cenários que forçam ou retiram alimentos (Tabela 1).", { keepNext: true }),
  caption("Tabela 1 – Custo da ração por cenário"),
  table(["Cenário", "R$/vaca/dia", "Variação vs. basal", "Economia anual (R$)"], [
    ["Basal (preços de GO)", "32,17", "–", "–"],
    ["**Otimizada (recomendada)**", "**26,07**", "**−19,0%**", "**197.199**"],
    ["Com 15% de milho", "26,72", "−16,9%", "176.169"],
    ["Sem sorgo", "27,14", "−15,6%", "162.382"],
    ["Com 5% de linhaça", "27,28", "−15,2%", "157.845"],
    ["Energia NASEM (TDN 76,99%)", "31,60", "−1,8%", "18.206"],
  ], [3400, 1800, 1900, 1900]),
  fonte(),
  P("Na dieta recomendada, o custo por kg de leite caiu de R$ 0,779 para R$ 0,631 e a receita sobre o custo da ração (IOFC) subiu de R$ 86,89 para R$ 92,99/vaca/dia (+7,0%). Manter o milho custa R$ 0,65/vaca/dia; incluir linhaça, R$ 1,21. Cerca de 61% da economia decorre da redução da mistura mineral da dieta basal, cuja adequação deve ser verificada na prática da fazenda."),
  H1("6 Análise de sensibilidade"),
  P("O quadro final do simplex mostrou que o milho só volta à dieta se o preço cair 13,2% (cerca de R$ 56/saca) e que o sorgo suporta alta de 17% antes de ser substituído. A análise de Sobol apontou a silagem de milho, o farelo de soja e o sorgo como os preços que mais afetam o custo, e o preço do leite como fator dominante da margem (98% da variância). Testes pareados sob 256 choques de preço confirmaram a vantagem da dieta recomendada sobre todas as alternativas da Tabela 1 (p < 0,001)."),
  H1("7 Validação no simulador"),
  P("A dieta foi executada no RuFaS no modo ~animals_only~, que isola o efeito nutricional, por um ano e com três sementes aleatórias (Tabela 2).", { keepNext: true }),
  caption("Tabela 2 – Resultados médios da simulação de um ano no RuFaS"),
  table(["Indicador", "Basal", "Otimizada", "Variação"], [
    ["Leite do lote (kg/dia)", "3.707", "3.720", "+0,3%"],
    ["Consumo de MS (kg/vaca/dia)", "25,48", "25,17", "−1,2%"],
    ["Metano entérico (g/kg de leite)", "8,20", "7,48", "−8,8%"],
  ], [3800, 1700, 1700, 1800]),
  fonte("Fonte: simulações no RuFaS 1.0.5, sementes 44, 45 e 46 (2026)."),
  P("A produção manteve-se estável. A redução de metano foi consistente nas três sementes, mas não é estatisticamente significativa com esse número de repetições (p = 0,25)."),
  H1("8 Considerações finais"),
  P("O estudo mostrou que é possível acoplar um módulo de pesquisa operacional ao RuFaS sem modificar o simulador: o módulo reutiliza os cálculos de exigência do RuFaS e devolve a dieta no seu formato de entrada. No caso estudado, a dieta otimizada reduziu o custo da ração em 19%, manteve a produção de leite e reduziu a intensidade de metano."),
  P("O principal aprendizado foi metodológico. Diante de um repositório grande, foi mais produtivo seguir o caminho dos dados, do metadado ao arquivo de alimentos e ao pen da vaca em lactação, do que tentar entender todo o código; foi assim que se descobriu que o arquivo de Goiás não era usado. Aprendeu-se ainda que otimização e simulação se complementam: o modelo linear encontra a dieta barata e o simulador verifica se ela se sustenta. Ficaram como limitações o rebanho sintético, os preços de uma única data e a validação de apenas um ano; o próximo passo é simular a fazenda completa com preços reais."),
];

Promise.all([
  build("Modelo_1_Artigo_Cientifico.docx", m1, "Times New Roman", 24),
  build("Modelo_2_Pesquisa_Operacional.docx", m2, "Arial", 22),
  build("Modelo_3_Estudo_de_Caso_RuFaS.docx", m3, "Georgia", 22),
]).then(() => console.log("ok"));
