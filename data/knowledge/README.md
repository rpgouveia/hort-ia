# Base de Conhecimento Agronômica — Hort.IA

Base própria e reduzida, construída por decisão da Ata de Execução nº 2 (01/10/2026) enquanto as
demais equipes não definem as bases oficiais. Todo registro cita a fonte e a página, e nasce como
`draft`; ao alinhar com a Assistência Técnica Digital, os registros passam a `validated_by_atd`.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `crops.json` | 15 culturas do MVP: janelas de plantio por região, espaçamento, propagação, produtividade |
| `guidelines.json` | Regras gerais (sol, irrigação, espaçamento em pequenos espaços, pH, clima, rotação, plantas repelentes) |
| `pests_diseases.json` | Classes do modelo de visão computacional com sintomas e manejo por grupo (ver "Pragas e doenças") |
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

## Adaptação regional

O município informado pelo produtor é convertido em uma das cinco regiões do Catálogo por
`hort_ia.core.geo.region_from_ibge_code`, sem tabela auxiliar: o código IBGE do município traz a UF
nos dois primeiros dígitos, e o primeiro dígito da UF é a região (Curitiba, 4106902 → PR → Sul).
`Crop.planting_months(region)` devolve os meses por tipo de cultivar.

**Por que o ZARC não foi incorporado** (levantamento, seção 2.3). Verificação feita em out/2026:

- Entre as 15 culturas do MVP, só a **batata** tem Zarc (mesa e indústria, Portarias SPA/MAPA 222
  a 225/2025). As únicas outras hortaliças zoneadas são cebola e alho, e o Zarc de tomate previsto é
  para **processamento industrial**, não para tomate de mesa.
- O Zarc foi feito para crédito e seguro rural: dá o risco de perda (20%, 30% ou 40%) por município,
  decêndio de plantio e classe de água do solo, em lavouras **de sequeiro** na maior parte das
  portarias. As próprias portarias dizem que lavouras irrigadas não estão presas a esses períodos, e
  horta urbana é irrigada.
- Integrá-lo exigiria exportar tabelas do Painel de Indicação de Riscos por município para atender
  uma única cultura.

Decisão: as janelas continuam vindo do Catálogo (por região). O Zarc fica registrado em
`sources.json` como fonte verificada, para reavaliação quando houver zoneamento de mais hortaliças
de mesa.

## Pragas e doenças

`pests_diseases.json` liga cada classe do modelo de visão computacional a sintomas e manejo. As fontes
não trazem orientação por doença ou por praga, e sim **por grupo**: doenças causadas por fungos, por
bactérias e por vírus, e pragas como ácaros, lagartas, lesmas e formigas. Por isso o manejo de cada
entrada vem do seu grupo, a partir da CT 47 (pp. 11-14) e do HPE (pp. 28-30 e 37-40), e as notas
indicam quando não há orientação específica para a doença.

- **Sem defensivo químico**: a CT 47 (p. 12) restringe defensivos ao uso com acompanhamento de
  profissional qualificado. Os tipos de manejo são só `preventive`, `cultural`, `biological` e
  `alternative`.
- **Sem doses nem receitas**: caldas e preparados naturais (`alternative`) aparecem só pelo nome,
  sempre com "Peça orientação técnica antes de preparar ou aplicar". Um teste barra números seguidos
  de g, ml, litro ou % nas descrições.
- Cada ação cita uma fonte com página; quando a ação vem de duas fontes, a primeira fica na ação e as
  duas ficam em `sources` da entrada.
- O sintoma tem fonte própria em `symptoms_sources`, que também aparece em `sources` da entrada. O
  validador recusa uma entrada com `symptoms` e sem `symptoms_sources`, com qualquer status, e a
  integridade da base confere se essas fontes estão em `sources.json`.
- Tudo continua `draft` até a revisão com agrônomos (9.4.1-9).

**O que o assistente mostra** (`Responder.pest_disease`), conforme o `validation_status`:

| Status | Resposta |
|---|---|
| `draft` | "O que ajuda:" seguido só das ações `preventive`, `cultural` e `biological`; termina com "Para tratar, o melhor é falar com a Assistência Técnica." (`handoff`). Caldas e preparados não aparecem. |
| `reviewed` ou `validated_by_atd` | Todas as ações, inclusive `alternative`, sem forçar o encaminhamento. |
| Sem ação para mostrar | "Ainda não tenho uma orientação conferida..." e encaminhamento. |

Quando a entrada tem sintoma, a resposta mostra "Como reconhecer: ..." logo depois de "Parece ser: X.",
com qualquer status: o sintoma é descritivo e ajuda a pessoa a conferir se a identificação do modelo
bate com o que vê na planta. As fontes citadas na resposta são as do sintoma, seguidas das das ações
mostradas, sem repetir; as fontes das ações escondidas ficam de fora. Plantas sadias e insetos
benéficos (vespas) têm respostas próprias, sem sintoma nem manejo.

## Conflitos entre fontes

| Cultura | Divergência | Decisão |
|---|---|---|
| Rúcula | Colheita: Catálogo 40-60 dias × HPE 25-30 dias | Catálogo |
| Cenoura | Espaçamento: HPE 20×10 cm × CT 47 20×5 cm | HPE |
| Abobrinha | Colheita: Catálogo 45-60 × HPE 60-90 dias | Catálogo |
| Tomate | Colheita: Catálogo 100-120 × HPE 90-100 dias | Catálogo |
| Cebolinha | Colheita: Catálogo 80-100 × HPE 70-90 dias | Catálogo |

## Lacunas conhecidas

- **Adaptação regional**: janelas por macrorregião, não por município (ver acima).
- **Plantio companheiro**: rúcula sem relações; nenhuma relação com evidência `research` ainda.
- **Batata**: sem espaçamento para pequenos espaços (ausente na Tabela 2 do HPE) e sem diretriz de
  irrigação (grupo "tubérculo" não coberto pelo CT 47).
- **Manjericão**: sem janela mensal para Nordeste e Norte. A única orientação disponível (Doc. 136) é
  cultivar em campo aberto no período quente, ou em vasos o ano todo.
- **Rúcula e manjericão**: sem produtividade de referência. Para rúcula, só foram encontrados
  experimentos isolados, com resultados de 0,7 a 3,3 kg/m² conforme o manejo, que não servem como
  valor de referência; para manjericão, nenhuma das fontes informa produtividade. Se a base financeira
  precisar desses números, eles devem entrar lá como premissa documentada.
- **Pragas e doenças** (tudo pendente de validação com agrônomos, 9.4.1-9):
  - doenças causadas por fungos e por bactérias sem sintomas específicos: as fontes descrevem o grupo,
    e as murchas e podridões das bactérias não correspondem à mancha na folha que o modelo reconhece;
  - tesourinhas e gorgulhos sem sintomas nem manejo: nenhuma das fontes da base trata deles;
  - formigas e besouros sem decisão sobre serem pragas (`beneficial: null`): só as formigas-cortadeiras
    cortam folhas, e a classe de besouros pode incluir joaninhas, que são predadoras;
  - doença do morango (*Diplocarpon earlianum*) sem nome popular: a resposta usa o nome científico.
- Nenhuma fonte traz exigência de sol ou água **por cultura**; isso fica em `guidelines.json`, por grupo
  (e por cultura, quando a fonte é específica).

## Lacunas resolvidas

| Data | Lacuna | Resolução |
|---|---|---|
| 2026-10 | Manjericão sem janela no Sul | Folder Embrapa (2006): final da primavera → nov-dez |
| 2026-10 | Manjericão sem diretriz de irrigação | Doc. 136, p. 20: irrigação diária |
