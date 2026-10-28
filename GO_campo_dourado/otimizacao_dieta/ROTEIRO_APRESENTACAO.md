# Roteiro de apresentação — Otimização da dieta (versão simples)

> **Ideia central:** não é para mostrar código nem o relatório de 20 páginas.
> São 5 slides com o problema, o método, o resultado, a sensibilidade e a
> validação. O resto fica como apêndice/backup.
>
> **Material interativo:** abra `drops_aprendizado_v4.html` no navegador. É uma
> trilha de 10 capítulos com trilho de progresso, índice e quiz: só abre o próximo
> portão quem acerta. Cada erro explica por que aquela alternativa está errada.
>
> **Versão editorial alternativa:** `drops_aprendizado_v3.html`, com estética de
> caderno de campo, glossário clicável, anotações salvas e controle de tamanho do
> texto.
>
> **Versão temática:** `drops_aprendizado_pirulito.html`, com uma estética
> original de fazenda de doces inspirada no universo pop dos pirulitos (sem uso
> de marca ou logo Chupa Chups).

---

## Slide 1 — O problema

**Título:** Qual dieta dá o menor custo sem perder nutrição?

- Fazenda leiteira em Goiás: **100 vacas**, sendo **88,6 em lactação**.
- Produção média: **41,3 kg de leite/vaca/dia**; consumo de **25,3 kg de MS/vaca/dia**.
- A dieta basal do RuFaS tem silagem de milho, silagem de leguminosa, milho, farelo de soja, caroço de algodão e mistura mineral.
- Preços usados: **CEPEA** (milho, soja, leite) e **Agrolink/cotações regionais** (farelo de soja em Anápolis e subprodutos), outubro/2026.
- Pergunta: **quais ingredientes e em que proporções** atendem às exigências ao menor custo?

**Frase para falar:** “Não queremos a dieta mais barata possível a qualquer custo; queremos a mais barata que ainda atenda energia, proteína, fibra e minerais.”

---

## Slide 2 — O método, sem complicar

**Título:** Programação linear: o simplex escolhe a mistura

- **Variável de decisão:** kg de MS/dia de cada alimento (19 alimentos candidatos).
- **Objetivo:** minimizar o custo total da ração.
- **Restrições:**
  - consumo de MS = 25,3 kg/dia;
  - proteína bruta ≥ 17,5%;
  - NDF entre 28% e 33% (fibra);
  - amido entre 25% e 35%;
  - cálcio e fósforo absorvíveis;
  - proteína não degradável (RUP) ≥ 1,2 kg/dia;
  - limites de inclusão de cada alimento.
- **Solver:** `scipy.optimize.linprog`, método **dual simplex** (HiGHS).
- **O que o simplex entrega:** a dieta ótima e o **preço sombra** de cada restrição.

**Explicação de 1 frase para o professor:**
“O simplex começa com uma solução viável e troca ingredientes até não existir
nenhuma troca que reduza o custo; o último quadro mostra quais restrições estão
‘apertando’ a dieta e quanto custaria afrouxá-las.”

**Preço sombra (exemplos):**
- +1 ponto percentual de TDN custa cerca de **R$ 0,63/vaca/dia**.
- +1 ponto percentual de proteína bruta custa cerca de **R$ 0,15/vaca/dia**.
- +1 kg de RUP digestível custa cerca de **R$ 6,41/vaca/dia**.

---

## Slide 3 — Resultado principal

**Título:** A dieta otimizada custa 19% menos

| Dieta | Custo (R$/vaca/dia) | vs. basal |
|---|---:|---:|
| Basal do RuFaS (com preços de GO) | 32,17 | — |
| **Otimizada iso-energética** | **26,07** | **−19,0%** |
| Otimizada atendendo NASEM (mais energia) | 31,60 | −1,8% |

- Economia: **R$ 6,10/vaca/dia**.
- Para 88,6 vacas: **≈ R$ 197 mil/ano**.
- Custo por kg de leite: **R$ 0,78 → R$ 0,63**.
- Margem sobre o custo da ração (IOFC): **R$ 86,89 → R$ 92,99/vaca/dia** (+7,0%).

**Dieta otimizada (iso-energética):**

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

**Mensagem:** o milho grão não entrou porque, aos preços atuais, o sorgo e o
glúten de milho entregam energia mais barata. A mistura mineral caiu de 3% para
0,5% + calcário.

---

## Slide 4 — Sensibilidade: o que muda a decisão?

**Título:** Os preços que mais importam

**Sensibilidade local (variação de ±20% em um preço por vez):**
- Silagem de milho: ±20% no preço → cerca de **±5,7%** no custo da ração.
- Sorgo: ±20% → cerca de **±4,7%**.
- Farelo de soja: ±20% → cerca de **−5,2% / +2,2%**.

**Sobol (varia todos os preços ao mesmo tempo, ±30%):**
- Silagem de milho: **ST ≈ 0,39** (39% da variância do custo).
- Farelo de soja: **ST ≈ 0,23**.
- Sorgo: **ST ≈ 0,19**.
- Linhaça: **ST ≈ 0,00** (não está na dieta).

