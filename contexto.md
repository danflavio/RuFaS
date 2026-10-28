# Contexto do trabalho — Otimização da dieta no RuFaS

**Última atualização:** 27/10/2026  
**Branch:** `go-campo-dourado`  
**Repositório:** `C:\CC\RuFaS`  
**Objetivo do arquivo:** servir de handoff para outra IA (ou outra pessoa) entender
rapidamente o que foi pedido, o que foi feito, onde está e o que **não** precisa
ser refeito.

---

## 1. Pedido original

O trabalho precisa entregar:

1. **Desenvolvimento de um módulo de otimização da dieta integrado ao RuFaS.**
2. **Avaliação do efeito econômico** da dieta.
3. **Análise de sensibilidade.**

Anotações da aula/professor:

- Problema de otimização: dada uma fazenda com X animais, conhecer os requisitos
  nutricionais e otimizar os ingredientes para formular uma dieta que atenda às
  necessidades.
- Fazer **teste de sensibilidade**.
- Preços dos nutrientes podem vir do **CEPEA**.
- **Sobol** como técnica de análise de sensibilidade.
- **PairWise Testing** — validar se é possível usar.
- Avaliar se é possível usar **simplex** e explicar o **último quadro do simplex
  na perspectiva do negócio**.
- O professor disse para **mudar os ingredientes** (milho, linhaça etc.) e usar
  **pesquisa operacional** para saber o que era mais vantajoso.

Orientação posterior do usuário:

> “Não adianta mostrarmos um trabalho muito bom; sabemos da nossa limitação, um
> trabalho medíocre já está ótimo.”

> “O objetivo é entregar um trabalho que tenha uma dieta, avalie a questão da
> pesquisa operacional e mostre que de alguma forma fizemos alguma coisa para
> tentar entender esse repositório monstruoso.”

**Portanto:** o trabalho pode ser simples. O importante é ter uma dieta,
explicar a pesquisa operacional e mostrar que o repositório foi investigado. Não
é necessário apresentar o código inteiro nem o relatório de 20 páginas.

---

## 2. O repositório e a branch

- O RuFaS é um simulador *whole-farm* de fazendas leiteiras (versão 1.0.5).
- Branch usada: `go-campo-dourado`.
- Cenário `GO_campo_dourado`: fazenda sintética em Goiás, 100 vacas, sendo
  **88,56 vacas em lactação** em média, **41,3 kg de leite/vaca/dia** e
  **25,3 kg de MS/vaca/dia**.
- A ração da vaca em lactação é o pen `LAC_COW_PEN_3`.

### Descoberta importante sobre os arquivos de alimentação

- O `farm_metadata.json` do cenário aponta para
  `GO_campo_dourado/inputs_resolvidos/feed.json`.
- Esse `feed.json` usa a biblioteca de alimentos do **Nordeste dos EUA**, com
  preços em US$, e uma dieta basal com:
  - 30% silagem de milho;
  - 18% silagem de leguminosa;
  - 24% milho grão;
  - 16% farelo de soja;
  - 9% caroço de algodão;
  - 3% mistura mineral.
- Existe também o `feed_goias.json`, com uma dieta e preços diferentes, mas ele
  **não está ligado a nenhum metadata**. Ou seja, a simulação de referência não
  o utiliza.
- O módulo de otimização usa o `feed.json` como **dieta basal** e aplica preços
  de Goiás na otimização.

### Trabalho que já existia na branch

A branch já tinha uma pasta `diet_optimization/` do commit
`ffa61cc65 feat: ajuste dieta`. Era um esqueleto inicial do mesmo módulo.
O trabalho atual **continuou e completou** esse esqueleto; não começou do zero.

---

## 3. O que foi construído

### Código

Pacote `diet_optimization/` na raiz do repositório:

| Arquivo | Função |
|---|---|
| `config.py` | Carrega configuração, dieta basal e cenários. |
| `feed_library.py` | Lê composição NASEM, preços e limites de inclusão. |
| `requirements.py` | Calcula exigências NASEM com o próprio RuFaS + restrições práticas. |
| `lp_model.py` | Formula e resolve o PL; duals e custos reduzidos. |
| `tableau.py` | Reconstrói o quadro final do simplex e faixas de RHS/preço. |
| `economics.py` | Custo, IOFC, economia anual, decomposição mineral. |
| `sensitivity.py` | OAT, Sobol, break-even, testes pareados. |
| `validation.py` | Resume as execuções de validação no RuFaS. |
| `integration.py` | Gera `feed_otimizado.json` e metadados para o RuFaS. |
| `report.py` | Gera relatório Markdown, gráficos e tabelas. |
| `html_report.py` | Gera HTML e PDF do relatório (Edge/Chrome headless). |
| `cli.py` | Interface `python -m diet_optimization`. |

