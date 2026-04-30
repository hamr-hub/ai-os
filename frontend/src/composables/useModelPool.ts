import { ref, type Ref } from 'vue'
import { getPoolList, getPoolDetail, loadFromPool, deleteFromPool } from '@/api/client'
import type { PoolEntry } from '@/types'

export function useModelPool() {
  const poolList: Ref<PoolEntry[]> = ref([])
  const currentDetail: Ref<PoolEntry | null> = ref(null)
  const total = ref(0)
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)

  const list = async (filter: string = 'all', page: number = 1, pageSize: number = 50) => {
    loading.value = true
    error.value = null
    try {
      const resp = await getPoolList(filter, page, pageSize)
      poolList.value = resp.models
      total.value = resp.total
    } catch (e: any) {
      error.value = e.message || '获取模型池失败'
      poolList.value = []
    } finally {
      loading.value = false
    }
  }

  const detail = async (modelKey: string) => {
    loading.value = true
    error.value = null
    try {
      currentDetail.value = await getPoolDetail(modelKey)
    } catch (e: any) {
      error.value = e.message || '获取模型详情失败'
      currentDetail.value = null
    } finally {
      loading.value = false
    }
  }

  const load = async (modelKey: string, engine: string = 'vllm') => {
    loading.value = true
    error.value = null
    try {
      return await loadFromPool(modelKey, engine)
    } catch (e: any) {
      error.value = e.message || '加载模型失败'
      return null
    } finally {
      loading.value = false
    }
  }

  const remove = async (modelKey: string, removeFiles: boolean = false) => {
    loading.value = true
    error.value = null
    try {
      const result = await deleteFromPool(modelKey, removeFiles)
      poolList.value = poolList.value.filter(m => m.config_key !== modelKey)
      total.value = poolList.value.length
      return result
    } catch (e: any) {
      error.value = e.message || '删除模型失败'
      return null
    } finally {
      loading.value = false
    }
  }

  return { poolList, currentDetail, total, loading, error, list, detail, load, remove }
}
