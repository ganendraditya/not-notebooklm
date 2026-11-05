import type { WorkspaceModel } from "@/stores/chatStore";
import { modelKey } from "./model-preferences";

function isWorkspaceModel(value: unknown): value is WorkspaceModel {
  return typeof value === "object" && value !== null
    && "id" in value && typeof value.id === "string"
    && "name" in value && typeof value.name === "string"
    && "profile_id" in value && typeof value.profile_id === "string"
    && "profile_name" in value && typeof value.profile_name === "string"
    && (!("protocol" in value) || value.protocol === "openai" || value.protocol === "anthropic")
    && (!("is_default" in value) || typeof value.is_default === "boolean");
}

export function resolveNewChatModel(models: WorkspaceModel[], lastSelectedKey?: string, pending?: { model: string; profile_id: string } | null): WorkspaceModel | undefined {
  return models.find((model) => pending?.model === model.id && pending.profile_id === model.profile_id)
    || models.find((model) => modelKey(model) === lastSelectedKey)
    || models[0];
}

export async function fetchWorkspaceModels(backendUrl: string): Promise<WorkspaceModel[]> {
  const response = await fetch(`${backendUrl}/llm/models`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data: unknown = await response.json();
  if (typeof data !== "object" || data === null || !("workspace_models" in data) || !Array.isArray(data.workspace_models)) throw new Error("Model list unavailable");
  if (!data.workspace_models.every(isWorkspaceModel)) throw new Error("Invalid model list");
  return data.workspace_models;
}
