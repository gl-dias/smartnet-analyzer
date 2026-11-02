-- SmartNet Analyzer: esquema do banco. Rode uma vez no SQL Editor do Supabase.
-- O script pode ser executado de novo sem perder dados.
--
-- O acesso é feito só pelo backend, com a chave de servidor. O RLS fica ativo e sem
-- políticas: quem usar as chaves públicas não lê nem grava nada.

create table if not exists public.sessoes (
  id uuid primary key default gen_random_uuid(),
  iniciada_em timestamptz not null default now(),
  finalizada_em timestamptz
);

create table if not exists public.grafos (
  id uuid primary key default gen_random_uuid(),
  sessao_id uuid references public.sessoes (id) on delete set null,
  nome text not null,
  direcionado boolean not null,
  ponderado boolean not null,
  vertices jsonb not null,
  arestas jsonb not null,
  origem_entrada text not null
    check (origem_entrada in ('manual', 'texto', 'linguagem_natural', 'voz', 'exemplo', 'importacao')),
  criado_em timestamptz not null default now()
);

-- grafo_id fica nulo quando o algoritmo rodou em um grafo que não foi salvo.
create table if not exists public.execucoes (
  id uuid primary key default gen_random_uuid(),
  grafo_id uuid references public.grafos (id) on delete set null,
  algoritmo text not null check (algoritmo in ('dfs', 'bfs', 'dijkstra', 'kruskal')),
  parametros jsonb not null,
  resultado jsonb not null,
  tempo_ms numeric not null,
  criado_em timestamptz not null default now()
);

-- aceito fica nulo até o usuário confirmar ou cancelar a revisão, e continua nulo
-- quando a chamada terminou em pergunta de esclarecimento ou em erro.
create table if not exists public.interpretacoes_ia (
  id uuid primary key default gen_random_uuid(),
  sessao_id uuid references public.sessoes (id) on delete set null,
  texto_entrada text not null,
  canal text not null check (canal in ('texto', 'voz')),
  operacoes jsonb not null,
  aceito boolean,
  criado_em timestamptz not null default now()
);

create index if not exists grafos_criado_em_idx on public.grafos (criado_em desc);
create index if not exists grafos_sessao_id_idx on public.grafos (sessao_id);
create index if not exists execucoes_grafo_id_idx on public.execucoes (grafo_id);
create index if not exists interpretacoes_ia_sessao_id_idx on public.interpretacoes_ia (sessao_id);

alter table public.sessoes enable row level security;
alter table public.grafos enable row level security;
alter table public.execucoes enable row level security;
alter table public.interpretacoes_ia enable row level security;

revoke all on public.sessoes, public.grafos, public.execucoes, public.interpretacoes_ia
  from anon, authenticated;
