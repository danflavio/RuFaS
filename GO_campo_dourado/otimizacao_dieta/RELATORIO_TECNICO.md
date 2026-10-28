# Relatório Técnico — Otimização da Dieta de Vacas Leiteiras Integrada ao RuFaS

**Disciplina:** Modelagem e Otimização Aplicada — IFG, Módulo 3  
**Data:** 28/10/2026  
**Repositório / branch:** RuFaS 1.0.5 — `go-campo-dourado`  
**Cenário:** Fazenda Campo Dourado (GO), `GO_campo_dourado`

---

## Resumo

Este trabalho desenvolve um módulo de **programação linear (PL)** acoplado ao
simulador de fazendas leiteiras **RuFaS**. O módulo formula, ao menor custo, a
ração das vacas em lactação de uma fazenda sintética de Goiás. As exigências
nutricionais vêm do próprio calculador NASEM do RuFaS. Os preços dos
ingredientes vêm do CEPEA e de cotações regionais.

A dieta recomendada (iso-energética) custa **R$ 26,07/vaca/dia**. A dieta basal
do RuFaS, avaliada com os mesmos preços, custa **R$ 32,17/vaca/dia**. A economia
é de **19,0%**, cerca de **R$ 197 mil/ano** para 88,56 vacas em lactação. O
quadro final do simplex mostra que a restrição mais cara é a de proteína não
degradável (RUP), e que o milho grão só entra na dieta se cair ~13%. A análise
de Sobol indica que o custo depende sobretudo da silagem de milho e que a margem
(IOFC) depende quase só do preço do leite. Na simulação de 1 ano no RuFaS, a
produção de leite ficou estável e a intensidade de metano caiu 8,8%.

A principal ressalva: cerca de 61% da economia vem da troca da mistura mineral
da dieta basal. A validação é de curto prazo e usa um rebanho sintético.

---

## 1. Introdução e objetivos

A alimentação é o maior custo variável de uma fazenda leiteira. Formular a
ração é um problema clássico de pesquisa operacional, conhecido como
**problema da dieta**: escolher quantidades de ingredientes que atendam às
exigências nutricionais ao menor custo.

O trabalho tem três objetivos:

1. Desenvolver um **módulo de otimização da dieta integrado ao RuFaS**.
2. Avaliar o **efeito econômico** da dieta otimizada.
3. Fazer uma **análise de sensibilidade** dos resultados.

A orientação da disciplina pediu ainda para:

- testar ingredientes alternativos (milho, sorgo, linhaça etc.) e verificar
  qual é mais vantajoso;
- usar o **simplex** e interpretar o **último quadro** na perspectiva do
  negócio;
- usar preços do **CEPEA**;
- usar **Sobol** para a sensibilidade global e avaliar o uso de **testes
  pareados (pairwise)**.

---

## 2. O simulador RuFaS e o cenário estudado

### 2.1 O que é o RuFaS

O RuFaS (*Ruminant Farm Systems*) é um simulador *whole-farm* de fazendas
leiteiras escrito em Python. Ele modela o rebanho, a nutrição, o leite, os
dejetos, o solo, as lavouras e as emissões em passos diários. A versão usada
(1.0.5) tem cerca de **214 arquivos e 82 mil linhas** de código no pacote
`RUFAS/`.

Os módulos explorados neste trabalho foram:

| Módulo do RuFaS | Papel para este trabalho |
|---|---|
| `RUFAS/biophysical/animal/nutrients/` | Calculador de exigências NASEM (energia, proteína, Ca, P). O módulo de otimização chama esse calculador diretamente. |
| `RUFAS/biophysical/animal/ration/` | Formulação e verificação da ração por pen. Uma ração `user_input` é imposta e o RuFaS verifica se atende às exigências. |
| `RUFAS/biophysical/animal/pen.py` | Organização do rebanho em pens; a vaca em lactação fica no `LAC_COW_PEN_3`. |
| `RUFAS/task_manager.py`, `main.py` | Execução de simulações a partir de arquivos de metadados e tarefas (`main.py -p`). |
| `RUFAS/input_manager.py` | Leitura do `farm_metadata.json` e dos arquivos de entrada (`feed.json`, `config.json`). |

### 2.2 O cenário `GO_campo_dourado`

