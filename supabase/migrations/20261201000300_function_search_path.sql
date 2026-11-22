-- Supabase advisor "function_search_path_mutable": ghim search_path cho hàm của app.
-- `public, extensions` phủ cả hai chỗ pgvector có thể nằm (public khi CREATE EXTENSION không chỉ schema, extensions trên Supabase).
-- Chỉ ALTER, không đụng dữ liệu; hàm mới sau này phải tự khai báo `set search_path` (có test canh).
alter function hybrid_search(text, text, halfvec, int, date, int, float, float, int)
  set search_path = public, extensions;
