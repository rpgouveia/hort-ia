# Base de Conhecimento Agronômica — Hort.IA

Base própria e reduzida, construída por decisão da Ata de Execução nº 2 (01/10/2026) enquanto as
demais equipes não definem as bases oficiais. Todo registro cita a fonte e a página, e nasce como
`draft`; ao alinhar com a Assistência Técnica Digital, os registros passam a `validated_by_atd`.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `crops.json` | 15 culturas do MVP: janelas de plantio por região, espaçamento, propagação, produtividade |
| `guidelines.json` | Regras gerais (sol, irrigação, espaçamento em pequenos espaços, pH, clima) |
| `pests_diseases.json` | Mapeamento das classes do modelo de visão computacional para manejo |
| `companions.csv` | Relações de plantio companheiro (direcionais: `crop_a` ajuda/prejudica `crop_b`) |
| `sources.json` | Registro das fontes citadas |

## Hierarquia de fontes (quando divergem)

1. **Catálogo Brasileiro de Hortaliças (2010)**: janelas de plantio e início de colheita, por região e
   tipo de cultivar. É a única fonte com dados para as cinco regiões.
2. **Horta em Pequenos Espaços (2012), Tabela 2**: espaçamento convencional e reduzido, propagação e
   tempo de mudas. Sua época de plantio vale só para Sudeste, Centro-Oeste, norte do Sul e sul do
   Nordeste, por isso não é usada quando o Catálogo tem o dado.
3. **Circular Técnica 47 (2007)**: produtividade em 10 m², grupos de hortaliças e regras gerais.

## Convenções

- Espaçamento em cm, na ordem *entre linhas × entre plantas*.
- `months_by_region`: região com `[]` = "não recomendável" na fonte; região ausente = sem dado.
- `pages` usa o número **impresso** na página.
- O HPE tem todos os direitos reservados: guardar apenas dados factuais e texto parafraseado.
- O script `scripts/build_crops_v1.py` registra como a primeira versão foi transcrita.

## Conflitos entre fontes

| Cultura | Divergência | Decisão |
|---|---|---|
| Rúcula | Colheita: Catálogo 40-60 dias × HPE 25-30 dias | Catálogo |
| Cenoura | Espaçamento: HPE 20×10 cm × CT 47 20×5 cm | HPE |
| Abobrinha | Colheita: Catálogo 45-60 × HPE 60-90 dias | Catálogo |
| Tomate | Colheita: Catálogo 100-120 × HPE 90-100 dias | Catálogo |
| Cebolinha | Colheita: Catálogo 80-100 × HPE 70-90 dias | Catálogo |

## Lacunas conhecidas

- **Manjericão** não está no Catálogo: sem janela de plantio para Sul, Nordeste e Norte.
- **Batata** não está na Tabela 2 do HPE: sem espaçamento para pequenos espaços.
- Nenhuma fonte traz exigência de sol ou água **por cultura**; isso fica em `guidelines.json`, por grupo.
- Rúcula e manjericão sem produtividade de referência (ausentes no CT 47).
