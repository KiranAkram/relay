# Relay

Voice-based physician shift handover for a cardiology ward. The outgoing
doctor records one spoken handover; Relay transcribes it, extracts an I-PASS
card per patient, lets the doctor review and confirm, and gives the incoming
doctor a prioritised dashboard with countdowns and alerts.

> "Bed 7 needs metoprolol by 8:30" → Bed 7 tops the dashboard with a
> countdown; an alert fires at 8:15 if nobody has acknowledged it.

**Work in progress.** Data model, transcript extraction and speech-to-text are
done; pipeline, API and dashboard are next. All patient data is synthetic.

Built on the [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template)
(FastAPI, SQLModel, PostgreSQL, React). MIT licensed.
