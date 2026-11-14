# Dataset de NLU — Assistente Conversacional (WBS 9.4)

Dados para o classificador de intenções do assistente. Substitui as estimativas das seções 5.1 e
5.2 do Levantamento de Dados, que foram escritas antes da base de conhecimento existir.

| Arquivo | Conteúdo | Quem escreve |
|---|---|---|
| `intents.yaml` | Exemplos de treino: 8 intenções, 30 a 50 frases cada | Rascunho da equipe, a ser substituído por perguntas reais |
| `test_utterances.yaml` | Conjunto de teste separado (critério de aceite do 9.4.1) | Quem **não** leu o `intents.yaml`, ou perguntas reais coletadas em campo |
| `responses.yaml` | Modelos de texto das respostas, em linguagem simples | Equipe, a validar com agrônomos |

Carregue com `hort_ia.nlp` (`load_intents`, `load_test_set`, `load_templates`). Avaliação de referência:

```bash
uv run python scripts/evaluate_nlu_baseline.py
```

## Intenções

| Intenção | Pergunta típica | Respondida por |
|---|---|---|
| `planting_time` | "quando planto alface?" | `Crop.planting_months(region)` |
| `what_to_plant` | "o que dá pra plantar agora?" | janelas de todas as culturas, filtradas por mês e região |
| `crop_care` | "quanto rego o tomate?", "dá em vaso?" | espaçamento, colheita, `small_space_recommended`, `guidelines.json` |
| `companion_planting` | "o que planto junto do tomate?" | `companions.csv`, `companion_roles`, diretrizes de rotação e repelentes |
| `pest_disease` | "meu tomate tá com mancha preta" | `pests_diseases.json` (+ rótulo do modelo de CV, quando há foto) |
| `market_price` | "quanto tá o tomate no Ceasa?" | base de mercado (`data/market/`) |
| `help` | "oi", "o que você sabe fazer?" | texto fixo |
| `fallback` | fora do escopo, ou pedido de falar com uma pessoa | texto fixo + encaminhamento à Assistência Técnica Digital |

## Fronteiras entre intenções

Casos que confundem, e a decisão tomada para cada um:

- **Colheita** ("quando colho a alface?") é `crop_care`, não `planting_time`. Já "quando planto X
  para colher?" ("quando planto beterraba pra colher no inverno?") é `planting_time`: a pergunta é a
  época de plantar, e a colheita só diz para quando.
- **Rotação** ("o que planto no lugar do repolho?") é `companion_planting`: é respondida pela
  diretriz de rotação por família.
- **Cultura específica × sugestão**: com cultura citada é `planting_time`; sem cultura é
  `what_to_plant`. O classificador confunde as duas, então o motor deve corrigir pela presença da
  entidade `crop` (ver "Linha de base").
- **Preço de produto** (tomate no Ceasa) é `market_price`; **preço de insumo** (muda, adubo,
  semente) é `fallback`, porque a base de mercado só tem preços de hortaliças no atacado.
- **Assunto fora da KB que cita cultura** ("receita de bolo de cenoura", "calorias do tomate",
  "conservar alface na geladeira") é `fallback`. Esses exemplos ensinam o modelo a não responder
  só porque reconheceu o nome de uma planta.
- **Pedido de falar com alguém** ("quero falar com um técnico") é `fallback`, porque leva ao
  encaminhamento para a Assistência Técnica Digital.

## Campo `origin`

| Valor | Significado |
|---|---|
| `draft` | Rascunho inicial (out/2026), feito com apoio de IA. Deve ser revisado e, aos poucos, substituído. |
| `team` | Escrito por alguém da equipe. |
| `field` | Pergunta real, transcrita como foi dita por agrônomo, coordenador de horta ou agricultor. |

O objetivo é que a proporção de `field` cresça. Perguntas reais valem mais que qualquer volume de
frases inventadas.

## Regras do conjunto de teste

