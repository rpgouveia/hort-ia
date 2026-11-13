# Base de Conhecimento Agronômica — Hort.IA

Base própria e reduzida, construída por decisão da Ata de Execução nº 2 (01/10/2026) enquanto as
demais equipes não definem as bases oficiais. Todo registro cita a fonte e a página, e nasce como
`draft`. Em nov/2026 a base recebeu a entrega v3 da Assistência Técnica Digital (ATD), fundida ao
formato atual (ver "Integração da entrega v3 da ATD").

## Status de validação

| `validation_status` | Significado | Efeito no assistente |
|---|---|---|
| `draft` | Curado pelo módulo de IA, ainda não conferido por outra equipe | Resposta cautelosa |
| `validated_by_atd` | Conferido pela ATD contra a fonte e a página citadas. **Não é aval agronômico**: a ATD não conta com profissional habilitado (LEIA-ME da entrega v3) | Igual a `draft` |
| `reviewed` | Revisado por agrônomo (9.4.1-9). A ATD não usa este status | Manejo completo, sem encaminhamento obrigatório |

Consequências (decisão D1 da integração): `validated_by_atd` não libera caldas e preparados
(`alternative`) nem tira o encaminhamento à Assistência Técnica, que é atribuição da ATD. A exigência
de registro completo (`missing_fields`) vale só para `reviewed`: um registro conferido pela ATD pode
ter lacunas (hortelã sem época, formigas sem decisão entre praga e benéfica).

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `crops.json` | 20 culturas (15 do MVP e 5 da entrega v3 da ATD): janelas de plantio por região, espaçamento, propagação, produtividade e, desde a v3, germinação, profundidade de semeadura, irrigação, pH, sol, rotação e temperaturas |
| `guidelines.json` | Regras gerais (sol, irrigação, espaçamento em pequenos espaços, pH, clima, rotação, plantas repelentes, semeadura) |
| `pests_diseases.json` | Classes do modelo de visão computacional com sintomas e manejo (ver "Pragas e doenças") |
| `companions.csv` | Relações de plantio companheiro, com nível de evidência (ver "Plantio companheiro") |
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
- O script `scripts/build_crops_v1.py` registra como a primeira versão foi transcrita;
  `scripts/merge_atd_v3.py`, como a entrega v3 da ATD foi fundida.
- **Campos da v3 em `crops.json`** (`germination`, `sowing_depth_cm`, `irrigation`, `soil_ph`, `sun`,
  `rotation`, `dev_temp`, `soil_temp`): todo valor preenchido exige `source` com página; um bloco sem
  valor é aceito desde que `notes` diga onde a busca foi feita e por que não há dado. Ainda não são
  usados pelo motor nem pelo assistente. `rotation.avoid_after` tem de ser igual às culturas da base da
  mesma família (`family`), conferido por teste.

## Plantio companheiro

As relações têm três níveis de evidência, que o motor e o assistente devem tratar de forma diferente:

| `evidence` | Origem | Onde fica |
|---|---|---|
| `technical` | Publicações da Embrapa | `companion_roles` em `crops.json`, diretrizes em `guidelines.json` e, desde a v3, 7 pares em `companions.csv` |
| `research` | Estudos publicados (v3: 7 testes de germinação com extrato, em placa de Petri) | `companions.csv` |
| `traditional` | Wikipedia, via dataset do Kaggle | `companions.csv` (37 relações) |

**Relações fora das saídas (decisão D6).** Ficam na base, mas não chegam à pontuação do motor, aos
motivos e avisos da recomendação, à resposta do assistente nem à rota `/recommender/companion-crops`:

- as relações `research`: as 7 recebidas são testes de germinação de sementes com extrato ou óleo
  essencial em placa de Petri, sem plantio junto, e uma delas tem aviso de possível erro de cópia no
  artigo. Elas não dizem o que acontece quando as plantas crescem lado a lado;
- as relações cuja fonte não está registrada como verificada em `sources.json` (hoje, as 7 `technical`
  da v3, que citam duas fontes ainda sem metadados).

O filtro fica num ponto só, `KnowledgeBase.is_usable` (`usable_companions` e `usable_companions_of`),
usado por todos os consumidores, para as rotas continuarem coerentes entre si. Hoje as 14 relações da
v3 estão fora; as 37 tradicionais seguem valendo. Quando a ATD enviar os metadados e confirmar as
relações, basta marcar a fonte como verificada (as `technical`) ou rever a regra (as `research`).

