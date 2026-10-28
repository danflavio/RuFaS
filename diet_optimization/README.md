# Módulo de otimização da dieta — RuFaS

Módulo de **programação linear (PL)** para formular a dieta da vaca em lactação ao
mínimo custo, integrado aos arquivos de entrada e saída do RuFaS. Gera dieta,
avaliação econômica, análise de sensibilidade local/global (Sobol), testes
pareados e os arquivos para rodar a dieta no simulador.

## Resultado principal

Com preços de Goiás de 27/10/2026 (CEPEA/Agrolink/cotações regionais):

| Dieta | Custo (R$/vaca/dia) | vs. basal |
|---|---:|---:|
| Basal do RuFaS (reavaliada com preços de GO) | 32,17 | — |
| **Iso-energética (recomendada)** | **26,07** | **−19,0%** |
| NASEM (TDN 76,99%) | 31,60 | −1,8% |
| Intermediária (74% TDN) | 27,92 | −13,2% |
| Com 15% de milho | 26,72 | −16,9% |
| Com 5% de linhaça | 27,28 | −15,2% |
| Sem sorgo | 27,14 | −15,6% |
| Máxima economia (sem RUP mínimo) | 24,83 | −22,8% |

A dieta iso-energética usa 48,6% de silagem de milho, 23,2% de sorgo, 12,6% de
glúten de milho, 9,2% de farelo de soja, 4,3% de farelo de algodão, 1,2% de
calcário, 0,5% de mistura mineral e 0,4% de ureia. Para 88,6 vacas, a economia
potencial é de cerca de **R$ 197 mil/ano**.

A validação no RuFaS (`animals_only`, 1 ano, seeds 44–46) manteve o leite
(3.720 vs. 3.707 kg/dia), reduziu o CMS em 1,2% e reduziu a intensidade de
metano entérico em 8,8%.

> **Cuidado:** 60,7% da economia vem da substituição da mistura mineral de 3%
> por calcário + fontes de fósforo mais baratas. Se a fazenda já usa uma mistura
> mineral mais barata, a economia cai. O cenário iso-energético mantém o mesmo
> TDN da dieta basal; ele **não** corrige o déficit teórico de energia do NASEM.

## Como rodar

```powershell
# Análise completa (Sobol 512, testes pareados 256)
.\.venv\Scripts\python.exe -m diet_optimization

# Versão rápida (Sobol 128, testes pareados 64)
.\.venv\Scripts\python.exe -m diet_optimization --fast

# Rodar também a validação de 1 ano no RuFaS
.\.venv\Scripts\python.exe -m diet_optimization --run-rufas
```

Saídas em `GO_campo_dourado/otimizacao_dieta/`:

- `RELATORIO_OTIMIZACAO_DIETA.md`, `.html` e `.pdf` — relatório completo;
- `drops_aprendizado.html` — trilha interativa de 10 drops com quiz e fazenda ilustrada;
- `drops_aprendizado_pirulito.html` — versão temática “fazenda de doces” da mesma trilha;
- `drops_aprendizado_v3.html` — versão 3, editorial, com fontes grandes, glossário, anotações salvas e controles de leitura;
- `drops_aprendizado_v4.html` — versão 4, layout de app de aprendizagem: trilho de progresso, índice, glossário e anotações salvas;
- `resultados.json` — resultados consolidados;
- `dieta_iso.csv`, `dieta_nasem.csv`, `dieta_basal.csv`;
- `quadro_simplex.csv`, `faixas_rhs.csv`, `faixas_preco.csv`;
- `sensibilidade_oat.csv`, `sobol_custo.csv`, `sobol_iofc.csv`;
- `pairwise_cenarios.csv`, `pairwise_break_even.csv`;
- `feed_otimizado.json`, `config_otimizado.json`,
  `farm_metadata_otimizado.json`, `_otimizacao_task_manager_metadata.json`;
- gráficos `fig_*.png`.

## Estrutura

| Arquivo | Função |
|---|---|
| `config.py` | Carrega configuração, dieta basal e cenários. |
| `feed_library.py` | Composição NASEM, preços, limites de inclusão. |
| `requirements.py` | Exigências NASEM + restrições práticas. |
| `lp_model.py` | Formulação e resolução do PL; duals e custos reduzidos. |
| `tableau.py` | Reconstrução do quadro final do simplex e faixas de RHS/preço. |
| `economics.py` | Custo, IOFC, economia anual, decomposição mineral. |
| `sensitivity.py` | OAT, Sobol, break-even, testes pareados. |
| `validation.py` | Sumarização das execuções de validação no RuFaS. |
| `integration.py` | Geração do `feed.json` e metadados para o RuFaS. |
| `report.py` | Relatório Markdown e gráficos. |
| `cli.py` | Interface de linha de comando. |

## Dados de entrada

- `GO_campo_dourado/inputs_resolvidos/NASEM_Comp.csv` — composição dos alimentos.
- `diet_optimization/data/prices_go_2026-10-27.csv` — preços e fontes.
- `diet_optimization/data/candidates.csv` — alimentos candidatos e limites.
- `diet_optimization/data/baseline_diet.json` — dieta basal do RuFaS.
- `diet_optimization/data/scenarios.json` — cenários de otimização.
- `GO_campo_dourado/baseline_daily.csv` — série diária extraída da execução basal.

Preços CEPEA: milho R$ 64,87/saca (27/10/2026), soja R$ 157,41/saca
(27/10/2026), leite GO R$ 2,9692/L (ago/2026). Farelo de soja em Anápolis/GO:
R$ 2.020/t (Agrolink, 27/10/2026). Subprodutos sem indicador público usam
cotação regional ou estimativa declarada no CSV.

## Método

- Variáveis: kg de MS/dia de cada alimento.
- Objetivo: minimizar custo total da ração.
- Restrições: DMI, PB, NDF, NDF de forragem, amido, extrato etéreo, TDN,
  Ca e P absorvíveis, relação Ca:P, RUP digestível e limites de inclusão.
- Solver: `scipy.optimize.linprog`, dual simplex (HiGHS).
- Sensibilidade local: preços sombra, custos reduzidos, faixas de RHS e preço
  de indiferença.
- Sensibilidade global: Sobol (SALib) sobre preços e preço do leite.
- Testes pareados: Wilcoxon + bootstrap sobre a mesma amostra de choques.

## Integração com o RuFaS

O `feed_otimizado.json` é uma cópia do `feed.json` com a ração `lac_cow`
substituída e os novos alimentos adicionados ao bloco `feeds`. O módulo também
gera `config_otimizado.json` (1 ano, `animals_only`) e os metadados/tasks para
rodar com `main.py -p`.

Para 5 anos `full_farm`, copie o `config.json` original e ajuste
`simulation_type` para `full_farm`. O CSV de saída pode passar de 500 MB.

## Limitações

- O PL é uma aproximação linear do NASEM; a validação no RuFaS é a ponte.
- Preços são uma fotografia; subprodutos têm incerteza maior.
- A validação é de 1 ano, 3 seeds, em rebanho sintético.
- O custo é o da ração da vaca em lactação, não o custo total da fazenda.
- A dieta usa ureia; exige adaptação e mistura uniforme.
- O efeito no CO₂e total depende de `full_farm` (dejetos, solo, culturas).

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_diet_optimization -q
```