1. **Quem escreve não pode ter lido o `intents.yaml`.** Se a mesma pessoa escreve treino e teste,
   os dois saem no mesmo estilo e a acurácia medida não vale para usuários reais.
2. **Perguntas coletadas em campo vão para o teste**, não para o treino, até haver pelo menos 10
   por intenção. Depois disso, as excedentes podem reforçar o treino.
3. **Transcrever como foi dito**, com erros, gírias e sem corrigir acentos.
4. **`intent: null`** quando a pergunta não se encaixa em nenhuma intenção. Essas perguntas indicam
   intenções que estão faltando e são o resultado mais útil da coleta.
5. **LGPD:** em `collected_from`, registrar só o papel (agrônomo, coordenador, agricultor), nunca
   o nome.

Os testes (`tests/test_nlu_dataset.py`) barram frase repetida entre treino e teste, intenção
desconhecida, frase duplicada entre intenções e intenção com menos de 30 ou mais de 50 exemplos.

**Por que de 30 a 50 exemplos por intenção.**

- **Mínimo de 30.** Um classificador TF-IDF precisa de dezenas de frases por intenção (estudo de
  9.4.1-1) para não ficar preso a poucas construções. A validação cruzada de 5 partes deixa cerca de 6
  frases por intenção em cada parte de teste, o mínimo para a medida não oscilar com uma frase só. E é
  o espaço para os três estilos (padrão, informal, com erro de digitação) espalhados pelas 20 culturas.
- **Máximo de 50.** Mantém as intenções equilibradas: a regressão logística favorece as classes com
  mais exemplos, e com esse teto a razão entre a maior e a menor fica abaixo de 1,7 para 1. Também freia
  o rascunho, que sem teto tende a crescer com variações da mesma frase, o que infla a validação cruzada
  sem ensinar vocabulário novo.
- **Quando revisar.** Com perguntas reais em volume (mais de 10 por intenção no teste, regra 2), o teto
  pode subir, desde que o equilíbrio entre intenções se mantenha. Mudar o limite é decisão da equipe.

## Linha de base (out/2026, rascunho, validação cruzada)

TF-IDF de n-gramas de caracteres + regressão logística: **73% de acurácia** em validação cruzada
de 5 partes sobre os 318 exemplos do rascunho (média de 5 partições; a primeira medição, de uma
partição só, deu 76%). A comparação com outras abordagens está no estudo de 9.4.1-1
(`docs/nlu/9.4.1-1_Estudo_Abordagens_NLU.md`). Como os dados vêm de um autor só, esse número é um
teto otimista; o número que vale é o do conjunto de teste.

As confusões mais frequentes orientam a abordagem do motor (9.4.1-3):

- `planting_time` × `what_to_plant`: a diferença é a presença de uma cultura, o que a extração de
  entidades resolve melhor do que o classificador.
- `fallback` é a classe mais fraca: fora do escopo é tudo que não é o resto, sem padrão próprio.
  Um limiar de confiança no classificador tende a funcionar melhor do que tratá-la como classe comum.
- `help` × `fallback`: perguntas sobre o uso do aplicativo ficam na fronteira entre as duas.

### Vocabulário de cuidados e pragas (14/11/2026)

No ensaio do roteiro de UAT (13/11/2026), as palavras de quem é da área não apareciam no treino:
"cuidado", "manejo", "solo", "pH" e "substrato" em nenhum exemplo, e "praga" e "doença" em três.
Sem elas, o modelo decidia pelo nome da cultura: batata estava em 6 exemplos de `market_price`, e uma
pergunta de cuidados com batata virava preço. O treino ganhou exemplos com essas palavras, escritos a
partir de uma lista de palavras, com outras culturas e construções, sem abrir o conjunto de teste.
Também foram retirados exemplos redundantes (a mesma construção com outra cultura) e as culturas foram
espalhadas: em `market_price`, `companion_planting` e `pest_disease`, o tomate deixou de concentrar os
exemplos.