### Dados

- `diet_optimization/data/prices_go_2026-10-27.csv`
- `diet_optimization/data/candidates.csv`
- `diet_optimization/data/baseline_diet.json`
- `diet_optimization/data/scenarios.json`
- `diet_optimization/data/config.json`

### Saídas principais

Em `GO_campo_dourado/otimizacao_dieta/`:

- `RELATORIO_OTIMIZACAO_DIETA.md`
- `RELATORIO_OTIMIZACAO_DIETA.html`
- `RELATORIO_OTIMIZACAO_DIETA.pdf` (21 páginas)
- `ROTEIRO_APRESENTACAO.md` — **o arquivo mais importante para apresentar**
- `feed_otimizado.json` — dieta pronta para rodar no RuFaS
- `farm_metadata_otimizado.json`, `config_otimizado.json`,
  `_otimizacao_task_manager_metadata.json`, `_otimizacao_tasks.json`
- `dieta_iso.csv`, `dieta_nasem.csv`, `dieta_basal.csv`, `cenarios.csv`
- `quadro_simplex.csv`, `faixas_rhs.csv`, `faixas_preco.csv`
- `sensibilidade_oat.csv`, `sobol_custo.csv`, `sobol_iofc.csv`
- `pairwise_cenarios.csv`, `pairwise_break_even.csv`
- `validacao_resumo.csv`, `validacao_testes.csv`
- gráficos `fig_*.png`
- `resultados.json`

### Testes

