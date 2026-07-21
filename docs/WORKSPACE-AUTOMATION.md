# Workspace automation

Every incoming audio recording, document, or image follows the same workflow:

1. Preserve the original source privately.
2. Extract text or transcribe locally with Whisper.
3. Classify the thought as book, business, project, personal, or mixed.
4. Extract structured ideas, tasks, decisions, scenes, themes, questions, and risks.
5. File it into the most appropriate existing workspace.
6. Rebuild that workspace's working document using its saved author/owner instructions.
7. Save the previous working document in revision history before replacing it.

The automatic integration setting defaults to enabled. Provider failures never delete the original or transcript. Failed analysis can be retried from the source library.

The **Author direction** field is persistent context. The **Reorganization request** field is a one-time instruction applied to the next rewrite. This supports feedback such as reorganizing chapters, changing a business plan structure, reconciling contradictions, or preserving specific language.