**Validação cruzada:** 73,6% (5 partes, regra de entidade em um só sentido, média de 5 partições), sobre
334 exemplos. Antes eram 76,5% sobre 323. A queda não é piora. Os exemplos retirados eram os
redundantes, que a validação cruzada acerta com facilidade porque há outro quase igual no treino. E os
que entraram são mais difíceis: palavras novas, culturas trocadas para o modelo não decidir pelo nome, e
frases curtas como "dicas de cuidado?". As sondas de vocabulário, frases que não estão no treino
(`tests/test_nlu_interpreter.py`), passaram de 9 para 15 acertos em 16.

**Marcador de cultura (avaliado e adiado).** A hipótese era trocar o nome da cultura por um marcador fixo
("cultura") só na entrada do classificador, para tirar o viés de cultura pela raiz. Passou no critério
de adoção (validação cruzada de 73,6% para 78,4%, nenhuma intenção caindo mais de 5 pontos; 74,9% para
80,1% numa versão anterior do treino), mas foi adiado. Com o marcador, a palavra "cultura" ganha peso
para as intenções com planta, e as mensagens sem cultura, sem esse peso, pendem para `what_to_plant` e
`help`. Num caso de referência isso criou uma resposta direta errada: "planta aguenta frio?" passou a
responder a lista do que plantar. Também "e a rega dela?" deixou de ser respondida direto. Reavaliar
depois da UAT, com perguntas reais.

**Limites conhecidos** do treino atual, registrados nos testes:

- "vale a pena ter horta?" confirma `market_price` (0,32), em vez de encaminhar. Não é resposta
  direta, e o treino não foi ajustado para essa frase.
- A sonda "que tipo de solo o espinafre prefere?" fica em `help` (0,32). Ela é marcada como falha
  esperada no teste, e o treino não foi ajustado para ela.
- "minha vizinha tem horta" recebe uma resposta direta errada (`pest_disease` 0,55). Já acontecia antes
  do vocabulário novo (0,64), e o treino não foi ajustado para essa frase.

## Interpretação das mensagens (9.4.1-4)

O NLU que usa este dataset está em `hort_ia.nlp.nlu` (`Interpreter`), conforme a abordagem de
`docs/nlu/9.4.1-3_Abordagem_Motor_Conversacional.md`: o modelo E do estudo de 9.4.1-1 (caracteres +
palavras, regressão logística), **treinado na inicialização a partir deste arquivo**, e as entidades
por dicionário gerado da base de conhecimento. Por isso:

- mudar `intents.yaml` muda o assistente na próxima inicialização, sem passo de "retreinar e salvar";
- um sinônimo novo em `data/knowledge/crops.json` passa a ser entendido sem mudar código;
- antes de mandar uma mudança, rode `uv run pytest tests/test_nlu_dataset.py tests/test_nlu_interpreter.py`.

Para ver o que o assistente entende de uma frase:

```bash
uv run python -m hort_ia.nlp "qndo plantar alfase?"
```

## Conversa (9.4.1-5)

O gerenciador de diálogo (`hort_ia.nlp.dialogue`) decide, a cada mensagem, se responde, confirma,
pergunta ou encaminha (seção 4.4 de 9.4.1-3). A rota é `POST /nlp/message`:

```bash
curl -X POST http://localhost:8080/nlp/message -H "Content-Type: application/json" \
  -d '{"text": "quando eu planto?", "ibge_code": 4106902}'
# {"decision": "ask", "text": "De qual planta você está falando?", ..., "context": {...}}
```

A interface guarda o `context` de cada resposta e o devolve na mensagem seguinte; o servidor não
guarda conversa nenhuma. O contexto tem só identificadores (intenção, cultura, pergunta pendente),
nunca o texto do usuário. `decision` diz o que a interface pode mostrar: `confirm` pede botões
Sim/Não; `ask`, uma resposta curta; `fallback` vem com `handoff`.