- As publicações da Embrapa trazem sobretudo **papéis** (manjericão, cebolinha, coentro e hortelã como
  repelentes, CT 47 p. 12 e HPE p. 30) e **regras** (rotação por família, CT 47 pp. 10-11; flores como
  abrigo de inimigos naturais), que não viram linhas no `companions.csv`.
- Na resposta do assistente, a nota final segue a evidência das relações mostradas (D9): só
  tradicionais, "Essas combinações vêm do costume de quem planta..."; tradicionais e técnicas, "Algumas
  dessas combinações têm indicação técnica..."; só técnicas, "Essas combinações têm indicação técnica."
- Nas linhas da v3, o texto livre que a ATD escreveu na coluna `mechanism` foi para o início de `notes`
  (o campo aceita só os valores do modelo): `allelopathy` nas `research` e `unknown` nas `technical`.
- `mutual=true`: a relação vale nos dois sentidos. Todo "avoid" do dataset é mútuo.
- `mechanism=unknown` em todas as linhas tradicionais: o dataset não informa o motivo e não inventamos.
- O mesmo par pode aparecer mais de uma vez, desde que em fontes diferentes.

**Conversão do dataset** (`scripts/build_companions_v1.py`, decisões documentadas no código):

- Nomes agrupados ("brassicas", "nightshades", "alliums", "cucurbits") foram expandidos para as culturas
  da KB que pertencem a eles; "brassicas" inclui só couve e repolho (rúcula e rabanete não são
  *Brassica oleracea*).
- Conflitos: relação sobre a própria cultura prevalece sobre a herdada de grupo. Três pares ficaram
  de fora por contradição só entre grupos: batata-couve, batata-repolho e couve-tomate.
- Rúcula ficou sem nenhuma relação tradicional: não aparece no dataset. A v3 trouxe duas `research`
  (couve e hortelã reduzindo a germinação da rúcula), fora das saídas pela D6.

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
entrada vem do seu grupo, a partir da CT 47 (pp. 11-14), e as notas indicam quando não há orientação
específica para a doença. Desde a v3, os textos das ações e dos sintomas são os da ATD.

- **Tipo do manejo por regra (D2).** A ATD envia cada ação como `{action, source}`, sem tipo. O texto
  da ATD vira `description`, sem alteração, e o `type` sai da primeira regra que casar, nesta ordem:
  `alternative` (calda, extrato, preparado, defensivo natural, óleo, sabão, fumo, nim/neem, infusão),
  `biological` (Bacillus thuringiensis, baculovírus, Trichogramma, controle biológico, inimigo natural
  liberado), `preventive` (semente, muda sadia, cultivar resistente, certificada) e `cultural` (o
  resto). A regra está em `scripts/merge_atd_v3.py` (`classify`) e um teste confere que todo `type` da
  base a segue. A classificação de cada ação foi enviada à ATD (`docs/knowledge/atd/retorno_v3/`).
- **`crop_scope`** (v3): `all_vegetables` nas pragas, que a CT 47 descreve como "as que atacam as
  hortaliças", com `crop_ids` vazio (vale para as 20 culturas); `specific` nas classes ligadas a uma
  cultura, com `crop_ids` preenchido. O validador recusa a combinação incoerente.
- **Vespas** têm `type: beneficial` (v3, CT 47 pp. 12-13). `beneficial: true` continua aceito; nos dois
  casos a entrada não tem ações e o assistente responde que o inseto ajuda a horta.

- **Sem defensivo químico**: a CT 47 (p. 12) restringe defensivos ao uso com acompanhamento de
  profissional qualificado. Os tipos de manejo são só `preventive`, `cultural`, `biological` e
  `alternative`.
- **Sem doses nem receitas**: caldas e preparados naturais (`alternative`) aparecem só pelo nome e
  nunca são mostrados pelo assistente fora de entradas `reviewed` (teste sobre todas as entradas, em
  `draft` e em `validated_by_atd`). Um teste barra números seguidos de g, ml, litro ou % nas descrições.
- Cada ação cita uma fonte com página, que também aparece em `sources` da entrada.
- O sintoma tem fonte própria em `symptoms_sources`, que também aparece em `sources` da entrada. O
  validador recusa uma entrada com `symptoms` e sem `symptoms_sources`, com qualquer status, e a
  integridade da base confere se essas fontes estão em `sources.json`.
