"use client"

import { type Dispatch, type SetStateAction } from "react"

import { preferredPreview } from "@/components/workspace-shell-state"
import {
  approveTaskRun,
  createPreviewDeployment,
  createTaskRun,
  createTaskRunReview,
  decideTaskPlan,
  denyTaskRun,
  forceCodexFailure,
  interruptTaskRun,
  listTaskRunPreviews,
  retryTaskRun,
  retryTaskRunWithFallback,
  saveArtifactWorkbenchEdit,
  startTaskRunPreview,
  stopPreview,
  type PreviewArtifact,
} from "@/lib/api"

type TaskArtifactActionOptions = {
  backendUrl: string
  refreshArtifacts: () => void
  refreshSelectedTasks: () => Promise<void>
  runClientAction: (
    action: () => Promise<void>,
    failureMessage: string,
  ) => void
  selectedPreview: PreviewArtifact | null
  setPreviewFrameKey: Dispatch<SetStateAction<number>>
  setSelectedArtifactId: Dispatch<SetStateAction<string | null>>
  setSyncError: Dispatch<SetStateAction<string | null>>
}

export function useTaskArtifactActions({
  backendUrl,
  refreshArtifacts,
  refreshSelectedTasks,
  runClientAction,
  selectedPreview,
  setPreviewFrameKey,
  setSelectedArtifactId,
  setSyncError,
}: TaskArtifactActionOptions) {
  function handleCreateTaskRun(taskId: string) {
    runClientAction(async () => {
      await createTaskRun(backendUrl, taskId)
      await refreshSelectedTasks()
    }, "无法启动任务运行")
  }

  function handleForceCodexFailure(taskId: string) {
    runClientAction(async () => {
      await forceCodexFailure(backendUrl, taskId)
      await refreshSelectedTasks()
      refreshArtifacts()
    }, "无法模拟 Codex 失败")
  }

  function handleInterruptTaskRun(taskRunId: string) {
    runClientAction(async () => {
      await interruptTaskRun(backendUrl, taskRunId)
      await refreshSelectedTasks()
    }, "无法中断任务运行")
  }

  function handleRetryTaskRun(taskRunId: string) {
    runClientAction(async () => {
      await retryTaskRun(backendUrl, taskRunId)
      await refreshSelectedTasks()
    }, "无法重试任务运行")
  }

  function handleRetryTaskRunWithFallback(taskRunId: string) {
    runClientAction(async () => {
      await retryTaskRunWithFallback(backendUrl, taskRunId)
      await refreshSelectedTasks()
    }, "无法使用 ScriptedMockAdapter 兜底重试")
  }

  function handleApproveTaskRun(taskRunId: string) {
    runClientAction(async () => {
      await approveTaskRun(backendUrl, taskRunId)
      await refreshSelectedTasks()
    }, "无法批准任务运行")
  }

  function handleApprovePlan(taskId: string) {
    runClientAction(async () => {
      await decideTaskPlan(
        backendUrl,
        taskId,
        "approve",
        "用户已在 AgentHub 界面批准 PMO 计划。",
      )
      await refreshSelectedTasks()
    }, "无法批准 PMO 计划")
  }

  function handleRejectPlan(taskId: string) {
    runClientAction(async () => {
      await decideTaskPlan(
        backendUrl,
        taskId,
        "reject",
        "用户已在 AgentHub 界面拒绝 PMO 计划。",
      )
      await refreshSelectedTasks()
    }, "无法拒绝 PMO 计划")
  }

  function handleRequestPlanClarification(taskId: string) {
    runClientAction(async () => {
      await decideTaskPlan(
        backendUrl,
        taskId,
        "clarification",
        "用户要求 Main Agent 先澄清计划。",
      )
      await refreshSelectedTasks()
    }, "无法请求 PMO 澄清")
  }

  function handleDenyTaskRun(taskRunId: string) {
    runClientAction(async () => {
      await denyTaskRun(
        backendUrl,
        taskRunId,
        "用户已在 AgentHub 界面拒绝审批请求。",
      )
      await refreshSelectedTasks()
    }, "无法拒绝任务运行")
  }

  function handleOpenPreview(preview: PreviewArtifact) {
    setSelectedArtifactId(`preview:${preview.id}`)
    setPreviewFrameKey((current) => current + 1)
  }

  function handleRefreshPreviews(taskRunId: string) {
    runClientAction(async () => {
      const previews = await listTaskRunPreviews(backendUrl, taskRunId)
      const hasHealthyPreview = previews.some(
        (preview) => preview.healthStatus === "healthy",
      )
      const shouldRestartSelectedPreview =
        selectedPreview?.taskRunId === taskRunId &&
        selectedPreview.healthStatus !== "healthy" &&
        !hasHealthyPreview
      const latestPreview = shouldRestartSelectedPreview
        ? await startTaskRunPreview(backendUrl, taskRunId)
        : preferredPreview(previews)
      if (latestPreview && selectedPreview?.taskRunId === taskRunId) {
        setSelectedArtifactId(`preview:${latestPreview.id}`)
        setPreviewFrameKey((current) => current + 1)
      }
      refreshArtifacts()
      setSyncError(null)
    }, "无法刷新预览")
  }

  function handleStartPreview(taskRunId: string) {
    runClientAction(async () => {
      const preview = await startTaskRunPreview(backendUrl, taskRunId)
      setSelectedArtifactId(`preview:${preview.id}`)
      setPreviewFrameKey((current) => current + 1)
      refreshArtifacts()
      setSyncError(null)
    }, "无法启动预览")
  }

  function handleCreateReview(taskRunId: string) {
    runClientAction(async () => {
      const review = await createTaskRunReview(backendUrl, taskRunId)
      setSelectedArtifactId(`review:${review.id}`)
      refreshArtifacts()
      setSyncError(null)
    }, "无法创建评审产物")
  }

  function handleCreateDeployment(previewId: string) {
    runClientAction(async () => {
      const deployment = await createPreviewDeployment(backendUrl, previewId)
      setSelectedArtifactId(`deployment:${deployment.id}`)
      refreshArtifacts()
      setSyncError(null)
    }, "无法创建部署卡片")
  }

  function handleStopPreview(previewId: string) {
    runClientAction(async () => {
      await stopPreview(backendUrl, previewId)
      if (selectedPreview?.id === previewId) {
        setPreviewFrameKey((current) => current + 1)
      }
      refreshArtifacts()
      setSyncError(null)
    }, "无法停止预览")
  }

  function handleSaveArtifactEdit(artifactId: string, contentMd: string, summary: string) {
    runClientAction(async () => {
      await saveArtifactWorkbenchEdit(backendUrl, artifactId, {
        contentMd,
        summary,
      })
      refreshArtifacts()
      setSelectedArtifactId(`workbench:${artifactId}`)
      setSyncError(null)
    }, "无法保存产物版本")
  }

  return {
    handleCreateTaskRun,
    handleForceCodexFailure,
    handleInterruptTaskRun,
    handleRetryTaskRun,
    handleRetryTaskRunWithFallback,
    handleApproveTaskRun,
    handleApprovePlan,
    handleRejectPlan,
    handleRequestPlanClarification,
    handleDenyTaskRun,
    handleOpenPreview,
    handleRefreshPreviews,
    handleStartPreview,
    handleCreateReview,
    handleCreateDeployment,
    handleStopPreview,
    handleSaveArtifactEdit,
  }
}