| Parâmetro | Valor |
|---|---:|
| Vacas no rebanho | 100 |
| Vacas em lactação (média) | 88,56 |
| Produção de leite | 41,3 kg/vaca/dia |
| Consumo de matéria seca (CMS) | 25,3 kg MS/vaca/dia |
| Peso vivo / dias em lactação | 650 kg / 150 dias |
| Pen da vaca em lactação | `LAC_COW_PEN_3` |

### 2.3 Achado sobre os arquivos de alimentação

Ao investigar o cenário, encontramos dois arquivos de alimentos:

- O `farm_metadata.json` aponta para `inputs_resolvidos/feed.json`. Esse arquivo
  usa a biblioteca de alimentos do **Nordeste dos EUA**, com preços em US$.
- O `feed_goias.json` tem dieta e preços diferentes, mas **não está ligado a
  nenhum metadata**. A simulação de referência não o usa.

Por isso, a dieta do `feed.json` foi tomada como **dieta basal**, e a ela foram
aplicados preços de Goiás. Assim, a comparação separa o efeito da formulação do
efeito do preço.

**Dieta basal (`feed.json`, pen da vaca em lactação):**

| Alimento | % da MS |
|---|---:|
| Silagem de milho | 30% |
| Milho grão | 24% |
| Silagem de leguminosa | 18% |
| Farelo de soja | 16% |
| Caroço de algodão | 9% |
| Mistura mineral | 3% |

---

## 3. Arquitetura do módulo `diet_optimization`

O módulo fica na raiz do repositório, como um pacote Python separado. Ele **lê**
dados do RuFaS, **otimiza** fora do simulador e **devolve** um `feed.json`
otimizado para o RuFaS simular.

```
 RuFaS (entradas)                 diet_optimization                    RuFaS (validação)
 ─────────────────               ────────────────────                 ──────────────────
 feed.json  ───────────►  feed_library.py  (composição, preço, limites)
 calculador NASEM ─────►  requirements.py  (exigências + restrições práticas)
 preços CEPEA (CSV) ───►        │
                                ▼
                         lp_model.py   (PL → scipy/HiGHS dual simplex)
                                │
               ┌────────────────┼──────────────────┐
               ▼                ▼                  ▼
          tableau.py      economics.py       sensitivity.py
       (quadro final,   (custo, IOFC,      (OAT, Sobol,
        preço sombra)    economia anual)    break-even, pareados)
                                │
                                ▼
                         integration.py ──► feed_otimizado.json ──► main.py -p (animals_only)
                                                                         │
                         validation.py ◄──── CSVs de saída ◄─────────────┘
                                │
                                ▼
                    report.py / html_report.py (relatório, gráficos, PDF)
```

| Arquivo | Função |
|---|---|
| `config.py` | Carrega configuração, dieta basal e cenários. |
| `feed_library.py` | Lê a composição NASEM dos alimentos, os preços e os limites de inclusão. |
| `requirements.py` | Calcula as exigências com o `nasem_requirements_calculator` do RuFaS e soma as restrições práticas. |
| `lp_model.py` | Monta e resolve o PL; extrai duais e custos reduzidos. |
| `tableau.py` | Reconstrói o quadro final do simplex e as faixas de RHS e de preço. |
| `economics.py` | Custo, custo por kg de leite, IOFC, economia anual, decomposição mineral. |
| `sensitivity.py` | Sensibilidade OAT, Sobol (SALib), break-even e testes pareados. |
| `integration.py` | Gera `feed_otimizado.json`, config, metadados e tarefa para o RuFaS. |
| `validation.py` | Resume as saídas das simulações e aplica o teste de Wilcoxon. |
| `cli.py` | Interface `python -m diet_optimization`. |

**Dados de entrada** (`diet_optimization/data/`): `prices_go_2026-10-27.csv`,
`candidates.csv` (19 alimentos), `baseline_diet.json`, `scenarios.json`,
`config.json`.

**Qualidade:** 14 testes automatizados em `tests/test_diet_optimization/`
(biblioteca de alimentos, modelo de PL, economia, sensibilidade e integração),
todos passando. O pacote passa em `black` e `flake8`.

---

## 4. Formulação do problema de programação linear

### 4.1 Modelo

**Variáveis de decisão:** `x_i` = kg de MS/vaca/dia do alimento `i`, para
19 alimentos candidatos.

