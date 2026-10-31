# README screenshots

These assets support the [repository README](../README.md) and are stored in the repository without external image hosting.

## Data and privacy

Captured on 31 October 2026 from the current local Recall application. Every project, person, conversation, date and amount shown is fictional and was written in English for these screenshots. No personal documents, filenames or user question history are included.

The captures use a fresh browser origin and a separate **Northstar Studio** collection. The application imports real fixture files through its normal UI and generates the answer with the local model. These are browser screenshots, not edited UI mockups or prepared answers.

Fixtures:

- [Northstar planning.jsonl](fixtures/Northstar%20planning.jsonl): three dated conversations about the Cedar launch, its release checklist and customer feedback.
- [Release notes.md](fixtures/Release%20notes.md): one undated Markdown note.

## Reproduce

1. Start Recall using the [local setup instructions](../app/local/README.md).
2. Use an empty browser profile or separate local origin. Do not clear an existing user's stored data.
3. Create **Northstar Studio** and import both fixture files.
4. Capture the views below. Inspect the entire frame, including the sidebar and recent questions, before saving.
5. Save direct browser captures as JPEG at the browser's normal viewport. These captures are 1280 pixels wide.

| Image | View | Action |
| --- | --- | --- |
| [recall-local-home.jpg](images/recall-local-home.jpg) | Home | Open **Ask Recall** after importing the fixtures |
| [recall-local-sources.jpg](images/recall-local-sources.jpg) | Sources | Open **Sources**, with all four sources visible |
| [recall-local-answer.jpg](images/recall-local-answer.jpg) | Answer | Ask **How much funding did we approve for the launch?** |
| [recall-local-source.jpg](images/recall-local-source.jpg) | Original passage | Open the launch decision citation from the answer |

The expected funding amount is **12800 EUR**. The exact generated wording may vary. Do not substitute real customer records or private files when refreshing these images.

The root README uses the four `recall-local-*.jpg` screenshots listed above.
