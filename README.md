# SmartNet Analyzer

Aplicação web para mapear uma cidade inteligente como um grafo e executar análises de conectividade e roteamento, com entrada manual, por texto, por linguagem natural e por voz.

**Aplicação publicada:** https://smartnet-analyzer.onrender.com

As credenciais da versão publicada foram enviadas ao professor no e-mail de entrega. Para execução local, o avaliador define as próprias credenciais no arquivo `.env`.

## Identificação

| | |
|---|---|
| **Integrantes** | Guilherme Dias ([MATRÍCULA]), Breno Chaves ([MATRÍCULA]), Barbara Malta ([MATRÍCULA]) |
| **Curso** | Engenharia de Computação/Software, Ibmec |
| **Disciplina** | Análise e Complexidade de Algoritmos (IBM3121), 6º período |
| **Professor** | Cassius Figueiredo |
| **Semestre** | 2026.2 |

## O problema

Um consórcio quer modernizar a infraestrutura de uma cidade inteligente. A cidade é modelada como um grafo: vértices são bairros ou pontos de interesse, e arestas são vias ou conexões com custo ou distância. A aplicação mapeia a cidade e responde a quatro perguntas:

| Algoritmo | Pergunta na cidade |
|---|---|
| DFS | Auditoria de rotas: a rede é conexa? Há becos sem saída ou bairros inalcançáveis? |
| BFS | Propagação de alertas: em quantos saltos um alerta chega a cada bairro? |
| Dijkstra | Rotas de emergência: qual o caminho de menor custo a partir de uma origem? |
| Kruskal | Rede de fibra ótica: qual o menor custo para conectar todos os bairros? |

## Funcionalidades

- Grafos direcionados e não direcionados, com ou sem peso.
- Lista de adjacência implementada do zero e exibida na interface, vértice a vértice.
- Botões para DFS, BFS, Dijkstra e Kruskal, com tabelas, complexidade teórica e tempo medido.
- Desenho do grafo com animação do resultado: ordem de visita, caminho mínimo e arestas da árvore geradora.
- Salvar, listar, carregar e excluir grafos no banco de dados.
- Ciclo interativo: é possível apagar o grafo, inserir outro e rodar quantos algoritmos quiser até clicar em **Finalizar aplicação**.
- Login com conta única, para proteger a aplicação publicada e o custo da API.

### Saída de cada algoritmo

- **DFS:** ordem de visita, árvore em texto indentado, predecessores, tempos de descoberta e finalização, componentes, classificação de conectividade, vértices inalcançáveis e becos sem saída.
- **BFS:** fila passo a passo, fila final de execução, nível de cada vértice e caminho com menos saltos até um destino opcional.
- **Dijkstra:** tabela de vértice, distância, predecessor e caminho, com `∞` para inalcançáveis, além das relaxações passo a passo. Pesos negativos são rejeitados com a explicação do motivo.
- **Kruskal:** decisão sobre cada aresta, arestas selecionadas e custo total. Em grafo desconexo, devolve a floresta geradora mínima e avisa. Em grafo direcionado, avisa e executa ignorando a direção.

## Formas de entrada

### Linguagem natural (destaque)

O usuário escreve em português livre, tanto para descrever a cidade quanto para pedir mudanças:

> A cidade tem os bairros O, A, B e C. O se liga ao A com custo 2 e ao C com custo 4. B liga em C com custo 1. As vias são de mão dupla.

> remova a via entre A e B

> mude o peso de O para C para 6

> rodar Dijkstra a partir de O

O modelo devolve uma **lista de operações**, nunca o grafo final. O backend valida cada operação na própria lista de adjacência e a **tela de revisão** mostra as operações com caixas de seleção e uma prévia do grafo. Nada é aplicado antes de o usuário clicar em **Confirmar**. Se a frase for ambígua, o modelo faz uma pergunta em vez de inventar dados.

### Voz (destaque)

O botão de microfone usa a Web Speech API do navegador, em português. A transcrição fica em uma caixa editável, para corrigir erros antes do envio, e segue o mesmo caminho e a mesma tela de revisão da linguagem natural. Funciona no Google Chrome, com internet: nessa aba, o áudio é processado pelo serviço de voz do navegador.

