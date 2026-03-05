# ⚽ Sheik das Apostas

**Plataforma inteligente de análise esportiva com IA para previsões de apostas.**

Sistema que coleta dados de múltiplas fontes (APIs de odds, estatísticas, resultados),
aplica modelos matemáticos (Poisson, ELO) e usa IA generativa para produzir
análises detalhadas e dicas de apostas com fundamentação estatística.

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────┐
│                   FRONTEND (Web)                     │
│         Dashboard com previsões e análises           │
│            HTML/CSS/JS (Jinja2 Templates)            │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                 BACKEND (FastAPI)                     │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │ API Routes  │ │ AI Analyzer  │ │ Stat Models  │  │
│  └─────────────┘ └──────────────┘ └──────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│               CAMADA DE DADOS                        │
│  ┌──────────┐ ┌──────────────┐ ┌─────────────────┐  │
│  │ Odds API │ │ Football API │ │ SQLite Cache    │  │
│  └──────────┘ └──────────────┘ └─────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## 📊 Funcionalidades

### Coleta de Dados
- **Odds em tempo real** de múltiplas casas de apostas (via The Odds API)
- **Dados de competições** — classificações, resultados, escalações (via football-data.org)
- **Histórico de confrontos** (head-to-head)
- **Cache local** em SQLite para economizar chamadas de API

### Modelos Estatísticos
- **Distribuição de Poisson** — previsão de gols baseada em médias ofensivas/defensivas
- **Sistema ELO** — rating de força relativa dos times
- **Value Bets** — identificação de odds com valor (probabilidade real > probabilidade implícita)
- **Over/Under & BTTS** — probabilidades calculadas estatisticamente

### Análise com IA
- **Análise qualitativa** — a IA recebe todos os dados e gera uma análise em linguagem natural
- **Justificativa** — cada tip vem com explicação do porquê
- **Nível de confiança** — porcentagem de confiança na previsão
- **Sugestão de mercados** — 1x2, over/under, BTTS, handicap

### Dashboard
- Jogos do dia com previsões
- Comparação de odds entre casas
- Histórico de acertos
- Filtros por liga/esporte

## 🚀 Como Rodar

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Configurar chaves de API
Copie `.env.example` para `.env` e preencha:
```
ODDS_API_KEY=sua_chave_aqui
FOOTBALL_DATA_API_KEY=sua_chave_aqui
OPENAI_API_KEY=sua_chave_aqui
```

### 3. Iniciar o servidor
```bash
python -m uvicorn app.main:app --reload
```

### 4. Acessar
Abra `http://localhost:8000` no navegador.

## 🔑 APIs Gratuitas Utilizadas

| API | Plano Gratuito | Dados |
|-----|---------------|-------|
| [The Odds API](https://the-odds-api.com/) | 500 créditos/mês | Odds de 40+ casas de apostas |
| [Football-Data.org](https://www.football-data.org/) | 10 req/min | Classificações, resultados, times, jogadores |
| [OpenAI](https://platform.openai.com/) | Pay-as-you-go | Análise com GPT para gerar tips |

## 📁 Estrutura do Projeto

```
sheik-das-apostas/
├── app/
│   ├── main.py              # FastAPI app principal
│   ├── config.py             # Configurações e variáveis de ambiente
│   ├── models/
│   │   ├── database.py       # SQLite setup
│   │   └── schemas.py        # Pydantic schemas
│   ├── services/
│   │   ├── odds_service.py   # Integração com The Odds API
│   │   ├── football_service.py # Integração com Football-Data.org
│   │   ├── ai_analyzer.py    # Análise com IA (OpenAI)
│   │   └── stats_engine.py   # Modelos estatísticos (Poisson, ELO)
│   ├── routes/
│   │   ├── matches.py        # Rotas de partidas
│   │   └── predictions.py    # Rotas de previsões
│   └── templates/
│       ├── base.html          # Template base
│       ├── index.html         # Dashboard principal
│       └── match.html         # Detalhe de partida
├── data/
│   └── sheik.db              # Banco SQLite (gerado automaticamente)
├── .env.example
├── requirements.txt
└── README.md
```
