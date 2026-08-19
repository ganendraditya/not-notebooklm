"use client";

import { useState, useEffect, useRef } from "react";
import { ChevronRight, ChevronUp, Check, Info, Sparkles } from "lucide-react";

export interface ModelTier {
  id: string;
  name: string; // e.g. "Low", "Medium", "High", "Extra Low"
}

export interface ModelGroup {
  id: string;
  name: string;
  badge?: string;
  tiers?: ModelTier[];
  directModelId?: string;
}

const MODEL_GROUPS: ModelGroup[] = [
  {
    id: "gemini-3.7-flash",
    name: "Gemini 3.7 Flash",
    tiers: [
      { id: "ag/gemini-3.7-flash-low", name: "Low" },
      { id: "ag/gemini-3.7-flash-medium", name: "Medium" },
      { id: "ag/gemini-3.7-flash-high", name: "High" },
    ]
  },
  {
    id: "gemini-3.6-flash",
    name: "Gemini 3.6 Flash",
    tiers: [
      { id: "ag/gemini-3.6-flash-low", name: "Low" },
      { id: "ag/gemini-3.6-flash-medium", name: "Medium" },
      { id: "ag/gemini-3.6-flash-high", name: "High" },
    ]
  },
  {
    id: "gemini-3.5-flash",
    name: "Gemini 3.5 Flash",
    tiers: [
      { id: "ag/gemini-3.5-flash-extra-low", name: "Extra Low" },
      { id: "ag/gemini-3.5-flash-low", name: "Low" },
      { id: "ag/gemini-3.5-flash-high", name: "High" },
    ]
  },
  {
    id: "gemini-3.1-pro",
    name: "Gemini 3.1 Pro",
    tiers: [
      { id: "ag/gemini-3.1-pro-low", name: "Low" },
      { id: "ag/gemini-pro-agent", name: "High" },
    ]
  },
  {
    id: "claude-sonnet-4.6",
    name: "Claude Sonnet 4.6 (Thinking)",
    directModelId: "ag/claude-sonnet-4-6"
  },
  {
    id: "claude-opus-4.6",
    name: "Claude Opus 4.6 (Thinking)",
    directModelId: "ag/claude-opus-4-6-thinking"
  },
  {
    id: "gpt-oss-120b",
    name: "GPT-OSS 120B (Medium)",
    directModelId: "ag/gpt-oss-120b-medium"
  },
  {
    id: "gemini-3-flash-preview",
    name: "Gemini 3 Flash Preview",
    directModelId: "gemini/gemini-3-flash-preview"
  },
  {
    id: "gemma-4-31b-it",
    name: "Gemma 4 31B IT",
    directModelId: "gemini/gemma-4-31b-it"
  }
];

interface ModelSelectorProps {
  backendUrl: string;
}