### Sem depender de IA ou de serviços externos

- **Manual:** formulário de vias e bairros, com tabela para editar pesos e remover itens.
- **Texto:** uma via por linha, como `O A 2`. Nomes com espaço vão entre aspas: `"Vila Isabel" Tijuca 3`.
- **Exemplos:** grafo do enunciado, direcionado, sem peso e desconexo.
- **Arquivo:** exportar e importar JSON.

## Por que lista de adjacência

Grafos de cidades são esparsos: cada bairro se liga a poucos vizinhos, logo E é muito menor que V².

| Critério | Lista de adjacência | Matriz de adjacência |
|---|---|---|
| Memória | O(V + E) | O(V²) |
| Percorrer os vizinhos de um vértice | O(grau) | O(V) |
| DFS e BFS no grafo inteiro | O(V + E) | O(V²) |
| Dijkstra com heap | O((V + E) log V) | O(V² log V) |

Os três algoritmos que percorrem vizinhos são beneficiados diretamente. A estrutura é um dicionário de vértice para lista de tuplas `(vizinho, peso)`, sem nenhuma biblioteca de grafos.

## Complexidade

V é o número de vértices, E o de arestas e d o grau do vértice.

### Algoritmos

| Algoritmo | Tempo | Espaço adicional | Justificativa |
|---|---|---|---|
| DFS | O(V + E) | O(V + E) | Cada vértice é aberto uma vez e cada lista é percorrida uma vez. A pilha guarda os vizinhos dos vértices abertos. |
| BFS | O(V + E) | O(V) | Cada vértice entra e sai da fila uma vez, com remoção O(1). |
| Dijkstra | O((V + E) log V) | O(V + E) | Cada aresta pode gerar uma inserção no heap, a O(log E) = O(log V). |
| Kruskal | O(E log E) | O(V + E) | A ordenação domina; as operações de Union-Find são quase constantes. |

A tabela de passos da BFS existe só para exibição: copiar a fila a cada passo soma até O(V²), sem fazer parte do algoritmo.

### Estruturas auxiliares

| Estrutura | Operação | Custo |
|---|---|---|
| Min-heap | inserir, extrair mínimo | O(log n) |
| Min-heap | consultar mínimo | O(1) |
| Union-Find (compressão de caminho e união por rank) | encontrar, unir | O(α(n)) amortizado |
| Merge sort | ordenar (estável) | O(n log n) em tempo e O(n) em espaço |

### Lista de adjacência

| Operação | Custo |
|---|---|
| Espaço total | O(V + E) |
| `adicionar_vertice` | O(V) |
| `adicionar_aresta` | O(d) |
| `remover_aresta` | O(d) |
| `alterar_peso` | O(log d) |
| `remover_vertice` | O(V + E) |
| `vizinhos` | O(d) |
| `arestas`, `para_dict` | O(V + E) |

## Convenções

- **Ordem alfabética dos vizinhos:** as listas ficam sempre ordenadas, o que torna os resultados determinísticos. A ordem ignora maiúsculas e acentos e compara números pelo valor, então `2` vem antes de `10`.
- **Grafo sem peso:** usa peso 1 internamente, e a interface esconde esse valor.
- **Arestas duplicadas:** são rejeitadas com mensagem clara. Em grafo não direcionado, A-B e B-A são a mesma aresta.
- **Self-loops:** são aceitos com aviso, pois não alteram o resultado de nenhum algoritmo.
- **DFS:** usa pilha explícita em vez de recursão, com a mesma ordem de visita, para não estourar o limite de recursão do Python em caminhos longos.
- **Empates no Dijkstra:** seguem a ordem alfabética dos vértices.
- **Empates no Kruskal:** seguem a ordem alfabética das arestas. As arestas escolhidas podem variar entre implementações, mas o custo não.

## Arquitetura

