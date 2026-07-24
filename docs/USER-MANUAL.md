# KnowledgeForge AI User Manual

**Version 0.10 · Local-first idea orchestration, research, strategy, and measurable execution**

KnowledgeForge turns unstructured recordings and documents into an organized private library, evolving workspaces, opportunities, and actionable plans. It is designed for people who want to capture ideas quickly and then steadily convert them into books, businesses, nonprofit initiatives, career growth, and completed work.

## 1. The operating model

KnowledgeForge works in five connected stages:

1. **Capture** — record on your phone, upload audio or documents, or record in the browser.
2. **Preserve** — keep the original file, local transcript, and metadata.
3. **Understand** — use the selected AI provider to extract meaning, themes, tasks, decisions, risks, and opportunities.
4. **Develop** — integrate useful material into a purpose-built Book, Venture, Impact, or Project Studio.
5. **Execute** — maintain a unified plan across Goals and every active workspace.

Whisper transcription happens locally. AI analysis uses the provider selected in the application. Private recordings, transcripts, databases, CVs, logs, and secrets are excluded from Git.

## 2. First-time setup

### Start KnowledgeForge

On Windows, use the **Start KnowledgeForge** desktop shortcut or run:

```powershell
.\scripts\Start-KnowledgeForge.ps1
```

Open `http://127.0.0.1:8765`. The top-right status should report that the worker is running and the selected AI is ready.

### Complete your private profile

Open **My Profile & Direction** and enter:

- your location;
- professional direction and summary;
- skills and certifications;
- interests and complete goals;
- preferred industries;
- subjects or opportunities to avoid.

Enter one list item per line. Commas inside an item are preserved. **Certifications** is the inventory of credentials already earned. Put credentials currently being pursued under **Goals**, for example:

```text
Earn CCSP (ISC2) - In Progress
Earn Terraform Associate by December 2026
```

Upload a PDF, DOCX, TXT, or Markdown CV. The interface shows the saved filename and provides download, replacement, and removal controls. The file is stored privately under `imports/profile`.

### Review AI profile suggestions

Select **Suggest updates from my library**. Suggestions do not alter your profile automatically. Expand each field, select only the fields you accept, and apply them. A selected field replaces that profile field so outdated fragments are not retained.

## 3. Capturing material

### Recommended phone workflow

Record using an iPhone recorder or Shortcut that saves into:

```text
iCloud Drive/KnowledgeForge/Inbox
```

Windows iCloud downloads the recording to the watched folder. KnowledgeForge then:

1. waits until the file is locally available and stable;
2. transcribes it with Whisper;
3. keeps a local recording copy;
4. saves the transcript and metadata;
5. adds it to the Source Library;
6. sends the transcript to the configured AI provider for analysis;
7. files and integrates it according to its content.

Keep the recording app open until it confirms that the file was saved. A phone shortcut can be interrupted if iOS locks before the recording action finishes.

### Direct upload

Open **Import and capture tools**:

- **Upload audio** accepts an existing recording.
- **Upload document or image** accepts supporting material.
- **Start recording** records from the current browser.
- **Scan sources** requests an immediate scan of the configured local Inbox. It does not scan your entire drive, existing library, cloud account, or the internet.

### State your destination in the recording

Automatic classification is useful but cannot always infer intent. Begin with a routing instruction when you know the destination:

```text
KnowledgeForge, file this under My Book. This is an idea for Chapter 4.
```

```text
File this under Cloud Security Engineer Career Pivot. This concerns my CCSP study plan.
```

This instruction becomes part of the transcript and gives the AI strong routing evidence.

## 4. Correcting or confirming where a source belongs

After a source appears:

1. Select it in **Source library**.
2. Review its title, category, tags, summary, and extracted analysis.
3. Choose the intended workspace from the workspace selector.
4. Select **Save**.
5. Select **Analyze and integrate**.

The source remains preserved even if you change its workspace. Integration updates the selected workspace document, relevant studio cards, and execution plan.

## 5. Working with purpose-built studios

