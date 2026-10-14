# Relay

**Live demo:** https://relay-i07o.onrender.com/

Voice-based physician shift handover for a cardiology ward. Replaces the
paper handover list.

The outgoing doctor records one spoken handover in the browser, covering
many patients. Relay transcribes it, extracts an I-PASS card per patient,
and the doctor reviews and confirms the cards. The incoming doctor gets a
prioritised dashboard with countdowns and alerts, and every patient keeps a
permanent record.

> "Bed 7 needs metoprolol by 8:30" → Bed 7 tops the dashboard with a
> countdown; an alert fires at 8:15 if nobody has acknowledged it.

## How it works

1. **Record**: the doctor records in the browser (up to 2 minutes).
2. **Transcribe**: OpenAI `gpt-transcribe`.
3. **Check**: the recording is rejected if it is not a clinical handover.
4. **Extract**: OpenAI structured output turns the transcript into one card
   per patient. Due times and patient matching are done in code, not by the
   model.
5. **Review and confirm**: nothing reaches a patient's record until the
   doctor confirms. Confirm is refused while any patient is unresolved.
6. **Dashboard**: every patient on the ward, ordered by the severity the
   doctor stated, then the nearest due task. An alert fires 15 minutes
   before a task is due.
7. **Patient record**: confirmed handovers, tasks and alerts, plus the
   recording (kept 30 days).

## Structure

- `backend/`: FastAPI, SQLModel, PostgreSQL, Alembic
  - `app/api/routes/`: handovers, dashboard, tasks, flags, patients
  - `app/pipeline.py`: transcribe → check → extract → match
  - `app/extraction/`: prompt, schema, due-time and patient-matching code
  - `app/services/`: speech-to-text, storage, job runner, quotas
- `frontend/`: React, TanStack Router and Query, shadcn/ui; built into the
  backend and served by FastAPI
- `render.yaml`: deployment on Render

## Status

Work in progress. All patient data is synthetic.

**Next up:** pulling patient information from SNF packets through the
API of a companion service I built, to help nurses.

Built on the [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template)
(FastAPI, SQLModel, PostgreSQL, React). MIT licensed.