`tests/test_diet_optimization/` — **14 testes passando**:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_diet_optimization -q
```

Também passam `black` e `flake8` no pacote novo.

---

## 4. Método de pesquisa operacional

### Formulação

- **Variáveis de decisão:** kg de MS/dia de cada alimento (19 alimentos
  candidatos).
- **Objetivo:** minimizar o custo total da ração (R$/vaca/dia).
- **Restrição de igualdade:** soma das MS = 25,3 kg/dia.
- **Restrições de desigualdade:**
  - proteína bruta ≥ 17,5% da MS;
  - NDF entre 28% e 33%;
  - NDF de forragem ≥ 18%;
  - amido entre 25% e 35%;
  - extrato etéreo entre 3% e 6%;
  - TDN mínimo (energia);
  - cálcio e fósforo absorvíveis;
  - relação Ca:P;
  - RUP digestível ≥ 1,2 kg/dia;
  - limites de inclusão de cada alimento.

O problema tem **19 variáveis e 37 restrições de desigualdade**, além da
igualdade de MS. Foi resolvido com `scipy.optimize.linprog`, método
**dual simplex** (HiGHS).

### Simplex e leitura de negócio

- O simplex começa com uma solução viável e troca ingredientes até não existir
  nenhuma troca que reduza o custo.
- O **quadro final** mostra:
  - a solução ótima (coluna RHS);
  - os **custos reduzidos**: quanto o preço de um alimento precisa cair para
    ele entrar na dieta;
  - os **preços sombra**: quanto custa apertar ou relaxar cada restrição.
- Exemplos de preços sombra da dieta iso-energética:
  - +1 p.p. de TDN ≈ **R$ 0,625/vaca/dia**;
  - +1 p.p. de proteína bruta ≈ **R$ 0,150/vaca/dia**;
  - +1 kg de RUP digestível ≈ **R$ 6,407/vaca/dia**;
  - +1 kg de MS de mistura mineral (mínimo de 0,5%) ≈ **R$ 6,052/vaca/dia**.

### Cenários

- **Iso-energético (recomendado):** TDN 72,12% (o mesmo da dieta basal),
  mantendo energia, proteína e fibra.
- **NASEM:** TDN 76,99%, corrigindo o déficit teórico de energia; NDF mínimo
  27,5% e Ca:P mínimo 1,2 para acomodar a alta densidade energética.
- **Intermediário:** TDN 74,0%.
- **Com milho 15%:** força pelo menos 15% de milho grão.
- **Com linhaça 5%:** força 5% de farelo de linhaça.
- **Sem sorgo:** simula indisponibilidade.
- **Máxima economia:** remove a exigência de RUP e reduz PB para 17,0%.

### Análise de sensibilidade

- **Local:** preço sombra, custo reduzido, faixas de RHS e preço de
  indiferença.
- **Global (Sobol):** 10 preços de alimentos ±30% e preço do leite ±20%;
  512 amostras; S1 e ST.
- **Testes pareados:** os mesmos choques de preço em todos os cenários;
  Wilcoxon + IC bootstrap de 95% (256 amostras).
- **Pairwise de ingredientes:** preço de indiferença entre pares (milho × sorgo,
  farelo de soja × farelo de algodão, farelo de soja × linhaça etc.).

### Validação no RuFaS

- Dieta convertida em `feed_otimizado.json`.
- Simulação `animals_only`, 1 ano (2015), seeds 44, 45 e 46.
- Comparação com a dieta basal nas mesmas condições.
- Modo `animals_only` isola o efeito nutricional; não inclui dejetos, solo,
  culturas nem custos completos da fazenda.

---

## 5. Resultados principais

### Custo e economia

| Dieta | Custo (R$/vaca/dia) | vs. basal |
|---|---:|---:|
| Basal do RuFaS (com preços de GO) | 32,17 | — |
| **Iso-energética (recomendada)** | **26,07** | **−19,0%** |
| NASEM (TDN 76,99%) | 31,60 | −1,8% |
| Intermediária (74% TDN) | 27,92 | −13,2% |
| Com 15% de milho | 26,72 | −16,9% |
| Com 5% de linhaça | 27,28 | −15,2% |
| Sem sorgo | 27,14 | −15,6% |
| Máxima economia (sem RUP mínimo) | 24,83 | −22,8% |

- Economia da iso-energética: **R$ 6,10/vaca/dia**.
- Para 88,56 vacas: **≈ R$ 197.199/ano**.
- Custo por kg de leite: **R$ 0,779 → R$ 0,631**.
- IOFC: **R$ 86,89 → R$ 92,99/vaca/dia** (+7,0%).
- Custo da ração como % da receita: **27,0% → 21,9%**.

### Dieta iso-energética

| Alimento | % da MS |
|---|---:|
| Silagem de milho | 48,6% |
| Sorgo grão | 23,2% |
| Glúten de milho (CGF) | 12,6% |
| Farelo de soja 48% | 9,2% |
| Farelo de algodão | 4,3% |
| Calcário calcítico | 1,2% |
| Mistura mineral | 0,5% |
| Ureia pecuária | 0,4% |

**Leitura:** o milho grão não entrou porque, por unidade de energia, o sorgo e o
glúten de milho estão mais baratos. A mistura mineral caiu de 3% para 0,5% +
calcário; o fósforo é suprido por farelo de algodão e glúten de milho.

### Validação no RuFaS

- Leite: **3.720 kg/dia** com a dieta otimizada vs. **3.707 kg/dia** da basal
  (estável).
- CMS: **−1,2%**.
- Metano entérico por kg de leite: **−8,8%**.
- A dieta NASEM também manteve o leite e reduziu levemente a intensidade de
  metano (−1,6% vs. basal no seed 44), mas custa **R$ 5,53/vaca/dia** mais que a
  iso-energética.

### Sensibilidade

- **Sobol — custo da ração:**
  - silagem de milho: ST ≈ **0,39**;
  - farelo de soja: ST ≈ **0,23**;
  - sorgo: ST ≈ **0,19**;
  - farelo de algodão: ST ≈ **0,13**;
  - milho grão: ST ≈ **0,08**;
  - linhaça: ST ≈ **0,00**.
- **Sobol — IOFC:** preço do leite tem ST ≈ **0,98**; os preços dos alimentos
  somam pouco.
- **Break-even:**
  - milho grão só entra se cair para ≈ **R$ 1,08/kg MS** (≈ **R$ 56/saca**,
    −13,2%);
  - farelo de linhaça só entra se cair para ≈ **R$ 1,83/kg MS** (−34,4%);
  - sorgo pode subir ≈ **17%** antes de o milho assumir o espaço;
  - farelo de algodão pode subir ≈ **3,3%** antes de o farelo de soja voltar.
- **Testes pareados (256 choques):**
  - iso vs. NASEM: +R$ 6,02/vaca/dia;
  - iso vs. com milho 15%: +R$ 0,72/vaca/dia;
  - iso vs. com linhaça 5%: +R$ 1,38/vaca/dia;
  - iso vs. sem sorgo: +R$ 0,99/vaca/dia;
  - iso vs. máxima economia: −R$ 1,46/vaca/dia;
  - todos com p < 0,001.

### Decomposição da economia

- Cerca de **60,7%** da diferença de custo está na linha de minerais
  (3% de mistura mineral → 0,5% + calcário).
- Os outros **39,3%** vêm da reformulação dos demais ingredientes.
- **Cuidado:** a decomposição é contábil. Parte do fósforo foi transferida para
  farelo de algodão e glúten de milho, cujo custo aparece nas outras linhas.
  O ganho líquido é a diferença total.
- Se a fazenda já usa uma mistura mineral mais barata, a economia será menor.
  O cenário “basal ajustado” (1% mineral + 1% calcário) custa R$ 29,52/vaca/dia,
  mas fica deficiente em P absorvível (~54 g/d vs. 64 g/d); não é um
  comparativo válido sem uma fonte de fósforo.

---

## 6. Preços usados

- **Milho:** R$ 64,87/saca de 60 kg (CEPEA, 27/10/2026).
- **Soja em grão:** R$ 157,41/saca (CEPEA Paranaguá, 27/10/2026).
- **Leite ao produtor — GO:** R$ 2,9692/L (CEPEA, ago/2026).
- **Farelo de soja — Anápolis/GO:** R$ 2.020/t (Agrolink, 27/10/2026).
- **Caroço de algodão:** referência regional R$ 1.200/t (Notícias
  Agrícolas/Scot; BA R$ 955/t, MT R$ 799/t).
- **Silagem de milho:** R$ 220/t matéria natural (Scot/ZS Máquinas; faixa
  R$ 190–220/t).
- **Demais subprodutos:** cotação regional ou estimativa declarada no CSV
  `prices_go_2026-10-27.csv`.
- **Câmbio:** R$ 5,35/US$ (Notícias Agrícolas, 27/10/2026).

---

## 7. Como rodar

```powershell
# Análise completa (Sobol 512, testes pareados 256)
.\.venv\Scripts\python.exe -m diet_optimization