export default function ModelSelector({ backendUrl }: ModelSelectorProps) {
  const [currentModelId, setCurrentModelId] = useState<string>("ag/gemini-3.7-flash-high");
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [activeSubmenuId, setActiveSubmenuId] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [notification, setNotification] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Fetch active model on mount
  useEffect(() => {
    fetch(`${backendUrl}/llm/models`)
      .then(res => res.json())
      .then(data => {
        if (data && data.current_model) {
          setCurrentModelId(data.current_model);
        }
      })
      .catch(err => console.error("Failed to load models:", err));
  }, [backendUrl]);

  // Click outside to close everything
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setActiveSubmenuId(null);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelectModelId = async (modelId: string, displayName: string) => {
    if (isUpdating) return;
    setIsUpdating(true);
    try {
      const res = await fetch(`${backendUrl}/llm/models/select`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: modelId })
      });
      if (res.ok) {
        setCurrentModelId(modelId);
        setIsOpen(false);
        setActiveSubmenuId(null);
        setNotification(`Active: ${displayName}`);
        setTimeout(() => setNotification(null), 2500);
      }
    } catch (err) {
      console.error("Failed to update model:", err);
    } finally {
      setIsUpdating(false);
    }
  };

  // Compute trigger button display info
  const getDisplayInfo = () => {
    for (const group of MODEL_GROUPS) {
      if (group.tiers) {
        const matchingTier = group.tiers.find(t => t.id === currentModelId);
        if (matchingTier) {
          return { groupName: group.name, tierName: matchingTier.name };
        }
      }
      if (group.directModelId === currentModelId) {
        return { groupName: group.name, tierName: null };
      }
    }
    return { groupName: "Gemini 3.7 Flash", tierName: "High" };
  };

  // Find active tier in a group if any
  const getActiveTierInGroup = (group: ModelGroup) => {
    if (!group.tiers) return null;
    return group.tiers.find(t => t.id === currentModelId) || null;
  };

  return (
    <div className="relative inline-block text-left select-none" ref={containerRef}>
      {/* Toast Notification */}
      {notification && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 px-3.5 py-1.5 rounded-full bg-blue-600/95 text-white text-xs font-medium shadow-2xl backdrop-blur animate-in fade-in slide-in-from-top-2 duration-200 flex items-center gap-1.5">
          <Sparkles size={13} className="text-yellow-300 animate-spin" />
          <span>{notification}</span>
        </div>
      )}

      {/* Trigger Button: Antigravity IDE Bottom Input Style */}
      <button
        type="button"
        onClick={() => {
          setIsOpen(prev => {
            const next = !prev;
            if (!next) setActiveSubmenuId(null);
            return next;
          });
        }}
        className="flex items-center gap-1.5 px-2 py-1 rounded-md text-[12.5px] text-gray-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer group focus:outline-none"
        title="Select AI Model"
      >
        {(() => {
          const { groupName, tierName } = getDisplayInfo();
          return (
            <span className="font-normal text-gray-200 group-hover:text-white truncate max-w-[220px] flex items-center gap-1.5">
              <span>{groupName}</span>
              {tierName && (
                <span className="text-gray-400 font-normal text-[11.5px] group-hover:text-gray-300 transition-colors">
                  {tierName}
                </span>
              )}
            </span>
          );
        })()}
        <ChevronUp 
          size={13} 
          className={`text-gray-400 group-hover:text-gray-200 transition-transform duration-200 ${isOpen ? "rotate-180 text-blue-400" : ""}`} 
        />
      </button>

      {/* Popover Menu Opening Upwards */}
      {isOpen && (
        <div className="absolute bottom-full left-0 mb-2.5 w-64 sm:w-72 rounded-xl bg-[#1e1f22] border border-white/15 shadow-2xl z-50 p-1.5 backdrop-blur-xl animate-in fade-in zoom-in-95 duration-150 overflow-visible">
          {/* Header */}
          <div className="px-2.5 py-1 mb-1">
            <span className="text-[11px] font-medium text-gray-400">
              Model
            </span>
          </div>

          {/* Model Group List */}
          <div className="space-y-0.5 overflow-visible">
            {MODEL_GROUPS.map((group) => {
              const hasTiers = !!group.tiers && group.tiers.length > 0;
              const activeTier = getActiveTierInGroup(group);
              const isDirectActive = group.directModelId === currentModelId;
              const isGroupActive = !!activeTier || isDirectActive;
              const isSubmenuOpen = activeSubmenuId === group.id;

              return (
                <div 
                  key={group.id} 
                  className="relative overflow-visible"
                >
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!hasTiers && group.directModelId) {
                        handleSelectModelId(group.directModelId, group.name);
                      } else if (hasTiers) {
                        // STRICT CLICK-ONLY: Clicking toggles/opens the submenu stably
                        setActiveSubmenuId(prev => prev === group.id ? null : group.id);
                      }
                    }}
                    className={`w-full text-left px-2.5 py-1.5 rounded-lg flex items-center justify-between gap-2 text-[12.5px] transition-colors cursor-pointer ${
                      isGroupActive 
                        ? "bg-[#2b2c31] border border-blue-500/50 text-white font-medium shadow-sm" 
                        : isSubmenuOpen
                          ? "bg-white/[0.08] text-white"
                          : "hover:bg-white/[0.06] text-gray-300 hover:text-white font-normal"
                    }`}
                  >
                    <span className="truncate flex-1 flex items-center gap-1.5">
                      <span>{group.name}</span>
                      {activeTier && (
                        <span className="text-gray-400 font-normal text-[11.5px]">
                          {activeTier.name}
                        </span>
                      )}
                    </span>

                    <div className="flex items-center gap-1 shrink-0">
                      {group.badge && (
                        <span className="flex items-center gap-0.5 px-1.5 py-0.2 rounded-full text-[10px] text-gray-400 bg-white/5 border border-white/10">
                          {group.badge}
                          <Info size={9} className="opacity-70" />
                        </span>
                      )}

                      {hasTiers ? (
                        <ChevronRight size={13} className={`transition-transform duration-150 ${isSubmenuOpen ? "text-blue-400 rotate-90 sm:rotate-0" : "text-gray-400"}`} />
                      ) : isDirectActive ? (
                        <Check size={13} className="text-blue-400 ml-0.5" />
                      ) : null}
                    </div>
                  </button>

                  {/* Cascading Submenu to the Right for Tiers (Opens strictly on CLICK and stays open until tier selected or clicked outside) */}
                  {hasTiers && isSubmenuOpen && (
                    <div 
                      data-submenu={group.id}
                      className="absolute left-full top-0 ml-1.5 w-32 rounded-xl bg-[#232428] border border-white/15 shadow-2xl p-1 z-[60] animate-in fade-in slide-in-from-left-1 duration-100 before:absolute before:top-0 before:-left-3 before:w-4 before:h-full"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {group.tiers!.map((tier) => {
                        const isTierSelected = tier.id === currentModelId;
                        return (
                          <button
                            key={tier.id}
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSelectModelId(tier.id, `${group.name} ${tier.name}`);
                            }}
                            disabled={isUpdating}
                            className={`w-full text-left px-3 py-1.5 rounded-lg text-xs flex items-center justify-between transition-colors cursor-pointer ${
                              isTierSelected 
                                ? "bg-white/15 text-white font-semibold" 
                                : "hover:bg-white/[0.08] text-gray-300 hover:text-white font-normal"
                            }`}
                          >
                            <span>{tier.name}</span>
                            {isTierSelected && (
                              <Check size={12} className="text-blue-400" />
                            )}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
