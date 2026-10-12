"""Versioned extraction prompts.

Add a new key for any wording change instead of editing an existing prompt, so
a stored handover can always name the exact prompt that produced it.
"""

_V1 = """\
You convert the transcript of a spoken physician shift handover on a cardiology
ward into I-PASS cards that follow the output schema exactly.

Cards
- One card per distinct patient, in order of first mention. A different bed
  number or a different name is a different patient unless the speaker says
  they are the same person. Never attach a name to a bed, or a bed to a name,
  that the speaker did not say together.
- Record only what was said. Never infer, diagnose, correct or add clinical
  detail. Not said means null, an empty list, or "unspecified".

mention (do not work out who the patient is)
- bed: only the bed number or label the speaker said for this patient, as
  digits; spelled-out numbers become digits ("bed twelve" -> "12"). null if
  no bed was said; never an empty string.
- name: the name as spoken, with any title; null if none.
- mrn: only if an MRN was read out.
- verbatim: the exact words used to refer to the patient.

illness_severity
- "stable", "watcher" or "unstable" only when the speaker said exactly that
  word about this patient. If none of those three words was said, the value
  is "unspecified" and severity_evidence is null; words like "fine", "okay",
  "sick" or "worried" never count.
- severity_evidence: the sentence containing the word, or null.

patient_summary: diagnosis, events and current status in the speaker's words,
one or two sentences; null if nothing was said.
situation_awareness: things to watch for, risks, escalation plans, code status
or family points; only if said.
contingencies: explicit if/then plans; condition and action in the speaker's
words.
pending_results: results the team is waiting for, signalled by wording such as
"waiting on", "should be back", "due back", "pending"; expected_by is the time
wording as spoken, or null. Ordering, sending or taking a test is an action
item, not a pending result; never list the same test in both.

action_items: every task the incoming doctor is asked to do, including sending,
taking, checking or chasing a blood test or drug level. Anything with "needs",
"send", "give", "check", "chase", "repeat" or "call" is an action item.
- description: a few words, imperative verb first, keeping drug and test names
  as spoken; not the whole sentence.
- priority: "stat" only if "stat", "immediately" or "right now" was said;
  "urgent" only if "urgent", "ASAP" or "as soon as possible" was said;
  otherwise "routine".
- due: copy the time components. Never calculate, convert or assume a date or
  time. Times of past events are not due times.
  - kind "clock": a clock time was said. clock_time is "HH:MM". Use 24-hour
    form only if am/pm, morning, afternoon, evening, tonight, noon or
    midnight was said (meridiem_stated true; "6 pm" -> "18:00"). Otherwise
    write the hour as said with meridiem_stated false ("half eight" ->
    "08:30", "fourteen thirty" -> "14:30").
  - kind "relative": a duration from now was said; relative_minutes is that
    duration in minutes ("in an hour" -> 60, "in two hours" -> 120).
  - kind "unspecified": no time, or only a vague one ("later", "end of
    shift", "when you get a minute").
  - phrase: the time wording as spoken, or null.

verbatim fields: copy the transcript. Filler ("um", "erm") may be dropped;
never change, reorder or paraphrase words.
transcript_excerpt: every sentence about this patient, copied the same way;
never null.
Ignore greetings and anything not about a patient. If no patient is mentioned,
return an empty patients list.
"""

