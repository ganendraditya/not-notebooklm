# Frontend Phase 1: RightSidebar Refactoring Status

## Current State
- **Target File:** `frontend/src/components/RightSidebar.tsx`
- **Current Line Count:** 1,874 lines (Verified via `wc -l`)
- **Status:** Incomplete. Needs further decoupling to reach best practices.

## What Has Been Done (Successfully Extracted)
1. `useCitationGenerator.ts` (Logic: Citation generation)
2. `DocumentReaderUtils.tsx` (Logic: HTML cleaning, highlight formatting)
3. `usePaperDetails.ts` (Logic/State: Paper fetching)
4. `CitationModal.tsx` (UI: Citation popup)
5. `DocumentReader.tsx` (UI: Paper reading mode, extracted but logic in RightSidebar needs adjustment for proper extraction)

## What Remains in RightSidebar.tsx (The Bloat)
1. **State & Hooks:** File upload refs, drag-and-drop state, selection state.
2. **Handlers & Logic:** `handleUploadBatch`, `renameDocument`, `deleteDocument`, `handleBulkDelete`.
3. **UI: Standard Sources List:** The list rendering user's uploaded documents.
4. **UI: Add Sources Modal:** The large modal for adding local files, URLs, etc.
5. **UI: Other Modals:** Bulk delete, rename confirmations.

## Next Steps (Action Plan)
1. Extract `AddSourcesModal` to `frontend/src/components/RightSidebar/AddSourcesModal.tsx`.
2. Extract Document List logic/UI to `DocumentListPanel.tsx`.
3. Extract Handlers to a custom hook (e.g., `useSourceManagement.ts`).
4. **MANDATORY:** After every single step, run `wc -l` to verify line count reduction and `npm run build` to verify type safety. NO ASSUMPTIONS.
