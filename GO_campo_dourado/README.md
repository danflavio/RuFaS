# Fazenda Sintética — GO_campo_dourado (RuFaS)

Fazenda sintética leiteira gerada para o modelo **RuFaS**, pronta para ser
executada de forma autocontida. Esta pasta traz todos os arquivos de entrada
já resolvidos (rebanho, alimentação, clima de Goiás, solo, cultura, etc.),
o metadata com os caminhos ajustados e os arquivos de task para rodar a
simulação com um único comando.

- **Cenário:** conservador (100 vacas, manejo base)
- **Estado / clima:** Goiás (GO)
- **Período da simulação:** 2015 a 2019 (5 anos)
- **Tipo de simulação:** `full_farm`
- **Última execução de referência:** 0 erros, 443 avisos

---

## Como rodar (Windows · PowerShell)

### 1. Pré-requisitos

- Python **3.12 ou 3.13**
- Git
- ~1 GB de espaço livre

### 2. Criar o ambiente e instalar

```powershell
cd C:\caminho\para\RuFaS
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" `
  "pandas==2.3.2" "numba==0.61.2" "scipy==1.16.2" "matplotlib==3.10.5"
```

> Use `-e` (instalação editável). O `pip install .` normal gera um pacote
> sem os subpacotes (`RUFAS.biophysical`, `RUFAS.EEE` etc.).
> Não use `constraints-release.txt`: ele é da v1.0.0 e conflita com o
> `pyproject.toml` atual.

### 3. Verificar a instalação

```powershell
.\.venv\Scripts\python.exe -c "import numpy, pandas, numba, SALib, RUFAS.biophysical; print('OK')"
```

### 4. Rodar a simulação

```powershell
.\.venv\Scripts\python.exe main.py -p .\GO_campo_dourado\_pipeline_task_manager_metadata.json -v warnings
```

Rode **da raiz do RuFaS**, não de dentro de `GO_campo_dourado/`.
A simulação de 5 anos leva alguns minutos e consome CPU/RAM.

### 5. Conferir o resultado

```powershell
Get-ChildItem output\CSVs, output\logs -File |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 10
```

Saídas:

```
output/CSVs/GO_campo_dourado_*.csv     variáveis diárias
output/logs/GO_campo_dourado_*         avisos, erros e logs
```

O infográfico está em `INFOGRAFICO_RESULTADOS.pdf` (e `.png`);
o estado e as pendências estão em `PENDENCIAS.md`.

> A task já está corrigida para `"random_seeds": [44]`. A execução que
> gerou o infográfico usou a seed automática `2.857.049.512`; a próxima
> execução será a linha de base reproduzível.

---

## Observações importantes

- A pasta `GO_campo_dourado/` já está no repositório; **não é necessário
  extrair ZIP**. Os caminhos no `farm_metadata.json` são relativos à raiz
  do RuFaS (ex.: `GO_campo_dourado/inputs_resolvidos/config.json`).
- Rode o comando a partir da raiz do RuFaS.
- A pasta `output/` não é versionada: o CSV pode passar de 500 MB.
- A task usa `random_seeds: [44]` para reprodutibilidade.

---

## Resultados de referência (execução de 19/10/2026)

| Indicador | Valor |
|---|---:|
| Leite médio | 3.701 kg/dia |
| Leite por vaca em lactação | 41,2 kg/dia |
| Leite total (5 anos) | 6.758 t |
| Vacas em lactação / secas | 89,9 / 11,6 |
| Consumo de MS | 3.418 kg/dia |
| Metano entérico | 20,1 t CH₄/ano |
| Metano de armazenamento | 30,0 t CH₄/ano |
| Metano total | 50,9 t CH₄/ano |
| CO₂e estimado | 1.477 t/ano |
| Intensidade | 1,09 kg CO₂e/kg leite |
| Ração comprada | 94,4% |
| Custo de ração | US$ 0,22/kg leite |
| Erros / avisos | 0 / 443 |

> Leia as ressalvas em `PENDENCIAS.md`: seed, FIPS/latitude/feed dos EUA,
> armazenamento de dejetos e carbono do solo ainda precisam de validação.

---

## Conteúdo da pasta

| Item | Descrição |
| --- | --- |
| `farm_metadata.json` | Índice dos inputs da fazenda (caminhos já ajustados). |
| `_pipeline_task_manager_metadata.json` | Aponta para o task file (usado no `-p`). |
| `_pipeline_tasks.json` | Define a task de simulação (output_prefix, seed, etc.). |
| `inputs_resolvidos/` | Todos os arquivos de entrada usados na simulação. |
| `parametrizacao.json` / `.md` | Resumo da parametrização / cenário da fazenda. |
| `INFOGRAFICO_RESULTADOS.pdf` / `.png` | Infográfico com os resultados. |
| `PENDENCIAS.md` | Estado da execução e o que falta validar. |
| `README.md` | Este arquivo. |
| `otimizacao_dieta/` | Módulo de otimização da dieta, relatório, gráficos e arquivos de integração. |

---

## Otimização da dieta (módulo novo)

A pasta `otimizacao_dieta/` contém o relatório, os gráficos e os arquivos de
integração gerados pelo módulo `diet_optimization/`, que formula a dieta da vaca
em lactação ao mínimo custo, com análise econômica e de sensibilidade. Para
rodar:

```powershell
.\.venv\Scripts\python.exe -m diet_optimization
```

O relatório completo está em `otimizacao_dieta/RELATORIO_OTIMIZACAO_DIETA.md`
(versões para leitura: `RELATORIO_OTIMIZACAO_DIETA.html` e `.pdf`).
Para entender o problema de forma interativa, abra
`otimizacao_dieta/drops_aprendizado.html` no navegador: são 10 drops na
fazenda, com quiz e avanço somente após acertar. Há também a versão temática
`otimizacao_dieta/drops_aprendizado_pirulito.html` (fazenda de doces) e a
`otimizacao_dieta/drops_aprendizado_v3.html` (fontes maiores, glossário,
anotações salvas e controle de leitura).
A dieta recomendada foi validada no RuFaS (`animals_only`, 1 ano) e o
`feed_otimizado.json` gerado pode ser usado no lugar do `feed.json` para
reproduzir a simulação. Veja `diet_optimization/README.md` para o método,
fontes de preço e limitações.