Os limites de confiança (`ANSWER_AT = 0.5`, `CONFIRM_AT = 0.3`) são valores iniciais e serão
recalibrados no conjunto de teste (9.4.2-2). Os textos das confirmações e perguntas ficam na seção
`dialogue` de `responses.yaml`.

## Respostas (seção 5.2)

**Decisão: sem modelo de linguagem para gerar respostas.** A equipe não vai usar API paga, e um
modelo local exigiria servidor com GPU para ficar abaixo dos 5 s do critério de aceite. Mais
importante: a produção de conteúdo agronômico está fora do escopo do 9.4. Por isso toda resposta é
um modelo de `responses.yaml` preenchido com dados da base de conhecimento ou da base de mercado,
pela classe `hort_ia.nlp.Responder`. O assistente nunca escreve uma recomendação que não esteja
nos dados.

Cada resposta (`Answer`) traz, além do texto:

- `sources`: as publicações de onde vieram os dados, para a API exibir se quiser;
- `handoff`: `true` quando não há dado ou o assunto está fora do escopo; a interface deve oferecer
  contato com a Assistência Técnica Digital;
- `missing_entity`: o que o gerenciador de diálogo precisa perguntar (planta ou cidade).

As funções recebem a entrada já interpretada (cultura, região, mês), então não dependem de como o
NLU for implementado. A região vem do código IBGE do município do perfil (`hort_ia.core.geo`), e a
UF escolhe o Ceasa local para preços.

Regras de escrita dos modelos: frases curtas, construções sem gênero ("dá para plantar {crop}"),
origem explícita quando a informação é tradicional, e "não sei" com encaminhamento quando não há
dado.

As respostas de praga e doença têm várias partes e são as únicas escritas uma parte por linha (`\n`):
"Parece ser: X.", "Como reconhecer: ..." (quando a base tem o sintoma), "O que ajuda:", cada ação como
item de lista (`action_item: "- {action}"`) e a frase final. Em rascunho, a frase final pede à
Assistência Técnica a confirmação do problema e o tratamento ("Para confirmar o problema e saber como
tratar, fale com a Assistência Técnica."), porque o modelo de visão pode errar e porque algumas
doenças, como as viroses, não têm cura. Conferida pela ATD (`validated_by_atd`), a resposta é a mesma
do rascunho: o status quer dizer "conferido contra a fonte e a página", não aval agronômico. Só
revisada por agrônomo (`reviewed`) a resposta usa o mesmo título "O que ajuda:" antes da lista,
mostra também as ações `alternative` e termina com "Se tiver dúvida sobre o problema, fale com a
Assistência Técnica.", que oferece a Assistência Técnica sem ligar o `handoff`. As demais intenções continuam num parágrafo só. A interface
deve preservar as quebras de linha (a app de validação as converte para Markdown na exibição).

**Limitações conhecidas, que viram encaminhamento à Assistência Técnica:**

- Pragas e doenças: o manejo da base é por grupo e nenhuma entrada foi revisada por agrônomo. O
  assistente mostra só a prevenção e encaminha o tratamento; besouros, tesourinhas e gorgulhos não têm
  orientação visível (ver `data/knowledge/README.md`, "Pragas e doenças").
- Plantio companheiro: só relações tradicionais chegam à resposta; as técnicas e de pesquisa da
  entrega v3 da ATD ficam de fora até a ATD confirmar (regra D6). A nota final diz de onde vêm as
  combinações mostradas (`traditional_note`, `mixed_note` ou `technical_note`). Rúcula, espinafre,
  brócolis e pimenta sem relação utilizável.
- Preços: só alface, batata, cebola, cenoura e tomate, preço de atacado do mês de referência da Conab.
- Manjericão sem janela de plantio no Norte e no Nordeste.
