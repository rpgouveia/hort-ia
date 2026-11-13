# Retorno da entrega v3 da ATD: pendências para resposta

Módulo de IA da Hort.IA, novembro de 2026. Resposta à entrega v3 da Assistência Técnica Digital
(arquivos como recebidos em `docs/knowledge/atd/entrega_v3/`).

**Como responder:** responda item a item, pelo número (por exemplo, "1: de acordo, exceto a linha
do ácaro"). Onde houver uma pergunta, uma frase basta. O arquivo `classificacao_manejo.csv`, nesta
pasta, acompanha o item 1.

**Resumo em uma frase:** a base da v3 partiu de uma versão antiga do repositório, então não pudemos
trocar os arquivos; juntamos o conteúdo de vocês ao formato atual, sem mudar os textos, e listamos
abaixo o que ficou para conferir.

---

## 1. Conferir a classificação das ações de manejo

As ações da v3 vêm como texto e fonte, sem dizer de que tipo são. O assistente precisa do tipo para
decidir o que mostrar, então classificamos cada ação por palavras do texto, nesta ordem:

| Tipo | Palavras que levam a ele | Aparece no assistente? |
|---|---|---|
| `alternative` (preparado natural) | calda, extrato, preparado, defensivo natural, óleo, sabão, fumo, nim/neem, infusão | Não, enquanto a entrada não for revisada por agrônomo |
| `biological` | Bacillus thuringiensis, baculovírus, Trichogramma, controle biológico, inimigo natural liberado | Sim |
| `preventive` | semente, muda sadia, cultivar resistente, certificada | Sim |
| `cultural` | todas as outras | Sim |

O arquivo `classificacao_manejo.csv` tem uma linha por ação (62 ações): a entrada, o texto de vocês
sem alteração, o tipo, a regra que decidiu, se aparece no assistente e o status da entrada.
Resultado: 35 `cultural`, 15 `alternative`, 10 `preventive` e 2 `biological`; 46 aparecem no
assistente e 16 não.

Pedimos atenção a três casos em que a regra pode não ter acertado:

- **Ácaro-rajado:** "Alternar os produtos usados, para não selecionar populações tolerantes." ficou
  `cultural` e é a única ação que aparece para o ácaro, porque as outras duas são caldas e ficam
  escondidas. Sozinha, a frase sugere usar produtos. Vocês preferem trocar o texto ou tirar a ação?
- **Gafanhotos:** "Usar armadilha luminosa associada a recipiente com água ou óleo." ficou
  `alternative` por causa da palavra "óleo", e por isso não aparece. O óleo aqui é da armadilha, não
  um preparado. Confirmam que ela pode aparecer (tipo `cultural`)?
- **Mariposas:** "Tratar como alerta precoce: a presença do adulto antecede o ataque das lagartas."
  ficou `cultural`. É mais um aviso do que uma ação. Mantemos assim?

**Ações que existiam e não estão na v3.** A base de 20/10 que vocês usaram já tinha algumas ações que
sumiram na v3. Seguimos a v3, mas queremos confirmar que foi de propósito:

- formigas: "Gergelim plantado perto da horta ajuda contra formigas-cortadeiras..." (HPE p. 40);
- ácaro, besouros, lagartas, gafanhotos e formigas: "Plantas aromáticas, como coentro, cebolinha,
  manjericão e cravo-de-defunto, junto das hortaliças podem afastar algumas pragas." (CT 47 p. 12);
- lesmas e caracóis: "Evite excesso de água no canteiro." (HPE p. 29).

A tabela do item 9 mostra, entrada por entrada, as ações antigas e as novas.

**Pergunta:** a classificação está certa? Se não, digam a linha e o tipo correto. Numa próxima
entrega, vocês podem mandar o tipo junto com cada ação?

## 2. Fontes de sintomas que faltaram

Todo sintoma mostrado pelo assistente precisa de fonte com página. Onde o texto do sintoma mudou e a
fonte não estava indicada nas notas, no PDF ou no próprio texto, **mantivemos o sintoma anterior, com
a fonte dele**, deixamos a entrada em `draft` e guardamos o texto de vocês nas notas da entrada.

**Sintoma novo sem fonte e página** (o que falta: a fonte e a página do texto de vocês):

| Entrada | Texto proposto pela ATD | Sintoma mantido (fonte) |
|---|---|---|
| `tomate_acaro_rajado` | "Ácaros são pragas microscópicas; sugam a seiva e causam deformação em folhas e brotos." | "Colônias muito pequenas no verso das folhas, com teias finas; sugam a seiva da planta." (CT 47 p. 12) |
| `praga_lagartas` | "Mastigadores. As menores penetram frutos, folhas e brotos; as maiores comem as folhas. Os ferimentos abrem porta de entrada para doenças. A lagarta-rosca vive enterrada e ataca a planta nova à noite, podendo derrubá-la." | "Comem as folhas; as menores entram em frutos e brotos. A lagarta-rosca vive no solo e derruba plantas novas à noite." (CT 47 p. 11) |
| `praga_gafanhotos` | "Mastigadores: comem ramos e folhas das plantas. A CT 47 trata paquinhas, grilos e gafanhotos no mesmo grupo." (cita a CT 47, mas sem página) | "Comem ramos e folhas." (CT 47 p. 12) |
| `praga_mariposas` | "O adulto não causa dano direto. A CT 47 cita moscas, besouros, borboletas e mariposas como as fases adultas que originam as larvas e lagartas, estas sim mastigadoras." (cita a CT 47, mas sem página) | "As mariposas adultas não comem a planta; o estrago é feito pelas lagartas que nascem dos ovos delas." (CT 47 p. 11) |
| `praga_lesmas` | "Aparelho bucal raspador: raspam as folhas e os ramos novos das hortaliças." | "Raspam folhas e ramos novos; aparecem mais quando há muita umidade." (CT 47 p. 12; HPE p. 29) |
| `praga_caracois` | Mesmo texto das lesmas | Mesmo texto das lesmas |

**Sintoma retirado na v3:** `tomate_begomovirose` e `tomate_mosaico` vieram sem sintoma. Mantivemos o
anterior: "Folhas e brotos novos amarelados, com manchas de verde claro e escuro (mosaico) e
enrugados." (CT 47 p. 11). Foi de propósito? Se sim, por quê?

**Texto que não é sintoma:** em `praga_gorgulhos`, o campo de sintoma veio com "Não descrito
individualmente na CT 47.". Como isso descreve a falta de fonte, e o assistente mostraria a frase como
"Como reconhecer: ...", não gravamos no sintoma; a frase está nas notas. Existe sintoma com fonte?

**Fontes que adotamos e pedimos para confirmar:**

- `praga_formigas`: CT 47 p. 12 (citada nas notas de vocês) e HPE p. 29 (notas e PDF, pedido 3).
- `praga_besouros`: HPE p. 29 (notas e PDF) e CT 47 p. 12, que era a fonte do texto anterior. A frase
  "comem e perfuram folhas, brotos e frutos" veio do texto anterior; a HPE p. 29 fala em "folhas e
  talos". A CT 47 p. 12 serve para os frutos?
- `praga_tesourinhas`: SENAR-PR PR.0306 p. 13 e Revista Ciência Agronômica (2013) p. 842, as do PDF. O
  trecho "preda ovos e lagartas pequenas da lagarta-do-cartucho" veio de qual fonte e página? O folder
  da Embrapa Milho e Sorgo está registrado com a observação "conteúdo do folder não consultado", e o
  artigo de Reis (1988) está sem página.
- `benefico_vespas`: CT 47 pp. 12 e 13, citadas no próprio texto.
- `batata_requeima` (p. 35) e `batata_pinta_preta` (p. 36): o PDF marca as duas páginas como "a
  conferir". Registramos isso nas notas. Podem conferir no impresso?

**Observação sobre a tesourinha.** Com o texto novo, a resposta do assistente para a foto de
tesourinha fica assim: "Como reconhecer: inseto que atua como inimigo natural..." e, logo depois,
"Ainda não tenho uma orientação conferida para combater isso." A segunda frase vem da regra geral para
pragas sem manejo e soa estranha depois da primeira. Vocês preferem manter, mudar o texto da descrição
ou rever a classe?

## 3. Metadados das 4 fontes não registradas

Estas fontes são citadas na v3, mas não estão em `sources_novas.json`. Entraram na base com o título
"Pendente: metadados a enviar pela ATD" e marcadas como não verificadas. **Enquanto isso, nada que
dependa delas aparece para o usuário.**

| Fonte citada | Onde aparece |
|---|---|
| `embrapa_folder_plantas_companheiras` | 3 relações técnicas de consórcio (alface-cebolinha, pimentão-alface, hortelã-couve); nota de vocês: fonte regional de Manaus-AM |
| `embrapa_horta_domestica_portal` | 4 relações técnicas de consórcio (cebolinha-coentro, coentro-alface, cebolinha-hortelã, cebolinha-manjericão) |
| `embrapa_it134_alface_crespa` | Irrigação da alface (`crops.json`), com página "nao confirmada" |
| `unioeste_alelopatia_couve` | As 7 relações de pesquisa (item 6) |

**Pedido:** para cada uma, título completo, autores ou editora, ano, endereço (URL), licença e as
páginas usadas.

## 4. Épocas de brócolis, coentro, espinafre e pimenta

Essas quatro culturas vieram sem época de plantio, e sem época elas nunca seriam recomendadas.
Preenchemos a partir do Catálogo Brasileiro de Hortaliças (páginas impressas), no mesmo formato das
outras culturas ("não recomendável" = nenhum mês). As quatro ficaram em `draft`, com a nota "Épocas
preenchidas pelo módulo de IA a partir do Catálogo (p. X), pendente de conferência da ATD".

| Cultura | Página | Sul | Sudeste | Nordeste | Centro-Oeste | Norte | Colheita (dias) |
|---|---|---|---|---|---|---|---|
| Brócolis de inverno | 22 | fev-set | fev-jul | não recomendável | fev-mai | não recomendável | 90-100 |
| Brócolis de verão | 22 | out-dez | set-jan | out-fev | out-jan | abr-jul | 80-100 |
| Coentro | 28 | set-jan | ago-fev | ano todo | ago-abr | abr-out | 50-60 |
| Espinafre | 33 | fev-set | fev-set | mar-ago | mar-ago | mar-mai | 60-80 |
| Pimenta | 48 | set-fev | ago-mar | ano todo | ago-dez | jul-dez | 90-120 |

**Pedidos:** conferir a tabela no Catálogo. A ficha do espinafre cobre duas espécies: qual delas a
base considera? (O nome científico na v3 é *Spinacia oleracea*.)

## 5. Época de plantio da hortelã

A hortelã veio sem época. Sem época, ela fica fora de toda recomendação, e o assistente responde que
não tem a informação. **Pedido:** época por região, com fonte e página, ou a confirmação de que não há
fonte institucional (como vocês registraram para outros campos).

Também faltam, nas 5 culturas novas, o grupo da hortaliça (folhosa, fruto, raiz...), a forma de
plantio (muda ou semeadura direta), o espaçamento e a indicação para vaso ou pouco espaço. Sem o grupo,
elas ficam sem orientação de rega; sem a indicação de vaso, ficam fora da lista quando a horta é em
pouco espaço. Se houver fonte, mandem junto.

## 6. Relações de pesquisa (consórcio)

As 7 relações `research` da v3 (couve sobre alface, rúcula e tomate; hortelã sobre rúcula, cenoura,
tomate e manjericão) são testes de germinação de sementes com extrato ou óleo essencial em placa de
Petri, sem plantar as culturas juntas. Uma delas (couve sobre tomate) tem o aviso de vocês de possível
erro de cópia no artigo (a tabela do tomate é igual à da rúcula).

Esses testes mostram que o extrato atrapalha a germinação no laboratório, mas não dizem o que acontece
quando as plantas crescem lado a lado no canteiro. Por isso, **propomos mantê-las na base, mas fora das
respostas**: elas não mudam a ordem das recomendações, não aparecem como aviso e não aparecem no
assistente nem na rota de consórcio. Fizemos isso num ponto só do sistema, para todas as partes
continuarem de acordo.

As 7 relações técnicas também estão fora das respostas, mas por outro motivo: as fontes ainda não têm
metadados (item 3). Quando chegarem, elas passam a valer.

**Pergunta:** vocês concordam em manter as relações de pesquisa fora das respostas?

## 7. Vespas

Aceitamos a reclassificação de praga para benéfica. A resposta do assistente continua a mesma: "Vespas
ajudam a horta: comem outras pragas. Não precisa combater." A ação que vocês sugeriram ("Não
controlar. Preservar plantando flores em volta da horta, que servem de abrigo e refúgio.") foi para as
notas, porque entradas benéficas não têm ações de manejo na base.

Dois pontos para avaliar:

1. A classe "wasp" do modelo de visão é genérica: junta vespas predadoras e parasitoides com espécies
   que furam frutos maduros. A resposta "não precisa combater" vale para todas?
2. Sugestão de frase de segurança, para acrescentar à resposta: "Se houver ninho perto de onde as
   pessoas trabalham, peça ajuda para retirar com segurança, sem usar veneno." Vocês aprovam esse
   texto ou propõem outro?

## 8. Significado de `validated_by_atd`

Adotamos a definição do LEIA-ME de vocês: `validated_by_atd` quer dizer **conferido contra a fonte e a
página**. Não é aval agronômico, não libera preparados naturais e não muda o encaminhamento à
Assistência Técnica. O status `reviewed` fica para a revisão por agrônomo.

O que isso muda no assistente:

- entradas `draft` e `validated_by_atd` têm a mesma resposta: mostram só as ações preventivas,
  culturais e biológicas, escondem caldas e preparados e sempre terminam encaminhando à Assistência
  Técnica;
- só `reviewed` mostra todas as ações e deixa o encaminhamento como opção;
- na base, a exigência de registro completo vale só para `reviewed`. Um registro conferido por vocês
  pode ter lacunas (por exemplo, formigas e besouros sem decisão entre praga e benéfico).

**Pergunta:** confirmam que é isso?

## 9. Os arquivos foram fundidos, não substituídos

A v3 partiu da base de 20/10/2026, anterior ao trabalho em pragas e doenças. Por isso os arquivos não
podiam substituir os do repositório: validados contra o modelo atual, davam 126 erros em `crops.json`,
214 em `pests_diseases.json` e 5 em `guidelines_novas.json`, e citavam 4 fontes não registradas.

Juntamos o conteúdo de vocês ao formato atual, sem mudar os textos:

- **Manejo:** cada ação virou "tipo + texto + fonte", com o tipo por regra (item 1).
- **Sintomas:** cada sintoma ganhou a fonte própria exigida pelo modelo (item 2).
- **Pragas:** `crop_scope` foi aceito; nas pragas `all_vegetables`, a lista de culturas ficou vazia, que
  na base quer dizer "vale para todas". A lista que veio tinha as 15 culturas antigas e deixaria de fora
  as 5 novas.
- **Consórcio:** o texto livre da coluna `mechanism` foi para o início das notas, porque o campo aceita
  só valores fixos (`allelopathy` nas relações de pesquisa, `unknown` nas técnicas).
- **Culturas:** os campos novos (germinação, profundidade, irrigação, pH, sol, rotação e temperaturas)
  foram aceitos como vieram. Os nomes "Brocolis" e "Hortela" ganharam acento, porque aparecem para o
  usuário.
- **Diretrizes:** as 6 entraram como vieram. A que aponta para o campo `rotation`
  (`rotacao_familia_por_cultura`) não aparece na resposta geral do assistente, porque fala de um campo
  de arquivo, e não de plantio.

**Pedido para a próxima entrega:** partir da base atual do repositório (`data/knowledge/`), e não da
base de 20/10. O script `scripts/merge_atd_v3.py` registra como esta fusão foi feita.

**Valores que já existiam e mudaram.** Comparamos campo a campo o que já existia (15 culturas, 37
relações e 27 pragas e doenças) com a v3. As 37 relações de consórcio não mudaram. Nas culturas, só
mudou o status. Em pragas e doenças, a tabela abaixo mostra cada diferença e o que adotamos (o campo
"management" lista as ações com o tipo entre colchetes; "(vazio)" quer dizer sem valor).

| Entrada | Campo | Valor atual | Valor da ATD | O que foi adotado |
|---|---|---|---|---|
| tomate | validation_status | draft | validated_by_atd | validated_by_atd |
| batata | validation_status | draft | validated_by_atd | validated_by_atd |
| pimentao | validation_status | draft | validated_by_atd | validated_by_atd |
| morango | validation_status | draft | validated_by_atd | validated_by_atd |
| alface | validation_status | draft | validated_by_atd | validated_by_atd |
| couve | validation_status | draft | validated_by_atd | validated_by_atd |
| repolho | validation_status | draft | validated_by_atd | validated_by_atd |
| cenoura | validation_status | draft | validated_by_atd | validated_by_atd |
| beterraba | validation_status | draft | validated_by_atd | validated_by_atd |
| rabanete | validation_status | draft | validated_by_atd | validated_by_atd |
| cebolinha | validation_status | draft | validated_by_atd | validated_by_atd |
| salsa | validation_status | draft | validated_by_atd | validated_by_atd |
| abobrinha | validation_status | draft | validated_by_atd | validated_by_atd |
| tomate_mancha_bacteriana | symptoms | (vazio) | Manchas pequenas de aspecto molhado nas folhas mais velhas, que secam e podem furar a folha. No fruto, pintas brancas que ficam marrons, ásperas e afundadas. | Manchas pequenas de aspecto molhado nas folhas mais velhas, que secam e podem furar a folha. No fruto, pintas brancas que ficam marrons, ásperas e afundadas. |
| tomate_mancha_bacteriana | management | [preventive] Use sementes e mudas sadias, de origem conhecida.<br>[cultural] Arranque as plantas doentes e destrua-as longe da horta.<br>[cultural] Evite excesso de umidade no canteiro.<br>[cultural] Onde a doença apareceu, plante por um tempo adubo verde ou culturas que não pegam a doença. | Evitar introduzir a doença por sementes ou mudas contaminadas.<br>Arrancar e queimar as plantas contaminadas.<br>Evitar excesso de umidade, que favorece o aparecimento. | [preventive] Evitar introduzir a doença por sementes ou mudas contaminadas.<br>[cultural] Arrancar e queimar as plantas contaminadas.<br>[cultural] Evitar excesso de umidade, que favorece o aparecimento. |
| tomate_mancha_bacteriana | sources | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_horta_pequenos_espacos p. 29 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct121_tomate p. 7; embrapa_ct84_mancha_bacteriana p. 3 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct121_tomate p. 7; embrapa_ct84_mancha_bacteriana p. 3; embrapa_ct47_cultivo_hortalicas p. 11-12 |
| tomate_mancha_bacteriana | validation_status | draft | validated_by_atd | validated_by_atd |
| tomate_mancha_bacteriana | notes | Manejo por grupo (doenças causadas por bactérias), sem orientação específica para esta doença. Sintomas específicos e validação com agrônomos (9.4.1-9). | Manejo GENÉRICO para doença bacteriana (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_ct121_tomate p. 7; embrapa_ct84_mancha_bacteriana p. 3. Sintomas validados pelo grupo em 10/11/2026. | Manejo GENÉRICO para doença bacteriana (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_ct121_tomate p. 7; embrapa_ct84_mancha_bacteriana p. 3. Sintomas validados pelo grupo em 10/11/2026. |
| tomate_pinta_preta | symptoms | (vazio) | Manchas escuras nas folhas mais velhas, com anéis em volta, parecendo um alvo. Às vezes com borda amarela. No caule, manchas compridas; no fruto, manchas escuras perto do cabo. | Manchas escuras nas folhas mais velhas, com anéis em volta, parecendo um alvo. Às vezes com borda amarela. No caule, manchas compridas; no fruto, manchas escuras perto do cabo. |
| tomate_pinta_preta | management | [preventive] Use sementes certificadas e, quando houver, variedades resistentes.<br>[cultural] Retire da horta as folhas e plantas doentes e os restos da colheita anterior.<br>[cultural] Regue sem encharcar e mantenha a adubação equilibrada.<br>[cultural] Faça rotação de culturas e plante na época indicada para a sua região.<br>[alternative] Caldas naturais, como a bordalesa e a sulfocálcica, são usadas contra manchas nas folhas. Peça orientação técnica antes de preparar ou aplicar. | Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>Usar cultivares resistentes e sementes certificadas.<br>Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. | [cultural] Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>[cultural] Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>[preventive] Usar cultivares resistentes e sementes certificadas.<br>[alternative] Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. |
| tomate_pinta_preta | sources | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_horta_pequenos_espacos p. 29 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct121_tomate p. 5 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct121_tomate p. 5; embrapa_ct47_cultivo_hortalicas p. 11, 14 |
| tomate_pinta_preta | validation_status | draft | validated_by_atd | validated_by_atd |
| tomate_pinta_preta | notes | Manejo por grupo (doenças causadas por fungos), sem orientação específica para esta doença. Sintomas específicos e validação com agrônomos (9.4.1-9). | Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_ct121_tomate p. 5. Sintomas validados pelo grupo em 10/11/2026. | Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_ct121_tomate p. 5. Sintomas validados pelo grupo em 10/11/2026. |
| tomate_requeima | symptoms | (vazio) | Manchas grandes, escuras e com aspecto molhado nas folhas, que depois secam. Caule com manchas escuras que quebram fácil. Fruto com manchas marrons e firmes. Com tempo úmido, aparece um mofo branco. | Manchas grandes, escuras e com aspecto molhado nas folhas, que depois secam. Caule com manchas escuras que quebram fácil. Fruto com manchas marrons e firmes. Com tempo úmido, aparece um mofo branco. |
| tomate_requeima | management | [preventive] Use sementes certificadas e, quando houver, variedades resistentes.<br>[cultural] Retire da horta as folhas e plantas doentes e os restos da colheita anterior.<br>[cultural] Regue sem encharcar e mantenha a adubação equilibrada.<br>[cultural] Faça rotação de culturas e plante na época indicada para a sua região.<br>[alternative] Caldas naturais, como a bordalesa e a sulfocálcica, são usadas contra manchas nas folhas. Peça orientação técnica antes de preparar ou aplicar. | Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>Usar cultivares resistentes e sementes certificadas.<br>Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. | [cultural] Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>[cultural] Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>[preventive] Usar cultivares resistentes e sementes certificadas.<br>[alternative] Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. |
| tomate_requeima | sources | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_horta_pequenos_espacos p. 29 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct121_tomate p. 5 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct121_tomate p. 5; embrapa_ct47_cultivo_hortalicas p. 11, 14 |
| tomate_requeima | validation_status | draft | validated_by_atd | validated_by_atd |
| tomate_requeima | notes | Manejo por grupo (doenças causadas por fungos), sem orientação específica para esta doença. Sintomas específicos e validação com agrônomos (9.4.1-9). | Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_ct121_tomate p. 5. Sintomas validados pelo grupo em 10/11/2026. | Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_ct121_tomate p. 5. Sintomas validados pelo grupo em 10/11/2026. |
| tomate_cladosporiose | symptoms | (vazio) | Manchas amareladas na parte de cima da folha. Na parte de baixo, aparece um mofo verde-oliva. | Manchas amareladas na parte de cima da folha. Na parte de baixo, aparece um mofo verde-oliva. |
| tomate_cladosporiose | management | [preventive] Use sementes certificadas e, quando houver, variedades resistentes.<br>[cultural] Retire da horta as folhas e plantas doentes e os restos da colheita anterior.<br>[cultural] Regue sem encharcar e mantenha a adubação equilibrada.<br>[cultural] Faça rotação de culturas e plante na época indicada para a sua região.<br>[alternative] Caldas naturais, como a bordalesa e a sulfocálcica, são usadas contra manchas nas folhas. Peça orientação técnica antes de preparar ou aplicar. | Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>Usar cultivares resistentes e sementes certificadas.<br>Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. | [cultural] Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>[cultural] Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>[preventive] Usar cultivares resistentes e sementes certificadas.<br>[alternative] Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. |
| tomate_cladosporiose | sources | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_horta_pequenos_espacos p. 29 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct31_cladosporiose p. 4 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct31_cladosporiose p. 4; embrapa_ct47_cultivo_hortalicas p. 11, 14 |
| tomate_cladosporiose | validation_status | draft | validated_by_atd | validated_by_atd |
| tomate_cladosporiose | notes | Manejo por grupo (doenças causadas por fungos), sem orientação específica para esta doença. Sintomas específicos e validação com agrônomos (9.4.1-9). | Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_ct31_cladosporiose p. 4. Sintomas validados pelo grupo em 10/11/2026. | Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_ct31_cladosporiose p. 4. Sintomas validados pelo grupo em 10/11/2026. |
| tomate_septoriose | symptoms | (vazio) | Começa nas folhas de baixo, com pintas pequenas de aspecto molhado. Depois ficam com o centro cinza, borda escura e volta amarela. Quase nunca atinge o fruto. | Começa nas folhas de baixo, com pintas pequenas de aspecto molhado. Depois ficam com o centro cinza, borda escura e volta amarela. Quase nunca atinge o fruto. |
| tomate_septoriose | management | [preventive] Use sementes certificadas e, quando houver, variedades resistentes.<br>[cultural] Retire da horta as folhas e plantas doentes e os restos da colheita anterior.<br>[cultural] Regue sem encharcar e mantenha a adubação equilibrada.<br>[cultural] Faça rotação de culturas e plante na época indicada para a sua região.<br>[alternative] Caldas naturais, como a bordalesa e a sulfocálcica, são usadas contra manchas nas folhas. Peça orientação técnica antes de preparar ou aplicar. | Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>Usar cultivares resistentes e sementes certificadas.<br>Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. | [cultural] Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>[cultural] Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>[preventive] Usar cultivares resistentes e sementes certificadas.<br>[alternative] Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. |
| tomate_septoriose | sources | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_horta_pequenos_espacos p. 29 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct121_tomate p. 6 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct121_tomate p. 6; embrapa_ct47_cultivo_hortalicas p. 11, 14 |
| tomate_septoriose | validation_status | draft | validated_by_atd | validated_by_atd |
| tomate_septoriose | notes | Manejo por grupo (doenças causadas por fungos), sem orientação específica para esta doença. Sintomas específicos e validação com agrônomos (9.4.1-9). | Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_ct121_tomate p. 6. Sintomas validados pelo grupo em 10/11/2026. | Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_ct121_tomate p. 6. Sintomas validados pelo grupo em 10/11/2026. |
| tomate_acaro_rajado | symptoms | Colônias muito pequenas no verso das folhas, com teias finas; sugam a seiva da planta. | Ácaros são pragas microscópicas; sugam a seiva e causam deformação em folhas e brotos. | Colônias muito pequenas no verso das folhas, com teias finas; sugam a seiva da planta. |
| tomate_acaro_rajado | management | [cultural] Plante flores em volta da horta: elas abrigam joaninhas, aranhas e outros predadores das pragas.<br>[cultural] Plantas aromáticas, como coentro, cebolinha, manjericão e cravo-de-defunto, junto das hortaliças podem afastar algumas pragas.<br>[alternative] Preparados com sabão neutro, infusão de cravo-de-defunto ou calda sulfocálcica são usados contra ácaros. Peça orientação técnica antes de preparar ou aplicar. | Aplicar calda sulfocálcica, que tem ação protetora contra ácaros.<br>Aplicar preparado à base de sabão neutro, conforme orientação técnica.<br>Alternar os produtos usados, para não selecionar populações tolerantes. | [alternative] Aplicar calda sulfocálcica, que tem ação protetora contra ácaros.<br>[alternative] Aplicar preparado à base de sabão neutro, conforme orientação técnica.<br>[cultural] Alternar os produtos usados, para não selecionar populações tolerantes. |
| tomate_acaro_rajado | sources | embrapa_ct47_cultivo_hortalicas p. 12; embrapa_horta_pequenos_espacos p. 30; embrapa_ct47_cultivo_hortalicas p. 14; embrapa_horta_pequenos_espacos p. 38-39 | embrapa_ct47_cultivo_hortalicas p. 12-14 | embrapa_ct47_cultivo_hortalicas p. 12-14; embrapa_ct47_cultivo_hortalicas p. 12; embrapa_ct47_cultivo_hortalicas p. 14; embrapa_ct47_cultivo_hortalicas p. 13 |
| tomate_acaro_rajado | validation_status | draft | validated_by_atd | draft |
| tomate_mancha_alvo | symptoms | (vazio) | Manchas redondas com uma volta amarela nas folhas. As manchas se juntam e a folha seca, como se estivesse queimada. | Manchas redondas com uma volta amarela nas folhas. As manchas se juntam e a folha seca, como se estivesse queimada. |
| tomate_mancha_alvo | management | [preventive] Use sementes certificadas e, quando houver, variedades resistentes.<br>[cultural] Retire da horta as folhas e plantas doentes e os restos da colheita anterior.<br>[cultural] Regue sem encharcar e mantenha a adubação equilibrada.<br>[cultural] Faça rotação de culturas e plante na época indicada para a sua região.<br>[alternative] Caldas naturais, como a bordalesa e a sulfocálcica, são usadas contra manchas nas folhas. Peça orientação técnica antes de preparar ou aplicar. | Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>Usar cultivares resistentes e sementes certificadas.<br>Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. | [cultural] Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>[cultural] Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>[preventive] Usar cultivares resistentes e sementes certificadas.<br>[alternative] Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. |
| tomate_mancha_alvo | sources | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_horta_pequenos_espacos p. 29 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_roraima_doc03_tomate p. 8 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_roraima_doc03_tomate p. 8; embrapa_ct47_cultivo_hortalicas p. 11, 14 |
| tomate_mancha_alvo | validation_status | draft | validated_by_atd | validated_by_atd |
| tomate_mancha_alvo | notes | Manejo por grupo (doenças causadas por fungos), sem orientação específica para esta doença. Sintomas específicos e validação com agrônomos (9.4.1-9). | Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_roraima_doc03_tomate p. 8. Sintomas validados pelo grupo em 10/11/2026. | Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_roraima_doc03_tomate p. 8. Sintomas validados pelo grupo em 10/11/2026. |
| tomate_begomovirose | symptoms | Folhas e brotos novos amarelados, com manchas de verde claro e escuro (mosaico) e enrugados. | (vazio) | Folhas e brotos novos amarelados, com manchas de verde claro e escuro (mosaico) e enrugados. |
| tomate_begomovirose | management | [cultural] Não há cura depois que aparece: arranque logo as plantas doentes e destrua-as longe da horta.<br>[preventive] Combata os insetos que transmitem o vírus, como mosca-branca, pulgões e tripes.<br>[preventive] Use sementes sadias e limpe as ferramentas: o vírus também passa por ferimentos e pelo contato com plantas doentes.<br>[cultural] Elimine plantações velhas e doentes antes de começar um novo plantio. | Não há controle depois de detectada: a prevenção é controlar os insetos vetores (pulgão, mosca-branca, tripes).<br>Eliminar imediatamente as plantas infectadas por queima ou enterrio.<br>Desinfetar ferramentas e evitar contato com partes de plantas contaminadas. | [cultural] Não há controle depois de detectada: a prevenção é controlar os insetos vetores (pulgão, mosca-branca, tripes).<br>[cultural] Eliminar imediatamente as plantas infectadas por queima ou enterrio.<br>[cultural] Desinfetar ferramentas e evitar contato com partes de plantas contaminadas. |
| tomate_begomovirose | notes | Virose transmitida por mosca-branca; manejo foca no vetor e na remoção de plantas. | Virose transmitida por mosca-branca; manejo foca no vetor e na remoção de plantas. Manejo GENÉRICO para doença virótica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. | Virose transmitida por mosca-branca; manejo foca no vetor e na remoção de plantas. Manejo GENÉRICO para doença virótica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Integração v3 (módulo de IA): A versão da ATD veio sem sintoma; mantido o texto anterior do módulo de IA, com sua fonte. Entrada em draft até a ATD confirmar (pendências, item 2). |
| tomate_mosaico | symptoms | Folhas e brotos novos amarelados, com manchas de verde claro e escuro (mosaico) e enrugados. | (vazio) | Folhas e brotos novos amarelados, com manchas de verde claro e escuro (mosaico) e enrugados. |
| tomate_mosaico | management | [cultural] Não há cura depois que aparece: arranque logo as plantas doentes e destrua-as longe da horta.<br>[preventive] Combata os insetos que transmitem o vírus, como mosca-branca, pulgões e tripes.<br>[preventive] Use sementes sadias e limpe as ferramentas: o vírus também passa por ferimentos e pelo contato com plantas doentes.<br>[cultural] Elimine plantações velhas e doentes antes de começar um novo plantio. | Não há controle depois de detectada: a prevenção é controlar os insetos vetores (pulgão, mosca-branca, tripes).<br>Eliminar imediatamente as plantas infectadas por queima ou enterrio.<br>Desinfetar ferramentas e evitar contato com partes de plantas contaminadas. | [cultural] Não há controle depois de detectada: a prevenção é controlar os insetos vetores (pulgão, mosca-branca, tripes).<br>[cultural] Eliminar imediatamente as plantas infectadas por queima ou enterrio.<br>[cultural] Desinfetar ferramentas e evitar contato com partes de plantas contaminadas. |
| tomate_mosaico | notes | (vazio) | Manejo GENÉRICO para doença virótica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. | Manejo GENÉRICO para doença virótica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Integração v3 (módulo de IA): A versão da ATD veio sem sintoma; mantido o texto anterior do módulo de IA, com sua fonte. Entrada em draft até a ATD confirmar (pendências, item 2). |
| tomate_saudavel | notes | (vazio) | Classe de controle: planta sadia, sem manejo associado. | Classe de controle: planta sadia, sem manejo associado. |
| batata_pinta_preta | symptoms | (vazio) | Manchas pequenas e escuras nas folhas de baixo e mais velhas, que ficam redondas e com anéis. As manchas se juntam e a folha seca. | Manchas pequenas e escuras nas folhas de baixo e mais velhas, que ficam redondas e com anéis. As manchas se juntam e a folha seca. |
| batata_pinta_preta | management | [preventive] Use sementes certificadas e, quando houver, variedades resistentes.<br>[cultural] Retire da horta as folhas e plantas doentes e os restos da colheita anterior.<br>[cultural] Regue sem encharcar e mantenha a adubação equilibrada.<br>[cultural] Faça rotação de culturas e plante na época indicada para a sua região.<br>[alternative] Caldas naturais, como a bordalesa e a sulfocálcica, são usadas contra manchas nas folhas. Peça orientação técnica antes de preparar ou aplicar. | Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>Usar cultivares resistentes e sementes certificadas.<br>Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. | [cultural] Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>[cultural] Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>[preventive] Usar cultivares resistentes e sementes certificadas.<br>[alternative] Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. |
| batata_pinta_preta | sources | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_horta_pequenos_espacos p. 29 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_cpact_batata_organica p. 36 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_cpact_batata_organica p. 36; embrapa_ct47_cultivo_hortalicas p. 11, 14 |
| batata_pinta_preta | validation_status | draft | validated_by_atd | validated_by_atd |
| batata_pinta_preta | notes | Manejo por grupo (doenças causadas por fungos), sem orientação específica para esta doença. Sintomas específicos e validação com agrônomos (9.4.1-9). | Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_cpact_batata_organica p. 36. Sintomas validados pelo grupo em 10/11/2026. | Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_cpact_batata_organica p. 36. Sintomas validados pelo grupo em 10/11/2026. Integração v3 (módulo de IA): A página do sintoma foi marcada pela ATD como 'a conferir' (PDF de validação, pedido 6): conferir no impresso. |
| batata_requeima | symptoms | (vazio) | Manchas pardo-esverdeadas nas folhas e hastes, com mofo branco na borda. A batata fica com podridão seca marrom-avermelhada. | Manchas pardo-esverdeadas nas folhas e hastes, com mofo branco na borda. A batata fica com podridão seca marrom-avermelhada. |
| batata_requeima | management | [preventive] Use sementes certificadas e, quando houver, variedades resistentes.<br>[cultural] Retire da horta as folhas e plantas doentes e os restos da colheita anterior.<br>[cultural] Regue sem encharcar e mantenha a adubação equilibrada.<br>[cultural] Faça rotação de culturas e plante na época indicada para a sua região.<br>[alternative] Caldas naturais, como a bordalesa e a sulfocálcica, são usadas contra manchas nas folhas. Peça orientação técnica antes de preparar ou aplicar. | Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>Usar cultivares resistentes e sementes certificadas.<br>Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. | [cultural] Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>[cultural] Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>[preventive] Usar cultivares resistentes e sementes certificadas.<br>[alternative] Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. |
| batata_requeima | sources | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_horta_pequenos_espacos p. 29 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_cpact_batata_organica p. 35 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_cpact_batata_organica p. 35; embrapa_ct47_cultivo_hortalicas p. 11, 14 |
| batata_requeima | validation_status | draft | validated_by_atd | validated_by_atd |
| batata_requeima | notes | Manejo por grupo (doenças causadas por fungos), sem orientação específica para esta doença. Sintomas específicos e validação com agrônomos (9.4.1-9). | Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_cpact_batata_organica p. 35. Sintomas validados pelo grupo em 10/11/2026. | Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_cpact_batata_organica p. 35. Sintomas validados pelo grupo em 10/11/2026. Integração v3 (módulo de IA): A página do sintoma foi marcada pela ATD como 'a conferir' (PDF de validação, pedido 6): conferir no impresso. |
| batata_saudavel | notes | (vazio) | Classe de controle: planta sadia, sem manejo associado. | Classe de controle: planta sadia, sem manejo associado. |
| pimentao_mancha_bacteriana | symptoms | (vazio) | Pintas pequenas e acinzentadas nas folhas, que ficam marrons com o centro seco. Também aparece no caule, nas flores e no fruto. As folhas amarelam e caem. | Pintas pequenas e acinzentadas nas folhas, que ficam marrons com o centro seco. Também aparece no caule, nas flores e no fruto. As folhas amarelam e caem. |
| pimentao_mancha_bacteriana | management | [preventive] Use sementes e mudas sadias, de origem conhecida.<br>[cultural] Arranque as plantas doentes e destrua-as longe da horta.<br>[cultural] Evite excesso de umidade no canteiro.<br>[cultural] Onde a doença apareceu, plante por um tempo adubo verde ou culturas que não pegam a doença. | Evitar introduzir a doença por sementes ou mudas contaminadas.<br>Arrancar e queimar as plantas contaminadas.<br>Evitar excesso de umidade, que favorece o aparecimento. | [preventive] Evitar introduzir a doença por sementes ou mudas contaminadas.<br>[cultural] Arrancar e queimar as plantas contaminadas.<br>[cultural] Evitar excesso de umidade, que favorece o aparecimento. |
| pimentao_mancha_bacteriana | sources | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_horta_pequenos_espacos p. 29 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_bpd223_pimentao p. 10 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_bpd223_pimentao p. 10; embrapa_ct47_cultivo_hortalicas p. 11-12 |
| pimentao_mancha_bacteriana | validation_status | draft | validated_by_atd | validated_by_atd |
| pimentao_mancha_bacteriana | notes | Manejo por grupo (doenças causadas por bactérias), sem orientação específica para esta doença. Sintomas específicos e validação com agrônomos (9.4.1-9). | Manejo GENÉRICO para doença bacteriana (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_bpd223_pimentao p. 10. Sintomas validados pelo grupo em 10/11/2026. | Manejo GENÉRICO para doença bacteriana (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_bpd223_pimentao p. 10. Sintomas validados pelo grupo em 10/11/2026. |
| pimentao_saudavel | notes | (vazio) | Classe de controle: planta sadia, sem manejo associado. | Classe de controle: planta sadia, sem manejo associado. |
| morango_leaf_scorch | name_pt | (vazio) | Mancha-de-diplocarpon (escaldadura da folha) | Mancha-de-diplocarpon (escaldadura da folha) |
| morango_leaf_scorch | symptoms | (vazio) | Manchas irregulares roxas ou amarronzadas nas folhas, sem o centro claro. Também pode aparecer no cabo da folha, no cabo da flor e nos estolões. | Manchas irregulares roxas ou amarronzadas nas folhas, sem o centro claro. Também pode aparecer no cabo da folha, no cabo da flor e nos estolões. |
| morango_leaf_scorch | management | [preventive] Use sementes certificadas e, quando houver, variedades resistentes.<br>[cultural] Retire da horta as folhas e plantas doentes e os restos da colheita anterior.<br>[cultural] Regue sem encharcar e mantenha a adubação equilibrada.<br>[cultural] Faça rotação de culturas e plante na época indicada para a sua região.<br>[alternative] Caldas naturais, como a bordalesa e a sulfocálcica, são usadas contra manchas nas folhas. Peça orientação técnica antes de preparar ou aplicar. | Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>Usar cultivares resistentes e sementes certificadas.<br>Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. | [cultural] Equilibrar a adubação, controlar a irrigação e eliminar restos de cultura contaminados.<br>[cultural] Fazer rotação de culturas e plantar na época favorável à hortaliça.<br>[preventive] Usar cultivares resistentes e sementes certificadas.<br>[alternative] Aplicar defensivo natural: calda bordalesa ou calda sulfocálcica. |
| morango_leaf_scorch | sources | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_horta_pequenos_espacos p. 29 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct96_morango p. 3; senar_pr0355_morango p. 18 | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct96_morango p. 3; senar_pr0355_morango p. 18; embrapa_ct47_cultivo_hortalicas p. 11, 14 |
| morango_leaf_scorch | validation_status | draft | validated_by_atd | validated_by_atd |
| morango_leaf_scorch | notes | Manejo por grupo (doenças causadas por fungos), sem orientação específica para esta doença. Sintomas específicos e validação com agrônomos (9.4.1-9). Nome popular pendente. | Nome popular: Embrapa CT 96 (p. 3) e SENAR-PR PR.0355 (p. 18). As fontes grafam Diplocarpon earliana; é o mesmo fungo. Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_ct96_morango p. 3; senar_pr0355_morango p. 18. Sintomas validados pelo grupo em 10/11/2026. | Nome popular: Embrapa CT 96 (p. 3) e SENAR-PR PR.0355 (p. 18). As fontes grafam Diplocarpon earliana; é o mesmo fungo. Manejo GENÉRICO para doença fúngica (CT 47, p. 11). Pendente manejo específico desta doença em fonte própria. Sintomas (v3): embrapa_ct96_morango p. 3; senar_pr0355_morango p. 18. Sintomas validados pelo grupo em 10/11/2026. |
| morango_saudavel | notes | (vazio) | Classe de controle: planta sadia, sem manejo associado. | Classe de controle: planta sadia, sem manejo associado. |
| praga_formigas | crop_ids | (vazio) | tomate, batata, pimentao, morango, alface, couve, rucula, repolho, cenoura, beterraba, rabanete, cebolinha, salsa, manjericao, abobrinha | (vazio) |
| praga_formigas | symptoms | Cortam folhas e ramos novos. | Aparelho bucal cortador: cortam folhas e ramos novos. | Aparelho bucal cortador: cortam folhas e ramos novos. |
| praga_formigas | management | [cultural] Gergelim plantado perto da horta ajuda contra formigas-cortadeiras: as folhas levadas para o formigueiro prejudicam o fungo de que elas se alimentam. Prefira o gergelim de semente preta.<br>[cultural] Plantas aromáticas, como coentro, cebolinha, manjericão e cravo-de-defunto, junto das hortaliças podem afastar algumas pragas. | Plantar flores em volta da horta para abrigar predadores naturais. | [cultural] Plantar flores em volta da horta para abrigar predadores naturais. |
| praga_formigas | sources | embrapa_ct47_cultivo_hortalicas p. 12; embrapa_horta_pequenos_espacos p. 40; embrapa_horta_pequenos_espacos p. 30 | embrapa_ct47_cultivo_hortalicas p. 11-14; embrapa_horta_pequenos_espacos p. 29; senar_pr0306_pragas p. 17 | embrapa_ct47_cultivo_hortalicas p. 11-14; embrapa_horta_pequenos_espacos p. 29; senar_pr0306_pragas p. 17; embrapa_ct47_cultivo_hortalicas p. 12 |
| praga_formigas | validation_status | draft | validated_by_atd | validated_by_atd |
| praga_formigas | notes | Decidir com agrônomos se a classe 'ants' deve ser tratada como praga (só as cortadeiras cortam folhas). | Ambíguo: formigas-cortadeiras são pragas, outras são neutras. Definir antes de revisar. AMBÍGUO: a CT 47 (p. 12) descreve formigas como cortadeiras, mas a classe do dataset não distingue espécie. Formigas não cortadeiras são neutras ou predadoras. Confirmar antes de recomendar controle. Fontes v3: HPE (p. 29) lista formigas entre os insetos mastigadores e cortadores; SENAR-PR PR.0306 (p. 17) cita formigas caçadoras como predadoras da larva-minadora. Segue ambígua. | Ambíguo: formigas-cortadeiras são pragas, outras são neutras. Definir antes de revisar. AMBÍGUO: a CT 47 (p. 12) descreve formigas como cortadeiras, mas a classe do dataset não distingue espécie. Formigas não cortadeiras são neutras ou predadoras. Confirmar antes de recomendar controle. Fontes v3: HPE (p. 29) lista formigas entre os insetos mastigadores e cortadores; SENAR-PR PR.0306 (p. 17) cita formigas caçadoras como predadoras da larva-minadora. Segue ambígua. Integração v3 (módulo de IA): Fonte do sintoma indicada pela ATD: CT 47 p. 12 (notas) e HPE p. 29 (notas e PDF de validação, pedido 3). |
| praga_besouros | crop_ids | (vazio) | tomate, batata, pimentao, morango, alface, couve, rucula, repolho, cenoura, beterraba, rabanete, cebolinha, salsa, manjericao, abobrinha | (vazio) |
| praga_besouros | symptoms | Comem e furam folhas, brotos e frutos; os mais comuns são as vaquinhas e os burrinhos. | Mastigadores: comem e perfuram folhas, brotos e frutos. Os mais comuns são os chamados burrinhos e vaquinhas. | Mastigadores: comem e perfuram folhas, brotos e frutos. Os mais comuns são os chamados burrinhos e vaquinhas. |
| praga_besouros | management | [cultural] Plante flores em volta da horta: elas abrigam joaninhas, aranhas e outros predadores das pragas.<br>[cultural] Plantas aromáticas, como coentro, cebolinha, manjericão e cravo-de-defunto, junto das hortaliças podem afastar algumas pragas.<br>[alternative] Calda de cebola é usada como repelente de vaquinhas, pulgões e lagartas. Peça orientação técnica antes de preparar ou aplicar. | Aplicar calda de fumo com pimenta, indicada para vaquinhas.<br>Aplicar calda de cebola, que repele vaquinhas. | [alternative] Aplicar calda de fumo com pimenta, indicada para vaquinhas.<br>[alternative] Aplicar calda de cebola, que repele vaquinhas. |
| praga_besouros | sources | embrapa_ct47_cultivo_hortalicas p. 12; embrapa_horta_pequenos_espacos p. 30; embrapa_ct47_cultivo_hortalicas p. 14; embrapa_horta_pequenos_espacos p. 38 | embrapa_ct47_cultivo_hortalicas p. 11-14; embrapa_horta_pequenos_espacos p. 29; senar_pr0306_pragas p. 13, 23 | embrapa_ct47_cultivo_hortalicas p. 11-14; embrapa_horta_pequenos_espacos p. 29; senar_pr0306_pragas p. 13, 23; embrapa_ct47_cultivo_hortalicas p. 12; embrapa_ct47_cultivo_hortalicas p. 14 |
| praga_besouros | validation_status | draft | validated_by_atd | validated_by_atd |
| praga_besouros | notes | A classe 'beetle' pode incluir joaninhas, que são predadoras de pragas (CT 47 p. 12). Decidir com agrônomos. | Ambíguo: a classe pode incluir joaninhas, que são predadoras benéficas. AMBÍGUO: a classe do dataset agrupa besouros-praga (vaquinha, Diabrotica) e predadores benéficos (joaninha). A CT 47 (p. 12) cita a joaninha como predadora de pragas. Não recomendar controle sem confirmar a espécie. Fontes v3: HPE (p. 29) cita burrinhos e vaquinhas como pragas; SENAR-PR PR.0306 traz joaninhas como inimigas naturais dos pulgões (p. 13) e a vaquinha como praga (p. 23). Segue ambíguo. | Ambíguo: a classe pode incluir joaninhas, que são predadoras benéficas. AMBÍGUO: a classe do dataset agrupa besouros-praga (vaquinha, Diabrotica) e predadores benéficos (joaninha). A CT 47 (p. 12) cita a joaninha como predadora de pragas. Não recomendar controle sem confirmar a espécie. Fontes v3: HPE (p. 29) cita burrinhos e vaquinhas como pragas; SENAR-PR PR.0306 traz joaninhas como inimigas naturais dos pulgões (p. 13) e a vaquinha como praga (p. 23). Segue ambíguo. Integração v3 (módulo de IA): Fonte do sintoma: HPE p. 29, indicada pela ATD (notas e PDF de validação, pedido 3), e CT 47 p. 12, fonte do texto anterior, que a ATD manteve (furam folhas, brotos e frutos; vaquinhas e burrinhos). |
| praga_lagartas | crop_ids | (vazio) | tomate, batata, pimentao, morango, alface, couve, rucula, repolho, cenoura, beterraba, rabanete, cebolinha, salsa, manjericao, abobrinha | (vazio) |
| praga_lagartas | symptoms | Comem as folhas; as menores entram em frutos e brotos. A lagarta-rosca vive no solo e derruba plantas novas à noite. | Mastigadores. As menores penetram frutos, folhas e brotos; as maiores comem as folhas. Os ferimentos abrem porta de entrada para doenças. A lagarta-rosca vive enterrada e ataca a planta nova à noite, podendo derrubá-la. | Comem as folhas; as menores entram em frutos e brotos. A lagarta-rosca vive no solo e derruba plantas novas à noite. |
| praga_lagartas | management | [biological] Produtos biológicos à base de Bacillus thuringiensis ou de baculovírus controlam lagartas. Compre em loja agropecuária e siga o rótulo.<br>[cultural] Plante flores em volta da horta: elas abrigam joaninhas, aranhas e outros predadores das pragas.<br>[cultural] Plantas aromáticas, como coentro, cebolinha, manjericão e cravo-de-defunto, junto das hortaliças podem afastar algumas pragas.<br>[alternative] Extrato de folhas de nim é usado contra lagartas e outros insetos. Peça orientação técnica antes de preparar ou aplicar. | Aplicar defensivo biológico: Bacillus thuringiensis ou baculovírus.<br>Aplicar calda de fumo com pimenta ou preparado de sabão neutro.<br>Aplicar calda de cebola, que age como repelente.<br>Preservar inimigos naturais: vespas do gênero Trichogramma parasitam lagartas.<br>Plantar flores em volta da horta para abrigar predadores naturais. | [biological] Aplicar defensivo biológico: Bacillus thuringiensis ou baculovírus.<br>[alternative] Aplicar calda de fumo com pimenta ou preparado de sabão neutro.<br>[alternative] Aplicar calda de cebola, que age como repelente.<br>[biological] Preservar inimigos naturais: vespas do gênero Trichogramma parasitam lagartas.<br>[cultural] Plantar flores em volta da horta para abrigar predadores naturais. |
| praga_lagartas | sources | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct47_cultivo_hortalicas p. 13; embrapa_ct47_cultivo_hortalicas p. 12; embrapa_horta_pequenos_espacos p. 30; embrapa_horta_pequenos_espacos p. 37 | embrapa_ct47_cultivo_hortalicas p. 11-14 | embrapa_ct47_cultivo_hortalicas p. 11-14; embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct47_cultivo_hortalicas p. 13; embrapa_ct47_cultivo_hortalicas p. 14; embrapa_ct47_cultivo_hortalicas p. 12 |
| praga_lagartas | validation_status | draft | validated_by_atd | draft |
| praga_tesourinhas | crop_ids | (vazio) | tomate, batata, pimentao, morango, alface, couve, rucula, repolho, cenoura, beterraba, rabanete, cebolinha, salsa, manjericao, abobrinha | (vazio) |
| praga_tesourinhas | symptoms | (vazio) | Inseto que atua como inimigo natural no controle biológico, com evidência para a cultura do milho (preda ovos e lagartas pequenas da lagarta-do-cartucho). Em hortaliças, pode contribuir para o controle natural de algumas pragas. | Inseto que atua como inimigo natural no controle biológico, com evidência para a cultura do milho (preda ovos e lagartas pequenas da lagarta-do-cartucho). Em hortaliças, pode contribuir para o controle natural de algumas pragas. |
| praga_tesourinhas | sources | (vazio) | embrapa_ct47_cultivo_hortalicas p. 11-14; senar_pr0306_pragas p. 13; embrapa_folder_doru_milho p. 1; reis_1988_doru_spodoptera p. None; redoan_2013_doru_seletividade p. 842 | embrapa_ct47_cultivo_hortalicas p. 11-14; senar_pr0306_pragas p. 13; embrapa_folder_doru_milho p. 1; reis_1988_doru_spodoptera p. None; redoan_2013_doru_seletividade p. 842 |
| praga_tesourinhas | notes | Podem atuar como predadoras de pulgões; verificar antes de recomendar controle. Sem conteúdo nas fontes da base; pendente com agrônomos (9.4.1-9). | Podem atuar como predadoras de pulgões; verificar antes de recomendar controle. AMBÍGUO e SEM FONTE: a CT 47 não descreve a tesourinha. Pendente de levantamento em fonte própria antes de virar recomendação. Fonte v3: SENAR-PR PR.0306 (p. 13) cita a tesourinha Doru luteipes como inimigo natural. Nenhuma fonte consultada a descreve como praga. Reclassificar como benéfica depende de decisão do grupo. Decisão do grupo (10/11/2026): não reclassificar como benéfica para hortaliças. A evidência de inimigo natural é para o milho; não há fonte de controle de pragas específicas das culturas desta base. Não recomendar controle da tesourinha; não afirmar que ela controla pragas de cada cultura. | Podem atuar como predadoras de pulgões; verificar antes de recomendar controle. AMBÍGUO e SEM FONTE: a CT 47 não descreve a tesourinha. Pendente de levantamento em fonte própria antes de virar recomendação. Fonte v3: SENAR-PR PR.0306 (p. 13) cita a tesourinha Doru luteipes como inimigo natural. Nenhuma fonte consultada a descreve como praga. Reclassificar como benéfica depende de decisão do grupo. Decisão do grupo (10/11/2026): não reclassificar como benéfica para hortaliças. A evidência de inimigo natural é para o milho; não há fonte de controle de pragas específicas das culturas desta base. Não recomendar controle da tesourinha; não afirmar que ela controla pragas de cada cultura. Integração v3 (módulo de IA): Fonte do sintoma indicada pela ATD (PDF de validação, pedido 3): SENAR-PR PR.0306 p. 13 e Revista Ciência Agronômica (2013) p. 842. O trecho 'preda ovos e lagartas pequenas' vem da Embrapa Milho e Sorgo, sem página (o conteúdo do folder não foi consultado e Reis 1988 está sem página): pendente. |
| praga_gafanhotos | crop_ids | (vazio) | tomate, batata, pimentao, morango, alface, couve, rucula, repolho, cenoura, beterraba, rabanete, cebolinha, salsa, manjericao, abobrinha | (vazio) |
| praga_gafanhotos | symptoms | Comem ramos e folhas. | Mastigadores: comem ramos e folhas das plantas. A CT 47 trata paquinhas, grilos e gafanhotos no mesmo grupo. | Comem ramos e folhas. |
| praga_gafanhotos | management | [cultural] Plante flores em volta da horta: elas abrigam joaninhas, aranhas e outros predadores das pragas.<br>[cultural] Plantas aromáticas, como coentro, cebolinha, manjericão e cravo-de-defunto, junto das hortaliças podem afastar algumas pragas. | Usar armadilha luminosa associada a recipiente com água ou óleo.<br>Plantar flores em volta da horta para abrigar predadores naturais. | [alternative] Usar armadilha luminosa associada a recipiente com água ou óleo.<br>[cultural] Plantar flores em volta da horta para abrigar predadores naturais. |
| praga_gafanhotos | sources | embrapa_ct47_cultivo_hortalicas p. 12; embrapa_horta_pequenos_espacos p. 30 | embrapa_ct47_cultivo_hortalicas p. 11-14 | embrapa_ct47_cultivo_hortalicas p. 11-14; embrapa_ct47_cultivo_hortalicas p. 12; embrapa_ct47_cultivo_hortalicas p. 13 |
| praga_gafanhotos | validation_status | draft | validated_by_atd | draft |
| praga_gafanhotos | notes | Sem manejo específico nas fontes; validar com agrônomos. | (vazio) | Integração v3 (módulo de IA): Sintoma: mantido o texto anterior do módulo de IA, com sua fonte, porque a ATD propôs um texto novo sem indicar fonte e página: «Mastigadores: comem ramos e folhas das plantas. A CT 47 trata paquinhas, grilos e gafanhotos no mesmo grupo.». Entrada em draft até a ATD indicar a fonte (pendências, item 2). |
| praga_mariposas | crop_ids | (vazio) | tomate, batata, pimentao, morango, alface, couve, rucula, repolho, cenoura, beterraba, rabanete, cebolinha, salsa, manjericao, abobrinha | (vazio) |
| praga_mariposas | symptoms | As mariposas adultas não comem a planta; o estrago é feito pelas lagartas que nascem dos ovos delas. | O adulto não causa dano direto. A CT 47 cita moscas, besouros, borboletas e mariposas como as fases adultas que originam as larvas e lagartas, estas sim mastigadoras. | As mariposas adultas não comem a planta; o estrago é feito pelas lagartas que nascem dos ovos delas. |
| praga_mariposas | management | [cultural] Armadilhas com luz sobre um recipiente com água ajudam a reduzir mariposas e outros insetos.<br>[biological] Produtos biológicos à base de Bacillus thuringiensis ou de baculovírus controlam lagartas. Compre em loja agropecuária e siga o rótulo.<br>[cultural] Plante flores em volta da horta: elas abrigam joaninhas, aranhas e outros predadores das pragas. | Usar armadilha luminosa ou recipiente com melaço ou feromônio para reduzir a população de adultos.<br>Tratar como alerta precoce: a presença do adulto antecede o ataque das lagartas. | [cultural] Usar armadilha luminosa ou recipiente com melaço ou feromônio para reduzir a população de adultos.<br>[cultural] Tratar como alerta precoce: a presença do adulto antecede o ataque das lagartas. |
| praga_mariposas | sources | embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct47_cultivo_hortalicas p. 13; embrapa_ct47_cultivo_hortalicas p. 12 | embrapa_ct47_cultivo_hortalicas p. 11-14 | embrapa_ct47_cultivo_hortalicas p. 11-14; embrapa_ct47_cultivo_hortalicas p. 11; embrapa_ct47_cultivo_hortalicas p. 13 |
| praga_mariposas | validation_status | draft | validated_by_atd | draft |
| praga_mariposas | notes | O dano é causado pela fase larval (lagarta). | O dano é causado pela fase larval (lagarta). O dano é causado pela fase larval. | O dano é causado pela fase larval (lagarta). O dano é causado pela fase larval. Integração v3 (módulo de IA): Sintoma: mantido o texto anterior do módulo de IA, com sua fonte, porque a ATD propôs um texto novo sem indicar fonte e página: «O adulto não causa dano direto. A CT 47 cita moscas, besouros, borboletas e mariposas como as fases adultas que originam as larvas e lagartas, estas sim mastigadoras.». Entrada em draft até a ATD indicar a fonte (pendências, item 2). |
| praga_lesmas | crop_ids | (vazio) | tomate, batata, pimentao, morango, alface, couve, rucula, repolho, cenoura, beterraba, rabanete, cebolinha, salsa, manjericao, abobrinha | (vazio) |
| praga_lesmas | symptoms | Raspam folhas e ramos novos; aparecem mais quando há muita umidade. | Aparelho bucal raspador: raspam as folhas e os ramos novos das hortaliças. | Raspam folhas e ramos novos; aparecem mais quando há muita umidade. |
| praga_lesmas | management | [cultural] Evite excesso de água no canteiro.<br>[cultural] À noite, deixe no chão, perto das plantas, um saco de pano molhado com água e um pouco de leite. De manhã, vire o saco e recolha as lesmas e caracóis que se juntaram embaixo. | Armadilha com leite: espalhar estopa ou saco de aniagem molhado com água e leite ao redor das plantas; pela manhã, virar e recolher os animais reunidos embaixo. | [cultural] Armadilha com leite: espalhar estopa ou saco de aniagem molhado com água e leite ao redor das plantas; pela manhã, virar e recolher os animais reunidos embaixo. |
| praga_lesmas | sources | embrapa_ct47_cultivo_hortalicas p. 12; embrapa_horta_pequenos_espacos p. 29; embrapa_ct47_cultivo_hortalicas p. 14; embrapa_horta_pequenos_espacos p. 39 | embrapa_ct47_cultivo_hortalicas p. 11-14 | embrapa_ct47_cultivo_hortalicas p. 11-14; embrapa_ct47_cultivo_hortalicas p. 12; embrapa_horta_pequenos_espacos p. 29; embrapa_ct47_cultivo_hortalicas p. 14 |
| praga_lesmas | validation_status | draft | validated_by_atd | draft |
| praga_lesmas | notes | (vazio) | Dano mais relevante em folhosas e em canteiro úmido. | Dano mais relevante em folhosas e em canteiro úmido. Integração v3 (módulo de IA): Sintoma: mantido o texto anterior do módulo de IA, com sua fonte, porque a ATD propôs um texto novo sem indicar fonte e página: «Aparelho bucal raspador: raspam as folhas e os ramos novos das hortaliças.». Entrada em draft até a ATD indicar a fonte (pendências, item 2). |
| praga_caracois | crop_ids | (vazio) | tomate, batata, pimentao, morango, alface, couve, rucula, repolho, cenoura, beterraba, rabanete, cebolinha, salsa, manjericao, abobrinha | (vazio) |
| praga_caracois | symptoms | Raspam folhas e ramos novos; aparecem mais quando há muita umidade. | Aparelho bucal raspador: raspam as folhas e os ramos novos das hortaliças. | Raspam folhas e ramos novos; aparecem mais quando há muita umidade. |
| praga_caracois | management | [cultural] Evite excesso de água no canteiro.<br>[cultural] À noite, deixe no chão, perto das plantas, um saco de pano molhado com água e um pouco de leite. De manhã, vire o saco e recolha as lesmas e caracóis que se juntaram embaixo. | Armadilha com leite: espalhar estopa ou saco de aniagem molhado com água e leite ao redor das plantas; pela manhã, virar e recolher os animais reunidos embaixo. | [cultural] Armadilha com leite: espalhar estopa ou saco de aniagem molhado com água e leite ao redor das plantas; pela manhã, virar e recolher os animais reunidos embaixo. |
| praga_caracois | sources | embrapa_ct47_cultivo_hortalicas p. 12; embrapa_horta_pequenos_espacos p. 29; embrapa_ct47_cultivo_hortalicas p. 14; embrapa_horta_pequenos_espacos p. 39 | embrapa_ct47_cultivo_hortalicas p. 11-14 | embrapa_ct47_cultivo_hortalicas p. 11-14; embrapa_ct47_cultivo_hortalicas p. 12; embrapa_horta_pequenos_espacos p. 29; embrapa_ct47_cultivo_hortalicas p. 14 |
| praga_caracois | validation_status | draft | validated_by_atd | draft |
| praga_caracois | notes | (vazio) | Mesmo tipo de dano da lesma. | Mesmo tipo de dano da lesma. Integração v3 (módulo de IA): Sintoma: mantido o texto anterior do módulo de IA, com sua fonte, porque a ATD propôs um texto novo sem indicar fonte e página: «Aparelho bucal raspador: raspam as folhas e os ramos novos das hortaliças.». Entrada em draft até a ATD indicar a fonte (pendências, item 2). |
| benefico_vespas | type | pest | beneficial | beneficial |
| benefico_vespas | crop_ids | (vazio) | tomate, batata, pimentao, morango, alface, couve, rucula, repolho, cenoura, beterraba, rabanete, cebolinha, salsa, manjericao, abobrinha | (vazio) |
| benefico_vespas | symptoms | (vazio) | Inimigo natural. A CT 47 (p. 12) cita a vespa entre os insetos predadores de pragas e (p. 13) registra o uso de Trichogramma pretiosum no controle de traças. | Inimigo natural. A CT 47 (p. 12) cita a vespa entre os insetos predadores de pragas e (p. 13) registra o uso de Trichogramma pretiosum no controle de traças. |
| benefico_vespas | management | (vazio) | Não controlar. Preservar plantando flores em volta da horta, que servem de abrigo e refúgio. | (vazio) |
| benefico_vespas | sources | embrapa_ct47_cultivo_hortalicas p. 12 | embrapa_ct47_cultivo_hortalicas p. 11-14 | embrapa_ct47_cultivo_hortalicas p. 11-14; embrapa_ct47_cultivo_hortalicas p. 12; embrapa_ct47_cultivo_hortalicas p. 13 |
| benefico_vespas | validation_status | draft | validated_by_atd | validated_by_atd |
| benefico_vespas | notes | Muitas espécies são predadoras ou parasitoides. Não recomendar controle. Fonte: CT 47, p. 12 (vespas como predadoras naturais das pragas, mesma passagem da diretriz flores_abrigo_inimigos_naturais). | Muitas espécies são predadoras ou parasitoides. Não recomendar controle. Reclassificado de 'pest' para 'beneficial'. | Muitas espécies são predadoras ou parasitoides. Não recomendar controle. Reclassificado de 'pest' para 'beneficial'. Integração v3 (módulo de IA): Fonte do sintoma: CT 47 pp. 12 e 13, citadas no próprio texto da ATD. Ação proposta pela ATD, não gravada em management porque entradas benéficas não têm ações: «Não controlar. Preservar plantando flores em volta da horta, que servem de abrigo e refúgio.». |
| praga_gorgulhos | crop_ids | (vazio) | tomate, batata, pimentao, morango, alface, couve, rucula, repolho, cenoura, beterraba, rabanete, cebolinha, salsa, manjericao, abobrinha | (vazio) |
| praga_gorgulhos | symptoms | (vazio) | Não descrito individualmente na CT 47. | (vazio) |
| praga_gorgulhos | sources | (vazio) | embrapa_ct47_cultivo_hortalicas p. 11-14 | embrapa_ct47_cultivo_hortalicas p. 11-14 |
| praga_gorgulhos | notes | Sem conteúdo nas fontes da base; pendente com agrônomos (9.4.1-9). | SEM FONTE na base atual e baixa relevância em horta urbana: o gorgulho é associado sobretudo a grãos armazenados. Avaliar se a classe deve permanecer no modelo. | SEM FONTE na base atual e baixa relevância em horta urbana: o gorgulho é associado sobretudo a grãos armazenados. Avaliar se a classe deve permanecer no modelo. Integração v3 (módulo de IA): Texto proposto pela ATD para o sintoma, não gravado por não trazer fonte com página (e por descrever a falta de fonte, não o sintoma): «Não descrito individualmente na CT 47.» (pendências, item 2). |

---

## Resumo do que foi integrado

| Arquivo | Antes | Depois | Observação |
|---|---|---|---|
| `crops.json` | 15 culturas | 20 culturas | 13 `validated_by_atd`, 7 `draft` (rúcula, manjericão, hortelã e as 4 com época preenchida pelo módulo) |
| `companions.csv` | 37 relações | 51 relações | 37 tradicionais (valem), 7 técnicas e 7 de pesquisa (fora das respostas, itens 3 e 6) |
| `guidelines.json` | 15 diretrizes | 21 diretrizes | As 6 da v3 |
| `sources.json` | 9 fontes | 38 fontes | 25 da v3 e 4 pendentes (item 3); 6 não verificadas no total (as 4 pendentes e os 2 datasets de imagem) |
| `pests_diseases.json` | 27 entradas, todas `draft`, 10 com sintoma | 27 entradas: 13 `validated_by_atd`, 14 `draft` | 22 com sintoma, 20 com manejo, 19 com alguma ação que aparece no assistente |

Não mexemos em `images_manifest.csv` nem em `image_sources.json`, que são do modelo de visão.
