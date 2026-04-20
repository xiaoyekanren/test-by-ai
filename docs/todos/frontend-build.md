# Frontend Build TODO

## Vite chunk size warning

- Status: 已优化
- Context: 通过 `vite.config.ts` 中的 `manualChunks` 函数将 vendor 依赖拆分为 5 个独立 chunk：vendor-core（vue/router/pinia）、vendor-ui（element-plus）、vendor-flow（vue-flow）、vendor-terminal（xterm）、vendor-http（axios）。
- 剩余问题: `vendor-ui`（element-plus）仍为 896 KB，超过 500 KB 阈值。需要后续通过 `unplugin-vue-components` 按需导入进一步优化。
