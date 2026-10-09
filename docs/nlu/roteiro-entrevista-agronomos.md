# Roteiro de conversa com agrônomos — Assistente Conversacional e Base de Conhecimento

Objetivo: coletar **perguntas reais** que agricultores urbanos fazem, do jeito que fazem, e
aproveitar o contato para validar pontos da base de conhecimento que hoje dependem de
interpretação da equipe.

Duração sugerida: 30 a 45 minutos por pessoa. As partes estão em ordem de prioridade: se o tempo
for curto, faça só a Parte 1.

## Antes da conversa

- Explique que o assistente é para agricultores de hortas urbanas e comunitárias, muitos com
  pouca familiaridade com celular e aplicativo.
- Peça autorização para anotar as perguntas. Não registre o nome da pessoa no material do
  projeto, só o papel (agrônomo, extensionista, coordenador de horta).
- **Não mostre a lista de intenções nem o `intents.yaml`** antes da Parte 1. Isso influencia as
  respostas e contamina o conjunto de teste.

## Parte 1 — Perguntas reais (prioridade máxima)

Anote cada pergunta **exatamente como a pessoa falar**, mesmo com erro ou gíria.

1. "Quais são as perguntas que os agricultores mais fazem para você?" Peça pelo menos 10.
2. "Como eles costumam perguntar? Pode falar do jeito que eles falam?"
3. Para cada tema abaixo, se ainda não apareceu: "e sobre ___, o que eles perguntam?"
   - época de plantar e o que plantar agora;
   - rega, espaçamento, colheita, plantar em vaso;
   - plantas que podem ficar juntas;
   - pragas, doenças, "bicho" e "mancha" na planta;
   - preço e venda da produção.
4. "Que perguntas eles fazem que você **não** consegue responder, ou que precisam de visita?"
   Essas respostas definem o que o assistente deve encaminhar para um técnico.
5. "Que palavras eles usam para as pragas mais comuns?" (ex.: "bicho", "lagartinha",
   "mosquinha branca", "piolho de planta"). Isso alimenta o reconhecimento de pragas.

## Parte 2 — Validar a base de conhecimento

Pontos em que a equipe precisou interpretar a fonte ou em que as fontes divergem:

| Ponto | Pergunta ao agrônomo |
|---|---|
| Pragas sem conteúdo | Para as pragas mais comuns da região (pulgão, mosca-branca, lagarta, lesma, formiga), qual manejo recomenda para horta urbana, sem agrotóxico? |
| Pulgão e mosca-branca | Não estão no modelo de visão computacional. São tão frequentes que deveriam entrar? |
| Cenoura e rabanete | O dataset tradicional diz para não plantar juntos, mas é prática comum semear no mesmo canteiro. Qual é a orientação? |
| Manjericão no Sul | Interpretamos "semeadura no final da primavera" como novembro e dezembro. Faz sentido para Curitiba e região? |
| Espaçamento da batata | A fonte imprime "0,90 x ,030"; lemos 0,90 × 0,30 m. Confere? |
| Alface no Sul | A fonte indica alface de inverno de fevereiro a outubro. Com as geadas daqui, isso vale? |

## Parte 3 — Linguagem das respostas

Leia duas ou três respostas de exemplo e pergunte se um agricultor entenderia e saberia o que
fazer:

- "Deixe um palmo (25 cm) entre uma muda de alface e outra."
- "Em outubro, aqui no Sul, dá para plantar alface, tomate, pimentão, abobrinha, beterraba e cebolinha."
- "Manjericão perto do tomate ajuda a espantar algumas pragas. Isso é recomendado pela Embrapa."
- "É costume plantar alface perto da cenoura, mas essa combinação não aparece nas recomendações da Embrapa."

Pergunte também: medidas em centímetros ou em "palmos"? Citar a Embrapa dá confiança ou é
indiferente para eles?

## Registro

Depois da conversa, passe as perguntas da Parte 1 para `data/nlu/test_utterances.yaml`:

```yaml
- {text: "ja posso por alface na horta?", intent: planting_time, origin: field,
   author: renato, collected_from: agronomo}
- {text: "da pra fazer horta em cima da laje?", intent: null, origin: field,
   author: renato, collected_from: agronomo, notes: "sem intenção correspondente"}
```

- `intent: null` quando nenhuma das 8 intenções serve. Essas são as mais importantes, porque
  mostram o que falta no assistente.
- Rode `uv run pytest tests/test_nlu_dataset.py` para checar se nenhuma pergunta coincidiu com o
  treino.
- As respostas da Parte 2 vão para a base de conhecimento como fonte nova (ex.: comunicação
  pessoal com o papel e a data, sem nome) e, quando confirmarem um registro, ele pode passar de
  `draft` para `reviewed`.
