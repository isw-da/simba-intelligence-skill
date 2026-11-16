# Licensing: mint, apply, renew

Mint against the instance's own token on the Logi Composer internal page with `SIMBA_INTELLIGENCE`, never `DISABLE_BI_FEATURES`.
Apply the downloaded key on Administration > Licenses.
Sign out and back in so the AI menus appear.

Based on evidence compiled 16 November 2026. The portal procedure was tested on 12 November 2026; the UI procedure was tested on 26.3.1.

---

## How the licence works

Simba Agentic Intelligence and Self Service Analytics (formerly Logi Composer) share one licence store. Both the Composer admin page and the SI Manage License dialog share the licence API. On 26.2 and earlier, the tested Discovery route is `/discovery/api/license`. For 26.3, the docs give `/api/license` and the chart places everything under `/composer`, giving `/composer/api/license`; this route is untested in the evidence. Swagger is at `/composer/swagger-ui.html`. SI has no separate licence endpoint: `/api/v1/license` returns 404. A 404 alone does not mean the licence failed.

The licence is in `zoomdata.public.key_value_entries`, under `ZD_LICENSE_KEY`. There is no separate licence table. It travels inside `zoomdata.dump`.

A regular key is bound to the installation. Its decoded `instance_id` holds the lowercase hexadecimal MD5 of the uppercase instance ID, not the literal `<instance id>`. A different looking value is therefore not proof of a mismatch. Mint from the running instance's own `.tok` file and compare the hash when checking a decoded key. Decoding the JWT payload does not verify its signature.

**Superseded (C2):** The 22 June 2026 diagnosis that a particular hash was a default or wrong ID is unreliable. The 7 July match and 12 November hash finding contradict it. The original June failure's cause remains unknown.

| Feature ID | Effect |
|---|---|
| `SIMBA_INTELLIGENCE` | Enables AI entitlement. In 26.3, LLM configuration and Workspaces are gated by this flag. |
| `DISABLE_BI_FEATURES` | Hides Create visual with AI from the Composer add menu. Dashboards and SI chat still work. Exclude this flag for the full AI and visual surface. |
| `_LICENSE_INFO` | Appears alongside `SIMBA_INTELLIGENCE` in the tested decoded key. Its function is not recorded. |

A key with neither of the first two flags was reported to keep working while pods stayed up, but risk reporting itself unlicensed after a restart. Use the tested combination: `SIMBA_INTELLIGENCE` present, `DISABLE_BI_FEATURES` absent.

The built in Composer trial starts on first startup, generates a unique installation ID, lasts 14 days and permits 5 users. It excludes AI. Setting `simbaIntelligence.enabled: true` in Helm does not add that entitlement or reveal LLM configuration.

---

## Renew or mint

1. **Check licence management before minting, then get the token.** Check the Helm values for `licenseKey` or `license.existingSecret`. A Helm managed licence has higher priority than the database key and must be changed through `helm upgrade`; UI or API replacement fails. The documented values are `licenseKey` and `licenseInstallationId`, or `license.existingSecret`. Properties installations use `zoomdata.license.key` and `zoomdata.installation.id` in `zoomdata.properties`. Use the installation's existing management route.

   Log in as a system administrator or member of the Supervisors group. On 26.3.1, open Administration > Licenses > Download Instance Token. Save the `.tok` file. Before applying a new key, select Download Current Key on Administration > Licenses and keep a private rollback copy of `license.key`. The Instance ID is at the top of the page; keep it private.

   On SI 25.x, 26.1 and 26.2, use user menu > License > Download Instance Token. Download Current Key saves the current key as `license.key`; keep a private rollback copy before replacing it.

   **Superseded for 26.3.1 (C6):** The older user menu > License > Submit New License path, recorded on 7 July 2026, is not the tested 26.3.1 navigation. It remains relevant to older builds.

2. **Check the token belongs to the instance.** It has three dot separated parts. The middle part is base64url JSON containing `instanceId` and `version`. Compare `instanceId` with the ID read directly from Administration > Licenses. Stop on a mismatch. The token's version should match the instance's version: `26.3` on the tested route. This is not a requirement for older builds to use `26.3`; check against their own version. Do not substitute an ID or a token from a test installation.

3. **Open the portal.** Connect to the insightsoftware VPN, open https://license.dundas.com/ and sign in with insightsoftware SSO. Portal access has only been proven from Amin's Windows work laptop on VPN, on 12 November 2026; the Mac session could not reach it. If you cannot reach the portal, ask Amin.

