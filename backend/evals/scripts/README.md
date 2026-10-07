# Handover scripts

Plain-text handovers, written as a doctor would speak them, for recording in
the browser (or text-to-speech) to test the full pipeline against the seed
census in `app/seed/patients.json`. Each is about 1–2 minutes read aloud.

| Script | Patients (bed) | What it exercises |
|---|---|---|
| `01_morning_handover.txt` | Khan (1), Ahmed (2), Baig (7), Haider (13, bed only), Lodhi (17) | clock times ("half eight", "at ten"), relative times ("in six hours", "in an hour"), two potassium contingencies ("if it's below three point five"), stated severities, allergy mention |
| `02_evening_handover.txt` | Abbas (15, DNR), Noor (22), Qazi (11, mis-transcribable), Raza (3), Iqbal (9), Akhtar (14, "was in nineteen, moved to fourteen") | unstable patients, "if systolic drops below…" contingency, bed move, relative times, "everyone else is stable" |
| `03_night_to_day_handover.txt` | Mirza (19), T. Sheikh (5), Y. Sheikh (12, "the other Sheikh"), I. Ahmed (21, "not Mrs Ahmed in bed two"), Z. Khan (8, "not the Khan in bed one") | same-surname disambiguation by bed, discharge, clock times, a closing remark about bed 17 that is not a new card |

Expected: one card per patient named above, in order of first mention; no
card for patients only mentioned in passing ("everyone else is stable"). The
closing line of script 3 about bed 17 is a result, not a task.