- **Backend:** Python, FastAPI e uvicorn. Reconstrói a lista de adjacência a cada requisição.
- **Front:** HTML, CSS e JavaScript puro em `public/`, servido pelo próprio FastAPI. O desenho usa vis-network por CDN.
- **Estado:** a aplicação é stateless. O front guarda o grafo atual e o envia em cada requisição.
- **Banco:** Supabase (Postgres), acessado pela API REST com a chave de servidor, somente no backend.
- **IA:** SDK oficial da Anthropic, com a ferramenta `aplicar_operacoes_grafo` em esquema estrito.
- **Resiliência:** entrada manual, estrutura e os quatro algoritmos não dependem do Supabase nem da Anthropic. Quando um serviço externo falha, a interface mostra um aviso.

```
smartnet-analyzer/
  src/
    app.py, config.py     aplicação, middlewares e variáveis de ambiente
    auth/                 login, sessão e limites de tentativas
    core/                 lista de adjacência, heap, union-find, merge sort
    core/algoritmos/      DFS, BFS, Dijkstra e Kruskal
    ia/                   chamada à Anthropic, validação e prompt
    db/                   cliente REST do Supabase
    api/                  rotas
  public/                 interface
  supabase/schema.sql     tabelas e RLS
  exemplos/               grafos de exemplo
  scripts/                gerador do hash da senha
  tests/                  testes automatizados
```

O modelo Claude Sonnet 5.5 não aceita `tool_choice` forçado: a API responde com erro 400, mesmo com thinking desligado. Por isso a chamada usa `tool_choice` automático com `strict: true`, e o backend confere se a ferramenta foi chamada. Uma resposta em texto vira pergunta ao usuário, nunca operação.

## Segurança

- **Login:** conta única definida por `APP_USUARIO` e `APP_SENHA_HASH` (hash bcrypt), com mensagem de erro genérica.
- **Sessão:** cookie assinado, HttpOnly, SameSite=Lax e Secure em produção, com duração de 8 horas a contar do login.
- **Proteção de rotas:** tudo exige sessão, exceto `/login`, `/logout`, `/saude` e os arquivos da tela de login. Rotas novas já nascem protegidas.
- **Limite de login:** 5 tentativas por IP a cada 15 minutos, além de um teto de 50 tentativas a cada 15 minutos para todos os IPs juntos.
- **Limites da IA:** 30 chamadas por sessão por hora, texto de até 2000 caracteres, `max_tokens` de 4000 e grafo de contexto de até 200 vértices e 1000 arestas. Pedidos inválidos são recusados antes de chamar a API.
- **Auditoria:** cada chamada à IA fica registrada na tabela `interpretacoes_ia`.
- **Banco:** RLS ativo em todas as tabelas, sem políticas de acesso. As chaves públicas não leem nem gravam nada, o que foi testado no banco real.
- **Limitação da sessão:** a sessão fica apenas no cookie assinado, sem registro no servidor. O logout apaga o cookie do navegador, mas uma cópia roubada continua válida até expirar (8 horas após o login). Trocar a `SECRET_KEY` invalida todas as sessões de uma vez.
- **IP de origem nos limites de login:** em produção, o IP vem de `X-Forwarded-For`, contado a partir do fim da lista, porque cada proxy acrescenta um IP ao final e o início é controlado pelo cliente. A variável `PROXIES_CONFIAVEIS` define a posição: `1` usa o último IP (padrão), `2` usa o penúltimo e `0` ignora o cabeçalho. No Render o valor correto é `3`, confirmado nos logs do deploy: a lista termina em cliente, Cloudflare e proxy interno. Localmente, o cabeçalho é sempre ignorado.

## Como rodar localmente

São necessários Python 3.11 ou superior (o projeto foi testado no 3.12) e o Google Chrome.

**1. Baixe o projeto e entre na pasta**

```bash
git clone https://github.com/gl-dias/smartnet-analyzer.git
cd smartnet-analyzer
```

**2. Crie e ative o ambiente virtual**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

No Windows, use `python -m venv .venv` e `.venv\Scripts\activate`.

**3. Instale as dependências**

```bash
pip install -r requirements.txt
```

