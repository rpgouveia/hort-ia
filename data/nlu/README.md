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

- **Colheita** ("quando colho a alface?") é `crop_care`, não `planting_time`.
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

## Linha de base (out/2026, rascunho, validação cruzada)

TF-IDF de n-gramas de caracteres + regressão logística: **76% de acurácia** em validação cruzada
de 5 partes sobre os 318 exemplos do rascunho. Como os dados vêm de um autor só, esse número é um
teto otimista; o número que vale é o do conjunto de teste.

As confusões mais frequentes orientam a abordagem do motor (9.4.1-3):

- `planting_time` × `what_to_plant`: a diferença é a presença de uma cultura, o que a extração de
  entidades resolve melhor do que o classificador.
- `fallback` é a classe mais fraca: fora do escopo é tudo que não é o resto, sem padrão próprio.
  Um limiar de confiança no classificador tende a funcionar melhor do que tratá-la como classe comum.
- `help` × `fallback`: perguntas sobre o uso do aplicativo ficam na fronteira entre as duas.

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

**Limitações conhecidas, que viram encaminhamento à Assistência Técnica:**

- Pragas e doenças: o assistente identifica (pelo rótulo do modelo de CV ou pelo nome citado), mas
  ainda não tem manejo conferido para nenhuma (Fase 3 da base de conhecimento).
- Plantio companheiro: rúcula sem relações.
- Preços: só alface, batata, cebola, cenoura e tomate, preço de atacado do mês de referência da Conab.
- Manjericão sem janela de plantio no Norte e no Nordeste.
