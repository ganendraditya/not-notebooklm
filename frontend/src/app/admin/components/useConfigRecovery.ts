import { useRef, useState } from "react";
import { loadAdminConfig, type ConfigUpdate } from "@/lib/admin-api";
import type { ConfigSection } from "@/lib/admin-config";
import type { AdminConfig } from "@/types/admin";

export interface ConfigRecovery {
  uncertain: boolean;
  reloading: boolean;
  error: boolean;
  markUncertain: () => void;
  reload: () => Promise<void>;
}

export function useConfigRecovery<K extends ConfigSection>(backendUrl: string, section: K, onReload: (update: ConfigUpdate<NonNullable<AdminConfig[K]>>) => void): ConfigRecovery {
  const [uncertain, setUncertain] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [error, setError] = useState(false);
  const lock = useRef(false);
  const reload = async () => {
    if (lock.current) return;
    lock.current = true; setReloading(true); setError(false);
    try {
      const current = await loadAdminConfig(backendUrl);
      const config = current[section];
      if (!config) throw new Error("Configuration section unavailable");
      onReload({ config, persistence: current.persistence });
      setUncertain(false);
    } catch { setError(true); }
    finally { lock.current = false; setReloading(false); }
  };
  return { uncertain, reloading, error, markUncertain: () => setUncertain(true), reload };
}
