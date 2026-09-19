# Visual Design Direction & Guidelines: Not-NotebookLM

> Official brand, UI/UX, and visual design specification for Not-NotebookLM.  
> Used in tandem with the `antislop` filter to provide clear direction, personality, and aesthetic discipline.

**Dial: ENERGY 2 / RHYTHM 2 / MOTION 1**

---

## 1. Product Identity & Soul

- **Core Purpose**: A high-rigor, distraction-free academic research assistant and comparative paper synthesis workspace.
- **Personality**: Empirical, serious, disciplined, trustworthy, and calm. The tool feels like an elite research lab workstation, not a flashy consumer novelty app.
- **Visual Aesthetic**: Tailored dark/light mode canvas inspired by modern scientific workstations and NotebookLM: clean division of workspace panes, crisp typography, subtle borders, high information density, and zero superficial clutter.

---

## 2. Layout Structure & Workspace Panes (Rhythm 2)

The application uses a functional, predictable three-pane layout designed for prolonged research focus:
1. **Left Navigation Sidebar (260px)**:
   - Houses workspace navigation (New Chat, Search, Library, Settings) and recent session history.
   - Footer strictly reserved for subtle app versioning and settings gear.
2. **Central Chat & Synthesis Stage (Flexible / Main Stage)**:
   - Conversation stream with clear separation between user prompts and synthesized academic responses.
   - Tabular comparisons, structured Markdown formatting, and interactive inline citation chips (`[Doc X, p. Y]`).
3. **Right Context & Document Inspector Pane (420–460px)**:
   - Split view between workspace source documents catalog and the authentic PDF canvas / Markdown reader.
   - Physical PDF reader with bounding box highlights matching citations from the chat.

---

## 3. Color Palette & Semantic Tokens (WCAG AA Compliant)

All UI surfaces strictly derive from CSS variable semantic tokens defined in `globals.css`:

### Dark Mode (Primary Research Environment)
- **App Canvas Background (`--app-bg`)**: `#212121`
- **Sidebar Surface (`--app-sidebar`)**: `#171717`
- **Inspector / Cards Surface (`--app-surface`, `--app-card`)**: `#1e1f20` / `#28292c`
- **Card Hover State (`--app-card-hover`)**: `#333438`
- **Input Surface (`--app-input-surface`)**: `#141415`
- **Subtle Borders (`--app-border`)**: `rgba(255, 255, 255, 0.10)`
- **Emphasized Borders (`--app-border-strong`)**: `rgba(255, 255, 255, 0.15)`
- **Dividers (`--app-divider`)**: `rgba(255, 255, 255, 0.05)`
- **Primary Text (`--app-text`)**: `#ffffff` (High contrast, crisp legibility)
- **Muted Text (`--app-text-muted`)**: `#9ca3af`
- **Dim / Metadata Text (`--app-text-dim`)**: `#6b7280`

### Light Mode
- **Canvas Background (`--app-bg`)**: `#f9f9fb`
- **Sidebar Surface (`--app-sidebar`)**: `#f3f3f6`
- **Surface / Cards (`--app-surface`)**: `#ffffff`
- **Card Hover State (`--app-card-hover`)**: `#f1f2f5`
- **Borders (`--app-border`)**: `rgba(0, 0, 0, 0.08)`
- **Primary Text (`--app-text`)**: `#09090b`
- **Muted Text (`--app-text-muted`)**: `#3f3f46`

### Functional Accent Colors (Energy 2)
- **Interactive Blue (`#2563eb` / `#3b82f6`)**: Primary action buttons, active tab indicators, and interactive citation chips.
- **Open Access / Verified Emerald (`#10b981`)**: Verified peer-reviewed publication badges and OA availability tags.
- **Citation / Bibliography Amber (`#f59e0b`)**: RIS / BibTeX indicators, paywalled/abstract-only badges.
- **Destructive Rose (`#ef4444`)**: Delete conversation, purge sources, and irreversible alerts.

---

## 4. Typography & Data Presentation

- **Sans-Serif (Body & Headers)**: `Plus Jakarta Sans`, system-ui, sans-serif.
  - Used for conversation copy, section headings, buttons, and metadata.
  - Clean geometry, open counters, and high legibility at micro sizes (11px–13px).
- **Monospace (Data & Technical Elements)**: `JetBrains Mono`, monospace.
  - Reserved strictly for DOIs, citations chips (`[Doc 1, p. 3]`), token counts, table numerical values, and code snippets.
  - **FORBIDDEN**: Large decorative monospace headings or uppercase monospace marketing slogans.

---

## 5. Micro-Interactions & Animation (Motion 1)

- Transitions must be brief, functional, and purposeful (150ms to 200ms duration with `ease-out`).
- Allowed: Subtle modal backdrop blur fade-in, smooth sidebar width toggle, dropdown popover scale (95% -> 100%), and button background hover shift.
- **FORBIDDEN**: Bouncy spring physics, persistent pulsing glows, decorative continuous rotations, or layout shifts that delay user interactions.

---

## 6. Antislop Quality Directives for Not-NotebookLM

When implementing or editing UI components:
1. **No Cosmetic Capsules**: Never place pill badges ("AI Powered", "Next-Gen", "Beta", "Smart") above headlines or cards unless they perform an authentic interactive function (e.g. format filter or active badge).
2. **No Button Arrow Slop**: Do not attach decorative `→` or `↗` icons to every action button.
3. **No Decorative Gradients**: Text and cards must never use rainbow or gradient text clipping (`bg-gradient-to-r from-purple to-pink bg-clip-text`).
4. **Honest Copywriting**: State system actions plainly ("Uploading paper", "Extracting citations", "Searching Europe PMC") without synthetic hype words ("revolutionary", "synergy", "supercharge").
5. **Interactive Citation Anchors**: Every reference chip (`[1]`, `[Doc 2]`) must link directly to the physical document inspector with jump-to-highlight capability.