**Parâmetros:** `c_i` = preço do alimento (R$/kg MS); `a_ij` = teor do
nutriente `j` no alimento `i`; `b_j` = exigência ou limite; `l_i`, `u_i` =
limites de inclusão.

```
minimizar    Z = Σ c_i · x_i                    (custo da ração, R$/vaca/dia)

sujeito a    Σ x_i = 25,3                        (consumo de MS fixo)
             Σ a_ij · x_i ≥ b_j                  (nutrientes mínimos)
             Σ a_ij · x_i ≤ b_j                  (nutrientes máximos)
             l_i ≤ x_i ≤ u_i                     (limites de inclusão)
             x_i ≥ 0
```

Restrições em porcentagem da MS são linearizadas multiplicando o limite pelo
CMS. Por exemplo, PB ≥ 17,5% vira `Σ PB_i · x_i ≥ 0,175 · Σ x_i`.

### 4.2 Restrições

| Grupo | Restrição | Valor (cenário iso-energético) |
|---|---|---|
| Energia | TDN mínimo | 72,12% da MS |
| Proteína | Proteína bruta mínima | 17,5% da MS |
| Proteína | RUP digestível mínima | 1,20 kg/dia |
| Fibra | NDF | 28% a 33% da MS |
| Fibra | NDF de forragem mínimo | 18% da MS |
| Carboidrato | Amido | 25% a 35% da MS |
| Gordura | Extrato etéreo | 3% a 6% da MS |
| Minerais | Ca e P absorvíveis | ≥ 66,8 g/d e ≥ 64,1 g/d |
| Minerais | Ca total mínimo / relação Ca:P | 0,60% / 1,5 a 2,5 |
| Prática | Limites de inclusão por alimento | ex.: ureia ≤ 0,6%, mineral ≥ 0,5% |

O problema tem **19 variáveis, 37 restrições de desigualdade e 1 de igualdade**.

As exigências NASEM calculadas pelo RuFaS para a vaca do cenário são: NEl
44,69 Mcal/dia, proteína metabolizável 2.557 g/dia, Ca absorvível 66,8 g/dia e
P absorvível 64,1 g/dia. A NEl exigida equivale a um TDN de 76,99% da MS. A
dieta basal tem TDN de 72,12%, ou seja, um **déficit teórico de energia**. Por
isso foram criados cenários com os dois níveis de energia (seção 4.4).

### 4.3 Método de solução

O PL foi resolvido com `scipy.optimize.linprog`, método **dual simplex**
(`highs-ds`, do HiGHS). O simplex é aplicável porque o objetivo e todas as
restrições são lineares e as variáveis são contínuas. O quadro final foi
reconstruído a partir da base ótima (`tableau.py`) para ler preços sombra,
custos reduzidos e faixas de estabilidade.

### 4.4 Cenários

| Cenário | O que muda |
|---|---|
| **Iso-energético (recomendado)** | TDN = 72,12%, o mesmo da basal; mantém energia, proteína e fibra. |
| NASEM | TDN = 76,99%; NDF mínimo 27,5% e Ca:P mínimo 1,2 para viabilizar a alta energia. |
| Intermediário | TDN = 74,0%. |
| Com milho 15% | Força pelo menos 15% de milho grão (logística da fazenda). |
| Com linhaça 5% | Força 5% de farelo de linhaça (apelo ômega-3). |
| Sem sorgo | Remove o sorgo (indisponibilidade). |
| Máxima economia | Remove a RUP mínima e reduz PB para 17,0% (limite teórico). |

---

## 5. Dados e preços

| Item | Preço | Fonte |
|---|---|---|
| Milho | R$ 64,87/saca de 60 kg | CEPEA/ESALQ, 27/10/2026 |
| Soja em grão | R$ 157,41/saca | CEPEA Paranaguá, 27/10/2026 |
| Leite ao produtor — GO | R$ 2,9692/L | CEPEA, ago/2026 |
| Farelo de soja — Anápolis/GO | R$ 2.020/t | Agrolink, 27/10/2026 |
| Caroço de algodão | R$ 1.200/t | Notícias Agrícolas / Scot (referência regional) |
| Silagem de milho | R$ 220/t de matéria natural | Scot / ZS Máquinas (faixa R$ 190–220/t) |
| Demais subprodutos | cotação regional ou estimativa | `prices_go_2026-10-27.csv` |
| Câmbio | R$ 5,35/US$ | Notícias Agrícolas, 27/10/2026 |

