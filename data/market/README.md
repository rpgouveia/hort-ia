# Base de Dados de Mercado — Conab (WBS 9.5.1-7)

Entregável de **9.5.1-7 Coletar e adicionar base de dados/informações no repositório**,
predecessor de 9.5.1-3 (definição da abordagem) e insumo de 9.5.1-4 (comparação de preços).
Alimenta a entrega **9.5 Matching Comercial e Preços de Referência**.

> Duas observações sobre o planejamento, para quem retomar isto depois:
> a atividade 9.5.1-7 **não está** na `docs/IA-GPMA.xlsx` versionada no repositório (foi
> acrescentada depois); e o Dicionário da EAP lista "coleta, tratamento e disponibilização dos
> dados de preços e mercado" como *exclusão* de 9.5, atribuindo-a a 9.1.1-2/9.1.1-4. Na prática
> esta base foi construída dentro de 9.5.1-7 — vale alinhar a redação dos dois documentos.

Fonte única: **Conab, Boletim Hortigranjeiro — tabelas de dados, edição de setembro de 2026**.
Escopo desta versão: **hortaliças** (alface, batata, cebola, cenoura, tomate) nos 12 entrepostos
(Ceasas) acompanhados pelo boletim. As abas de frutas ficaram fora.

Carregue com `hort_ia.market` (loader próprio, independente da base agronômica):

```bash
uv run python -m hort_ia.market      # relatório de cobertura
```

## Arquivos

| Arquivo | Conteúdo | Grão | Linhas |
|---|---|---|---|
| `products.json` | Os 5 produtos cotados, com o vínculo opcional para `data/knowledge/crops.json` | produto | 5 |
| `entrepostos.json` | As 12 Ceasas: cidade, UF, região e todas as grafias da fonte | entreposto | 12 |
| `prices_reference.csv` | Preço do mês de referência + variação mensal + média ponderada nacional | produto × entreposto | 55 |
| `prices_monthly.csv` | Série histórica de preços (25 meses) | produto × entreposto × mês | 1367 |
| `quantities.csv` | Volume comercializado nos 3 meses publicados | produto × entreposto × mês | 150 |
| `volume_totals.csv` | Total de hortaliças comercializado nas Ceasas analisadas | categoria × mês | 32 |
| `supply_microregions.csv` | Ranking das 20 maiores microrregiões fornecedoras | produto × posição | 100 |
| `supply_uf.csv` | Oferta por UF (partição completa) | produto × UF | 61 |
| `sources.json` | Registro das fontes citadas por esta base (só a Conab) | fonte | 1 |

## Mês de referência: ago/2026, não set/2026

Todas as abas têm o título "Setembro de 2026" e `Preços-Hortaliças!E3` guarda o serial `46266`
(= 01/09/2026), **mas esse é o mês da edição, não dos dados**. As evidências:

1. O preço do snapshot é idêntico ao último mês da série: `Preços-Alface!Z5` =
   `Preços-Hortaliças!B6` = `3,2329679...`, e o cabeçalho `Z4` é o serial `46235` = 01/08/2026.
2. `Q-Total-Hortaliças!B19` diz literalmente *"Comparativo ago/26 jul/26 (mês anterior)"*.
3. As abas `Quantidade-*` estão corretamente rotuladas "Agosto de 2026".

Logo o subcabeçalho `Jul/Jun` em `Preços-Hortaliças!C5` é um rótulo desatualizado: o valor é a
variação ago/jul (`3,2330 / 4,5947 − 1 = −0,2964`). O script `scripts/build_market_v1.py`
reconfere o item 1 a cada execução e aborta se o snapshot divergir da série.

## Convenções

- Preços em **R$/kg**, arredondados a 2 casas (a fonte traz ruído de float: `3.2329679316297173`).
- Variações mensais com 4 casas, como fração (`-0.2964` = queda de 29,64%).
- Quantidades em **kg inteiros**.
- Meses no formato `YYYY-MM`.
- **Ausência nunca é `0`.** Na fonte, dado faltante vem como `0` ou `#DIV/0!`; aqui a linha
  simplesmente não existe. Por isso toda medida é estritamente positiva no schema — um preço `0`
  contaminaria qualquer comparação. As ausências são recuperáveis comparando com
  `entrepostos.json` e aparecem no relatório de cobertura.
  Atenção: variação `0` **é dado** ("preço estável"), e é mantida.
- `entrepost_id` vazio em `prices_reference.csv` = linha **`Média Ponderada`**, a média nacional
  ponderada por volume. Não é recalculável a partir das outras linhas: a Conab não publica os pesos.
- `crop_id` nulo = produto fora das 15 culturas do MVP em `data/knowledge/crops.json`.
- Em `SourceRef`, **`pages` guarda o nome da aba** (ex.: `"Preços-Alface"`).
- Os registros **não** têm `validation_status`: a Conab é fonte oficial publicada, não uma
  transcrição da equipe aguardando revisão agronômica, então o fluxo
  `draft → validated_by_atd` da base agronômica não se aplica.

## Lacunas conhecidas

- **CEASA/GO e CEASA/DF não publicaram nada nesta edição** (preço `0` e variação `#DIV/0!`): sem
  preço de referência e sem volume. A série histórica de Goiânia existe; a de Brasília tem só 3
  dos 25 meses.
- Volumes só em 3 meses (ago/2025, jul/2026, ago/2026) — é tudo o que o boletim publica.
- `supply_microregions.csv` é um **top 20 truncado: não é somável** e não serve para calcular
  participação de mercado. Para isso use `supply_uf.csv`, que é uma partição completa.
- `supply_uf.csv` aceita `UF = NI` ("não informado"), usado em cebola e cenoura.
- A série de preços é esparsa por entreposto; o relatório de cobertura mostra o preenchimento.
- `cebola` tem dados de mercado mas nenhum registro agronômico; `morango` é o inverso.
- `volume_totals.csv` cobre **todas** as hortaliças (não só as 5) e a lista de "Ceasas
  consideradas" (`Q-Total-Hortaliças!F5:F16`) é uma cesta diferente da das tabelas de preço: ela
  cita `CEASA/SC - FLORIANOPOLIS` (a mesma unidade de São José) e `CEASA/RS - PORTO ALEGRE`, que
  não aparece em nenhuma tabela de preço. Não tente conciliar os totais com a soma por entreposto.
- Volume de 2026 parcial (jan–ago).
- A planilha bruta **não é versionada** (`.gitignore` exclui `data/*`, exceto as bases versionadas como `data/knowledge/` e `data/market/`).

## Atualização mensal

1. Baixar as tabelas de dados da nova edição no portal da Conab/Prohort.
2. Ajustar em `scripts/build_market_v1.py`: `BULLETIN_EDITION`, `REFERENCE_MONTH`,
   `SERIES_FIRST`/`SERIES_LAST` e `QUANTITY_MONTHS`.
3. `uv run python scripts/build_market_v1.py caminho/para/boletim.xlsx` — o script aborta se um
   entreposto mudar de nome ou se o snapshot não bater com a série, e lista as lacunas da fonte.
4. `uv run pytest tests/test_market_dataset.py -v` e atualizar as constantes de escopo do teste.
