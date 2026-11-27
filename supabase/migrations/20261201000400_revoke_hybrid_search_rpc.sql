-- hybrid_search chỉ backend (role postgres qua DATABASE_URL) gọi; không để anon / authenticated gọi qua PostgREST RPC.
-- anon / authenticated chỉ có trên Supabase (Postgres thuần của test/CI không có), nên revoke theo từng role đang tồn tại.
do $$
declare r text;
begin
  revoke execute on function hybrid_search(text, text, halfvec, int, date, int, float, float, int) from public;
  for r in select rolname from pg_roles where rolname in ('anon', 'authenticated') loop
    execute format('revoke execute on function hybrid_search(text, text, halfvec, int, date, int, float, float, int) from %I', r);
  end loop;
end $$;
