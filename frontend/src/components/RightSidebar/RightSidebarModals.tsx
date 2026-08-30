import React from "react";
import { Document } from "@/stores/documentStore";
import { AddSourcesModal } from "./AddSourcesModal/AddSourcesModal";
import { CitationModal } from "./CitationModal";
import { BulkDeleteModal } from "./BulkDeleteModal";
import { RenameModal } from "./RenameModal";
import { generateCitations } from "@/hooks/useCitationGenerator";

interface RightSidebarModalsProps {
  // Add Sources Modal Props
  isAddSourcesModalOpen: boolean;
  setIsAddSourcesModalOpen: (open: boolean) => void;
  doiInput: string;
  setDoiInput: (val: string) => void;
  handleImportDoi: (e?: React.FormEvent) => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  isDraggingOver: boolean;
  setIsDraggingOver: (dragging: boolean) => void;
  handleUploadBatch: (files: File[]) => void;
  documentsLength: number;
  pendingSourcesLength: number;

  // Citation Modal Props
  isCiteModalOpen: boolean;
  setIsCiteModalOpen: (open: boolean) => void;
  paperDetails: any;
  viewingDoc: Document | null;

  // Bulk Delete Modal Props
  showBulkDeleteConfirm: boolean;
  docToDelete: number | null;
  selectedCount: number;
  isBulkDeleting: boolean;
  setShowBulkDeleteConfirm: (show: boolean) => void;
  setDocToDelete: (id: number | null) => void;
  handleConfirmBulkDelete: () => void;

  // Rename Modal Props
  isRenameModalOpen: boolean;
  renamingDoc: Document | null;
  renameTitleInput: string;
  isSavingRename: boolean;
  setRenameTitleInput: (title: string) => void;
  setIsRenameModalOpen: (open: boolean) => void;
  handleSaveRename: (e?: React.FormEvent) => void;
}

export const RightSidebarModals: React.FC<RightSidebarModalsProps> = ({
  isAddSourcesModalOpen,
  setIsAddSourcesModalOpen,
  doiInput,
  setDoiInput,
  handleImportDoi,
  fileInputRef,
  isDraggingOver,
  setIsDraggingOver,
  handleUploadBatch,
  documentsLength,
  pendingSourcesLength,

  isCiteModalOpen,
  setIsCiteModalOpen,
  paperDetails,
  viewingDoc,

  showBulkDeleteConfirm,
  docToDelete,
  selectedCount,
  isBulkDeleting,
  setShowBulkDeleteConfirm,
  setDocToDelete,
  handleConfirmBulkDelete,

  isRenameModalOpen,
  renamingDoc,
  renameTitleInput,
  isSavingRename,
  setRenameTitleInput,
  setIsRenameModalOpen,
  handleSaveRename
}) => {
  return (
    <>
      {/* Google NotebookLM Style 'Add Sources' Centered Modal Dialog */}
      <AddSourcesModal
        isOpen={isAddSourcesModalOpen}
        onClose={() => setIsAddSourcesModalOpen(false)}
        doiInput={doiInput}
        setDoiInput={setDoiInput}
        handleImportDoi={handleImportDoi}
        fileInputRef={fileInputRef}
        isDraggingOver={isDraggingOver}
        setIsDraggingOver={setIsDraggingOver}
        handleUploadBatch={handleUploadBatch}
        documentsLength={documentsLength}
        pendingSourcesLength={pendingSourcesLength}
      />

      {/* Citation Modal */}
      <CitationModal
        isOpen={isCiteModalOpen}
        onClose={() => setIsCiteModalOpen(false)}
        citations={generateCitations(
          paperDetails?.title || ((viewingDoc as any)?.filename || "paper") || "",
          paperDetails?.authors || [],
          paperDetails?.year || "2024",
          paperDetails?.journal || "",
          paperDetails?.doi || "",
          paperDetails?.url || (paperDetails?.doi ? "https://doi.org/$" : "")
        )}
        doiStr={paperDetails?.doi || ""}
      />

      {/* Centered Modal for Bulk Delete Confirmation */}
      <BulkDeleteModal
        isOpen={showBulkDeleteConfirm}
        selectedCount={docToDelete !== null ? 1 : selectedCount}
        isBulkDeleting={isBulkDeleting}
        onClose={() => {
          setShowBulkDeleteConfirm(false);
          setDocToDelete(null);
        }}
        onConfirm={handleConfirmBulkDelete}
      />

      {/* Centered Modal for Renaming Single Document */}
      <RenameModal
        isOpen={isRenameModalOpen}
        renamingDoc={renamingDoc}
        renameTitleInput={renameTitleInput}
        isSavingRename={isSavingRename}
        onInputChange={setRenameTitleInput}
        onClose={() => setIsRenameModalOpen(false)}
        onSave={handleSaveRename}
      />
    </>
  );
};