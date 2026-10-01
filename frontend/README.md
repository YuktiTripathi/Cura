# Cura frontend

Independent React + Vite UI. It talks only to the Cura API.

```bash
npm install
npm run dev
```

Optional env:

```
VITE_CURA_API_URL=http://127.0.0.1:8000
VITE_CURA_USER_ID=demo-user-001
```

## Tests and checks

```bash
npm test          # vitest
npm run build     # typecheck (incl. API drift checks) + production build
```

## API types

`src/types/api.generated.ts` is generated from the backend's live OpenAPI schema
(`openapi/cura.json`, exported from FastAPI rather than the hand-maintained
`contracts/openapi.yaml`). `src/types/apiContract.ts` fails the typecheck if a field the UI
relies on disappears from the backend.

After changing a backend response model:

```bash
source ../backend/.venv/bin/activate
npm run gen:openapi   # refresh openapi/cura.json from FastAPI
npm run gen:api       # regenerate src/types/api.generated.ts
npm run build
```

`npm run check:api` fails if the generated file is out of date with `openapi/cura.json`.

## Theme

The header toggle cycles system → light → dark (stored in `localStorage` as `cura_theme`).
Colours are CSS variables at the top of `src/styles.css`.

