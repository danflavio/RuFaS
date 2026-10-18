# Relatório técnico básico — RuFaS (Ruminant Farm Systems)

**Data:** 18/10/2026
**Versão do modelo:** 1.0.5
**Cenário executado:** `animals_only` (somente rebanho)
**Ambiente:** Windows, Python 3.13.14, `.venv` local, instalação editável (`pip install -e`)

---

## 1. Sumário executivo

Foi executada uma simulação de **7 anos** (2013–2019) de uma fazenda leiteira de **100 vacas Holstein**, no modo `animals_only`, que simula **apenas o rebanho**. O modelo produziu, em média:

- **3.739 kg de leite/dia** (≈ **1.365 t/ano**);
- **41,3 kg de leite por vaca em lactação/dia**;
- **90,6 vacas em lactação** e **11,2 vacas secas** em média;
- **27,9 kg de matéria seca (MS) consumida por vaca em lactação/dia**;
- **82,2 kg de metano entérico/dia** (≈ **30 t CH₄/ano**);
- **22 g de CH₄ por kg de leite**.

A execução terminou com **0 erros** e **145 avisos** (nenhum crítico). O tempo observado foi de aproximadamente **3 minutos**.

> **Importante:** este modo não simula dejetos, solo, culturas nem estoque de alimento. Os resultados cobrem **produção animal, consumo e metano entérico**, não a pegada ambiental completa da fazenda.

---

## 2. O que é o RuFaS

O **RuFaS** é um simulador científico *whole-farm* de fazendas leiteiras, de código aberto (GPL-3.0), mantido pela comunidade `RuminantFarmSystems`. Ele integra quatro módulos biológicos:

| Módulo | Função |
|---|---|
| **Animal** | Rebanho, nutrição (NASEM/NRC), crescimento, reprodução, lactação, excreção |
| **Manure** | Manejo de dejetos: handler, separador, digestor, armazenamento e emissões |
| **Field** | Solo e cultura: ciclos de C, N e P, água, erosão, produtividade |
| **Feed Storage** | Silos, inventário, perdas e formulação de ração |

Além deles, o **EEE** (Emissions, Energy and Economics) calcula emissões, energia e economia — ainda parcialmente integrado.

O modo escolhido (`animals_only`) ativa **somente o módulo Animal**.

---

## 3. Cenário executado

| Parâmetro | Valor |
|---|---|
| Tipo de simulação | `animals_only` |
| Início | 2013, dia 1 |
| Fim | 2019, dia 365 |
| Duração | 2.556 dias simulados (`simulation_day` 0–2555) |
| Semente aleatória | 42 |
| Padrão nutricional | NASEM |
| Condado (FIPS) | 55025 — Dane County, Wisconsin (EUA) |
| Raça | Holstein (HO) |
| Valores detalhados (*data origins*) | desativados |
| Cross-validation | ativa (animal, feed, weather) |

### Rebanho inicial (input)

| Categoria | Quantidade |
|---|---:|
| Bezerras (calf) | 8 |
| Novilhas I | 44 |
| Novilhas II | 38 |
| Novilhas III (*springers*) | 5 |
| Vacas | 100 |
| Substituições disponíveis | 500 |
| Total de animais | ~195 |

### Manejo (input)

- **3 ordenhas por dia**;
- reprodução de vacas por **TAI** e de novilhas por **SynchED**;
- sêmen convencional;
- secagem aos **218 dias** de prenhez;
- mortalidade de bezerras e novilhas: **0%**;
- descarte por produção de leite, a partir de **60 dias em lactação**;
- gordura do leite: **4,0%**; proteína: **3,2%** (valores fixos de entrada, não simulados).

### Modelo de metano

| Categoria | Modelo |
|---|---|
| Bezerras | Pattanaik |
| Novilhas I, II e III | IPCC |
| Vacas secas e em lactação | IPCC |
| Mitigação | Nenhuma |

### Instalações

4 baias (*freestall*, galpão aberto):

| Baia | Categoria | Nº de baias individuais |
|---|---|---:|
| 0 | Bezerras | 15 |
| 1 | Crescimento | 90 |
| 2 | Pré-parto (*close-up*) | 22 |
| 3 | Vacas em lactação | 88 |

---

## 4. Dados de entrada (inputados)

O cenário usa o metadata `input/metadata/example_animals_only_metadata.json`, que referencia:

