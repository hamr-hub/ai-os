import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { PoolEntry, DownloadTask, SearchResult } from '@/types'
import {
  getPoolList, loadFromPool, deleteFromPool,
  searchModels, recommendModel,
  startDownload, cancelDownload, listDownloads,
} from '@/api/client'
import { onDownloadMessage } from '@/utils/downloadWebSocket'

export const useModelPoolStore = defineStore('modelPool', () => {
  const pool = ref<PoolEntry[]>([])
  const downloads = ref<DownloadTask[]>([])
  const searchResults = ref<SearchResult[]>([])
  const searchTotal = ref(0)
  const loading = ref(false)
  const downloading = ref(false)
  const searching = ref(false)
  const error = ref<string | null>(null)

  let wsUnsub: (() => void) | null = null

  const fetchPool = async () => {
    loading.value = true
    error.value = null
    try {
      const resp = await getPoolList()
      pool.value = resp.models
    } catch (e: unknown) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  const searchModelsAction = async (keyword: string, source: string = 'all', limit: number = 20) => {
    searching.value = true
    error.value = null
    try {
      const resp = await searchModels(keyword, source, limit)
      searchResults.value = resp.results
      searchTotal.value = resp.total
    } catch (e: unknown) {
      error.value = (e as Error).message
      searchResults.value = []
    } finally {
      searching.value = false
    }
  }

  const getRecommendation = async (keyword: string = '', source: string = 'all') => {
    searching.value = true
    try {
      const resp = await recommendModel(keyword, source)
      if (resp.recommended) {
        searchResults.value = [resp.recommended, ...resp.candidates.filter(c => c.name !== resp.recommended?.name)]
      } else {
        searchResults.value = resp.candidates
      }
      searchTotal.value = resp.candidates.length
    } catch {
      // ignore
    } finally {
      searching.value = false
    }
  }

  const startDownloadAction = async (modelName: string, source: string = 'hf', saveDir?: string) => {
    downloading.value = true
    error.value = null
    try {
      const result = await startDownload(modelName, source, saveDir)
      if ('task_id' in result) {
        const task = result as DownloadTask
        downloads.value.unshift(task)
        connectWS()
        return task
      }
      return result
    } catch (e: unknown) {
      error.value = (e as Error).message
      return null
    } finally {
      downloading.value = false
    }
  }

  const cancelDownloadAction = async (taskId: string) => {
    try {
      await cancelDownload(taskId)
      downloads.value = downloads.value.map(t =>
        t.task_id === taskId ? { ...t, status: 'cancelled' as const } : t
      )
    } catch (e: unknown) {
      error.value = (e as Error).message
    }
  }

  const refreshDownloads = async () => {
    try {
      downloads.value = await listDownloads()
    } catch {
      // ignore
    }
  }

  const loadFromPoolAction = async (modelKey: string, engine: string = 'vllm') => {
    loading.value = true
    error.value = null
    try {
      const result = await loadFromPool(modelKey, engine)
      await fetchPool()
      return result
    } catch (e: unknown) {
      error.value = (e as Error).message
      return null
    } finally {
      loading.value = false
    }
  }

  const deleteFromPoolAction = async (modelKey: string, removeFiles = false) => {
    loading.value = true
    error.value = null
    try {
      await deleteFromPool(modelKey, removeFiles)
      pool.value = pool.value.filter(m => m.config_key !== modelKey)
    } catch (e: unknown) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  const connectWS = () => {
    if (!wsUnsub) {
      wsUnsub = onDownloadMessage((msg) => {
        const idx = downloads.value.findIndex(t => t.task_id === msg.task_id)
        if (idx >= 0) {
          const existing = downloads.value[idx]
          downloads.value[idx] = {
            ...existing,
            status: msg.event === 'download_completed' ? 'completed' :
                    msg.event === 'download_failed' ? 'failed' :
                    msg.event === 'download_started' ? 'downloading' : existing.status,
            progress_pct: msg.progress_pct ?? existing.progress_pct,
            speed_mbps: msg.speed_mbps ?? existing.speed_mbps,
            eta_seconds: msg.eta_seconds ?? existing.eta_seconds,
            downloaded_bytes: msg.downloaded_bytes ?? existing.downloaded_bytes,
            total_bytes: msg.total_bytes ?? existing.total_bytes,
            error_message: msg.error_message ?? existing.error_message,
          }
        }
        if (msg.event === 'download_completed' || msg.event === 'download_failed') {
          fetchPool()
        }
      })
    }
  }

  const disconnectWS = () => {
    if (wsUnsub) {
      wsUnsub()
      wsUnsub = null
    }
  }

  return {
    pool, downloads, searchResults, searchTotal,
    loading, downloading, searching, error,
    fetchPool, searchModelsAction, getRecommendation,
    startDownloadAction, cancelDownloadAction, refreshDownloads,
    loadFromPoolAction, deleteFromPoolAction,
    connectWS, disconnectWS,
  }
})
