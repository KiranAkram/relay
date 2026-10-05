import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { AlertTriangle, Plus, Trash2, UserCheck } from "lucide-react"
import { useState } from "react"

import {
  type ActionItemDraft,
  type HandoverPatientPublic,
  type HandoverPatientUpdate,
  HandoversService,
  type IllnessSeverity,
  type TaskPriority,
} from "@/client"
import { CensusPicker } from "@/components/Patients/CensusPicker"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const SEVERITIES: { value: IllnessSeverity; label: string }[] = [
  { value: "unspecified", label: "Not stated" },
  { value: "stable", label: "Stable" },
  { value: "watcher", label: "Watcher" },
  { value: "unstable", label: "Unstable" },
]
const PRIORITIES: TaskPriority[] = ["routine", "urgent", "stat"]

type Contingency = { condition: string; action: string; verbatim?: string }

type Draft = {
  illness_severity: IllnessSeverity
  patient_summary: string
  situation_awareness: string
  contingencies: Contingency[]
  action_items: ActionItemDraft[]
}

const toDraft = (card: HandoverPatientPublic): Draft => ({
  illness_severity: card.illness_severity,
  patient_summary: card.patient_summary ?? "",
  situation_awareness: card.situation_awareness ?? "",
  contingencies: card.contingencies.map((c) => ({
    condition: String(c.condition ?? ""),
    action: String(c.action ?? ""),
    verbatim: c.verbatim ? String(c.verbatim) : undefined,
  })),
  action_items: card.action_items.map((a) => ({ ...a })),
})

/** Only the fields that differ from the server copy, for a precise audit trail. */
function changedFields(
  card: HandoverPatientPublic,
  draft: Draft,
): HandoverPatientUpdate {
  const base = toDraft(card)
  const update: HandoverPatientUpdate = {}
  if (draft.illness_severity !== base.illness_severity)
    update.illness_severity = draft.illness_severity
  if (draft.patient_summary !== base.patient_summary)
    update.patient_summary = draft.patient_summary || null
  if (draft.situation_awareness !== base.situation_awareness)
    update.situation_awareness = draft.situation_awareness || null
  if (
    JSON.stringify(draft.contingencies) !== JSON.stringify(base.contingencies)
  )
    update.contingencies = draft.contingencies
  if (JSON.stringify(draft.action_items) !== JSON.stringify(base.action_items))
    update.action_items = draft.action_items
  return update
}

/** ISO (UTC) → value for <input type="datetime-local"> in the browser's zone. */
function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return ""
  const d = new Date(iso)
  const offsetMs = d.getTimezoneOffset() * 60_000
  return new Date(d.getTime() - offsetMs).toISOString().slice(0, 16)
}

const fromLocalInput = (value: string): string | null =>
  value ? new Date(value).toISOString() : null

interface ReviewCardProps {
  handoverId: string
  card: HandoverPatientPublic
  readOnly: boolean
}