**4. Crie o arquivo de configuração**

```bash
cp .env.example .env
```

No Windows, use `copy .env.example .env`.

**5. Defina as suas credenciais de acesso**

```bash
python scripts/gerar_hash_senha.py
```

O script pede a senha no terminal e imprime o hash. No `.env`, preencha:

```
APP_USUARIO=o_usuario_que_voce_escolher
APP_SENHA_HASH=o_hash_impresso_pelo_script
```

**6. Defina a chave de sessão**

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Cole o resultado em `SECRET_KEY` no `.env`.

**7. Serviços opcionais**

Sem eles, a aplicação funciona normalmente, com avisos nas funções que dependem de cada um:

- `ANTHROPIC_API_KEY`: habilita a linguagem natural e a voz.
- `SUPABASE_URL` e `SUPABASE_SERVICE_KEY`: habilitam salvar grafos e a auditoria.

**8. Inicie o servidor**

```bash
uvicorn src.app:app --reload
```

**9. Abra a aplicação**

Acesse http://localhost:8000 no Chrome e entre com as credenciais do passo 5.

**Dica para começar:** na aba **Importar/Exemplos**, clique em **Carregar grafo de exemplo (enunciado)** e rode os quatro algoritmos com origem O.

## Como configurar o Supabase

1. Crie um projeto em [supabase.com](https://supabase.com).
2. Abra o **SQL Editor**, cole o conteúdo de `supabase/schema.sql` e clique em **Run**.
3. Em **Project Settings**, copie a URL do projeto e a chave de servidor. O cliente aceita a chave nova (`sb_secret_...`) e a antiga (`service_role`).
4. Preencha `SUPABASE_URL` e `SUPABASE_SERVICE_KEY` no `.env`.

Nunca use as chaves públicas nem exponha a chave de servidor. No plano gratuito, o projeto pausa após cerca de uma semana sem uso e pode ser reativado no painel.

## Deploy no Render

O arquivo `render.yaml` descreve um Web Service Python no plano gratuito, e `.python-version` fixa o Python em 3.12.

1. No painel do Render, clique em **New** e depois em **Blueprint**, e selecione este repositório.
2. Preencha as variáveis pedidas: `AMBIENTE=producao`, `APP_USUARIO`, `APP_SENHA_HASH`, `SECRET_KEY`, `PROXIES_CONFIAVEIS=3`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL=claude-sonnet-5-5`, `SUPABASE_URL` e `SUPABASE_SERVICE_KEY`.
3. Confira se o plano é **Free** e confirme o deploy.

**Atenção ao cold start:** no plano gratuito, o serviço dorme após 15 minutos sem acesso e o primeiro acesso seguinte leva cerca de 1 minuto. Os limites de tentativas ficam em memória e são zerados quando o serviço reinicia.

## Como rodar os testes

Com o ambiente virtual ativo, na raiz do projeto:

```bash
python -m pytest
```

Os testes não precisam de `.env` e nunca chamam a Anthropic nem o Supabase de verdade: esses serviços são simulados. Além dos resultados do enunciado, eles cobrem grafo direcionado, sem peso e desconexo, peso negativo, vértice isolado, autenticação e limites. Dijkstra, Kruskal e BFS também são comparados em 100 grafos aleatórios com Bellman-Ford, Prim e uma busca por camadas.

## Resultados esperados no grafo do enunciado

Grafo não direcionado e ponderado:

```
O-A 2, O-B 5, O-C 4, A-B 2, A-D 7, A-F 12, B-C 1,
B-D 4, B-E 3, C-E 4, D-E 4, D-T 5, E-T 7, F-T 3
```

Com origem O e vizinhos em ordem alfabética:

| Algoritmo | Resultado |
|---|---|
| DFS | O, A, B, C, E, D, T, F |
| BFS | O, A, B, C, D, F, E, T |
| Dijkstra | O=0, A=2, B=4, C=4, E=7, D=8, T=13, F=14 |
| Kruskal | Custo total 20, com 7 arestas |

## Link do deploy

https://smartnet-analyzer.onrender.com
