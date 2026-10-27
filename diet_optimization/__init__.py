"""Módulo de otimização linear de dietas integrado ao RuFaS.

O módulo lê a composição de alimentos do RuFaS (NASEM_Comp.csv), uma tabela de
preços (CEPEA/cotações regionais) e a dieta basal executada no RuFaS, resolve um
problema de programação linear (PL) de mínimo custo e gera:

- dieta ótima em base de matéria seca (MS);
- avaliação econômica (R$/vaca/dia, R$/kg de leite, margem sobre o custo da ração);
- análise de sensibilidade local (preços sombra, custos reduzidos, faixas de RHS);
- análise de sensibilidade global (Sobol) e testes pareados;
- quadro final do simplex com leitura econômica;
- arquivos de integração para rodar a dieta no RuFaS.

O pacote é um complemento ao RuFaS: não altera o núcleo do modelo e conversa com
ele pelos arquivos de entrada e saída.
"""

from .config import load_config, load_baseline, load_scenarios
from .feed_library import Feed, load_feeds
from .requirements import Requirements, build_requirements, compute_nasem_requirements
from .lp_model import DietLP, DietSolution

__all__ = [
    "Feed",
    "load_feeds",
    "Requirements",
    "build_requirements",
    "compute_nasem_requirements",
    "DietLP",
    "DietSolution",
    "load_config",
    "load_baseline",
    "load_scenarios",
]
