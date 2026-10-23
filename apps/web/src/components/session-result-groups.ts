import type { SessionTask, TaskRun } from "@/lib/api"
import type { ArtifactPanelItem } from "./preview-card"

export type ResultBatch = { runId: string; run: TaskRun | null; ordinal: number | null; items: ArtifactPanelItem[] }
export type ResultGroup = { id: string; title: string; associated: boolean; current: ResultBatch | null; history: ResultBatch[] }

export function groupSessionResults(tasks: SessionTask[], artifacts: ArtifactPanelItem[]): ResultGroup[] {
  const owners = new Map<string, string>()
  const groups = new Map<string, ResultGroup>()
  const batches = new Map<string, ResultBatch>()
  for (const task of tasks) {
    const runs = task.taskRuns.map((run, index) => {
      owners.set(run.id, task.id)
      const batch = { runId: run.id, run, ordinal: index + 1, items: [] as ArtifactPanelItem[] }
      batches.set(run.id, batch)
      return batch
    })
    groups.set(task.id, { id: task.id, title: task.title, associated: true, current: runs.at(-1) ?? null, history: runs.slice(0, -1).reverse() })
  }
  for (const artifact of artifacts) {
    if (!owners.has(artifact.taskRunId)) {
      const key = `unassociated:${artifact.taskRunId}`
      if (!groups.has(key)) {
        const batch = { runId: artifact.taskRunId, run: null, ordinal: null, items: [] as ArtifactPanelItem[] }
        groups.set(key, { id: key, title: artifact.taskTitle, associated: false, current: null, history: [batch] })
        batches.set(artifact.taskRunId, batch)
      }
    }
    batches.get(artifact.taskRunId)?.items.push(artifact)
  }
  return [...groups.values()].filter(group => group.current || group.history.some(batch => batch.items.length))
}
