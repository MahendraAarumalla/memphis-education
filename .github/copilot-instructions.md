<!-- .github/copilot-instructions.md for memphis-education / pixel-agents -->
# Copilot instructions — Pixel Agents (memphis-education)

This file gives actionable, repository-specific guidance so an AI coding agent can be productive immediately.

Summary
- Project is a VS Code extension + standalone server + React webview (pixel-agents). Major code lives in `pixel-agents/`.
- Key boundaries:
  - Extension backend: `pixel-agents/src/` (VS Code activation, `PixelAgentsViewProvider.ts`, terminal lifecycle)
  - Webview UI: `pixel-agents/webview-ui/src/` (React + Vite, canvas game loop, `OfficeState` imperative model)
  - Standalone server: `pixel-agents/server/src/` (HTTP hook receiver, `server.ts`, Vitest tests)
  - Scripts & asset pipeline: `pixel-agents/scripts/` and `webview-ui/public/assets/`

What to read first
- `pixel-agents/CLAUDE.md` — authoritative architecture notes (messages, JSONL shapes, polling vs hooks). Read before touching watchers or timers.
- `pixel-agents/README.md` — developer quickstart and high-level constraints.
- `pixel-agents/src/PixelAgentsViewProvider.ts` and `pixel-agents/src/agentManager.ts` — where terminals/agents are bound.
- `pixel-agents/webview-ui/src/office/` and `webview-ui/src/engine/gameLoop.ts` — imperative game model and rendering.

Critical flows & conventions (concrete)
- Agent detection: extension watches Claude JSONL transcripts at `~/.claude/projects/<project-hash>/<session-id>.jsonl`. Hooks mode (HTTP hook) is preferred; heuristic polling (500ms/1s/3s/30s) is fallback. See `server/src/` and `src/fileWatcher.ts`.
- Message protocol between extension ↔ webview uses `postMessage` with keys like `openClaude`, `agentCreated`, `agentToolStart`, `agentToolDone`, `layoutLoaded`, `furnitureAssetsLoaded` — check `CLAUDE.md` for full list.
- Persistence patterns: user-level layout in `~/.pixel-agents/layout.json` (atomic write via `.tmp` + rename), agents persisted to VS Code `workspaceState` key `pixel-agents.agents`.
- Rendering model: `OfficeState` is NOT React state — it's imperative. Mutations require calling the explicit React bridge (e.g., `onEditorSelectionChange()`) or dispatching `postMessage` updates.

Project-specific coding rules
- Avoid adding inline magic numbers — use `src/constants.ts` (extension) or `webview-ui/src/constants.ts` (webview).
- TypeScript: project prefers `as const` over `enum`. Use `import type` for type-only imports.
- File watching: always pair `fs.watch` with a polling fallback and implement partial-line buffering for append-only JSONL files (look at `fileWatcher.ts` and `transcriptParser.ts`).
- Tool completion events: debounce `agentToolDone` by ~300ms to avoid UI flicker (implemented in the extension).

Build, test, and debug (commands)
- Install & build (root `pixel-agents`):
  - `npm install`
  - `cd pixel-agents/webview-ui && npm install && cd ../.. && npm run build`
  - Run in VS Code: press F5 to launch Extension Development Host.
- Tests:
  - `npm test` (all)
  - `npm run test:server` (Vitest server tests in `pixel-agents/server/__tests__`)
  - `npm run test:webview` (webview tests)
  - `npm run e2e` (Playwright E2E)

Where to make changes for common tasks
- Add/modify agent behavior or terminal lifecycle: `pixel-agents/src/agentManager.ts`, `PixelAgentsViewProvider.ts`.
- Change message shapes, add a new postMessage type: update both extension `src/constants.ts` and webview `webview-ui/src/constants.ts` and handlers in `useExtensionMessages.ts`.
- Modify layout model or persistence: `layoutPersistence.ts` and `webview-ui/src/layout/*` (serializer, editor tools).
- Asset changes: add files under `webview-ui/public/assets/` and rebuild (`scripts/` assist with asset pipeline).

Important tests & CI signals
- Server has unit tests under `pixel-agents/server/__tests__` (Vitest). Use `npm run test:server` locally when touching server/hook logic.
- Webview integration and asset-related logic have separate tests — run `npm run test:webview` after edits to sprite, catalog, or renderer.

Examples (copyable)
- Build and run extension dev host:
  - `cd pixel-agents && npm install && cd webview-ui && npm install && cd .. && npm run build && code --extensionDevelopmentPath=$(pwd) --extensionTestsPath=$(pwd)`
- Run server tests only:
  - `cd pixel-agents && npm run test:server`

Notes & gotchas (from code)
- JSONL `/clear` rotates files — do not assume a static file path for long-running sessions.
- `characterSpritesLoaded` → `floorTilesLoaded` → `wallTilesLoaded` → `furnitureAssetsLoaded` → `layoutLoaded` is the expected asset load order.
- Webview uses integer zoom (integer DPR scaling) and does not call `ctx.scale(dpr)` — be careful when changing renderer assumptions.
- When changing default layout: export via the command palette “Pixel Agents: Export Layout as Default” (writes `webview-ui/public/assets/default-layout.json`), then rebuild.

If unsure
- Read `pixel-agents/CLAUDE.md` (big picture + many protocol details). When in doubt about timing or polling, follow the established timers in `src/constants.ts`.

---
If you want, I can now merge this into the repo (create the file) or expand any section with concrete code pointers/examples. What should I update next?