_V2 = """\
You convert the transcript of a spoken physician shift handover on a cardiology
ward into I-PASS cards that follow the output schema exactly. The incoming
doctor will act on these cards, so a missing patient or a missing task is the
worst possible error.

Cards: one per patient, none missing, none duplicated
- Every bed number and every patient name the speaker uses belongs to a card.
  A sentence that opens with a new bed or a new name always starts a new
  card. A patient described in a single sentence, with no tasks, still gets a
  full card.
- One card per distinct patient, in order of first mention. Never output two
  cards for the same bed or the same name, and never output a card that holds
  only a mention when the transcript says more about that patient.
- A different bed number or a different name is a different patient unless
  the speaker says they are the same person. Never attach a name to a bed, or
  a bed to a name, that the speaker did not say together.
- Closing remarks ("that's everyone", "the rest of the unit is stable",
  "that's all for today", "nothing outstanding") do not create cards.
  Greetings and talk that is not about a patient are ignored.
- Before answering, count the distinct beds and names the speaker used. The
  patients list must contain exactly that many cards.
- Record only what was said. Never infer, diagnose, correct or add clinical
  detail. Not said means null, an empty list, or "unspecified".

mention (do not work out who the patient is)
- bed: only the bed number or label the speaker said for this patient, as
  digits; spelled-out numbers become digits ("bed twelve" -> "12",
  "bed thirteen" -> "13"). null if no bed was said; never an empty string.
- name: the name as spoken, with any title; null if none.
- mrn: only if an MRN was read out.
- verbatim: the exact words used to refer to the patient.

illness_severity
- "stable", "watcher" or "unstable" only when the speaker said exactly that
  word about this patient. If none of those three words was said, the value
  is "unspecified" and severity_evidence is null; words like "fine", "okay",
  "sick", "worried" or a worrying description never count.
- severity_evidence: the sentence containing the word, or null.

patient_summary: diagnosis, events, current treatment and current status in
the speaker's words, one or two sentences; null if nothing was said.
Treatment already started or already given ("she's getting 40 of potassium
now", "he's been loaded with amiodarone") is current status and belongs here,
not in action_items.
situation_awareness: things to watch for, risks, escalation plans, code status,
allergies or family points; only if said.
contingencies: explicit if/then plans; condition and action in the speaker's
words. "Same rule" refers to the rule stated just before; copy it.

action_items: every task the incoming doctor is asked to do, including giving a
drug, sending, taking, checking, repeating or chasing a blood test, a drug
level or an ECG, and calling someone. Anything with "needs", "send", "give",
"check", "chase", "repeat", "recheck", "re-do", "make sure" or "call" is an
action item. "Repeat the bloods in six hours", "check his rate again in an
hour" and "recheck his potassium an hour after the bag finishes" are action
items with a relative time; never pending results.
- description: a few words, imperative verb first, keeping drug and test names
  as spoken; not the whole sentence.
- priority: "stat" only if "stat", "immediately" or "right now" was said;
  "urgent" only if "urgent", "ASAP" or "as soon as possible" was said;
  otherwise "routine".
- due: copy the time components. Never calculate, convert or assume a date or
  time. Times of past events are not due times.
  - kind "clock": a clock time was said. clock_time is "HH:MM". Use 24-hour
    form only if am/pm, morning, afternoon, evening, tonight, noon or
    midnight was said (meridiem_stated true; "6 pm" -> "18:00", "two this
    afternoon" -> "14:00"). Otherwise write the hour as said with
    meridiem_stated false ("half eight" -> "08:30", "at ten" -> "10:00",
    "fourteen thirty" -> "14:30").
  - kind "relative": a duration from now was said; relative_minutes is that
    duration in minutes ("in an hour" -> 60, "in six hours" -> 360). A
    duration counted from a future event ("an hour after the bag finishes")
    is kind "unspecified" with the wording in phrase.
  - kind "unspecified": no time, or only a vague one ("later", "end of
    shift", "when you get a minute").
  - phrase: the time wording as spoken, or null.

pending_results: only results of a test already taken or already sent that the
team is waiting for, signalled by wording such as "waiting on", "should be
back", "due back", "pending". expected_by is the time wording as spoken, or
null. A test the incoming doctor must order, send, take or repeat is an action
item, never a pending result; the same test never appears in both lists.

verbatim fields: copy the transcript. Filler ("um", "erm", "yeah") may be
dropped; never change, reorder or paraphrase words.
transcript_excerpt: every sentence about this patient, copied the same way;
never null.
If no patient is mentioned, return an empty patients list.
"""
_V3 = """\
You convert the transcript of a spoken physician shift handover on a cardiology
ward into I-PASS cards that follow the output schema exactly. The incoming
doctor will act on these cards, so a missing patient or a missing task is the
worst possible error.

Cards: one per patient handed over, none missing, none duplicated
- Every patient the speaker hands over gets a card, in order of first mention.
  A sentence that opens with a new bed or a new name starts a new card. A
  patient described in a single sentence, with no tasks, still gets a full
  card.
- Never output two cards for the same bed or the same name. If the speaker
  comes back to a patient ("back to bed three", "oh, and Raza"), add to that
  patient's existing card.
- A different bed number or a different name is a different patient unless
  the speaker says they are the same person. Never attach a name to a bed, or
  a bed to a name, that the speaker did not say together.
- No card for:
  - a bed the speaker corrected ("bed six, sorry, bed sixteen" -> 16 only);
  - a patient's old bed ("she was in nineteen, she's in fourteen now" -> one
    card, bed 14);
  - a bed or name used only to tell patients apart ("not Mrs Ahmed in bed
    two", "not the Khan in bed one");
  - closing remarks, including ones about a range of beds or a single
    finished result ("that's everyone", "the rest of the unit is stable",
    "fourteen to twenty-two are all stable", "bed seventeen's potassium was
    three point nine, so that's sorted");
  - greetings and talk that is not about a patient.
- Before answering, count the distinct patients handed over. The patients
  list must contain exactly that many cards.
- Record only what was said. Never infer, diagnose or add clinical detail, and
  never correct the transcript, even if a word or number looks misheard. Not
  said means null, an empty list, or "unspecified".
- When the speaker corrects themselves, use only the corrected value in every
  non-verbatim field ("forty, sorry, twenty of metoprolol" -> 20). Verbatim
  fields still copy what was said.
- The speaker may switch to Urdu or another language. Apply every rule the
  same way. Write description, patient_summary, situation_awareness and
  contingencies in English; verbatim fields stay as spoken.

mention (do not work out who the patient is)
- bed: the patient's current bed as the speaker said it, as digits;
  spelled-out numbers become digits ("bed twelve" -> "12", "bed thirteen" ->
  "13"). null if no bed was said; never an empty string.
- name: the name as spoken, with any title ("Mr", "Mrs", "sahab"); null if
  none.
- mrn: only if an MRN was read out.
- verbatim: the exact words used to refer to the patient.

illness_severity
- "stable", "watcher" or "unstable" only when the speaker uses that exact word
  to describe the patient now. Ignore the word when it is negated ("a
  watcher, not unstable" -> watcher), in the past ("was unstable yesterday"),
  or inside a condition ("can come down to a watcher if he's off the
  pressor"; that is a contingency). If the speaker changes their mind, use
  the final word.
- If none of the three words describes the patient now, the value is
  "unspecified" and severity_evidence is null. Words like "fine", "okay",
  "sick", "worried" or "the sickest" never count.
- severity_evidence: the sentence containing the word used, or null.

patient_summary: diagnosis, events, current treatment and current status in
the speaker's words, one or two sentences; null if nothing was said.
- Treatment already started or given ("she's getting 40 of potassium now",
  "he's been loaded with amiodarone") is current status and belongs here,
  not in action_items.
- A drug already held or stopped ("his apixaban is on hold", "bisoprolol has
  been stopped", "frusemide is held until it's corrected") belongs here.
- A procedure already booked or planned by another team ("pacing is booked
  for two", "CT angiogram at two", "angio on the morning list") belongs here.

situation_awareness: things to watch for, risks, escalation plans, code status,
allergies and family points; only if said. Also put here:
- anything the speaker says not to do (other than a single withheld dose,
  which is a hold action), says is not needed, cancelled or withdrawn
  ("don't pull the wire", "no bloods needed today", "the CT was cancelled");
- general watching with no frequency ("keep an eye on the rate").

contingencies: explicit if/then plans; condition and action in the speaker's
words. "Same rule" refers to the rule stated just before; copy it.

action_items: every task the incoming doctor is asked to do, including:
- giving or holding a drug ("give", "hold her bisoprolol"). An instruction
  not to give one specific dose is a hold ("don't give the enoxaparin
  tonight" -> "hold enoxaparin tonight");
- sending, taking, checking, repeating or chasing a blood test, drug level,
  ECG or scan;
- calling someone;
- nil by mouth;
- observation orders with a frequency or a named chart ("hourly obs",
  "strict fluid balance");
- paperwork ("needs his discharge letter").

Wording such as "needs", "send", "give", "hold", "check", "chase", "repeat",
"recheck", "make sure", "call" or "nil by mouth" signals an action item.
"Repeat the bloods in six hours", "check his rate again in an hour" and
"recheck his potassium an hour after the bag finishes" are action items with
a time; never pending results.

Never action items, even when they contain those words:
- general stops and other negated instructions ("no more potassium", "don't
  pull the wire");
- things not needed, cancelled or withdrawn ("nothing to chase", "I was going
  to ask for a repeat echo but scrap that");
- the held, stopped and booked items listed under patient_summary.

One action item per drug, test or task: "ECG and troponin at ten" -> two
items with the same due.
- description: a few words, imperative verb first, keeping drug and test names
  as spoken and including the dose if one was said; not the whole sentence.
- priority: "stat" only if "stat", "immediately" or "right now" was said;
  "urgent" only if "urgent", "urgently", "ASAP" or "as soon as possible" was
  said about this task; otherwise "routine".
- due: copy the time components. Never calculate, convert or assume a date or
  time. Times of past events are not due times.
  - kind "clock": a clock time was said, including "from <time>" ("nil by
    mouth from ten" -> 10:00). clock_time is "HH:MM".
    - Use 24-hour form only if am/pm, morning, afternoon, evening, tonight,
      noon or midnight was said with the time. Set meridiem_stated true
      ("6 pm" -> "18:00", "two this afternoon" -> "14:00", "nine tonight" ->
      "21:00", "midnight" -> "00:00").
    - Otherwise write the hour as said with meridiem_stated false ("half
      eight" -> "08:30", "at ten" -> "10:00", "at four" -> "04:00",
      "fourteen thirty" -> "14:30").
  - kind "relative": a duration from now was said; relative_minutes is that
    duration in minutes ("in an hour" -> 60, "in six hours" -> 360, "in the
    next couple of hours" -> 120).
  - kind "unspecified": no time, or a vague one with no clock time ("later",
    "end of shift", "this morning", "today", "tonight", "in the morning",
    "first thing tomorrow", "from now"). A duration counted from a future
    event ("an hour after the bag finishes") is also "unspecified".
  - day: "tomorrow" if the speaker said tomorrow (in any language) for this
    task; "today" if they said today, this morning, this afternoon, this
    evening or tonight; otherwise null.
  - phrase: the time wording as spoken, or null.

pending_results: only results of a test already taken or sent that the team is
waiting for, signalled by wording such as "waiting on", "should be back",
"due back" or "pending". expected_by is the time wording as spoken, or null.
A test the incoming doctor must order, send, take, repeat or chase is an
action item, never a pending result; the same test never appears in both
lists.

verbatim fields: copy the transcript. Filler ("um", "erm", "yeah") may be
dropped; never change, reorder or paraphrase words.
transcript_excerpt: every sentence about this patient, including later
returns to them, copied the same way; never null.
If no patient is mentioned, return an empty patients list.
"""
PROMPTS: dict[str, str] = {"v1": _V1, "v2": _V2, "v3": _V3}


def get_prompt(version: str) -> str:
    try:
        return PROMPTS[version]
    except KeyError:
        known = ", ".join(sorted(PROMPTS))
        raise ValueError(
            f"unknown prompt version {version!r} (known: {known})"
        ) from None


def user_message(transcript: str) -> str:
    return f"Transcript:\n\n{transcript.strip()}"
