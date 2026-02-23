# 🦅 Consists Trade AI - Manual de Voo Institucional

## 1. Visão Geral
**Consists Trade AI** é um Motor Quantitativo Autônomo de Alta Frequência, arquitetado para operar como um fundo de investimentos privado. O sistema utiliza a inteligência do **Gemini 2.5 Flash-Lite** para realizar análises fractais de mercado (macro/micro) e o **MetaTrader 5 (MT5)** para execução de ordens com latência zero. O motor conta com um Filtro de Horário Institucional e uma Estratégia Camaleão (Regime-Switching) que adapta a tática de operação de acordo com o regime atual do mercado.

## 2. Arquitetura (Monorepo)
O projeto segue uma arquitetura Monorepo dividida em duas camadas principais:
- **Frontend (O Cockpit):** Desenvolvido em Next.js (React) com Tailwind CSS e Zustand. Interface "Dark Mode Institucional" inspirada em terminais Bloomberg, com gráficos Lightweight Charts e gestão de estado em tempo real.
- **Backend (O Motor):** Desenvolvido em Python com FastAPI e WebSockets. Responsável pela integração nativa com o MetaTrader 5, inferência de IA via `google-genai` e comunicação com o banco de dados Supabase (PostgreSQL).

## 3. Pré-requisitos Críticos
Para que o motor quantitativo funcione corretamente, o ambiente de produção **DEVE** atender aos seguintes requisitos:
- **Sistema Operacional:** Windows 10/11 ou Windows Server (VPS). A biblioteca `MetaTrader5` do Python funciona **exclusivamente** em ambiente Windows.
- **MetaTrader 5:** Instalado, logado em uma conta de corretora e com o RLP (Retail Liquidity Provider) ou Algorithmic Trading ativado.
- **Python:** Versão 3.10 ou superior.
- **Node.js:** Versão 18 ou superior.
- **Supabase:** Projeto criado com as tabelas `trade_configs`, `trade_history` e `system_logs` configuradas (incluindo as colunas de `horario_inicio` e `horario_fim` na tabela `trade_configs`).

---

## 4. Setup do Backend (Motor Python)

Abra um terminal (PowerShell ou CMD) na raiz do projeto e siga os passos:

### 4.1. Criar e Ativar o Ambiente Virtual (venv)
```bash
cd backend
python -m venv venv
venv\Scripts\activate
```

### 4.2. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 4.3. Configurar Variáveis de Ambiente
Crie um arquivo `.env` dentro da pasta `backend/` com as seguintes credenciais:
```env
# Supabase
SUPABASE_URL=sua_url_do_supabase
SUPABASE_KEY=sua_anon_key_do_supabase

# Gemini AI
GEMINI_API_KEY=sua_chave_api_do_google_ai_studio

# MetaTrader 5
MT5_LOGIN=seu_login_mt5
MT5_PASSWORD=sua_senha_mt5
MT5_SERVER=seu_servidor_mt5
```

### 4.4. Iniciar os Serviços
Você precisará de dois terminais rodando simultaneamente no backend (ambos com o `venv` ativado):

**Terminal 1: Servidor WebSocket (FastAPI)**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Terminal 2: Loop Principal de Trading (O Robô)**
```bash
python trading_bot.py
```

---

## 5. Setup do Frontend (Cockpit Next.js)

Abra um novo terminal na raiz do projeto:

### 5.1. Instalar Dependências
```bash
npm install
```

### 5.2. Configurar Variáveis de Ambiente
Crie um arquivo `.env.local` na raiz do projeto:
```env
NEXT_PUBLIC_SUPABASE_URL=sua_url_do_supabase
NEXT_PUBLIC_SUPABASE_ANON_KEY=sua_anon_key_do_supabase

# URL do WebSocket apontando para a sua VPS Windows
NEXT_PUBLIC_WS_URL=ws://SEU_IP_DA_VPS:8000/ws/logs
```

### 5.3. Iniciar o Servidor de Desenvolvimento
```bash
npm run dev
```
Acesse `http://localhost:3000` no seu navegador.

### 5.4. Build para Produção (Netlify / Vercel)
Para fazer o deploy do frontend em plataformas como Netlify ou Vercel:
```bash
npm run build
```
*Nota: Lembre-se de configurar as variáveis de ambiente (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_WS_URL`) diretamente no painel da sua plataforma de hospedagem.*

---

## 6. ⚠️ AVISO DE RISCO INSTITUCIONAL (LEIA COM ATENÇÃO)

**O TRADING ALGORÍTMICO ENVOLVE ALTO RISCO DE PERDA DE CAPITAL.**
Este software foi desenvolvido para fins institucionais e educacionais. 

**REGRA DE OURO:** 
1. **SEMPRE inicie o sistema em uma CONTA DEMO do MetaTrader 5.**
2. Valide a latência, a assertividade da IA e o comportamento do gerenciamento de risco exaustivamente.
3. Ajuste o tamanho do **Lote (Volume)** no painel de configurações (Cockpit) ou diretamente no banco de dados antes de conectar a uma conta real.
4. O desenvolvedor não se responsabiliza por perdas financeiras decorrentes do uso deste software.
