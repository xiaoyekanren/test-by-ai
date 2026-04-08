# IoTDB CLI TODO

## Long connection terminal

- Status: TODO
- Context: the long connection CLI now uses `@xterm/xterm` to render the interactive IoTDB CLI session instead of a custom text output area.
- Follow-up: evaluate terminal theme, font size, selected text copy behavior, and search over terminal history.
- Follow-up: define SSH and CLI session timeout behavior, including clearer user feedback when the remote process exits or the network drops.
- Follow-up: consider extracting the xterm setup into a dedicated component if `IoTDBView.vue` keeps growing.

## Frontend bundle

- Status: TODO
- Context: `chunkSizeWarningLimit` currently reduces build warning noise, but it does not reduce real bundle size.
- Follow-up: evaluate deliberate vendor chunk splitting for Vue, Element Plus, Vue Flow, and xterm when frontend performance work is prioritized.