- **Fonte do sintoma na v3 (D3).** Nas 10 doenças, a página indicada no PDF de validação da ATD
  (pedido 6). Nas pragas: texto igual ao anterior, mantida a fonte; texto novo, a fonte que as notas,
  o PDF ou o próprio texto da ATD indicam (formigas, besouros, tesourinhas e vespas); sem indicação,
  mantido o sintoma anterior com sua fonte, a entrada fica em `draft` e o texto proposto pela ATD vai
  para `notes` (ácaro-rajado, lagartas, gafanhotos, mariposas, lesmas e caracóis). Begomovirose e
  mosaico vieram sem sintoma e mantêm o anterior.
- Nenhuma entrada é `reviewed`: isso depende da revisão com agrônomos (9.4.1-9).

**O que o assistente mostra** (`Responder.pest_disease`), conforme o `validation_status`:

| Status | Resposta |
|---|---|
| `draft` ou `validated_by_atd` | "O que ajuda:" seguido só das ações `preventive`, `cultural` e `biological`; termina com "Para confirmar o problema e saber como tratar, fale com a Assistência Técnica." (`handoff`). Caldas e preparados não aparecem. |
| `reviewed` | "O que ajuda:" seguido de todas as ações, inclusive `alternative`; termina com "Se tiver dúvida sobre o problema, fale com a Assistência Técnica.", sem ligar o `handoff`. |
| Sem ação para mostrar | "Ainda não tenho uma orientação conferida..." e encaminhamento. Acontece também quando todas as ações são `alternative` (besouros). |

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
| Tomate (v3) | Germinação: SENAR-PR (p. 49) ótima 18-24 °C × Coleção Plantar 5 (p. 11) 20-25 °C | SENAR-PR (mais detalhado e do Paraná); o outro valor em `germination.alt_source` (decisão da ATD) |
| Alface (v3) | Germinação: Epagri BD 107 (p. 34) ótima 24 °C, faixa 4-27 °C × SENAR-PR (p. 44) faixa 15-25 °C | Epagri (tabela comparável entre espécies); SENAR-PR em `alt_source` (decisão da ATD) |

## Integração da entrega v3 da ATD (nov/2026)

A ATD partiu da base de 20/10, anterior ao trabalho em pragas e doenças, e mandou arquivos para
substituir os desta pasta. Validados contra o modelo atual, davam 126 erros em `crops.json`, 214 em
`pests_diseases.json` e 5 em `guidelines_novas.json`, e citavam 4 fontes não registradas. Por isso a
entrega foi **fundida**: o conteúdo da ATD entrou no formato atual, com as regras de segurança
valendo. A entrega, como recebida, está em `docs/knowledge/atd/entrega_v3/`; o retorno à ATD (a
classificação do manejo e as pendências, numeradas), em `docs/knowledge/atd/retorno_v3/`. A próxima
entrega deve partir desta pasta.

| Arquivo | O que entrou |
|---|---|
| `crops.json` | 5 culturas novas (coentro, hortelã, brócolis, espinafre, pimenta) e os campos da v3 nas 20; 13 culturas passaram a `validated_by_atd` |
| `companions.csv` | 14 relações novas (7 `technical`, 7 `research`), todas fora das saídas pela D6 |
| `guidelines.json` | 6 diretrizes (semeadura, pH e sol da Epagri; luz do tomate e radiação da alface do SENAR-PR; rotação por cultura) |
| `sources.json` | 25 fontes da v3 e 4 citadas sem registro, como `verified: false` e título "Pendente: metadados a enviar pela ATD" (D7) |
| `pests_diseases.json` | Sintomas e manejo da ATD, tipo do manejo por regra (D2), fonte do sintoma (D3), vespas `beneficial` (D4), `crop_scope` |

**Épocas preenchidas pelo módulo de IA (D8).** Brócolis (inverno e verão, p. 22), coentro (p. 28),
espinafre (p. 33) e pimenta (p. 48) vieram sem época de plantio; as janelas foram preenchidas a partir
do Catálogo Brasileiro de Hortaliças, no formato das outras culturas, e essas 4 culturas estão em
`draft` até a ATD conferir. A ficha do espinafre no Catálogo cobre duas espécies. Hortelã continua sem
época (pendência da ATD) e, por isso, fica fora de toda recomendação (`no_region_data`).