**Na margem (IOFC), o preço do leite domina:** ST ≈ **0,98**.

**Preço de indiferença (quando o alimento entra):**
- Milho grão: só entra se cair para **≈ R$ 56/saca** (−13%).
- Farelo de linhaça: só entra se cair para **≈ R$ 1,83/kg MS** (−34%).
- Sorgo pode subir **≈ 17%** antes de o milho assumir o espaço.

**Frase para falar:** “A ração é uma alavanca de custo, mas o preço do leite é a
alavanca de receita. Negociar leite importa mais do que perseguir o último
centavo na ração.”

---

## Slide 5 — Validação e limitações

**Título:** A dieta funciona no RuFaS?

- Simulação `animals_only`, **1 ano (2015)**, seeds 44, 45 e 46.
- Leite: **3.720 kg/dia** com a dieta otimizada vs. **3.707 kg/dia** da basal → estável.
- Consumo de MS: **−1,2%**.
- Metano entérico por kg de leite: **−8,8%**.
- A dieta NASEM também manteve o leite, mas custa **R$ 5,53/vaca/dia** mais que a iso-energética.

**Limitações (dizer com tranquilidade):**
- O modelo é uma **aproximação linear** do NASEM; o RuFaS é a validação.
- Preços são uma **fotografia** de outubro/2026; subprodutos têm mais incerteza.
- Validação de **1 ano e 3 seeds**; não é prova de longo prazo.
- O custo é só da **ração da vaca em lactação**, não da fazenda inteira.
- Cerca de **61% da economia** vem da troca da mistura mineral; se a fazenda já usa uma mistura mais barata, a economia cai.
- A dieta usa **ureia**; exige adaptação gradual e mistura uniforme.

**Conclusão em 1 frase:**
“A dieta iso-energética é a recomendação econômica; a NASEM é a opção
conservadora. O próximo passo é rodar `full_farm` e validar com os preços e a
dieta reais da fazenda.”

---

## Perguntas prováveis (respostas curtas)

**1. Por que o milho não entrou?**
Porque, por unidade de energia, o sorgo e o glúten de milho estão mais baratos.
O milho só entra se cair para cerca de R$ 56/saca.

**2. Por que a linhaça não entrou?**
Porque o farelo de linhaça está caro para o que entrega de proteína/energia.
Só entraria com queda de ~34%. Se a fazenda quiser leite com apelo funcional
(ômega-3), o prêmio é de ~R$ 1,22/vaca/dia; é decisão de mercado, não de mínimo custo.

**3. O que é preço sombra?**
É quanto o custo aumenta se a restrição ficar 1 unidade mais apertada. Ex.:
+1 p.p. de TDN custa ~R$ 0,63/vaca/dia. Ajuda a saber qual exigência é “cara”.

**4. O que é Sobol?**
É uma análise de sensibilidade global: varia todos os preços ao mesmo tempo e
mede quanto cada um contribui para a variação do custo. Diferente de variar um
por vez.

**5. Isso é seguro nutricionalmente?**
A dieta atende às restrições impostas e foi validada no RuFaS por 1 ano. Mas é
uma aproximação linear; o ideal é acompanhar escore corporal, consumo e leite, e
rodar `full_farm`.

**6. Qual é o lucro?**
O trabalho calcula **economia de custo de ração** e **IOFC**, não lucro líquido.
Não entram custos fixos, mão de obra, capital, bezerras, novilhas e vacas secas.

**7. Por que a dieta NASEM custa quase o mesmo que a basal?**
Porque ela exige mais energia (TDN 76,99% vs. 72,12%). O ganho de segurança
nutricional consome quase toda a economia. A iso-energética é mais barata, mas
mantém o mesmo TDN da basal; não corrige o déficit teórico do NASEM.

**8. O que é o quadro final do simplex?**
É a tabela que mostra a solução ótima, os custos reduzidos (quanto um alimento
precisa cair para entrar) e os preços sombra (quanto custa apertar/relaxar cada
restrição). Está no apêndice do relatório.

---

## O que NÃO precisa mostrar

- O código inteiro (`diet_optimization/`).
- O relatório de 20 páginas.
- Todos os índices de Sobol, todas as faixas de RHS, todos os CSVs.
- O quadro simplex completo (só o conceito e 2–3 preços sombra).

Leve o relatório em PDF/HTML como **backup** e use os 5 slides.

---

## Frase de abertura

“O trabalho resolve um problema clássico de pesquisa operacional: formular a
dieta de menor custo que atenda às exigências nutricionais de um lote de vacas.
Usamos programação linear, preços de Goiás e validação no RuFaS.”

## Frase de fechamento

“O resultado principal é uma dieta 19% mais barata, com leite estável e menor
intensidade de metano na validação. A principal ressalva é que parte da economia
vem da correção da mistura mineral e que a validação é de curto prazo; o próximo
passo é rodar a fazenda completa e validar com os preços reais.”
