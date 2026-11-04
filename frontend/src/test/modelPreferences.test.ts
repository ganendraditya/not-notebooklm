import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { MODEL_PREFERENCES_KEY, modelKey, useModelPreferences } from "@/hooks/chat/useModelPreferences";
import type { WorkspaceModel } from "@/stores/chatStore";

const model = (id: string, profile_id = "provider"): WorkspaceModel => ({ id, name: id, profile_id, profile_name: "Provider" });

describe("model preferences", () => {
  beforeEach(() => localStorage.clear());

  it("limits recent choices to five unique provider/model pairs", async () => {
    const { result } = renderHook(() => useModelPreferences());
    for (let index = 0; index < 7; index++) act(() => result.current.recordRecent(model(String(index))));
    act(() => result.current.recordRecent(model("4")));
    expect(result.current.recent).toEqual(["4", "6", "5", "3", "2"].map((id) => modelKey(model(id))));
    await waitFor(() => expect(JSON.parse(localStorage.getItem(MODEL_PREFERENCES_KEY)!).recent).toEqual(result.current.recent));
  });

  it("uses unambiguous keys even when IDs contain separators", () => {
    expect(modelKey(model("c", "a:b"))).not.toBe(modelKey(model("b:c", "a")));
    const { result } = renderHook(() => useModelPreferences());
    act(() => result.current.toggleFavorite(model("same", "a")));
    act(() => result.current.toggleFavorite(model("same", "b")));
    expect(result.current.favorites).toHaveLength(2);
  });

  it("recovers from invalid JSON without preventing later changes", () => {
    localStorage.setItem(MODEL_PREFERENCES_KEY, "{interrupted");
    const { result } = renderHook(() => useModelPreferences());
    expect(result.current.favorites).toEqual([]);
    expect(result.current.recent).toEqual([]);
    act(() => result.current.toggleFavorite(model("working")));
    expect(result.current.favorites).toEqual([modelKey(model("working"))]);
  });
});
