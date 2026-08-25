"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  children?: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("[ErrorBoundary caught an error]:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center p-6 text-center border border-red-500/20 bg-red-500/5 rounded-xl my-4">
          <div className="p-3 rounded-full bg-red-500/10 text-red-500 mb-3">
            <AlertTriangle size={24} />
          </div>
          <h3 className="text-sm font-semibold text-app-text mb-1">
            {this.props.fallbackTitle || "Komponen mengalami kendala"}
          </h3>
          <p className="text-xs text-app-text-muted mb-4 max-w-sm">
            {this.state.error?.message || "Terjadi kesalahan yang tidak terduga saat memuat bagian ini."}
          </p>
          <Button
            size="sm"
            variant="outline"
            onClick={() => this.setState({ hasError: false })}
            className="text-xs flex items-center gap-1.5 cursor-pointer"
          >
            <RotateCcw size={13} />
            <span>Coba lagi</span>
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