Os preços foram convertidos para R$/kg de MS usando o teor de MS de cada
alimento. A composição nutricional vem da biblioteca de alimentos do RuFaS
(NASEM).

---

## 6. Resultados

### 6.1 Dieta ótima (iso-energética)

| Alimento | % MS | kg MS/dia | R$/kg MS | R$/dia |
|---|---:|---:|---:|---:|
| Silagem de milho | 48,6% | 12,29 | 0,62 | 7,65 |
| Sorgo grão | 23,2% | 5,88 | 1,01 | 5,95 |
| Glúten de milho (CGF) | 12,6% | 3,18 | 1,23 | 3,92 |
| Farelo de soja 48% | 9,2% | 2,34 | 2,26 | 5,29 |
| Farelo de algodão | 4,3% | 1,08 | 2,00 | 2,16 |
| Calcário calcítico | 1,2% | 0,32 | 0,30 | 0,09 |
| Mistura mineral | 0,5% | 0,13 | 6,00 | 0,76 |
| Ureia pecuária | 0,4% | 0,10 | 2,53 | 0,25 |
| **Total** | **100%** | **25,3** | | **26,07** |

![Composição da dieta](fig_dieta.png)

**Leitura:**

- O **milho grão saiu da dieta**. Por unidade de energia, sorgo e glúten de
  milho estão mais baratos aos preços de outubro/2026.
- O **farelo de soja caiu de 16% para 9,2%**. Parte da proteína passou para
  farelo de algodão, glúten de milho e ureia.
- A **mistura mineral caiu de 3% para 0,5%**, com 1,2% de calcário. O fósforo
  passou a vir do farelo de algodão e do glúten de milho.

### 6.2 Adequação nutricional

| Indicador | Basal | Iso-energética | NASEM | Exigência |
|---|---:|---:|---:|---|
| PB (% MS) | 18,56 | 17,50 | 17,82 | ≥ 17,50 |
| NDF (% MS) | 28,72 | 28,00 | 27,50 | 28,0 (27,5 NASEM) – 33,0 |
| Amido (% MS) | 27,47 | 35,00 | 31,53 | 25,0 – 35,0 |
| Extrato etéreo (% MS) | 4,28 | 3,18 | 4,79 | 3,0 – 6,0 |
| TDN (% MS) | 72,12 | 72,12 | 76,99 | 72,12 (76,99 NASEM) |
| RUP digestível (kg/d) | 1,20 | 1,20 | 1,20 | ≥ 1,20 |
| P absorvível (g/d) | 64,51 | 64,06 | 64,06 | ≥ 64,06 |

A dieta iso-energética atende a todas as restrições. Várias ficam exatamente no
limite (PB, NDF mínimo, amido máximo, TDN, RUP, P), comportamento típico de uma
solução de vértice do simplex.

### 6.3 Efeito econômico

| Indicador | Basal | Iso-energética | NASEM |
|---|---:|---:|---:|
| Custo da ração (R$/vaca/dia) | 32,17 | **26,07** | 31,60 |
| Custo por kg de leite (R$/kg) | 0,779 | **0,631** | 0,765 |
| IOFC (R$/vaca/dia) | 86,89 | **92,99** | 87,45 |
| Ração como % da receita | 27,0% | **21,9%** | 26,5% |
| Economia anual (88,56 vacas) | — | **R$ 197.199** | R$ 18.206 |

*IOFC (income over feed cost) = receita do leite − custo da ração.*

A economia é de R$ 6,10/vaca/dia (−19,0%). O IOFC sobe 7,0%.

**Decomposição da economia.** Cerca de **60,7%** da diferença está na linha de
minerais (3% de mistura mineral → 0,5% + calcário) e **39,3%** na reformulação
dos demais ingredientes. A decomposição é contábil: parte do fósforo foi
transferida para o farelo de algodão e o glúten de milho, cujo custo aparece em
outras linhas. Se a fazenda real já usa uma mistura mineral mais barata, a
economia será menor.

### 6.4 Comparação de cenários

