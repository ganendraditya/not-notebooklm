import { describe, expect, it } from "vitest";
import { parseChatDeleteProposal, parseSourceRenameEvent } from "@/lib/sourceActions";

describe("parseChatDeleteProposal", () => {
  it("accepts unique positive IDs only for the expected chat", () => {
    const content = '<!-- SOURCES_ACTION: {"action":"confirm_delete","chat_id":"chat-1","doc_ids":[7,8,7]} -->';

    expect(parseChatDeleteProposal(content, "chat-1")).toEqual({
      chatId: "chat-1",
      documentIds: [7, 8],
    });
  });

  it.each([
    ['<!-- SOURCES_ACTION: {"action":"confirm_delete","chat_id":"chat-2","doc_ids":[7]} -->', "chat-1"],
    ['<!-- SOURCES_ACTION: {"action":"bulk_delete","deleted_doc_ids":[7]} -->', "chat-1"],
    ['<!-- SOURCES_ACTION: {"action":"confirm_delete","chat_id":"chat-1","doc_ids":["7"]} -->', "chat-1"],
    ['<!-- SOURCES_ACTION: {"action":"confirm_delete","chat_id":"chat-1","doc_ids":[0]} -->', "chat-1"],
    ['<!-- SOURCES_ACTION: not json -->', "chat-1"],
  ])("rejects invalid action payload %s", (content, expectedChatId) => {
    expect(parseChatDeleteProposal(content, expectedChatId)).toBeNull();
  });
});

describe("parseSourceRenameEvent", () => {
  it("accepts a successful event for the expected chat", () => {
    expect(parseSourceRenameEvent({
      type: "source_renamed",
      chat_id: "chat-1",
      doc_id: 947,
      source_number: 2,
      previous_title: "Paper B",
      new_title: "Evaluation Dataset",
    }, "chat-1")).toEqual({
      chatId: "chat-1",
      docId: 947,
      sourceNumber: 2,
      previousTitle: "Paper B",
      newTitle: "Evaluation Dataset",
    });
  });

  it.each([
    { type: "source_renamed", chat_id: "chat-2", doc_id: 947, source_number: 2, previous_title: "Paper B", new_title: "New" },
    { type: "source_renamed", chat_id: "chat-1", doc_id: 0, source_number: 2, previous_title: "Paper B", new_title: "New" },
    { type: "source_renamed", chat_id: "chat-1", doc_id: 947, source_number: 0, previous_title: "Paper B", new_title: "New" },
    { type: "source_renamed", chat_id: "chat-1", doc_id: 947, source_number: 2, previous_title: "Paper B", new_title: "  " },
    { type: "source_renamed", chat_id: "chat-1", doc_id: "947", source_number: 2, previous_title: "Paper B", new_title: "New" },
  ])("rejects invalid event payloads", (event) => {
    expect(parseSourceRenameEvent(event, "chat-1")).toBeNull();
  });
});