### Book Studio

Use for books, essays, and long-form authorship. Its boards can cover:

- outline and manuscript;
- scenes, characters, locations, and themes;
- research and source evidence;
- continuity and contradictions;
- writing targets and revisions.

Use **Owner direction** for persistent rules such as voice, audience, canon, structure, exclusions, or chapter strategy. Use **Reorganization request** for a specific revision. Previous document versions remain preserved.

### Venture Studio

Use for business opportunities. It organizes:

- customer and problem evidence;
- alternatives and value proposition;
- solution, channels, revenue, and costs;
- assumptions, experiments, metrics, and traction.

Keep assumptions separate from validated facts. Use online opportunity validation before investing heavily.

### Impact Studio

Use for nonprofit and social-impact initiatives. It connects:

- need and beneficiaries;
- inputs, activities, outputs, and outcomes;
- intended impact and indicators;
- partners, assumptions, risks, safeguards, and sustainability.

### Project Studio

Use for technical, career, learning, or general projects. It maintains goals, evidence, milestones, risks, decisions, deliverables, and execution tasks.

### Add context, rename, or delete a workspace

Select **Manage workspace** to edit its name and strategic context. Context can include purpose, background, constraints, target users, desired outcomes, definitions, and success measures. It is supplied to AI whenever that workspace is developed.

Deleting a workspace removes its studio cards, living document, and execution plan. Its Source Library records are preserved and become unassigned so original evidence is not lost.

### Strategy, research, and improvement lab

- **Research for this workspace** performs an owner-approved public search and asks AI to distinguish evidence from interpretation, cite URLs, expose uncertainty, and produce measurable recommendations.
- Results do not alter the workspace automatically. Review them, then select **Add reviewed research to workspace**.
- **Create improved version** uses the complete workspace context to strengthen material you paste into the selection box.
- Review the result before selecting **Add improved version to workspace**.

Public search queries contain the workspace name, your research request, and configured location. They do not send your CV, private source library, or full workspace to the search engine. KnowledgeForge reads bounded text from eligible public result pages, rejects local/private-network targets, and gives those extracts plus workspace context to the selected AI provider.

## 6. Growth & Progress

**Growth & Progress** is the portfolio-level control center. It joins:

- profile goals;
- AI-created growth actions;
- unfinished tasks from every active workspace.

### Active commitments

Each goal has:

- a status;
- evidence-based progress from 0–100%;
- an optional target date;
- supporting notes and evidence.

Progress is calculated from completed linked actions and automatically tops out at 90%. This makes the bar useful evidence rather than a manually chosen number. KnowledgeForge flags commitments with no actions or no recent action activity as **stalled**. Select **Confirm complete** only when the outcome is genuinely finished; it moves to the collapsed **Completed commitments** history.

### Build my priority plan

Select **Build my priority plan** to ask the active AI to produce a focused plan for the selected horizon. The planner must:

- give every in-progress certification concrete next actions;
- include relevant active-project work;
- avoid duplicating existing workspace tasks;
- balance deadlines, career progress, and ongoing commitments;
- estimate the time required;
- order work by status, priority, and target date.

Mark an action complete from the unified queue. Workspace tasks completed here are also completed inside their original workspace.

Choose a two-, four-, or twelve-week horizon before building the plan. The default **Top focus** view shows only the ten highest-priority actions. Switch to **Growth only**, **Workspace only**, or **Full backlog** when reviewing a particular area. The total-work estimate covers the entire backlog, not only the ten visible actions.

### Recommended review rhythm

- **Daily:** complete the first meaningful action in the unified queue.
- **Weekly:** review stalled work and rebuild the priority plan.
- **After new material:** check whether the AI created or changed workspace tasks.
- **Monthly:** pause commitments that are no longer strategic and review completed evidence.

## 7. Opportunity discovery

The Opportunity Feed analyzes your profile together with relevant existing library material. New content adds evidence; it does not replace the older context.