| Arquivo | Conteúdo | Destaque |
|---|---|---|
| `input/data/config/example_animals_only_config.json` | Configuração geral | 2013–2019, NASEM, FIPS 55025 |
| `input/data/animal/example_freestall_animal.json` | Rebanho, manejo, baias, ração, metano | 100 vacas, 4 baias, 3 ordenhas |
| `input/data/animal/animal_population.json` | Pool de animais para inicialização | 306 bezerras, 1.150 novilhas I, 1.044 novilhas II, 71 novilhas III, 2.662 vacas, 7.104 substituições |
| `input/data/animal_genetics/mean_phenotype.csv` | Fenótipo médio por ano de nascimento | — |
| `input/data/animal_genetics/TopListingSemen_HO.csv` | Sêmen Holstein | — |
| `input/data/animal/lactation_curve_adjustment_inputs.json` | Ajustes da curva de lactação | — |
| `input/data/feed/example_Midwest_feed.json` | Biblioteca de alimentos (10 itens) | Custos e limites de compra |
| `input/data/feed/NASEM_Comp_with_TDN_urea.csv` | Composição NASEM | — |
| `input/data/feed/user_feeds.csv` | Alimentos definidos pelo usuário | — |
| `input/data/weather/example_temperate_weather.csv` | Clima diário | 12.661 dias (1989–2023) |
| `input/data/EEE/*` | Custos, emissões e constantes | Usados parcialmente |
| `input/data/animal/no_animal.json` (não usado) | — | — |
| `no_field`, `no_soil`, `no_crop` | Desativam campo/solo/cultura | — |
| `no_manure_processor_*` | Desativam manejo de dejetos | — |
| `no_feed_storage_*` | Desativam silos | — |
| `no_tractor_dataset` | Sem tratores | — |

### Ração

- Ração **definida pelo usuário** (`user_input: true`);
- reformulação a cada **30 dias**;
- até **250 tentativas** de reformulação;
- sem buffer de fósforo.

### Clima

O arquivo cobre **1989–2023** (12.661 dias), mas a simulação usa apenas **2013–2019**. O modelo usa temperatura média, máxima, mínima, precipitação, graus-dia e irrigação.

---

## 5. O que o modo `animals_only` faz — e o que não faz

**Faz:**

- dinâmica do rebanho (nascimento, crescimento, transição entre categorias, descarte, morte);
- reprodução (estro, IA, prenhez, perda gestacional, parto);
- lactação (curva de Wood ajustada por ano) e produção de leite;
- exigências nutricionais (NASEM) e consumo;
- excreção de dejetos (massa, N, P, sólidos) — **calculada, mas não processada**;
- metano entérico.

**Não faz:**

- armazenamento, separação, digestão ou emissões de dejetos;
- solo, cultura, colheita, erosão, lixiviação;
- silos, inventário, perdas de alimento;
- restrição real de alimento: **todo pedido de ração é atendido como comprado**;
- análise econômica completa (EEE).

---

## 6. Dados gerados (output)

### Arquivos

| Arquivo | Tamanho | Conteúdo |
|---|---:|---|
| `output/CSVs/animals_only_saved_variables_csv_all_variables.txt_*.csv` | 260 MB | 903 colunas × 260.062 linhas |
| `output/logs/*` | 54 arquivos | logs, avisos, erros, uso de variáveis |
| `output/graphics/leite_diario.png` | ~100 KB | gráfico gerado a partir do CSV |

> **Atenção:** o CSV é um *dump* plano. Apenas **2.556 linhas** têm `simulation_day` preenchido (as linhas diárias); as outras ~257 mil são registros de outros tipos, com `NaN` na maioria das colunas. Para analisar, selecione colunas com `usecols` e use `dropna`.
>
> Não foram gerados JSONs, relatórios nem gráficos nativos do RuFaS porque só o filtro `csv_all_variables.txt` estava habilitado. Para isso seriam necessários filtros `json_*`, `report_*` ou `graph_*` em `output/output_filters/`.

### Indicadores

| Indicador | Média | Mínimo | Máximo |
|---|---:|---:|---:|
| Leite total do rebanho (kg/dia) | **3.739,4** | 3.227,4 | 4.166,0 |
| Vacas em lactação | **90,6** | 77 | 104 |
| Vacas secas | **11,2** | 2 | 24 |
| Leite por vaca em lactação (kg/dia) | **41,3** | — | — |
| Consumo de MS por vaca em lactação (kg/dia) | **27,9** | 25,4 | 29,5 |
| Dejeto úmido da baia de lactação (kg/dia) | **7.143** | 5.495 | 8.180 |
| Metano entérico total (kg/dia) | **82,2** | — | — |
| Metano entérico por vaca em lactação (kg/dia) | **0,61** | — | — |
| Intensidade de metano (g CH₄/kg leite) | **22,0** | — | — |

### Totais do período

