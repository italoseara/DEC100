# DEC100 — BitUESC Ring MVP

Atividade em sala de aula da matéria DEC100 - Sistemas Distribuídos.

Este MVP transforma cada processo em um servidor BitUESC que participa de um anel lógico de 4 nós. Qualquer nó pode receber transações de um cliente e replicá-las no anel via TCP+JSON. Cada servidor mantém um arquivo de bloco (`transactions.log`) com os mesmos eventos quando o limiar de 6 transações é atingido.

## Requisitos

- Python 3.10+
- Linux/macOS (testado em Linux)

Instale dependências (se necessário):

```zsh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Estrutura

- `src/connection/server.py`: servidor BitUESC com replicação no anel.
- `src/connection/client.py`: cliente TCP simples (usado pela `App`).
- `src/bituesc/app.py`: UI CLI para enviar transações ao servidor local.
- `src/main.py`: inicialização do servidor e da `App` com parâmetros do anel.

## Como rodar 4 nós em localhost

Escolha 4 portas, por exemplo: `25565`, `25566`, `25567`, `25568`. Cada nó aponta seu sucessor para o próximo, e o último aponta para o primeiro.

Abra quatro terminais e inicie cada nó:

```zsh
# Nó 0
python3 src/main.py
# Server port (default 25565): 25565
# Node ID [0-3] (default 0): 0
# Successor host (default localhost): localhost
# Successor port (default 25565): 25566
```

```zsh
# Nó 1
python3 src/main.py
# Server port (default 25565): 25566
# Node ID [0-3] (default 0): 1
# Successor host (default localhost): localhost
# Successor port (default 25565): 25567
```

```zsh
# Nó 2
python3 src/main.py
# Server port (default 25565): 25567
# Node ID [0-3] (default 0): 2
# Successor host (default localhost): localhost
# Successor port (default 25565): 25568
```

```zsh
# Nó 3
python3 src/main.py
# Server port (default 25565): 25568
# Node ID [0-3] (default 0): 3
# Successor host (default localhost): localhost
# Successor port (default 25565): 25565
```

Cada instância iniciará um servidor e a UI cliente local (`App`). Você pode usar qualquer uma das quatro UIs para enviar transações.

## Teste rápido

1. No nó 0, crie uma conta e deposite:
   - `[1] Create Account` → `alice`
   - `[5] Deposit` → `alice`, valor `50`
2. Em qualquer outro nó (ex.: nó 2), consulte saldo:
   - `[3] Get Account Balance` → `alice`
3. O saldo deve coincidir. As transações `DEPOSIT/WITHDRAW` entram no bloco; ao atingir 6, um bloco é escrito em `transactions.log` em cada nó.

## Como funciona (resumo)

- `REPLICATE_TXN`: mensagem JSON com `{type, txn_id, origin_id, hop, payload}` circula no anel.
- Deduplicação: `txn_id` em `seen_txn_ids` evita reprocessar e loop infinito.
- Encaminhamento: cada nó aplica localmente e encaminha ao sucessor; para ao voltar ao `origin_id` depois de 4 hops.

## Limitações do MVP

- Sem reconexão automática nem heartbeats entre nós.
- Sem sincronização de estado ao reiniciar.
- Segurança/assinatura e ACKs completos não implementados.

## Próximos passos

- Heartbeats e retry/backoff.
- Sincronização de estado (`STATE_REQUEST/STATE_DIFF`).
- Configuração por arquivo (`config/nodes.yaml`).
- Testes de integração e tolerância a falhas.