1. Update the profile and CV.
2. Select **Discover opportunities**.
3. Save promising items or dismiss weak ones.
4. Select **Validate online** to perform an approval-based public-evidence check.
5. Select **Accept** to create the appropriate workspace and initial plan.

Online search receives only a minimal search phrase derived from the opportunity title and location—not your CV or private library.

## 8. Asking your private library

Use **Ask your project** to reason across the selected workspace’s complete private context: imported documents and images, transcribed audio, living document, studio cards, owner direction, and execution plan. Useful questions include:

- “Show every idea connected to Chapter 4.”
- “What contradictions exist in this character’s background?”
- “Which certification actions are overdue or blocked?”
- “What evidence supports this business opportunity?”
- “Assemble the notes about the opening scene.”
- “What work should I complete this week?”

Answers should cite the supporting source-note IDs and identify uncertainty.

## 9. AI providers and privacy

Choose a provider and model under **AI engine**. API keys entered through **Add or manage API keys** are protected with Windows Credential Manager and are not returned to the browser. Ollama can be used for local inference when installed and running.

Provider selection controls analysis, opportunity discovery, workspace development, chat, and planning. Whisper remains the local transcription engine.

Before using a cloud provider, assume that the transcript or document content required for that operation will be sent to that provider. Use a local model for material that must not leave the machine.

## 10. Finishing and exporting work

Workspace tasks must be completed or dismissed before **Complete workspace** becomes available. Completion requires confirmation and creates:

- a final snapshot;
- an outcome and deliverable review;
- lessons and unresolved items;
- demonstrated-skill suggestions;
- possible follow-up opportunities.

Profile suggestions from completion remain approval-based. A completed workspace can be reopened.

Use **Export document** to export the living workspace document. Original recordings and transcripts remain available independently.

## 11. Troubleshooting

### A phone recording appears online-only

In Windows File Explorer, request **Always keep on this device** for the iCloud KnowledgeForge folder. KnowledgeForge waits for the file, but iCloud must download it before Whisper can read it.

### The worker sees no new files

- Confirm the watched path is `B:\iCloud\iCloudDrive\KnowledgeForge\Inbox`.
- Confirm the file has a supported audio extension.
- Select **Scan sources**.
- Check the worker status and private logs.

### AI analysis is pending

- Confirm the provider shows **ready**.
- Verify its API key.
- Select **Process pending now**.
- Review `logs/knowledgeforge.log` for the private diagnostic.

### A source went to the wrong workspace

Open the source, select the correct workspace, save it, and select **Analyze and integrate**. For future recordings, speak the intended workspace name at the beginning.

### A plan seems unrealistic

Correct target dates or owner direction, complete or revise the relevant actions, and rebuild the plan. AI-generated plans are proposals; your explicit completion decisions remain authoritative.

## 12. Complete control reference

### My Profile & Direction

- **Save profile** stores the fields shown on screen. Goals become active commitments; Certifications remain a credential inventory.
- **Upload or replace CV** stores the private original under `imports/profile` and extracts text for profile-aware analysis.
- **Download copy** retrieves the stored private CV.
- **Remove CV** deletes the stored CV and extracted CV text.
- **Suggest updates from my library** proposes profile changes from the CV and library. Nothing changes until fields are selected and approved.
- **Apply selected fields** replaces only the selected profile fields.
- **Discard all** removes pending suggestions without changing the profile.

### Growth & Progress

- **Top focus / Growth only / Workspace only / Full backlog** changes which open actions are shown. It never deletes work.
- **Sync profile** re-reads Goals and active workspace tasks. A Goal removed from the profile is archived from focus.
- **Build my priority plan** asks the active AI to create an ordered plan for the selected horizon with estimates and dates.
- **Plan horizon** selects a two-, four-, or twelve-week planning window.
- **Circle beside an action** marks that action complete and recalculates evidence-based commitment progress.
- **Confirm complete** moves a genuinely finished commitment to **Completed commitments** at 100%.
- **Completed commitments** expands the historical list so finished work does not occupy active focus.