| Indicador | Valor |
|---|---:|
| Leite produzido | **9.558 t** (≈ 1.365 t/ano) |
| Metano entérico | ≈ **30 t CH₄/ano** |
| Gordura do leite | 4,0% (fixo) |
| Proteína do leite | 3,2% (fixo) |

### Metano por baia (média diária)

| Baia | kg CH₄/dia |
|---|---:|
| Vacas em lactação | 55,62 |
| Crescimento (novilhas) | 21,31 |
| Pré-parto | 5,04 |
| Bezerras | 0,19 |
| **Total** | **82,17** |

---

## 7. Leitura dos resultados

1. **Produção por vaca (41,3 kg/dia)** é alta. Isso é coerente com **3 ordenhas/dia** e com uma dieta de alta energia; não é um valor típico de fazenda média (30–35 kg).
2. **Consumo de 27,9 kg MS/dia** está alinhado com vaca de alta produção. A relação leite/MS ≈ **1,48 kg leite por kg MS** é biologicamente plausível.
3. **Metano de 0,61 kg/vaca/dia** e **22 g/kg de leite** estão na faixa esperada para gado leiteiro de alta produção.
4. **Vacas secas (~11%)** e **90,6 em lactação** são compatíveis com o rebanho inicial de 100 vacas e a fração de lactação informada (0,8356).
5. **Dejeto de ~79 kg/vaca/dia** é coerente com ingestão e excreção de uma vaca adulta.
6. A produção **oscila pouco** (3.227–4.166 kg/dia), indicando estabilidade do rebanho no período.

---

## 8. Avisos (145) e qualidade dos dados

Nenhum erro. Os avisos se concentram em:

| Qtd. | Aviso | Impacto |
|---:|---|---|
| 132 | `no simulation_day available` ao montar `info_map` | Cosmético; afeta apenas rastreabilidade de algumas variáveis iniciais |
| 9 | Chaves opcionais ausentes no input (ex.: `minutes_away_for_milking` na baia de bezerras) | Baixo; o modelo usa valor padrão |
| 2 | Ajuste da curva de lactação indisponível para 2019 | Baixo; usou ajuste de 2016 |
| 2 | Vacas de **paridade 5** ausentes no `animal_population.json` | **Relevante**; o `HerdFactory` precisou gerar/amostrar de outra forma. Recomenda-se regenerar o arquivo de população |
| — | Aviso fixo "Under construction, use the results with caution" | Institucional |

**Recomendação:** gerar um novo `animal_population.json` com o comando de inicialização de rebanho do RuFaS para eliminar os avisos de paridade 5.

---

## 9. Como reproduzir

```powershell
# 1. ambiente
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" `
  "pandas==2.3.2" "numba==0.61.2" "scipy==1.16.2" "matplotlib==3.10.5"

# 2. filtro CSV
Rename-Item output\output_filters\_csv_all_variables.txt csv_all_variables.txt

# 3. wrapper de metadata (UTF-8 sem BOM!)
$json = @'
{
  "files": {
    "tasks": {
      "title": "Task manager data",
      "description": "Quick animals only run",
      "path": "input/data/tasks/example_animals_only_task.json",
      "type": "json",
      "properties": "tasks_properties"
    }
  }
}
'@
[System.IO.File]::WriteAllText("$PWD\input\metadata\quick_animals_tm_metadata.json", $json,
    (New-Object System.Text.UTF8Encoding($false)))

# 4. executar
.\.venv\Scripts\python.exe main.py -p input/metadata/quick_animals_tm_metadata.json -v warnings
```

---

## 10. Limitações deste relatório

- **Não é validação científica.** É uma execução de exemplo com dados de demonstração (EUA, Wisconsin).
- **Não representa uma fazenda brasileira.** Clima, dieta, preços e solos são dos EUA.
- O modo `animals_only` **não calcula a pegada ambiental completa**: faltam emissões de dejetos, solo e cultivo.
- O CSV é um dump bruto; os números acima foram extraídos por seleção de colunas e médias diárias.
- A produção de leite é influenciada por parâmetros fixos (3 ordenhas, 4% de gordura, 3,2% de proteína) e pela qualidade do pool de animais.

---

## 11. Próximos passos sugeridos

1. Rodar `full_farm` para obter a pegada completa (dejetos + solo + cultivo).
2. Gerar um `animal_population.json` próprio para remover os avisos de paridade 5.
3. Habilitar filtros `json_*` / `report_*` / `graph_*` para saídas menores e gráficos nativos.
4. Adaptar clima, dieta e preços para uma fazenda brasileira antes de qualquer conclusão local.
