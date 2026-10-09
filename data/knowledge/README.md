# Base de Conhecimento Agronômica — Hort.IA

Base própria e reduzida, construída por decisão da Ata de Execução nº 2 (01/10/2026) enquanto as
demais equipes não definem as bases oficiais. Todo registro cita a fonte e a página, e nasce como
`draft`; ao alinhar com a Assistência Técnica Digital, os registros passam a `validated_by_atd`.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `crops.json` | 15 culturas do MVP: janelas de plantio por região, espaçamento, propagação, produtividade |
| `guidelines.json` | Regras gerais (sol, irrigação, espaçamento em pequenos espaços, pH, clima, rotação, plantas repelentes) |
| `pests_diseases.json` | Mapeamento das classes do modelo de visão computacional para manejo |
| `companions.csv` | Relações de plantio companheiro entre as 15 culturas, com nível de evidência |
| `sources.json` | Registro das fontes citadas por esta base |

## Hierarquia de fontes (quando divergem)

1. **Catálogo Brasileiro de Hortaliças (2010)**: janelas de plantio e início de colheita, por região e
   tipo de cultivar. É a única fonte com dados para as cinco regiões.
2. **Horta em Pequenos Espaços (2012), Tabela 2**: espaçamento convencional e reduzido, propagação e
   tempo de mudas. Sua época de plantio vale só para Sudeste, Centro-Oeste, norte do Sul e sul do
   Nordeste, por isso não é usada quando o Catálogo tem o dado.
3. **Circular Técnica 47 (2007)**: produtividade em 10 m², grupos de hortaliças e regras gerais.
4. **Fontes específicas por cultura**, apenas onde as três anteriores não têm dado. Hoje: manjericão
   (folder Embrapa Pantanal, 2006; Documentos 136 da Embrapa Agroindústria Tropical, 2011).

## Convenções

- Espaçamento em cm, na ordem *entre linhas × entre plantas*.
- `months_by_region`: região com `[]` = "não recomendável" na fonte; região ausente = sem dado.
- `pages` usa o número **impresso** na página.
- Uma cultura pode combinar janelas de fontes diferentes, desde que cada região apareça uma só vez
  por tipo de cultivar. Interpretações da fonte (ex.: "final da primavera" = nov-dez) ficam em `notes`.
- O HPE tem todos os direitos reservados: guardar apenas dados factuais e texto parafraseado.
- O script `scripts/build_crops_v1.py` registra como a primeira versão foi transcrita.

## Plantio companheiro

As relações têm três níveis de evidência, que o motor e o assistente devem tratar de forma diferente:

| `evidence` | Origem | Onde fica |
|---|---|---|
| `technical` | Publicações da Embrapa | `companion_roles` em `crops.json` e diretrizes em `guidelines.json` |
| `research` | Estudos de consórcio (ainda não levantados) | `companions.csv` |
| `traditional` | Wikipedia, via dataset do Kaggle | `companions.csv` |

- As publicações da Embrapa não trazem pares "A ajuda B": trazem **papéis** (manjericão e cebolinha como
  repelentes, CT 47 p. 12 e HPE p. 30) e **regras** (rotação por família, CT 47 pp. 10-11; flores como
  abrigo de inimigos naturais). Por isso não viram linhas no `companions.csv`.
- `mutual=true`: a relação vale nos dois sentidos. Todo "avoid" do dataset é mútuo.
- `mechanism=unknown` em todas as linhas tradicionais: o dataset não informa o motivo e não inventamos.
- O mesmo par pode aparecer mais de uma vez, desde que em fontes diferentes.

**Conversão do dataset** (`scripts/build_companions_v1.py`, decisões documentadas no código):

- Nomes agrupados ("brassicas", "nightshades", "alliums", "cucurbits") foram expandidos para as culturas
  da KB que pertencem a eles; "brassicas" inclui só couve e repolho (rúcula e rabanete não são
  *Brassica oleracea*).
- Conflitos: relação sobre a própria cultura prevalece sobre a herdada de grupo. Três pares ficaram
  de fora por contradição só entre grupos: batata-couve, batata-repolho e couve-tomate.
- Rúcula ficou sem nenhuma relação: não aparece no dataset.

## Conflitos entre fontes

| Cultura | Divergência | Decisão |
|---|---|---|
| Rúcula | Colheita: Catálogo 40-60 dias × HPE 25-30 dias | Catálogo |
| Cenoura | Espaçamento: HPE 20×10 cm × CT 47 20×5 cm | HPE |
| Abobrinha | Colheita: Catálogo 45-60 × HPE 60-90 dias | Catálogo |
| Tomate | Colheita: Catálogo 100-120 × HPE 90-100 dias | Catálogo |
| Cebolinha | Colheita: Catálogo 80-100 × HPE 70-90 dias | Catálogo |

## Lacunas conhecidas

- **Plantio companheiro**: rúcula sem relações; nenhuma relação com evidência `research` ainda.
- **Batata**: sem espaçamento para pequenos espaços (ausente na Tabela 2 do HPE) e sem diretriz de
  irrigação (grupo "tubérculo" não coberto pelo CT 47).
- **Manjericão**: sem janela mensal para Nordeste e Norte. A única orientação disponível (Doc. 136) é
  cultivar em campo aberto no período quente, ou em vasos o ano todo.
- **Rúcula e manjericão**: sem produtividade de referência. Para rúcula, só foram encontrados
  experimentos isolados, com resultados de 0,7 a 3,3 kg/m² conforme o manejo, que não servem como
  valor de referência; para manjericão, nenhuma das fontes informa produtividade. Se a base financeira
  precisar desses números, eles devem entrar lá como premissa documentada.
- Nenhuma fonte traz exigência de sol ou água **por cultura**; isso fica em `guidelines.json`, por grupo
  (e por cultura, quando a fonte é específica).

## Lacunas resolvidas

| Data | Lacuna | Resolução |
|---|---|---|
| 2026-10 | Manjericão sem janela no Sul | Folder Embrapa (2006): final da primavera → nov-dez |
| 2026-10 | Manjericão sem diretriz de irrigação | Doc. 136, p. 20: irrigação diária |
