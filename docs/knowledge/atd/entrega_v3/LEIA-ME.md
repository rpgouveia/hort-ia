# Entrega — Módulo de Assistência Técnica Digital (Pacote 8)

Base de conhecimento agronômica para o Módulo de Inteligência Artificial.
Mantém o formato definido pelo Grupo de IA (README da Hort.IA), com incrementos.

Data: 20/10/2026
Equipe: Deborah Santos Lizardo, Cecília Lucchesi Mardegan, Leonardo Lino Guedes

---

## knowledge/

### crops.json  — SUBSTITUI o atual
20 culturas (eram 15). Novas: coentro, hortelã, brócolis, espinafre e pimenta.

Campos acrescentados, cada um com `source` e `pages`:
`germination`, `sowing_depth_cm`, `irrigation`, `soil_ph`, `sun` e `rotation`.
`companion_roles` preenchido em coentro, cebolinha, hortelã e manjericão.
`family` e `scientific_name` preenchidos nas 5 culturas novas.

`rotation` materializa por cultura a regra da CT 47 (pp.10-11): traz
`rotation_group` (a família botânica) e `avoid_after`, a lista das culturas
desta base que não devem ser plantadas em sequência no mesmo canteiro.
Famílias com mais de uma cultura: Brassicaceae (5), Solanaceae (4),
Apiaceae (3), Amaranthaceae (2) e Lamiaceae (2).

43 dos 100 campos novos têm dado. Os vazios trazem em `notes` onde a busca
foi feita e por que não há valor — não refazer o mesmo caminho.

Conflitos entre fontes resolvidos e registrados em `notes`, com a fonte
preterida em `alt_source`: germinação do tomate e da alface.

### companions.csv  — SUBSTITUI o atual
51 relações: as 37 `traditional` originais, preservadas, mais 14 novas
(7 `technical`, 7 `research`). Nenhum conflito com as existentes; 3 confirmam
linhas que antes só tinham origem em Wikipedia.

Fecha três lacunas declaradas no README da Hort.IA: a ausência de evidência
`research`, a ausência de pares técnicos vindos da Embrapa e a rúcula sem
nenhuma relação.

### pests_diseases.json  — SUBSTITUI o atual
27 entradas. Antes: 27/27 sem `management`, sem `sources` e sem `symptoms`.
Agora: 21 com manejo, 23 com fonte e página, 11 com sintomas.

Campo novo `crop_scope` (`all_vegetables` | `specific`): a Circular Técnica 47
descreve as pragas como "as que atacam as hortaliças", sem especificar cultura.
Listar culturas específicas seria precisão inventada.

Vespa reclassificada de `pest` para `beneficial` (CT 47 p.12 e p.13).
Besouro e formiga marcados como ambíguos — a mesma classe agrupa praga e
inimigo natural; não recomendar controle sem confirmar a espécie.
Tesourinha e gorgulho sem manejo: não constam em fonte institucional.

### guidelines_novas.json  — SOMAR ao guidelines.json existente
6 regras. Três gerais da Epagri, que valem quando não há valor por espécie:
profundidade de semeadura igual a 3x o diâmetro da semente, pH 6,0 e sol o dia
todo. Duas específicas: tomate com mínimo de 8 h de luz e alface com limite de
19 MJ/m²/dia — essa é radiação, não horas, e não se converte uma na outra.
E uma que aponta a rotação por cultura, agora em `crops.json`.

### sources_novas.json  — SOMAR ao sources.json existente
12 fontes. 6 da Embrapa (Coleção Plantar e Sistemas de Produção) e 6 de fora.

As duas mais produtivas não são da Embrapa e são regionalmente mais
adequadas a Curitiba:
- Epagri, Boletim Didático 107 (SC, 2014) — Tabela 8 traz temperatura de
  germinação por espécie, para 29 hortaliças.
- SENAR-PR (PR, 2015) — tomate e alface. Atenção: dados de ambiente
  protegido, não de campo aberto.

---

## images/

### images_manifest.csv
O recorte que o Grupo de IA pediu: quais classes dos datasets entram, com que
rótulo e ligadas a qual cultura.
71 linhas — manter, revisar, remover e candidato.

### image_sources.json
Os datasets de imagem avaliados, com licença e cobertura verificada.

**Recomendação: adotar o PlantSeg no lugar do New Plant Diseases Dataset.**

Cobertura confirmada no `Metadata.csv` do zip oficial (11.458 imagens,
35 plantas, 138 classes). O PlantSeg cobre 10 das 20 culturas, com fotos de
campo; o PlantVillage cobria 4, com folha destacada em fundo de laboratório.
As 4 do PlantVillage estão contidas nas 10 do PlantSeg.

Decisão pendente do Grupo de IA: a licença é CC BY-NC-ND 4.0. O NC atende uso
acadêmico; o ND precisa ser avaliado quanto a treinamento de modelo.