# Versão rápida (Sobol 128, testes pareados 64)
.\.venv\Scripts\python.exe -m diet_optimization --fast

# Rodar também a validação de 1 ano no RuFaS
.\.venv\Scripts\python.exe -m diet_optimization --run-rufas

# Testes
.\.venv\Scripts\python.exe -m pytest tests\test_diet_optimization -q
```

Rodar a dieta otimizada no RuFaS:

```powershell
.\.venv\Scripts\python.exe main.py -p .\GO_campo_dourado\otimizacao_dieta\_otimizacao_task_manager_metadata.json -v errors
```

O comando acima usa `animals_only`, 1 ano, seed 44. Para `full_farm` de 5 anos,
copie o `config.json` original e ajuste `simulation_type` para `full_farm`.

---

## 8. O que apresentar (versão simples)

**Não apresentar o código inteiro nem o relatório de 21 páginas.**

Seguir `GO_campo_dourado/otimizacao_dieta/ROTEIRO_APRESENTACAO.md`:

1. **Problema:** qual dieta atende às exigências ao menor custo?
2. **Método:** PL, variáveis, objetivo, restrições; simplex e preço sombra.
3. **Resultado:** basal R$ 32,17 → otimizada R$ 26,07 (−19%); dieta e economia.
4. **Sensibilidade:** Sobol, break-even do milho/linhaça, preço do leite no IOFC.
5. **Validação e limitações:** RuFaS 1 ano, leite estável, metano −8,8%;
   aproximação linear, preços de outubro/2026, 1 ano/3 seeds, escopo da ração.

Levar o PDF/HTML como backup. Os gráficos mais fáceis de explicar são
`fig_dieta.png` e `fig_custo.png`.

---

## 9. Limitações e o que NÃO afirmar

1. **Não é validação científica.** É um estudo exploratório com fazenda
   sintética, preços de um dia e validação de 1 ano.
2. **O PL é uma aproximação linear do NASEM.** O RuFaS é a ponte para o modelo
   completo; o módulo não substitui o simulador.
3. **Preços são uma fotografia.** Subprodutos como sorgo, CGF, farelo de
   algodão e linhaça têm incerteza maior; alguns são estimativas declaradas.
4. **A validação é curta.** 1 ano, 3 seeds (NASEM só seed 44). Não prova
   comportamento de longo prazo.
5. **O custo é só da ração da vaca em lactação.** Não inclui bezerras, novilhas,
   vacas secas, armazenamento, perdas, mistura, mão de obra, energia, capital
   ou custos fixos.
6. **Não é lucro.** O trabalho calcula economia de custo de ração e IOFC, não
   lucro líquido.
7. **Cerca de 61% da economia vem da linha mineral.** Se a fazenda já usa uma
   mistura mais barata, a economia cai. A decomposição é contábil; o P foi
   transferido para outros alimentos.
8. **A dieta iso-energética não corrige o déficit teórico do NASEM.** Ela mantém
   o TDN da basal (72,12%). A dieta NASEM atende 76,99%, mas custa mais.
9. **Ureia exige cuidado.** A dieta usa 0,4% de ureia; adaptação gradual e
   mistura uniforme são obrigatórias.
10. **`feed_goias.json` não está ligado ao metadata.** A simulação de referência
    usa `feed.json` (Nordeste dos EUA). O módulo usa `feed.json` como basal e
    aplica preços de Goiás.

---

## 10. Estado do Git

- Branch: `go-campo-dourado`.
- Últimos commits:
  - `335d3a2a1 feat: ajuste dieta v2` — módulo, relatório, dados, testes,
    saídas, README/PENDENCIAS, `pyproject.toml`.
  - `e746e0681 feat: ajuste dieta v3` — caminhos relativos nos metadados,
    integração e PDF final.
- `HEAD` = `origin/go-campo-dourado` = `e746e0681`.
- Árvore de trabalho limpa no momento da criação deste arquivo (antes de
  adicionar o próprio `contexto.md`).
- Para conferir:

```powershell
git status
git log --oneline -3
git rev-parse HEAD origin/go-campo-dourado
```

---

## 11. Handoff para outra IA

**Leia nesta ordem:**

1. `GO_campo_dourado/otimizacao_dieta/ROTEIRO_APRESENTACAO.md`
2. `GO_campo_dourado/otimizacao_dieta/RELATORIO_OTIMIZACAO_DIETA.md`
3. `diet_optimization/README.md`
4. `diet_optimization/lp_model.py`
5. `diet_optimization/data/scenarios.json`

**Não refaça a otimização.** Ela já está pronta, testada e validada. Se o
usuário pedir para “melhorar”, priorize:

- rodar `full_farm` de 5 anos;
- substituir preços estimados por cotações reais da fazenda;
- testar uma restrição ou penalidade de metano;
- revisar a premissa da mistura mineral (3% na basal);
- aumentar o número de seeds da validação.

**Se o usuário pedir para apresentar,** use os 5 slides do roteiro. Não tente
explicar todo o código. A frase de fechamento é:

> “O resultado principal é uma dieta 19% mais barata, com leite estável e menor
> intensidade de metano na validação. A principal ressalva é que parte da
> economia vem da correção da mistura mineral e que a validação é de curto
> prazo; o próximo passo é rodar a fazenda completa e validar com os preços
> reais.”

---

## 12. Glossário rápido

- **PL:** programação linear; otimização com objetivo e restrições lineares.
- **Simplex:** algoritmo que resolve PL trocando variáveis na base até o ótimo.
- **Preço sombra:** quanto o custo muda se uma restrição for apertada/relaxada
  em uma unidade.
- **Custo reduzido:** quanto o preço de um alimento precisa cair para ele entrar
  na dieta.
- **Sobol:** análise de sensibilidade global; varia todos os parâmetros ao mesmo
  tempo e mede a contribuição de cada um.
- **Pairwise:** comparação pareada de cenários sob os mesmos choques de preço.
- **IOFC:** *income over feed cost*; receita do leite menos custo da ração.
- **TDN:** nutrientes digestíveis totais; proxy de energia.
- **RUP:** proteína não degradável no rúmen.
- **NDF:** fibra em detergente neutro; ligada à saúde ruminal.
- **DMI:** consumo de matéria seca.
- **CMS:** consumo de matéria seca (mesma coisa que DMI, em português).
