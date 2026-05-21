# Embedding the SI chatbot in a host app

Taking NLQ out of the Playground and into a customer-facing application.
The setup skill gets you to a built, governed source that answers
questions in the Playground; this reference covers the next step, putting
that same chatbot inside someone else's app.

Companion to `post-install.md` (build the source) and
`nlq-stress-testing.md` (validate it before anyone embeds it). Do not
embed a source you have not stress-tested; a hallucination in a demo
playground is recoverable, the same answer inside a customer's product is
not.

---

## Which SI surface this is

The embeddable chatbot is the Composer-embedded surface (SI v1):
`apiBaseUrl` points at `<server>/intelligence`, and it renders through the
Composer embed manager, the same `createComponent` API used for
dashboards. This is a different thing from the standalone v2 Playground
(`/playground?sourceId=...`, served gunicorn-direct), which is a hosted
page, not an embeddable component. If you want NLQ inside an application,
you want the embeddable chatbot described here. See
`datadog-logs.md` § SI v1 vs SI v2 for the full distinction.

---

## Prerequisites

1. A built, stress-tested source on the SI deployment, and its
   `<sourceId>`.
2. The Composer embed manager available from the host
   (`<server>/discovery/embed/embed.js`, exposed as
   `window.initComposerEmbedManager`).
3. A trusted-access token minted for the user who will be asking
   questions. The token's user is what row-level and column-level
   security evaluate against, so the chatbot only ever sees data that
   user is permitted to see. This is the governance from
   `data-source-modelling.md` applied at query time.

---

## The component

```js
const embedManager = await initComposerEmbedManager({
  getToken: async () => ({ access_token, expires_in })
});

const chat = await embedManager.createComponent('chat-bot', {
  sources: ['<sourceId>'],          // the semantic-layer + RLS context
  theme: 'composer',                // composer | modern | dark; needs a `symphony` section
  config: {
    apiBaseUrl: '<server>/intelligence',
    mode: 'auto',                   // none | auto | visual
    allowModeSwitch: true,
    timeout: 60000
  },
  onClose: () => { /* host closes the panel; also call destroy() */ }
});
await chat.render(document.getElementById('chat-host'));
```

Field notes:

- `sources` is the heart of it. Pass the governed source(s); the chatbot
  reasons over their semantic layer (field meanings, metric definitions,
  joins) and obeys their security rules. Multiple sources are supported.
- `mode`: `none` is text answers only, `visual` builds a chart, `auto`
  lets the model decide. `allowModeSwitch` shows the user the toggle.
- `theme` needs a `symphony` section in the theme JSON for the chatbot
  surface to pick up brand colours. See the composer-mcp `THEMES.md` for
  the theme JSON structure.

---

## Events

Wire the chatbot into the host application with `addEventListener`. The
ones worth handling:

```js
chat.addEventListener('composer-chat-bot-loaded', () => { /* ready */ });

chat.addEventListener('composer-chat-visual-received', (e) => {
  const nlq = e.detail.visParams.visual_request.description;  // the question, in words
  // hand off to your own logging / analytics here
});

chat.addEventListener('composer-chat-visual-action-executed', (e) => {
  // user acted on a generated visual (e.g. opened it in the builder)
});
```

A generated chart can be opened in a `visual-builder` component and saved
as a real visual, which turns an NLQ answer into a reusable dashboard
tile. That hand-off is host-side wiring; the builder embed lives in the
composer-mcp embed docs.

---

## Loading pitfalls (the hard-won ones)

These cost hours if you hit them blind.

- Never `display: none` the chat panel. A zero-dimension container leaves
  the chatbot stuck on "Loading Assistant" forever. Hide it with
  `opacity` / `visibility` / off-screen positioning instead.
- Render once. Re-rendering the same component leaks state and sockets;
  create it on first open and keep the reference.
- Boot on auth-ready. Creating the component before the token exists
  fails silently.
- In a drawer or modal, set `_isDrawerEmbed: true` so host-side WebSocket
  filter injection (used to push dashboard filters) does not bleed into
  the chatbot's own queries.
- The chatbot uses Blueprint portal popups, which mount at the document
  root. You need three CSS overrides on `#logi-modal-root` for popovers
  and dropdowns to sit above your app chrome.
- Call `destroy()` on teardown, including from `onClose`.

---

## Where the rest lives

This doc is the SI-side view: what to pass, what governance you get, and
the chatbot-specific gotchas. The generic embed-manager mechanics
(filter passing between the host and embeds, `targetComponents` scoping,
event capture for product analytics, modal embed defaults) are documented
once in the composer-mcp repo and apply here unchanged:

- `isw-da/composer-mcp` → `CHATBOT_EMBED.md` (the chatbot embed in full)
- `isw-da/composer-mcp` → `EMBEDDING_RUNTIME.md` (filters, events, modal embeds)
- `isw-da/composer-mcp` → `THEMES.md` (the theme JSON `symphony` section)

---

## Sources

- Embed SI on symphony playground (CMP-9046): https://insightsoftware.atlassian.net/wiki/spaces/DCI/pages/17862524939
- AI Differentiation Guide for Internal Teams (SI required to embed the chatbot): https://insightsoftware.atlassian.net/wiki/spaces/DCI/pages/16757850674
- Simba Intelligence + Simba Core/Composer Deployment Strategy: https://insightsoftware.atlassian.net/wiki/spaces/SCP/pages/18122997766
