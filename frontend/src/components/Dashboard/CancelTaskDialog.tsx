import { useState } from "react"

import type { TaskPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import { Textarea } from "@/components/ui/textarea"

interface CancelTaskDialogProps {
  task: TaskPublic
  onCancel: (reason: string) => void
  loading: boolean
}

/** Dropping a clinical task needs a reason; it stays on the patient record. */
export function CancelTaskDialog({
  task,
  onCancel,
  loading,
}: CancelTaskDialogProps) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState("")
  const valid = reason.trim().length >= 3

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) setReason("")
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="ghost" className="text-muted-foreground">
          Cancel task
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Cancel this task?</DialogTitle>
          <DialogDescription>
            “{task.description}” will be closed without being done. The reason
            is kept on the patient's record.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2">
          <Label htmlFor={`cancel-reason-${task.id}`}>Reason</Label>
          <Textarea
            id={`cancel-reason-${task.id}`}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Already given on the previous shift"
            autoFocus
          />
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={loading}>
              Keep task
            </Button>
          </DialogClose>
          <LoadingButton
            variant="destructive"
            disabled={!valid}
            loading={loading}
            onClick={() => {
              onCancel(reason.trim())
              setOpen(false)
            }}
          >
            Cancel task
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