| Cenário | R$/vaca/dia | vs. basal | Economia anual |
|---|---:|---:|---:|
| Basal (preços de GO) | 32,17 | — | — |
| Máxima economia (sem RUP mínimo) | 24,83 | −22,8% | R$ 237.224 |
| **Iso-energético (recomendado)** | **26,07** | **−19,0%** | **R$ 197.199** |
| Com milho 15% | 26,72 | −16,9% | R$ 176.169 |
| Sem sorgo | 27,14 | −15,6% | R$ 162.382 |
| Com linhaça 5% | 27,28 | −15,2% | R$ 157.845 |
| Intermediário (74% TDN) | 27,92 | −13,2% | R$ 137.173 |
| NASEM (76,99% TDN) | 31,60 | −1,8% | R$ 18.206 |

![Custo por cenário](fig_custo.png)

Respondendo à pergunta "qual ingrediente é mais vantajoso":

- **Manter 15% de milho** custa R$ 0,65/vaca/dia a mais que a dieta ótima.
- **Incluir 5% de linhaça** custa R$ 1,21/vaca/dia a mais. É uma decisão de
  mercado (leite com ômega-3), não de mínimo custo.
- **Ficar sem sorgo** custa R$ 1,07/vaca/dia a mais. O sorgo é o principal
  ingrediente energético da solução.
- **Atender à energia NASEM** custa R$ 5,53/vaca/dia a mais. É o preço da
  segurança nutricional.

![Fronteira custo × energia](fig_fronteira.png)

---

## 7. O quadro final do simplex na perspectiva do negócio

O quadro final do simplex (`quadro_simplex.csv`) contém três informações úteis
para o gestor:

1. **Coluna RHS** — a solução ótima: quanto usar de cada alimento.
2. **Custos reduzidos** — para um alimento fora da dieta, quanto o preço dele
   precisa cair para que valha a pena incluí-lo.
3. **Preços sombra** (duais) — quanto o custo diário muda se uma exigência for
   apertada ou relaxada em uma unidade.

### 7.1 Preços sombra das restrições ativas

| Restrição ativa | Valor | Faixa sem trocar a base | Preço sombra | Leitura de negócio |
|---|---:|---|---:|---|
| RUP digestível mínima | 1,20 kg | 1,13 – 1,20 | R$ 6,407/kg | A exigência mais cara. Cada kg extra de proteína protegida custa R$ 6,41/vaca/dia. |
| Inclusão mínima de mistura mineral | 0,13 kg | 0,00 – 0,13 | R$ 6,052/kg | O mineral comercial é caro; o piso de 0,5% é uma decisão de segurança, não de custo. |
| TDN mínimo | 72,12 p.p. | 71,69 – 72,12 | R$ 0,625/p.p. | Subir 1 ponto de energia custa R$ 0,63/vaca/dia. Só vale se render mais que isso em leite. |
| PB mínima | 17,50 p.p. | 16,48 – 17,53 | R$ 0,150/p.p. | Proteína bruta é barata na margem (há ureia e farelo de algodão). |
| Amido máximo | 35,00 p.p. | 33,28 – 35,01 | R$ 0,078/p.p. | O limite de saúde ruminal custa pouco. |
| P absorvível mínimo | 64,06 g | 62,08 – 64,21 | R$ 0,027/g | Fósforo é suprido barato pelos subprodutos. |

**Exemplo de decisão.** Para corrigir o déficit de energia (72,12% → 76,99%
TDN), o preço sombra prevê ~R$ 0,63 por ponto. Mas a faixa de estabilidade vai
só até 72,12%: acima disso a base muda e o custo marginal cresce. O cenário
NASEM confirma: são R$ 5,53/vaca/dia a mais, e não 4,87 × 0,625 ≈ R$ 3,04.
O preço sombra vale **dentro da faixa**.

### 7.2 Custos reduzidos e preços de indiferença

**Alimentos fora da dieta — quanto precisariam cair para entrar:**

| Alimento | Preço atual (R$/kg MS) | Preço de entrada | Queda necessária |
|---|---:|---:|---:|
| Silagem de leguminosa | 0,70 | 0,67 | −3,9% |
| Caroço de algodão | 1,31 | 1,21 | −7,8% |
| Farelo de trigo | 1,00 | 0,91 | −9,3% |
| Melaço de cana | 1,22 | 1,08 | −11,5% |
| **Milho grão** | **1,24** | **1,08** | **−13,2%** |
| Polpa cítrica | 1,25 | 1,06 | −15,0% |
| Soja em grão | 2,94 | 2,30 | −21,9% |
| Farelo de canola | 2,24 | 1,60 | −28,8% |
| Casca de soja | 1,15 | 0,81 | −29,3% |
| **Farelo de linhaça** | **2,79** | **1,83** | **−34,4%** |
| Farelo de girassol | 1,55 | 1,02 | −34,5% |

