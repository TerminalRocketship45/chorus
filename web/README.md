# Chorus web (frontend)

Vite + React + TypeScript. Plain CSS, no UI framework, no chart library (the trend chart on the
teacher view is a small inline SVG, see `src/components/TrendChart.tsx`).

## Disk layout

Home quota is full, so everything heavy lives on lustre and is symlinked in:

- Node 22 LTS (official linux-x64 tarball) is unpacked at
  `/lustre/smuexa01/client/users/rbankapur/chorus_scratch/node/node-v22.20.0-linux-x64/`.
- The npm cache is `/lustre/smuexa01/client/users/rbankapur/chorus_scratch/npm_cache`.
- `web/node_modules` is a symlink to
  `/lustre/smuexa01/client/users/rbankapur/chorus_scratch/web_node_modules` (the real directory).
  Never let a real `node_modules` land under `~/chorus`.

`/lustre/smuexa01/client/users/rbankapur/chorus_scratch/env.sh` did not exist yet when this was
set up, so there was nothing to append a `PATH` export to (the setup task says to append to it
only if it already exists). Put Node on your `PATH` for this shell with:

```sh
export PATH="/lustre/smuexa01/client/users/rbankapur/chorus_scratch/node/node-v22.20.0-linux-x64/bin:$PATH"
export npm_config_cache="/lustre/smuexa01/client/users/rbankapur/chorus_scratch/npm_cache"
```

If `chorus_scratch/env.sh` is created later (e.g. by the Python-side setup), move these two lines
into it and `source` it instead of pasting them by hand.

## Commands

Run from `web/` with the PATH above exported:

```sh
npm install           # only needed once / after package.json changes
npm run dev            # Vite dev server; proxies /api -> http://localhost:8000
VITE_MOCK=1 npm run dev  # same, but serves fixture API responses (see src/mock/)
npm run build          # tsc --noEmit, then the production build into web/dist
npm run typecheck       # tsc --noEmit only
npm test                # vitest, runs the unit tests once
```

`npm run dev` proxies `/api/*` to `http://localhost:8000`, where the FastAPI service
(`src/chorus_api/`) is expected to run in development. In production, FastAPI serves the built
`web/dist/` directly, so there is no proxy.

## Dev mock

`src/mock/server.ts` is a tiny fixture server for every route in `docs/api.md`. It's wired into
`vite.config.ts` as a server-only Vite plugin (`apply: "serve"`) and only activates when the
`VITE_MOCK=1` environment variable is set when starting `vite dev`. It is never pulled into
`npm run build`'s output: the plugin hook it uses doesn't run during a build, and the handler
module is imported dynamically only inside that hook.

Fixtures live in `src/mock/fixtures.ts`, including one `AnalyzeResponse` that exercises every
`display` value from `docs/api.md` (`correct`, `accent_ok`, `misread` with a heard word,
`skipped`, `extra_nearby`, `repeated`, `self_corrected`) and a second with `accent_adjusted: null`.

## Where things live

- `src/types/api.ts` — TypeScript types mirroring `docs/api.md` exactly.
- `src/lib/api.ts` — the HTTP client for `/api/*`.
- `src/lib/display.ts` — the ONLY place that maps a word's `display` value to how it renders.
- `src/content/results.ts` — the measured accent-filter numbers, in one place so they can be
  updated after the pending GPU re-evaluation without hunting through the app.
- `src/content/app.ts` — the app name (`APP_NAME`) and other app-wide constants.
- `src/mock/` — the dev-only fixture API (see above).
- `src/pages/` — one file per screen; `src/components/` — shared pieces (word rendering, score
  panel, trend chart, header/footer).
