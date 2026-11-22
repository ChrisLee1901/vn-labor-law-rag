"use client";

import { History, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { clearChats, deleteChat, loadChats, type StoredChat } from "@/lib/chat-storage";

const fmt = (t: number) =>
  new Date(t).toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

interface ListProps {
  currentId: string;
  onOpen: (c: StoredChat) => void;
  onDeleted: (id: string) => void;
}

function HistoryList({ currentId, onOpen, onDeleted }: ListProps) {
  const [chats, setChats] = useState(loadChats);

  if (chats.length === 0) return <p className="px-4 text-sm text-muted-foreground">Chưa có cuộc hội thoại nào được lưu.</p>;
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 pb-4">
      <ul className="space-y-1.5">
        {chats.map((c) => (
          <li key={c.id} className="flex items-center gap-1">
            <Button
              type="button"
              variant={c.id === currentId ? "secondary" : "ghost"}
              onClick={() => onOpen(c)}
              className="h-auto min-w-0 flex-1 flex-col items-start gap-0 py-2 text-left whitespace-normal"
            >
              <span className="w-full truncate font-medium">{c.title}</span>
              <span className="text-xs font-normal text-muted-foreground">{fmt(c.updatedAt)}</span>
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={`Xóa cuộc hội thoại: ${c.title}`}
              onClick={() => {
                deleteChat(c.id);
                setChats(loadChats());
                onDeleted(c.id);
              }}
            >
              <Trash2 />
            </Button>
          </li>
        ))}
      </ul>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="self-start"
        onClick={() => {
          clearChats();
          setChats([]);
          onDeleted(currentId);
        }}
      >
        Xóa tất cả
      </Button>
    </div>
  );
}

export function HistorySheet({ disabled, ...props }: ListProps & { disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button type="button" variant="outline" size="sm" disabled={disabled}>
          <History /> Lịch sử
        </Button>
      </SheetTrigger>
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>Lịch sử hội thoại</SheetTitle>
          <SheetDescription>Lưu trên trình duyệt này, tối đa 20 cuộc gần nhất.</SheetDescription>
        </SheetHeader>
        <HistoryList
          {...props}
          onOpen={(c) => {
            setOpen(false);
            props.onOpen(c);
          }}
        />
      </SheetContent>
    </Sheet>
  );
}