4. **Choose the tested generator.** Under Internal Licenses, select **Logi Composer: Generate license for internal use**.

   Avoid **Simba Agentic Intelligence: Generate Logi Composer license for SAI...**. The tested internal SAI page silently adds `DISABLE_BI_FEATURES` and has no controls to remove it. The SAI trial page was only viewed and is unverified.

   **Superseded (C3):** The 7 July 2026 claim that every internally mintable key contains `DISABLE_BI_FEATURES` is contradicted by the 12 November Composer internal page test.

5. **Fill the form as follows.** These are the values used in the tested internal mint, not a recorded customer sizing policy.

   | Field | Enter or check |
   |---|---|
   | Description | Optional free text. For a repro or test key, use `insightsoftware internal test` and do not use a customer name. For a customer key, a description such as `<customer> evaluation` is fine; the NexGen key used a customer description. |
   | Licensee | Fixed to `insightsoftware - <your name>`; cannot be edited. |
   | License Type | Instance, the only option on this page. |
   | Instance Token | Paste the `.tok` contents, drag the file onto the box, or double click to browse. |
   | Expiry | Choose the required date, no later than today plus 90 days. Default is plus 90 days; buttons run from `+15d` to `+90d`, or type `yyyy-mm-dd`. |
   | User Count | 100 |
   | Concurrent Session Count | 250 |
   | Concurrent Service Instances | 1 |
   | Connector Restriction Type | None |
   | Features: Simba Agentic Intelligence | Leave unticked for the proven route below. |
   | Additional Feature IDs | Enter only `SIMBA_INTELLIGENCE`. |
   | Version check | Off in the recorded keys. |

   **Superseded as a general limit (C4):** Leo's relayed 12 November 2026 advice of up to 30 days matches trial pages. Internal pages permit up to 90 days, supported by actual 90 day keys. Stay within 90 days even though the portal's browser validation script was observed to throw an error.

   The Composer trial page was only viewed: it has a required editable Licensee, Instance or OEM type, Unlimited checkboxes and a maximum of 30 days. Its minted feature behaviour is untested.

   **Superseded as a proven alternative (C8):** The 12 November runbook said either checkbox state gives the same result. Checkbox only and explicit feature ID keys decoded alike, but only the key with `SIMBA_INTELLIGENCE` in Additional Feature IDs was applied and proven.

6. **Generate and inspect before downloading.** Click Generate License. The page reloads with key text, Download and a Decoded license box. Check `features` includes `SIMBA_INTELLIGENCE` and may include `_LICENSE_INFO`, but excludes `DISABLE_BI_FEATURES`. Check `expiration_date` is the intended date and check the instance hash. Download the `.key` text file; the recorded naming pattern is `SSA-<id>-<licensee>-<description>.key`.

   **Superseded by the actual result (C5):** For NexGen, 12 November 2026, the prompt requested `+30d`, implying 12 December, but the decoded and applied key expired 3 December 2026. Trust the decoded key and live status, not button arithmetic. A guide screenshot showing 1 December was a demo instance, not that customer's key. The discrepancy's cause is unknown.

7. **Apply the key.** On 26.3.1, open Administration > Licenses > Choose File, select the `.key`, then Submit. On older SI builds, use user menu > License > Submit New License, choose the key and Submit.

   API alternative: on 26.2 and earlier use the tested Discovery route `/discovery/api/license`; on 26.3 use `/composer/api/license` per the docs and chart layout, untested in the evidence. The docs give `/api/license` with Swagger at `/composer/swagger-ui.html`. Authenticate as admin, read the existing licence for rollback, then submit the key with this exact media type and body shape. Supply the actual key privately; the following is a request template only.

   ```http
   GET <licence route>

   POST <licence route>
   Content-Type: application/vnd.composer.v3+json

   {"licenseKey": "<key>"}
   ```

   Multipart, plain JSON media type and octet stream returned 415. Choose the licence route for the deployment as stated above. A 404 alone does not mean the licence failed. A rewriting proxy caused a UI upload CORS 403 in July; applying server side avoided that proxy artefact.

8. **Sign out and back in.** No pod restart was needed in the 12 November test.

   **Superseded (C1):** The 2 September 2026 hard refresh advice, repeated on 12 November before testing, did not work on 26.3.1. Even a hard refresh left LLM and Workspaces hidden; signing out and in revealed them.

9. **Verify the result.** Administration > Licenses must show **Valid** and the intended new expiry immediately after Submit. After signing in again, confirm Workspaces in the left menu and LLM under Administration > Tools. Check that Create visual with AI is available when that surface is required.

   GET `/discovery/api/license` on 26.2 and earlier exposes `instanceId`, `expirationDate`, `userCount`, `concurrentSessionLimit` and `features`. For 26.3, use GET `/composer/api/license` per the docs and chart layout, untested in the evidence. A 404 alone does not mean the licence failed. Confirm the limits and feature flags, not just a successful upload. Run a Playground smoke query when the provider and data are configured; an HTTP 200 alone is not proof of the answer.

   The browser console error below means AI is not licensed. A blank Playground can coexist with working login, LLM configuration, connections, sources and Data Source Agent.

   ```text
   SIMBA_INTELLIGENCE feature is not licensed
   ```

   This was recorded from `logi-chat.js`. On the tested trial, `/composer/llm-configuration` returned 404 and `/composer/intelligence/` returned 400; guessing those URLs did not unlock AI.