The unified queue is a cross-workspace focus view. **Workspace execution plan** is the detailed, editable plan for the currently selected workspace; the same workspace task may therefore be visible in both contexts, but it is one underlying task.

### Workspace studio

- **Workspace selector** changes the active workspace and the scope used by Ask your project.
- **New workspace** creates a Book, Venture, Impact, Project, or General studio.
- **Manage workspace** opens editable name and strategic-context fields.
- **Save workspace details** stores the renamed workspace and owner context.
- **Delete workspace** removes workspace structures while preserving Source Library records.
- **Build or refresh studio** asks AI to create purpose-specific boards and reference cards.
- **Add context/card** adds owner-authored information that AI refreshes preserve.
- **Edit** changes a studio card and makes it owner-authored.
- **Export document** downloads the current living document.
- **Save direction** stores persistent owner rules for tone, canon, audience, constraints, and structure.
- **Reorganize workspace** applies the typed revision request while preserving the prior document version.
- **Add task** creates an owner-authored workspace action.
- **Replan with AI** refreshes open AI actions but preserves manual and completed tasks.
- **Complete workspace** appears only after all tasks are done or dismissed; it creates a completion snapshot and review.
- **Reopen workspace** returns completed work to active status.
- **Research for this workspace** searches public evidence for the owner-entered question and produces URL-cited findings.
- **Add reviewed research to workspace** saves the reviewed report as a research card.
- **Create improved version** strengthens pasted material using complete workspace context.
- **Add improved version to workspace** saves the reviewed result as developed content.

### AI Opportunity Feed

- **Status selector** switches among New, Saved, Validated, Accepted, Completed, and Dismissed ideas.
- **Discover opportunities** analyzes the profile plus the existing private library and refreshes unaccepted suggestions.
- **Validate online** checks minimal public evidence using the title and location only.
- **Save** retains an idea for later; **Dismiss** removes it from focus.
- **Accept** creates the most suitable purpose-built workspace and initial plan.

### Import and capture tools

- **Start recording / Stop and save** captures microphone audio in the browser and submits it for transcription.
- **Upload audio** copies an audio file into KnowledgeForge and starts processing.
- **Upload document or image** extracts supported content, adds it to the library, and starts analysis.
- **Scan sources** checks only the configured local Inbox for newly arrived supported audio. The continuous worker performs the same check automatically; this button is an immediate manual retry.

### AI engine and keys

- **Provider** and **Model** select the AI used for analysis, planning, studios, opportunities, and chat.
- **Use this AI** saves that provider/model choice.
- **Process pending now** retries sources whose AI analysis is pending or failed. Whisper transcription is separate.
- **Save securely** stores a provider key in the deployment’s configured secret backend; on Windows this is DPAPI-protected Credential Manager.
- **Remove** deletes that stored provider key. Secret fields are cleared immediately and keys are never returned to the page.

### Source library and Ask your project

- **All workspaces**, **search**, and **All types** filter the source list without changing records.
- Selecting a source opens its transcript, metadata, extracted meaning, and managed original audio.
- **Tags** are searchable topic labels that help retrieve and group related sources.
- **Save edits only** stores corrected title, category, tags, summary, and workspace assignment without spending AI tokens.
- **Save, analyze & integrate** saves those edits first, then reruns AI analysis and updates the assigned workspace.
- **Delete source audio** permanently removes only KnowledgeForge’s managed audio copy. The transcript, summary, analysis, and workspace content remain.
- **Ask across the complete project** answers from every source type plus the workspace document, cards, direction, and plan.

## 13. Efficient operating checklist

1. Capture thoughts without trying to organize them on the phone.
2. State the destination when you know it.
3. Let automatic transcription and analysis finish.
4. Correct routing only when necessary.
5. Develop accepted ideas inside their specialized studio.
6. Work from **Growth & Progress**, not from memory.
7. Complete actions so evidence-based progress updates automatically.
8. Replan weekly and after major new inputs.
9. Complete or pause work deliberately.
10. Export durable outputs while retaining original sources.