**Alimentos na dieta — quanto podem subir antes de serem substituídos:**

| Alimento | Preço atual (R$/kg MS) | Preço de saída | Aumento suportado |
|---|---:|---:|---:|
| Silagem de milho | 0,62 | 0,64 | +3,0% |
| Farelo de algodão | 2,00 | 2,07 | +3,3% |
| Farelo de soja 48% | 2,26 | 2,41 | +6,4% |
| Glúten de milho | 1,23 | 1,31 | +6,4% |
| Sorgo grão | 1,01 | 1,18 | +17,0% |
| Ureia | 2,53 | 3,37 | +33,4% |

**Regra prática para o comprador:** o milho passa a competir se o preço posto na
fazenda ficar abaixo de **~R$ 56/saca** (hoje R$ 64,87). O sorgo pode subir até
17% antes de perder espaço para o milho. Já o farelo de algodão e a silagem têm
margem estreita (~3%): pequenas altas mudam a fórmula.

---

## 8. Análise de sensibilidade

Foram usadas três abordagens complementares.

### 8.1 Sensibilidade local (um fator por vez)

Cada preço foi variado ±20% isoladamente.

![Tornado](fig_tornado.png)

A silagem de milho é o item de maior impacto: ±20% no seu preço move o custo em
cerca de ±5,7% (amplitude de R$ 3,01/dia). Seguem sorgo (R$ 2,29) e farelo de
soja (R$ 1,94). A linhaça tem impacto nulo porque não está na dieta.

### 8.2 Sensibilidade global (Sobol)

O método de Sobol varia **todos** os parâmetros ao mesmo tempo e decompõe a
variância da saída. O índice S1 mede o efeito isolado de cada fator; o ST mede o
efeito total, incluindo interações. Configuração: 10 preços de alimentos ±30%,
preço do leite ±20%, 512 amostras base (SALib), *bootstrap* de 100.

**Custo da ração:**

| Preço | S1 | ST |
|---|---:|---:|
| Silagem de milho | 0,381 | **0,392** |
| Farelo de soja 48% | 0,167 | **0,226** |
| Sorgo grão | 0,174 | **0,189** |
| Farelo de algodão | 0,091 | 0,129 |
| Milho grão | 0,044 | 0,082 |
| Glúten de milho | 0,047 | 0,051 |
| Demais (caroço, soja grão, trigo, linhaça) | ≤ 0,005 | ≤ 0,012 |

![Sobol custo](fig_sobol_custo.png)

**Margem sobre a ração (IOFC):** o preço do leite tem **ST = 0,98**. Todos os
preços de alimentos somados explicam menos de 2% da variância.

![Sobol IOFC](fig_sobol_iofc.png)

**Leitura:** a ração é a alavanca de **custo**, e nela os contratos de silagem e
farelo de soja importam mais que a busca por ingredientes alternativos. Mas a
alavanca da **margem** é o preço do leite.

A diferença entre ST e S1 do farelo de soja e do milho mostra **interações**:
o efeito do preço de um depende do preço dos outros, porque o simplex troca
ingredientes na base quando os preços relativos mudam.

### 8.3 Testes pareados (pairwise)

O *pairwise testing* foi avaliado e adaptado em duas formas:

**a) Cenário contra cenário sob os mesmos choques.** Foram sorteados 256
choques de preço (±20%). Cada choque foi aplicado a todos os cenários, e as
diferenças de custo foram comparadas com o teste de Wilcoxon pareado e IC
bootstrap de 95%. O pareamento remove o efeito comum de mercado.

| Comparação (B − iso) | Δ médio (R$/vaca/dia) | IC 95% | p |
|---|---:|---|---:|
| NASEM | +5,94 | 5,80 – 6,08 | < 0,001 |
| Intermediário | +1,79 | 1,73 – 1,86 | < 0,001 |
| Com linhaça 5% | +1,30 | 1,25 – 1,36 | < 0,001 |
| Sem sorgo | +0,98 | 0,89 – 1,08 | < 0,001 |
| Com milho 15% | +0,73 | 0,65 – 0,80 | < 0,001 |
| Máxima economia | −1,51 | −1,58 – −1,44 | < 0,001 |