**Ajustes de formato** (sem mudar o conteúdo): os nomes "Brocolis" e "Hortela" receberam acento; a
diretriz `rotacao_familia_por_cultura`, que só aponta para o campo `rotation`, não entra na resposta
geral do assistente sobre plantio companheiro; a ação proposta para as vespas ("Não controlar.
Preservar plantando flores...") foi para `notes`, porque entradas benéficas não têm ações.

**Lacunas fechadas pela ATD:**

| Lacuna (antes) | Situação |
|---|---|
| Doenças causadas por fungos e por bactérias sem sintomas específicos | Fechada: as 10 doenças têm sintoma com fonte e página |
| Doença do morango sem nome popular | Fechada: "Mancha-de-diplocarpon (escaldadura da folha)" |
| Plantio companheiro sem relação `research` | Fechada na base, mas fora das saídas (D6) |
| Plantio companheiro sem pares técnicos da Embrapa | Fechada na base, mas fora das saídas até a ATD enviar os metadados das fontes (D6, D7) |
| Rúcula sem relações | Fechada na base (duas `research`), fora das saídas (D6) |
| Nenhuma fonte com sol ou água por cultura | Parcial: `sun` e `irrigation` em `crops.json` para algumas culturas (só o tomate tem horas de sol) |
| Tesourinhas sem sintoma | Parcial: descrição como inimigo natural, com fonte; continua sem manejo |

**Conflitos novos registrados na entrega:** germinação do tomate e da alface (tabela "Conflitos entre
fontes"). A entrega também marca páginas a conferir: repolho (`sowing_depth_cm` e `irrigation`, fonte
de 1981 sem paginação), alface (`irrigation`, fonte não registrada), cenoura (temperatura mínima de
germinação com leitura incerta) e os sintomas da requeima e da pinta-preta da batata.

## Lacunas conhecidas

- **Adaptação regional**: janelas por macrorregião, não por município (ver acima).
- **Plantio companheiro**: as 14 relações da v3 (as únicas `research` e `technical` em pares) fora das
  saídas até a ATD confirmar (D6); rúcula, espinafre, brócolis e pimenta sem relação utilizável.
- **Culturas da v3**: sem `crop_groups`, propagação, espaçamento e indicação para pequeno espaço; por
  isso ficam sem diretriz de irrigação e fora da lista quando `small_space` está ligado. Hortelã sem
  época de plantio.
- **Batata**: sem espaçamento para pequenos espaços (ausente na Tabela 2 do HPE) e sem diretriz de
  irrigação (grupo "tubérculo" não coberto pelo CT 47).
- **Manjericão**: sem janela mensal para Nordeste e Norte. A única orientação disponível (Doc. 136) é
  cultivar em campo aberto no período quente, ou em vasos o ano todo.
- **Rúcula e manjericão**: sem produtividade de referência. Para rúcula, só foram encontrados
  experimentos isolados, com resultados de 0,7 a 3,3 kg/m² conforme o manejo, que não servem como
  valor de referência; para manjericão, nenhuma das fontes informa produtividade. Se a base financeira
  precisar desses números, eles devem entrar lá como premissa documentada.
- **Pragas e doenças** (tudo pendente de revisão com agrônomos, 9.4.1-9):
  - manejo das doenças ainda genérico, por grupo (a própria ATD registra a pendência em `notes`);
  - tesourinhas e gorgulhos sem manejo; gorgulhos também sem sintoma;
  - formigas e besouros sem decisão sobre serem pragas (`beneficial: null`), agora com fontes dos dois
    lados; nos besouros todas as ações são caldas, então o assistente não mostra nenhuma;
  - 6 pragas em `draft` porque a ATD propôs sintoma novo sem indicar fonte e página (ver D3 acima).
- Sol e água por cultura: só parte das culturas tem dado em `crops.json` (campos `sun` e `irrigation`);
  o assistente continua usando as diretrizes de `guidelines.json`, por grupo.

## Lacunas resolvidas

| Data | Lacuna | Resolução |
|---|---|---|
| 2026-10 | Manjericão sem janela no Sul | Folder Embrapa (2006): final da primavera → nov-dez |
| 2026-10 | Manjericão sem diretriz de irrigação | Doc. 136, p. 20: irrigação diária |
| 2026-11 | Sintomas das 10 doenças; nome popular da doença do morango | Entrega v3 da ATD (ver "Integração da entrega v3 da ATD") |
