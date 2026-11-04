import type { WorkspaceModel } from "@/stores/chatStore";

function isWorkspaceModel(value: unknown): value is WorkspaceModel {
  return typeof value === "object" && value !== null
    && "id" in value && typeof value.id === "string"
    && "name" in value && typeof value.name === "string"
    && "profile_id" in value && typeof value.profile_id === "string"
    && "profile_name" in value && typeof value.profile_name === "string"
    && (!("protocol" in value) || typeof value.protocol === "string")
    && (!("is_default" in value) || typeof value.is_default === "boolean");
}

export async function fetchWorkspaceModels(backendUrl: string): Promise<WorkspaceModel[]> {
  const response = await fetch(`${backendUrl}/llm/models`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data: unknown = await response.json();
  if (typeof data !== "object" || data === null || !("workspace_models" in data) || !Array.isArray(data.workspace_models)) throw new Error("Model list unavailable");
  if (!data.workspace_models.every(isWorkspaceModel)) throw new Error("Invalid model list");
  return data.workspace_models;
}