Conclusão: a vantagem da dieta iso-energética sobre as alternativas não depende
de um preço específico; ela se mantém sob choques de mercado.

**b) Ingrediente contra ingrediente.** Para pares de substitutos, calculou-se o
preço de indiferença:

| Par | Resultado |
|---|---|
| Milho × sorgo | O sorgo pode subir +17,0% antes de o milho voltar. |
| Farelo de soja × farelo de algodão | O farelo de algodão pode subir só +3,3%. |
| Farelo de soja × linhaça | A linhaça teria de cair −34,4%. |
| Farelo de soja × soja em grão | A soja em grão teria de cair −21,9%. |
| Glúten de milho × farelo de trigo | O farelo de trigo teria de cair −9,3%. |

![Preço de indiferença](fig_break_even.png)

---

## 9. Validação no RuFaS

O PL é uma aproximação linear do NASEM. Para verificar se a dieta "funciona" no
modelo completo, ela foi convertida em `feed_otimizado.json` e simulada no
RuFaS:

- modo `animals_only` (isola o efeito nutricional), 1 ano (2015);
- seeds 44, 45 e 46 para basal e iso-energética; seed 44 para NASEM;
- a ração é imposta como `user_input` e o RuFaS recalcula exigências, consumo,
  leite e metano.

| Cenário | Seed | Leite (kg/dia, lote) | CMS (kg/vaca/dia) | CH₄ (g/kg leite) |
|---|---|---:|---:|---:|
| Basal | 44 | 3.657 | 25,39 | 8,20 |
| Basal | 45 | 3.726 | 25,47 | 8,17 |
| Basal | 46 | 3.738 | 25,57 | 8,24 |
| Iso-energética | 44 | 3.715 | 25,11 | 7,48 |
| Iso-energética | 45 | 3.710 | 25,11 | 7,45 |
| Iso-energética | 46 | 3.734 | 25,28 | 7,50 |
| NASEM | 44 | 3.697 | 24,71 | 8,07 |

![Validação no RuFaS](fig_validacao.png)

**Médias (iso vs. basal):** leite 3.720 vs. 3.707 kg/dia (+0,3%, estável); CMS
−1,2%; metano entérico por kg de leite **−8,8%**. O sinal é consistente nas
três seeds, mas, com só 3 repetições, o Wilcoxon tem baixo poder (p = 0,25).

---

## 10. Limitações

1. **Estudo exploratório.** Fazenda sintética, preços de um dia e validação de
   1 ano. Não é validação científica nem recomendação de campo.
2. **Linearização.** O NASEM é não linear. O PL usa TDN, PB e RUP digestível
   como proxies. O RuFaS serve de ponte para o modelo completo.
3. **Preços.** São uma fotografia de outubro/2026. Subprodutos (sorgo, CGF,
   farelo de algodão, linhaça) têm maior incerteza; alguns são estimativas.
4. **Mistura mineral.** ~61% da economia vem dela. A premissa de 3% da basal
   pode não refletir a prática de uma fazenda real.
5. **Escopo.** Só a ração da vaca em lactação. Não inclui bezerras, novilhas,
   vacas secas, armazenamento, perdas, mão de obra ou custos fixos. O resultado
   é economia de ração e IOFC, **não lucro**.
6. **Energia.** A dieta iso-energética não corrige o déficit teórico do NASEM.
   A dieta NASEM corrige, mas custa mais.
7. **Ureia.** 0,4% da MS exige adaptação gradual e mistura uniforme.
8. **Validação curta.** `animals_only`, 1 ano, 3 seeds. Não avalia dejetos,
   solo, lavouras nem efeitos de longo prazo.

## 11. Trabalhos futuros

- Rodar `full_farm` por 5 anos com as dietas basal e iso-energética.
- Substituir as estimativas de preço por cotações reais da fazenda.
- Incluir uma restrição ou penalidade de metano (preço de carbono).
- Revisar a premissa da mistura mineral da dieta basal.
- Aumentar o número de seeds da validação.

---

## 12. Conclusão

