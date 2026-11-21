create extension if not exists vector;

create table legal_docs (
  code text primary key,
  number text,
  title text,
  doc_type text check (doc_type in ('luat','bo_luat','vbhn','nghi_dinh','thong_tu')),
  issuer text,
  issued_on date,
  effective_from date,
  effective_to date,
  status text,
  replaced_by text references legal_docs(code),
  amends text[] not null default '{}',
  source_url text,
  file_sha256 text
);

create table articles (
  index_version int not null,
  id text not null,
  doc_code text not null references legal_docs(code),
  number int,
  suffix text,
  title text,
  chapter text,
  content text,
  primary key (index_version, id)
);

create table chunks (
  index_version int not null,
  id text not null,
  parent_id text not null,
  doc_code text not null references legal_docs(code),
  article int,
  clause int,
  point text,
  content text,
  embed_text text not null,
  n_tokens int,
  embedding halfvec(1024),
  fts tsvector generated always as (to_tsvector('simple', embed_text)) stored,
  fts_noaccent tsvector,
  primary key (index_version, id)
);

create index chunks_embedding_hnsw on chunks using hnsw (embedding halfvec_ip_ops) with (m = 16, ef_construction = 64);
create index chunks_fts on chunks using gin (fts);
create index chunks_fts_noaccent on chunks using gin (fts_noaccent);
create index chunks_doc_article on chunks (index_version, doc_code, article);

create table legal_refs (
  index_version int not null,
  src_id text not null,
  dst_doc_code text,
  dst_doc_number text,
  dst_article int,
  dst_clause int,
  dst_point text,
  rel text check (rel in ('cites','details','amends'))
);

create table app_config (
  key text primary key,
  value jsonb,
  updated_at timestamptz default now()
);
insert into app_config(key, value) values ('active_index_version', '1'), ('refusal_tau', '0.35');

create table canned_answers (
  id serial primary key,
  question_norm text unique,
  answer text,
  sources jsonb,
  created_at timestamptz default now()
);

create table feedback (
  id bigserial primary key,
  trace_id text,
  score smallint check (score in (-1, 1)),
  comment text,
  created_at timestamptz default now()
);

-- No policies: only server-side connections (table owner / service role) can access.
alter table legal_docs enable row level security;
alter table articles enable row level security;
alter table chunks enable row level security;
alter table legal_refs enable row level security;
alter table app_config enable row level security;
alter table canned_answers enable row level security;
alter table feedback enable row level security;
