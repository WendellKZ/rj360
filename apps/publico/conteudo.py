# -*- coding: utf-8 -*-
"""Conteudo editorial do site publico e do diagnostico.

Fica em Python (e nao no banco) porque e texto de marca: muda por revisao, nao
no dia a dia. As chaves sao ASCII; os textos exibidos ao visitante levam a
acentuacao correta do portugues.
"""

ETAPAS_JORNADA = [
    {
        "dia": "D+0",
        "titulo": "Diagnóstico",
        "duracao": "15 dias",
        "desc": "Análise completa da situação: dívidas, credores, garantias e fluxo de caixa. "
                "Entendimento do cenário jurídico.",
        "respiro": "O primeiro passo já foi dado. Agora tem alguém olhando para o problema junto com você.",
    },
    {
        "dia": "D+15",
        "titulo": "Raio-X dos credores",
        "duracao": "15 dias",
        "desc": "Cada credor detalhado: valor original, juros, garantias, ações. "
                "Classificação por prioridade e viabilidade de negociação.",
        "respiro": "Conhecer o tamanho real do problema é o que tira o medo do escuro.",
    },
    {
        "dia": "D+30",
        "titulo": "Estratégia",
        "duracao": "30 dias",
        "desc": "Plano de ação: quem negociar primeiro, o que proteger, o que contestar. "
                "Cronograma realista.",
        "respiro": "Agora existe um plano. Não promessa — plano.",
    },
    {
        "dia": "D+60",
        "titulo": "Blindagem e tréguas",
        "duracao": "60 dias",
        "desc": "Acordos de prazo, contestação de valores indevidos, proteção do patrimônio pessoal. "
                "Fôlego para negociar.",
        "respiro": "A pressão diminui. Você volta a dormir.",
    },
    {
        "dia": "D+120",
        "titulo": "Acordos credor a credor",
        "duracao": "60 dias",
        "desc": "Negociação individual: desconto, parcelamento, reestruturação. "
                "Cada acordo acompanhado em tempo real.",
        "respiro": "Cada acordo fechado é um peso a menos. E você vê cada um acontecer.",
    },
    {
        "dia": "D+180",
        "titulo": "Novo fôlego",
        "duracao": "",
        "desc": "Acordos assinados, caixa respirando e plano de prevenção rodando. "
                "A empresa volta a operar com saúde.",
        "respiro": "A luz no fim do túnel deixa de ser figura de linguagem.",
    },
]

COMO_FUNCIONA = [
    {
        "numero": 1,
        "titulo": "Diagnóstico gratuito",
        "desc": "Sete perguntas, menos de três minutos. Você descobre a urgência do seu caso "
                "e recebe um retorno humano com prazo definido.",
    },
    {
        "numero": 2,
        "titulo": "Raio-X e estratégia",
        "desc": "Levantamos cada credor, cada garantia e cada risco. Você recebe um plano "
                "com ordem de prioridade e cronograma.",
    },
    {
        "numero": 3,
        "titulo": "Negociação acompanhada",
        "desc": "Negociamos credor a credor e você acompanha tudo na área do cliente: "
                "status, economia e documentos, com data.",
    },
]

# Quiz: cada opcao vale pontos. "pf" encerra o fluxo (divida so de pessoa fisica).
PERGUNTAS_QUIZ = [
    {
        "chave": "titularidade",
        "texto": "A dívida é apenas da empresa (CNPJ)?",
        "opcoes": [
            ("Sim, só CNPJ", 0),
            ("Mista (empresa + aval pessoal)", 1),
            ("Não, só pessoal (PF)", "pf"),
        ],
    },
    {
        "chave": "faturamento",
        "texto": "Qual o faturamento mensal da empresa?",
        "opcoes": [
            ("Até R$ 100 mil", 1),
            ("R$ 100 mil a R$ 300 mil", 2),
            ("R$ 300 mil a R$ 500 mil", 3),
            ("Acima de R$ 500 mil", 3),
        ],
    },
    {
        "chave": "divida",
        "texto": "Qual o valor total da dívida?",
        "opcoes": [
            ("Até R$ 300 mil", 1),
            ("R$ 300 mil a R$ 1 milhão", 2),
            ("R$ 1 milhão a R$ 3 milhões", 3),
            ("Acima de R$ 3 milhões", 4),
        ],
    },
    {
        "chave": "credor",
        "texto": "Quem é o principal credor?",
        "opcoes": [
            ("Bancos", 2),
            ("Fisco (impostos)", 2),
            ("Fornecedores", 1),
            ("Misto (vários)", 2),
        ],
    },
    {
        "chave": "situacao",
        "texto": "Qual a situação atual?",
        "opcoes": [
            ("Execução judicial", 3),
            ("Protesto / Serasa", 2),
            ("Fornecedor cortando prazo", 2),
            ("Apertando, mas controlando", 1),
        ],
    },
    {
        "chave": "aval",
        "texto": "Você ofereceu aval pessoal (imóvel etc.)?",
        "opcoes": [("Sim", 2), ("Não sei", 1), ("Não", 0)],
    },
    {
        "chave": "negociacao",
        "texto": "Já tentou negociar com os credores?",
        "opcoes": [("Sim, sem sucesso", 2), ("Estou tentando", 1), ("Ainda não", 0)],
    },
]

TOTAL_PERGUNTAS = len(PERGUNTAS_QUIZ)