O trabalho entregou um módulo de pesquisa operacional que conversa com o RuFaS
nos dois sentidos: **usa** o calculador NASEM e a biblioteca de alimentos do
simulador e **devolve** uma dieta pronta para ser simulada.

1. O problema da dieta foi formulado como PL e resolvido pelo simplex. A dieta
   iso-energética custa **R$ 26,07/vaca/dia (−19%)**, com economia potencial de
   **~R$ 197 mil/ano**.
2. O quadro final do simplex traduz a solução em linguagem de negócio. A RUP é
   a exigência mais cara (R$ 6,41/kg), e cada ponto de TDN custa R$ 0,63. O
   milho só compete abaixo de ~R$ 56/saca, e a linhaça teria de cair 34%.
3. A sensibilidade mostra que o custo depende da silagem de milho, do farelo de
   soja e do sorgo. A margem depende do preço do leite (ST ≈ 0,98). A vantagem
   da dieta ótima se mantém sob choques de preço (testes pareados, p < 0,001).
4. No RuFaS, a dieta manteve o leite e reduziu a intensidade de metano em 8,8%.

A principal ressalva é que parte relevante da economia vem da correção da
mistura mineral e que a validação é de curto prazo. O próximo passo é a
simulação da fazenda completa com preços reais.

---

## Apêndice A — Reprodutibilidade

```bash
# Análise completa (Sobol 512, testes pareados 256)
python -m diet_optimization

# Versão rápida (Sobol 128, testes pareados 64)
python -m diet_optimization --fast

# Inclui a validação de 1 ano no RuFaS
python -m diet_optimization --run-rufas

# Rodar a dieta otimizada diretamente no RuFaS
python main.py -p GO_campo_dourado/otimizacao_dieta/_otimizacao_task_manager_metadata.json -v errors

# Testes do módulo
python -m pytest tests/test_diet_optimization -q
```

## Apêndice B — Arquivos de saída

Todos em `GO_campo_dourado/otimizacao_dieta/`:

| Arquivo | Conteúdo |
|---|---|
| `feed_otimizado.json`, `farm_metadata_otimizado.json`, `config_otimizado.json` | Dieta e configuração prontas para o RuFaS |
| `dieta_iso.csv`, `dieta_nasem.csv`, `dieta_basal.csv`, `cenarios.csv` | Dietas e comparação de cenários |
| `quadro_simplex.csv`, `faixas_rhs.csv`, `faixas_preco.csv`, `break_even.csv` | Quadro final do simplex e sensibilidade local |
| `sensibilidade_oat.csv`, `sobol_custo.csv`, `sobol_iofc.csv` | Sensibilidade OAT e global |
| `pairwise_cenarios.csv`, `pairwise_break_even.csv` | Testes pareados |
| `validacao_resumo.csv`, `validacao_testes.csv` | Validação no RuFaS |
| `fig_*.png` | Gráficos usados neste relatório |

## Referências

- CEPEA/ESALQ/USP. Indicador do milho ESALQ/BM&FBovespa, 27/10/2026. https://www.cepea.org.br/br/indicador/milho.aspx
- CEPEA/ESALQ/USP. Indicador da soja — Paranaguá, 27/10/2026. https://www.cepea.org.br/br/indicador/soja.aspx
- CEPEA/ESALQ/USP. Leite ao produtor — Goiás, ago/2026. https://www.cepea.org.br/br/indicador/leite.aspx
- Agrolink. Farelo de soja — Anápolis/GO, 27/10/2026. https://www.agrolink.com.br/cotacoes/diversos/farelo-de-soja
- NASEM. *Nutrient Requirements of Dairy Cattle*, 8th ed. National Academies Press, 2021.
- Ruminant Farm Systems (RuFaS), v1.0.5. https://github.com/RuminantFarmSystems/RuFaS
- Herman, J.; Usher, W. SALib: an open-source Python library for sensitivity analysis. *JOSS*, 2017.
- Saltelli, A. et al. *Global Sensitivity Analysis: The Primer*. Wiley, 2008.
- Virtanen, P. et al. SciPy 1.0. *Nature Methods*, 2020.
- Huangfu, Q.; Hall, J. Parallelizing the dual revised simplex method (HiGHS). *Math. Prog. Computation*, 2018.
- Dantzig, G. B. The diet problem. *Interfaces*, 20(4), 1990.
