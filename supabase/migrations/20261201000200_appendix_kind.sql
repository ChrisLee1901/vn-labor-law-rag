-- Phụ lục (vd danh mục địa bàn ND293-2025) lưu vào articles với kind='phu_luc', number = số phụ lục.
alter table articles add column kind text not null default 'dieu' check (kind in ('dieu','phu_luc'));
