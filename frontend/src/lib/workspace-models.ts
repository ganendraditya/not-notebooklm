import type { WorkspaceModel } from "@/stores/chatStore";

export async function fetchWorkspaceModels(backendUrl: string): Promise<WorkspaceModel[]> {
  const response = await fetch(`${backendUrl}/llm/models`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data: unknown = await response.json();
  if (typeof data !== "object" || data === null || !("workspace_models" in data) || !Array.isArray(data.workspace_models)) throw new Error("Model list unavailable");
  if (!data.workspace_models.every((item) => typeof item === "object" && item !== null && typeof item.id === "string" && typeof item.profile_id === "string")) throw new Error("Invalid model list");
  return data.workspace_models as WorkspaceModel[];
}
