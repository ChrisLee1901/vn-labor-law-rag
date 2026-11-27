-- RRF fusion of FTS (accented OR unaccented tsquery) and semantic (halfvec inner product) branches.
-- Embeddings are L2-normalized, so `<#>` (negative inner product) ascending = best first.
create or replace function hybrid_search(
  query_text text,
  query_noaccent text,
  query_embedding halfvec(1024),
  index_version int,
  as_of date,
  match_count int default 40,
  full_text_weight float default 1,
  semantic_weight float default 1,
  rrf_k int default 50
) returns table(id text, parent_id text, score float)
language sql stable as $$
  with q as (
    select
      case when nullif(btrim(query_text), '') is null then null
           else to_tsquery('simple', query_text) end as t,
      case when nullif(btrim(query_noaccent), '') is null then null
           else to_tsquery('simple', query_noaccent) end as tn
  ),
  fts as (
    select c.id, c.parent_id,
           row_number() over (order by greatest(
             coalesce(ts_rank_cd(c.fts, q.t), 0),
             coalesce(ts_rank_cd(c.fts_noaccent, q.tn), 0)) desc, c.id) as rank
    from chunks c
    join legal_docs d on d.code = c.doc_code
    cross join q
    where c.index_version = hybrid_search.index_version
      and d.effective_from <= as_of and (d.effective_to is null or as_of < d.effective_to)
      and (c.fts @@ q.t or c.fts_noaccent @@ q.tn)
    order by rank
    limit match_count * 2
  ),
  semantic as (
    select c.id, c.parent_id,
           row_number() over (order by c.embedding <#> query_embedding, c.id) as rank
    from chunks c
    join legal_docs d on d.code = c.doc_code
    where query_embedding is not null
      and c.embedding is not null
      and c.index_version = hybrid_search.index_version
      and d.effective_from <= as_of and (d.effective_to is null or as_of < d.effective_to)
    order by rank
    limit match_count * 2
  )
  select coalesce(fts.id, semantic.id) as id,
         coalesce(fts.parent_id, semantic.parent_id) as parent_id,
         (coalesce(full_text_weight / (rrf_k + fts.rank), 0)
          + coalesce(semantic_weight / (rrf_k + semantic.rank), 0))::float as score
  from fts full outer join semantic on fts.id = semantic.id
  order by score desc, 1
  limit match_count
$$;