Sobre o PlantVillage: há estudo medindo que um classificador treinado com
8 pixels apenas do FUNDO das imagens, sem folha, atinge 49% de acurácia em
38 classes (acaso = 2,6%). Metade do sinal é contexto de captura.
Referência registrada no arquivo.

---

## Cobertura de imagem

Com imagem (10): alface, abobrinha, batata, brócolis, cenoura, manjericão,
morango, pimentão, repolho e tomate.

Sem imagem (10): cebolinha, salsa, coentro, rabanete, beterraba, espinafre,
pimenta, couve, rúcula e hortelã.

Busca feita em Zenodo, IEEE DataPort, Roboflow, Kaggle e Data in Brief.
Para essas 10 não existe conjunto com licença declarada. Diagnóstico por foto
fica restrito às 10 cobertas; as demais caem no fluxo de triagem e
redirecionamento para avaliação profissional, já previsto pelo módulo.

Atenção a homônimos: "Malabar spinach" é bertalha (Basella alba), não
espinafre; "cabbage" é repolho; "cauliflower" é couve-flor, não couve.

---

## Pendências

1. PlantSeg — decidir sobre a cláusula ND da licença (Grupo de IA).
2. PlantSeg — ao adotar, criar o id de cada classe na base e escrever o
   manejo com fonte, como já foi feito para as 27 do PlantVillage.
3. Repolho — `sowing_depth_cm` e `irrigation` estão com
   `"pages": "nao confirmada"`. A fonte é de 1981 e o PDF não preserva a
   paginação; conferir no impresso.
4. README da Hort.IA — três lacunas listadas como abertas já foram fechadas
   por esta entrega, e há dois conflitos novos a registrar.

---

## Significado do status `validated_by_atd`

`validated_by_atd` significa que o dado foi **conferido pela ATD contra a fonte
e a página citadas**. Não é aval agronômico e não transfere responsabilidade
técnica à ATD, que não conta com profissional habilitado (Premissa P-02; Log
de Mudanças, escopo excluído).

Consequências para o consumo da base:
- o status **não libera** preparados naturais (caldas, extratos) nas respostas
  automáticas;
- o status **não altera** a regra de redirecionamento, que é atribuição
  exclusiva da ATD (Ata de Alinhamento de 18/09/2026);
- o status `reviewed` (agrônomo) **não é utilizado** pela ATD.

---

## Histórico de versões

- **v1 — 20/10/2026:** entrega inicial.
- **v2 — 09/11/2026:** removida a única dose da base (`tomate_acaro_rajado`),
  em conformidade com a regra "sem doses nem receitas" proposta pelo módulo de
  IA; incluída a definição do status `validated_by_atd`.

---

## Versão 3 (11/2026): o que mudou em relação à v2

Mudanças mínimas: nenhum campo novo e nenhuma estrutura alterada. Só foram
preenchidos campos que já existiam e acrescentadas fontes.

### pests_diseases.json
- `symptoms` preenchido nas 10 doenças causadas por fungos e bactérias
  (tomate: mancha-bacteriana, pinta-preta, requeima, cladosporiose,
  septoriose e mancha-alvo; batata: pinta-preta e requeima; pimentão:
  mancha-bacteriana; morango). Cada uma com fonte e página em `sources`.
- `morango_leaf_scorch`: `name_pt` = "Mancha-de-diplocarpon (escaldadura da
  folha)" (Embrapa CT 96, p. 3; SENAR-PR PR.0355, p. 18).
- Formigas e besouros: fontes novas dos dois lados (praga e inimigo natural).
  Continuam ambíguos.
- Tesourinhas: fontes novas como inimigo natural (SENAR-PR PR.0306, p. 13;
  Embrapa Milho e Sorgo; Revista Ciência Agronômica, 2013). Decisão do grupo:
  não reclassificar como benéfica para hortaliças, porque a evidência é para
  o milho. O texto diz que ela pode contribuir para o controle natural de
  algumas pragas, sem afirmar controle de pragas de cada cultura.
- As 10 doenças com sintomas novos passaram para `validated_by_atd`
  (validação do grupo em 10/11/2026), no sentido definido pela ATD:
  conferido contra fonte e página, não é aval agronômico.

### sources_novas.json
- 13 fontes novas: Embrapa, SENAR-PR, EPAMIG e um artigo da Revista Ciência Agronômica.

### Conferido sem alteração
- `crops.json`: épocas e espaçamentos de alface, repolho, rúcula, manjericão,
  morango, abobrinha e tomate conferem com o Catálogo Brasileiro de
  Hortaliças e com a Tabela 2 do Horta em Pequenos Espaços (p. 35).

### Preparados naturais e período de carência
Não existe período de carência universal para preparados caseiros. A única
indicação nas fontes é genérica: o HPE (p. 30) diz para não colher, em média,
antes de cinco dias, atentando ao produto usado, e cita cerca de duas semanas
para preparados com sabão (p. 38). Por isso a base não traz carência por
preparado, e os preparados continuam ocultos nas respostas automáticas.
