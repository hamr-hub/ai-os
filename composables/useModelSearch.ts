import { ref, type Ref } from 'vue'
import { searchModels, recommendModel, checkModelMemory } from '@/api/client'
import type { SearchResult, RecommendResult } from '@/types'

export function useModelSearch() {
  const results: Ref<SearchResult[]> = ref([])
  const recommendResult: Ref<RecommendResult | null> = ref(null)
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)

  const search = async (keyword: string, source: string = 'all', limit: number = 10) => {
    loading.value = true
    error.value = null
    try {
      const data = await searchModels(keyword, source, limit)
      results.value = data.results
    } catch (e: any) {
      error.value = e.message || '搜索失败'
      results.value = []
    } finally {
      loading.value = false
    }
  }

  const recommend = async (keyword: string, source: string = 'all') => {
    loading.value = true
    error.value = null
    try {
      recommendResult.value = await recommendModel(keyword, source)
    } catch (e: any) {
      error.value = e.message || '推荐失败'
      recommendResult.value = null
    } finally {
      loading.value = false
    }
  }

  const checkMemory = async (modelName: string) => {
    try {
      return await checkModelMemory(modelName)
    } catch (e: any) {
      error.value = e.message || '显存校验失败'
      return null
    }
  }

  return { results, recommendResult, loading, error, search, recommend, checkMemory }
}