export function ReviewCard({ handoverId, card, readOnly }: ReviewCardProps) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [draft, setDraft] = useState<Draft>(() => toDraft(card))
  const update = changedFields(card, draft)
  const dirty = Object.keys(update).length > 0
  const path = { id: handoverId, card_id: card.id }
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["handovers", handoverId] })

  const save = useMutation({
    mutationFn: (body: HandoverPatientUpdate) =>
      HandoversService.updateCard({ path, body }),
    onSuccess: () => showSuccessToast("Card saved"),
    onError: handleError.bind(showErrorToast),
    onSettled: refresh,
  })
  const remove = useMutation({
    mutationFn: () => HandoversService.deleteCard({ path }),
    onSuccess: () => showSuccessToast("Card removed"),
    onError: handleError.bind(showErrorToast),
    onSettled: refresh,
  })

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }))
  const unresolved =
    card.match_status === "ambiguous" || card.match_status === "unmatched"
  const matched = card.match_candidates.find(
    (c) => c.patient_id === card.patient_id,
  )

  return (
    <Card className={unresolved ? "border-amber-500/70" : undefined}>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <span>“{card.mention_verbatim}”</span>
          {card.patient_id ? (
            <Badge variant="outline" asChild>
              <Link
                to="/patients/$patientId"
                params={{ patientId: card.patient_id }}
              >
                <UserCheck />
                {matched
                  ? `${matched.given_name} ${matched.family_name} · Bed ${matched.bed ?? "?"} · MRN ${matched.mrn}`
                  : "Patient set by you · open record"}
              </Link>
            </Badge>
          ) : (
            <Badge className="border-transparent bg-amber-500 text-black">
              <AlertTriangle />
              {card.match_status === "ambiguous"
                ? "Which patient?"
                : "No census match"}
            </Badge>
          )}
          {card.edited_by_doctor && <Badge variant="secondary">Edited</Badge>}
        </CardTitle>
        {card.transcript_excerpt && (
          <CardDescription className="italic">
            {card.transcript_excerpt}
          </CardDescription>
        )}
      </CardHeader>

      <CardContent className="flex flex-col gap-5">
        {unresolved && !readOnly && (
          <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
            {card.match_status === "ambiguous" ? (
              <div className="flex flex-col gap-2">
                <p>Several patients fit this mention. Pick one:</p>
                <div className="flex flex-wrap gap-2">
                  {card.match_candidates.map((c) => (
                    <Button
                      key={c.patient_id}
                      size="sm"
                      variant="outline"
                      disabled={save.isPending}
                      onClick={() => save.mutate({ patient_id: c.patient_id })}
                    >
                      {c.given_name} {c.family_name} · Bed {c.bed ?? "?"} · MRN{" "}
                      {c.mrn}
                      <span className="text-muted-foreground">
                        ({c.reason})
                      </span>
                    </Button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                <p>
                  Nobody on the census matched this mention. Choose the patient
                  it belongs to, or remove the card.
                </p>
                <CensusPicker
                  disabled={save.isPending}
                  onPick={(patientId) => save.mutate({ patient_id: patientId })}
                />
              </div>
            )}
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-[180px_1fr]">
          <div className="flex flex-col gap-2">
            <Label>Illness severity</Label>
            <Select
              value={draft.illness_severity}
              onValueChange={(v) =>
                set("illness_severity", v as IllnessSeverity)
              }
              disabled={readOnly}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SEVERITIES.map((s) => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {card.severity_evidence && (
              <p className="text-xs text-muted-foreground italic">
                “{card.severity_evidence}”
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor={`summary-${card.id}`}>Patient summary</Label>
            <Textarea
              id={`summary-${card.id}`}
              value={draft.patient_summary}
              onChange={(e) => set("patient_summary", e.target.value)}
              readOnly={readOnly}
            />
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor={`situation-${card.id}`}>Situation awareness</Label>
          <Textarea
            id={`situation-${card.id}`}
            value={draft.situation_awareness}
            onChange={(e) => set("situation_awareness", e.target.value)}
            readOnly={readOnly}
            placeholder="What to watch for"
          />
        </div>

        <fieldset className="flex flex-col gap-2">
          <Label>Contingencies (if … then …)</Label>
          {draft.contingencies.map((c, i) => (
            <div key={i} className="flex gap-2">
              <Input
                placeholder="If"
                value={c.condition}
                readOnly={readOnly}
                onChange={(e) =>
                  set(
                    "contingencies",
                    draft.contingencies.map((x, j) =>
                      j === i ? { ...x, condition: e.target.value } : x,
                    ),
                  )
                }
              />
              <Input
                placeholder="Then"
                value={c.action}
                readOnly={readOnly}
                onChange={(e) =>
                  set(
                    "contingencies",
                    draft.contingencies.map((x, j) =>
                      j === i ? { ...x, action: e.target.value } : x,
                    ),
                  )
                }
              />
              {!readOnly && (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Remove contingency"
                  onClick={() =>
                    set(
                      "contingencies",
                      draft.contingencies.filter((_, j) => j !== i),
                    )
                  }
                >
                  <Trash2 />
                </Button>
              )}
            </div>
          ))}
          {!readOnly && (
            <Button
              variant="outline"
              size="sm"
              className="self-start"
              onClick={() =>
                set("contingencies", [
                  ...draft.contingencies,
                  { condition: "", action: "" },
                ])
              }
            >
              <Plus />
              Add contingency
            </Button>
          )}
        </fieldset>

        <fieldset className="flex flex-col gap-2">
          <Label>Action items</Label>
          {draft.action_items.map((a, i) => {
            const edit = (patch: Partial<ActionItemDraft>) =>
              set(
                "action_items",
                draft.action_items.map((x, j) =>
                  j === i ? { ...x, ...patch } : x,
                ),
              )
            return (
              <div
                key={i}
                className="grid gap-2 rounded-md border p-3 md:grid-cols-[1fr_120px_200px_auto]"
              >
                <Input
                  placeholder="What needs doing"
                  value={a.description}
                  readOnly={readOnly}
                  onChange={(e) => edit({ description: e.target.value })}
                />
                <Select
                  value={a.priority ?? "routine"}
                  onValueChange={(v) => edit({ priority: v as TaskPriority })}
                  disabled={readOnly}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PRIORITIES.map((p) => (
                      <SelectItem key={p} value={p}>
                        {p}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  type="datetime-local"
                  value={toLocalInput(a.due_at)}
                  readOnly={readOnly}
                  onChange={(e) => {
                    const due_at = fromLocalInput(e.target.value)
                    edit({
                      due_at,
                      due_kind: due_at
                        ? (a.due_kind ?? "clock")
                        : "unspecified",
                      needs_review: false,
                      review_reason: null,
                    })
                  }}
                />
                {!readOnly && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Remove action item"
                    onClick={() =>
                      set(
                        "action_items",
                        draft.action_items.filter((_, j) => j !== i),
                      )
                    }
                  >
                    <Trash2 />
                  </Button>
                )}
                <div className="text-xs text-muted-foreground md:col-span-4">
                  {a.due_phrase && <span>Spoken: “{a.due_phrase}”. </span>}
                  {a.needs_review && (
                    <span className="text-amber-600 dark:text-amber-400">
                      Check this time: {a.review_reason}
                    </span>
                  )}
                </div>
              </div>
            )
          })}
          {!readOnly && (
            <Button
              variant="outline"
              size="sm"
              className="self-start"
              onClick={() =>
                set("action_items", [
                  ...draft.action_items,
                  {
                    description: "",
                    priority: "routine",
                    due_kind: "unspecified",
                    due_at: null,
                  },
                ])
              }
            >
              <Plus />
              Add action item
            </Button>
          )}
        </fieldset>

        {card.pending_results.length > 0 && (
          <div className="flex flex-col gap-1 text-sm">
            <Label>Pending results</Label>
            <ul className="list-disc pl-5 text-muted-foreground">
              {card.pending_results.map((p, i) => (
                <li key={i}>
                  {String(p.description ?? "")}
                  {p.expected_by ? ` — ${String(p.expected_by)}` : ""}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>

      {!readOnly && (
        <CardFooter className="justify-between">
          <Button
            variant="ghost"
            className="text-destructive"
            disabled={remove.isPending}
            onClick={() => {
              if (window.confirm("Remove this card from the handover?"))
                remove.mutate()
            }}
          >
            <Trash2 />
            Remove card
          </Button>
          <LoadingButton
            disabled={!dirty}
            loading={save.isPending}
            onClick={() => save.mutate(update)}
          >
            Save changes
          </LoadingButton>
        </CardFooter>
      )}
    </Card>
  )
}
