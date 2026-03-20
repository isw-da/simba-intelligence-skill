# Sharing and Maintaining the SI Skill Across the Team

How to deploy this skill so everyone on the team has it, and how to keep
it updated as the product evolves.

---

## Option 1: GitHub Repository (recommended)

The most robust approach. Everyone pulls from the same source, changes are
tracked, and updates are automatic.

### Setup

1. Create a private repo: `insightsoftware/simba-intelligence-skill`
2. Push the `simba-intelligence-setup/` folder to it
3. Add a README.md (outside the skill folder) explaining how to install it

### How team members install it

**Claude (skill upload):**
1. Clone or download the repo
2. Zip the `simba-intelligence-setup/` folder
3. Upload in Claude: Settings → Capabilities → Skills

**ChatGPT (custom GPT):**
1. Open the `universal/simba-intelligence-llm-guide.md` file from the repo
2. Create a custom GPT with its contents as the Instructions
3. Share the GPT link with the team

**Gemini (Gem):**
1. Same as ChatGPT but create a Gem instead

### How to update

When someone learns something new (a deployment gotcha, a new provider, a
product change):

1. Clone the repo
2. Edit the relevant reference file
3. Commit and push
4. Post in the team Slack/Teams channel: "Skill updated — [what changed]"
5. Team members re-download and re-upload the skill

### Branching strategy

Keep it simple:
- `main` — the current production skill
- Feature branches for significant changes
- No need for PRs on small fixes — trust the team

---

## Option 2: Claude Organization Skills (simplest for Claude users)

Claude supports org-wide skill deployment for teams on Claude for Work.

### Setup

1. An admin uploads the skill in the Claude admin console
2. It becomes available to all team members automatically
3. Updates are pushed centrally — team members don't need to re-upload

### How to update

The admin replaces the skill file. All team members get the update
automatically in their next conversation.

### Limitation

Only works for Claude. ChatGPT and Gemini users still need the universal
guide via GitHub or manual distribution.

---

## Option 3: Shared Drive (simplest, least robust)

Put the skill zip and universal guide on a shared Google Drive, OneDrive,
or SharePoint folder.

### Setup

1. Create a shared folder: "SI Installation Skill"
2. Upload: `simba-intelligence-setup.zip`, `simba-intelligence-llm-guide.md`,
   and the installer scripts
3. Share with the team

### How to update

Replace the files in the shared folder. Post in Slack/Teams that they've
been updated.

### Limitation

No version history (unless using Google Drive/SharePoint versioning). No
way to see what changed between versions. No automatic distribution — team
members must re-download manually.

---

## What to update and when

### After every product release

- Chart version references (check all reference files for hardcoded versions)
- Pod names if they change
- Service ports if they change
- New configuration options in values files
- LLM provider model updates (new models, deprecated models)

### After every deployment you do

- Any new gotcha you hit → add to `troubleshooting.md`
- Any environment-specific finding → add to the relevant deployment reference
- Any customer question the skill couldn't answer → add the knowledge

### After team meetings / calls

- If someone shares a finding (like the OKE image path issue from the
  D+A call), add it to the skill immediately
- The skill is a living document — it should be the team's collective
  deployment knowledge, not one person's notes

---

## Contribution workflow (GitHub)

Simple process that works for a small team:

1. Hit a problem or learn something during a deployment
2. Open the relevant reference file
3. Add the knowledge (be specific: what the symptom was, what the cause
   was, what the fix was)
4. Commit with a meaningful message: "Add OKE image path workaround"
5. Push to main
6. Post in team channel: "Updated the SI skill — added [thing]"

No approval process needed for small additions. For structural changes
(new reference files, rewriting sections), discuss in team channel first.

---

## Versioning

Use a simple version comment at the top of SKILL.md:

```
<!-- Skill version: 2026-03-12 -->
```

Update this date with every change. Team members can check if their local
copy is current by comparing dates.

For the GitHub approach, git commit history serves as the version log.

---

## Testing changes

After updating the skill:

1. Upload the updated skill to Claude
2. Open a new conversation
3. Ask: "I want to install Simba Intelligence on [the environment you updated]"
4. Verify Claude gives correct, up-to-date guidance
5. If something is wrong, fix the reference file and re-test

For the universal guide, test in ChatGPT:
1. Paste the updated guide
2. Ask the same question
3. Verify the answer reflects your changes
