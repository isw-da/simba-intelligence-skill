# Peter's "still confirmed not working" list: settled, and explained

Tested 27 August 2026 against the embed SDK served by a live Simba Intelligence 26.2.1
install (Composer as the `discovery` subchart, kind cluster). The SDK was fetched from the
running instance at `/discovery/embed/embed.js`, 44,422 bytes, served unauthenticated, and
saved as `embed-26.2.1.js`.

Source of the claims: Peter Armstrong's `Logi-Composer-Symphony-Embedding-Reference.md:643-646`, section
headed "Still confirmed not working". None of the three carried a date, and the same section
retracts an earlier claim of his own at `:641` marked "Previously incorrect documentation",
so the list needed retesting before reuse.

## Method, and what it can and cannot prove

This is static analysis of the shipped SDK, not a browser run. That is weaker than a live
embed for questions of runtime behaviour, and stronger than either party's documentation for
questions of what the API surface contains. All three claims turn out to be surface
questions, which is why this method settles them.

Counts are true occurrence counts (`grep -o | wc -l`). The file is minified to a single
line, so line-based counting would have read every count as 1, and did on the first pass.

## Verdict: all three confirmed, 26.2.1

### 1. `dashboardComponent.trigger('EMBED/PUBLISH', ...)` throws "trigger is not a function"

**Confirmed.** The string `trigger` occurs **zero times** in the entire SDK. There is no such
method on any class.

Two separate reasons it fails, and the second is the one worth knowing. The publish API is
`publish(topic, message, options)`, and it is defined on the **EmbedManager**, not on a
dashboard component. Its constructor is visible in the same region
(`this.config=e, this.componentList={}, this.config.getToken&&this.initializeToken()`).

So the working call is `embedManager.publish(topic, message, options)`. Reaching for the
component is the error, and no rename of `trigger` would have fixed it.

### 2. `initialFilters` with `forTopic` is accepted but does not filter

**Confirmed.** `initialFilters` is real: 11 occurrences, a declared property assigned in the
component constructor alongside `interactivityProfileName`, `interactivityOverrides` and
`menuEventsConfig`.

`forTopic` occurs **zero times**. The SDK has no such key. JavaScript accepts unknown
properties on an object without complaint, so the call succeeds and the key is dropped on the
floor. That is precisely "accepted but does not filter", and it is silent by construction.

### 3. Dispatching `CustomEvent('EMBED/PUBLISH')` on `document` has no effect

**Confirmed, and the SDK shows the fix.** The whole dispatcher is:

```js
const L = (e, t) => {
  const i = (o = {type: e, data: t}, new CustomEvent("EMBED/CUSTOM_EVENT", {detail: o, bubbles: true}));
  var o;
  document.dispatchEvent(i)
};
```

and `publish` is `publish(e,t,i){ L("EMBED/PUBLISH", {topic:e, message:t, options:i}) }`.

The event **name** on the wire is `EMBED/CUSTOM_EVENT`. `EMBED/PUBLISH` is not an event name
at all: it is the `detail.type` discriminator inside it. So dispatching an event *named*
`EMBED/PUBLISH` reaches nothing, because nothing is listening for that name.

The equivalent that should work, derived from the SDK rather than guessed:

```js
document.dispatchEvent(new CustomEvent("EMBED/CUSTOM_EVENT", {
  detail: { type: "EMBED/PUBLISH", data: { topic, message, options } },
  bubbles: true
}));
```

Corroborating detail: `document.addEventListener` occurs zero times in the SDK, and
`postMessage` zero times. The only three `addEventListener` calls bind
`composer-dashboard-loaded`, `composer-visual-builder-loaded` and `discovery-report-loaded`.
So this is a `document.dispatchEvent` bus with a single event name and an inner type, and the
receiving half lives in the embedded application rather than in this file.

## What this changes

Peter's list was right on all three counts and should be kept, not retested again. What it
lacked was the mechanism, and the mechanism converts two of the three from "does not work"
into "here is the call that does".

The `EMBED/CUSTOM_EVENT` wrapper in particular is absent from both knowledge bases. Anyone
trying to drive an embedded dashboard from outside the SDK needs it, and would otherwise
conclude from Peter's list that the door is shut.

## Not settled here

Whether the `EMBED/CUSTOM_EVENT` form actually filters a live dashboard end to end. That
needs a dashboard, a data source and a browser, and this instance is a fresh install with an
empty source list (`{"content":[]}`). The static evidence says the listener exists and the
name is right; it does not prove the round trip.
