# GO Campo Dourado — estado e pendências

**Última execução:** 19/10/2026, 20:43
**Resultado:** 0 erros, 443 avisos
**Modo:** `full_farm` · 2015–2019 · 100 vacas Holstein

## Arquivos

- Entradas: `GO_campo_dourado/inputs_resolvidos/`
- Saída bruta: `output/CSVs/GO_campo_dourado_*.csv` (535 MB, fora do Git)
- Logs: `output/logs/GO_campo_dourado_*`
- Infográfico: `GO_campo_dourado/INFOGRAFICO_RESULTADOS.pdf` e `.png`

## Correções já aplicadas

1. `animal.json` → `animal_config.from_literature.culling` recebeu os quatro campos do esquema 1.0.5:
   - `annual_death_prob = 0.05`
   - `parity_death_dist = [0.2, 0.3, 0.5]`
   - `annual_sale_prob = 0.32`
   - `parity_sale_dist = [0.2, 0.3, 0.5]`
2. `_pipeline_tasks.json` → `random_seed` (singular) corrigido para `random_seeds: [44]`.

> Atenção: a execução registrada no infográfico usou a seed automática **2.857.049.512**, porque a correção da seed foi feita depois. Para reprodutibilidade, rode novamente.

## Números da execução

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

## Pendências para a próxima sessão

1. **Rerodar com seed 44** para gerar a linha de base reproduzível.
2. **Alinhar o cenário ao Brasil/GO:**
   - `FIPS_county_code` está 55025 (Wisconsin);
   - latitude/longitude dos campos estão em NY/IL;
   - biblioteca de alimentos é do Nordeste dos EUA.
3. **Calibrar o armazenamento de dejetos:** 30 t CH₄/ano = 57% do CO₂e. Verificar temperatura, área e cobertura.
4. **Investigar as 20 falhas de colheita** e a ausência de safra em 2015–2016.
5. **Não usar o carbono do solo:** caiu ~44% em 5 anos (156→86 t C/ha e 146→82 t C/ha), resultado implausível.
6. **Completar emissões de ração:** faltam os feeds 216 (calf starter) e 301 (mineral mix).
7. **Verificar o storage 108** (alfalfa hay) não mapeado para nenhum alimento disponível.
8. **`feed_goias.json` não está ligado ao `farm_metadata.json`.** A simulação de
   referência usa `feed.json` (biblioteca do Nordeste dos EUA, com preços em US$).
   O arquivo `feed_goias.json` tem uma dieta e preços diferentes, mas não é
   referenciado por nenhum metadata. O módulo `diet_optimization/` usa o
   `feed.json` como dieta basal e aplica preços de Goiás na otimização; se a
   intenção era rodar o RuFaS com `feed_goias.json`, é preciso trocar o caminho
   em `farm_metadata.json` e validar a dieta no simulador.

## Comando para rerodar

```powershell
cd C:\CC\RuFaS
.\.venv\Scripts\python.exe main.py -p .\GO_campo_dourado\_pipeline_task_manager_metadata.json -v warnings
```