---

## Renewing an existing instance

Renew before the displayed expiry, including when an evaluation runs beyond it. Composer notifies when a key is about to expire. No fixed renewal lead time is recorded.

The proven renewal is a fresh mint against the running instance's own token, followed by applying the new key. A 7 July 2026 renewal used this route and ran to 5 October 2026. Download the current token and check its ID before minting. No source confirms that token contents stay stable between runs or that an old token can always be reused. A changed instance ID requires the matching token.

The claim on 12 November 2026 that an extension can be made later from the same portal page was not tested as an extension workflow. Do not treat it as proof of token stability.

After a standard or trial licence expires, documentation says only system administrators can log in to update it; regular users see a licence expired message. The Mac lab, with expiry 10 September 2026, instead showed `server_error` on every SI login even with the correct password. Treat expiry as a possible cause of that symptom.

---

## Customer instances

1. The customer downloads their own `.tok` from Administration > Licenses and sends it by email or Teams. They also confirm the Instance ID directly from that screen for the private comparison.
2. We check the token, mint against that installation, verify the decoded features and expiry, then supply the `.key`. Amin can mint internal SI and Composer keys himself. Do not substitute a key from our lab.
3. The customer selects the `.key`, submits it, signs out and back in, then checks Valid, expiry, Workspaces and LLM. We verify those results with them.

**Extension contacts and C7 disagreement:** For NexGen, 12 November 2026, the session said to ask **Paige Noble or Leo ZHAO** for an extension. For NexGen, 13 November 2026, the stakeholder slide identified Paige Noble as Account Manager for commercials and licensing, and the status deck named Amin, Leo and Paige as licence owners. These are contacts, not evidence of who approves an extension.

For NexGen, Leo ZHAO's message of 4 November 2026 offered to get a pixel perfect key when told they were ready; it was read on 9 November. Do not interpret that as the Composer approval process.

The Composer 26 documentation, with no publication date recorded in the evidence compiled 16 November 2026, says keys come through DevNet License Manager to the organisation's License POC; ask the Account Manager if that person is unknown. The Composer chart README for 26.3, also undated in that collection, says to contact Simba support for AI entitlement. No tested newer source resolves these routes or assigns customer extension approval. There is no justified Superseded ruling for C7.

---

## Traps

1. **A restore replaces the licence.** The key travels with `zoomdata.dump`. Restore first, then inspect GET `/discovery/api/license` on 26.2 and earlier or GET `/composer/api/license` on 26.3 per the docs and chart layout (26.3 route untested in the evidence). A 404 alone does not mean the licence failed. Preserve the current key privately and replace it if necessary. Restoring `mcpdemo-20260731` reintroduced `DISABLE_BI_FEATURES` and lost the visual enabled key applied on 20 July.

   Restoring the six databases and rerunning the chart dbm job carried the licence and identity into 26.2; restoring 26.2 dumps into a fresh 26.3 installation also carried them. Sanitised metadata archives can redact the licence and require a fresh mint against the restored instance's own token.

   | Freeze or rig finding | Recorded expiry or state |
   |---|---|
   | Webinar freeze, taken 2 September 2026 | One note says 1 December 2026; another says the freeze excludes the licence. Unverified, C9. |
   | A customer freeze, finding recorded around 2 September 2026 | Freeze key expires 14 September 2026. A restore after that date brings an expired key. |
   | A customer freeze, November webinar source cited in the 16 November 2026 collection | Freeze key expires 1 December 2026. |
   | Mac lab, 30 October 2026 source | Key expired 10 September 2026; no replacement recorded. |

   **C9 remains unresolved:** The two webinar notes were written around 2 September 2026 and have no later check. Neither supersedes the other. Read the live licence after restoring before relying on any freeze date.

2. **The SAI internal generator disables part of the visual surface.** Use the Composer internal page and inspect the decoded flags. The older backup reference's broad claim that `DISABLE_BI_FEATURES` hides dashboards is superseded by the specific 2 September 2026 finding: it hides Create visual with AI while dashboards and SI chat work.
3. **Keys from another instance are silently rejected.** Use the target's own token. The missing AI console error can be the only visible symptom; the original June diagnosis is uncertain as explained under C2.
4. **Never spoof an instance ID.** Rewriting the ID to validate a non matching key defeats instance binding and risks the vendor relationship.
5. **Refresh is insufficient on 26.3.1.** Apply, sign out, sign back in. A routine pod restart was not required.
6. **Helm keys override database keys.** Update a Helm managed licence through Helm. UI or API success assumptions do not override that priority.

