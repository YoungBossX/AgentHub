import { type ComposerContextItem } from "@/components/message-composer"
import { type ArtifactPanelItem } from "@/components/preview-card"
import { type ArtifactContextIntent } from "@/components/task-card-list"
import {
  type ArtifactWorkbenchArtifact,
  type PreviewArtifact,
} from "@/lib/api"


export function preferredPreview(previews: PreviewArtifact[]) {
  return [...previews].reverse().find((preview) => preview.healthStatus === "healthy") ??
    previews[previews.length - 1] ??
    null
}


export function mergeArtifactPanelItems(
  evidenceItems: ArtifactPanelItem[],
  workbenchArtifacts: ArtifactWorkbenchArtifact[],
): ArtifactPanelItem[] {
  const coveredArtifactIds = new Set(
    evidenceItems.map((item) => item.artifact.artifactId),
  )
  const workbenchItems = workbenchArtifacts
    .filter((artifact) => !coveredArtifactIds.has(artifact.artifactId))
    .map(
      (artifact): ArtifactPanelItem => ({
        artifact,
        id: `workbench:${artifact.artifactId}`,
        kind: "workbench",
        taskRunId: artifact.taskRunId,
        taskTitle: artifact.title,
      }),
    )

  return [...evidenceItems, ...workbenchItems]
}

export function appendContextItem(
  items: ComposerContextItem[],
  nextItem: ComposerContextItem,
) {
  const withoutDuplicate = items.filter((item) => item.id !== nextItem.id)
  return [...withoutDuplicate, nextItem]
}

export function removeContextItem(
  items: ComposerContextItem[],
  itemId: string,
) {
  return items.filter((item) => item.id !== itemId)
}

export function moveContextItem(
  items: ComposerContextItem[],
  itemId: string,
  direction: "up" | "down",
) {
  const index = items.findIndex((item) => item.id === itemId)
  if (index < 0) {
    return items
  }
  const targetIndex = direction === "up" ? index - 1 : index + 1
  if (targetIndex < 0 || targetIndex >= items.length) {
    return items
  }
  const next = [...items]
  const [item] = next.splice(index, 1)
  next.splice(targetIndex, 0, item)
  return next
}

export function contextIntentDraft(intent: ArtifactContextIntent) {
  const drafts: Record<ArtifactContextIntent, string> = {
    ask: "请解释这个上下文的关键内容、当前状态和下一步建议。",
    revise: "请基于这个上下文继续修改，并说明需要执行的任务。",
    send_to_agent: "@orchestrator 请基于这个上下文安排后续处理。",
  }
  return drafts[intent]
}
