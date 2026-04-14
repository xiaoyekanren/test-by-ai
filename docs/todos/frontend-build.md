# Frontend Build TODO

## Vite chunk size warning

- Status: Partially addressed
- Context: `npm run build` succeeds, but Vite warns that `_plugin-vue_export-helper-87YlmiK8.js` is larger than the default 500 KB threshold.
- Current finding: the chunk is a shared vendor bundle that includes dependencies such as Vue and Element Plus; it is not caused by the IoTDB page alone.
- Current mitigation: `build.chunkSizeWarningLimit` is set to `1200` in `frontend/vite.config.ts` to reduce build warning noise.
- Better optimization option: split vendor chunks intentionally, for example Vue core, Element Plus, Vue Flow, and xterm, then verify runtime loading order and page behavior.
- Recommendation: defer real chunk splitting until performance work is prioritized.