---

## Logi Report, pixel perfect and OEM versus retail

For NexGen, 4 November 2026, Leo ZHAO offered to obtain the pixel perfect licence when they were ready. The 9 November source recorded no request for company details or a server ID. The generator page, minting inputs and maximum duration are unknown; do not use the Composer recipe as a PPR recipe.

Older Logi Report v19 documentation dated 28 November 2024 says to update Server through Server Console > Administration > Configuration > License Key > here, enter the user ID and key supplied by the account manager, then Submit. Designer documentation from 2021 gives this command from `<install_root>\bin`:

```text
rp UID INSTALLKEY
```

These are historical procedures, not verified instructions for Logi Report 26.3.1. Older Logi Info/Report documentation describes a 15 day built in trial after which Studio is unusable and reports stop; applicability to current Logi Report is unknown.

Composer OEM licensing is distinct: documentation says an OEM key allows unlimited deployments without a key per instance and unattended installs with only `licenseKey` in Helm values. The portal's Composer trial page offers OEM type, but it was not minted or tested. The backup reference mentions portable keys with `instance_id: enabled=false`; the portal control for that is unknown.

Simba Data Connectivity driver OEM versus retail is a separate mechanism. A 3 September 2026 binary comparison found no licence enforcement or bundled `.lic` in a branded OEM driver build; retail enforced licensing and included a `.lic`. Craig Chaplin confirmed on 28 May 2026 that a Simba Linux licence has Platform Linux and no architecture field, covering x86 and ARM. Do not transfer those driver conclusions to Composer.

The recorded 26.3 entitlement decision says legacy Symphony bundle customers get SI features without extra charge, existing Self Service Analytics customers need an upsell, and new ISVs get the bundle. Visualisation over MCP is Read Only on a standalone Agentic Intelligence licence. These commercial statements do not replace checking the actual key.

---

## Not yet known

* Which portal page mints Logi Report or pixel perfect keys, what inputs it needs and its maximum duration.
* Who approves customer extensions and how much lead time they need; C7 remains unresolved.
* Whether an extension uses the same portal page without a new token, or whether an old token stays reusable between runs.
* Which portal control disables the `instance_id` restriction for a portable key.
* Why the NexGen key minted on 12 November 2026 expired 3 December rather than the requested 12 December, C5.
* Whether Composer trial keys decode like internal keys or add `DISABLE_BI_FEATURES`; the SAI trial behaviour is also untested.
* The NexGen License POC and DevNet self service arrangement, unrecorded in the 12 November 2026 findings.
* The intended customer trial user and session limits; 100 and 250 are recorded defaults, not a sizing policy.
* Whether Leo expects Teams or a ticket for the pixel perfect request; his 4 November 2026 offer does not specify the route.
* The offline or air gapped renewal procedure; the 6 October 2026 question has no recorded answer.
* Whether the Mac lab's expired key has been replaced since the 30 October 2026 note.
* Whether the Windows Docker route using `bootstrap-composer.ps1` has the same licensing UI.
* A Mac copy of the Windows `Downloads\runbook.md` and portal screenshots 01 to 06; only the attached runbook text was available.
* Who besides Amin has portal access, and whether access without VPN is possible.
* Whether the webinar freeze includes a licence and which expiry it restores, C9.
* What `_LICENSE_INFO` does and the full replica limits for licences applied through UI or API; the evidence's replica caveat was truncated.

---

## Sources

* `~/si-docs-mirror/logi-composer-current/v26/articles/manage-composer-26/43701121443341-request-and-apply-a-new-license-key.md` and `43701073826829-apply-licenses.md` under the v26 articles tree.
* `~/si-docs-mirror/logi-devnet/articles/logi-report/configuring-logi-report-server-v19/5741416097559-updating-the-server-license.md`.
* `~/si-docs-mirror/logi-devnet/articles/general/report/4404609236119-updating-the-designer-license-key.md`.
* `~/si-docs-mirror/logi-devnet/articles/logi-info/install-logi-info-logi-report/1500009530921-install-logi-info-logi-report.md`.
* `~/box-rigs/si263/composer/README.md`: chart 1.22.0, appVersion 26.3.
* `eval-deck/guide/simba-trial-guide.html` and `eval-deck/guide/nexgen-setup-guide.html` in this repo.

Session notes and memory files held by Amin; ask him for detail.
