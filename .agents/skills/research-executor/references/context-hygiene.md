# Executor context hygiene

One Campaign gets one fresh Goal Mode context. Read `CONTEXT_PACK.md` and only
explicit references. Keep terminal logs, model files, full advisor responses, and
other Campaign histories out of active context. Checkpoint confirmed findings,
tentative hypotheses, current state, references, and next three actions before
pause or compaction.
