<script setup lang="ts">
import { computed, watch, ref } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

interface DatasetConfig {
  label: string
  data: number[]
  borderColor?: string
  backgroundColor?: string
  fill?: boolean
  tension?: number
  pointRadius?: number
  borderWidth?: number
}

const props = withDefaults(
  defineProps<{
    labels: string[]
    datasets: DatasetConfig[]
    title?: string
    height?: number
    yMin?: number
    yMax?: number
    yUnit?: string
    showLegend?: boolean
    animate?: boolean
  }>(),
  {
    height: 200,
    yMin: undefined,
    yMax: undefined,
    yUnit: '',
    showLegend: true,
    animate: true,
  }
)

const chartRef = ref<any>(null)

const chartData = computed(() => ({
  labels: props.labels,
  datasets: props.datasets.map((ds) => ({
    label: ds.label,
    data: ds.data,
    borderColor: ds.borderColor ?? '#6366f1',
    backgroundColor: ds.backgroundColor ?? 'rgba(99, 102, 241, 0.1)',
    fill: ds.fill ?? false,
    tension: ds.tension ?? 0.4,
    pointRadius: ds.pointRadius ?? 0,
    borderWidth: ds.borderWidth ?? 2,
  })),
}))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: props.animate ? ({ duration: 300 } as any) : (false as any),
  interaction: {
    mode: 'index' as const,
    intersect: false,
  },
  plugins: {
    legend: {
      display: props.showLegend,
      position: 'top' as const,
      labels: {
        color: '#94a3b8',
        font: { size: 12 },
        boxWidth: 12,
        boxHeight: 2,
        padding: 16,
      },
    },
    title: {
      display: !!props.title,
      text: props.title,
      color: '#f1f5f9',
      font: { size: 14, weight: 'bold' as const },
      padding: { bottom: 8 },
    },
    tooltip: {
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      titleColor: '#f1f5f9',
      bodyColor: '#94a3b8',
      borderColor: 'rgba(99, 102, 241, 0.3)',
      borderWidth: 1,
      padding: 10,
      cornerRadius: 8,
      titleFont: { size: 12 },
      bodyFont: { size: 12 },
      callbacks: {
        label: (ctx: any) => {
          const val = ctx.parsed.y
          return `${ctx.dataset.label}: ${val.toFixed(1)}${props.yUnit}`
        },
      },
    },
  },
  scales: {
    x: {
      grid: {
        color: 'rgba(99, 102, 241, 0.06)',
        drawBorder: false,
      },
      ticks: {
        color: '#475569',
        font: { size: 11 },
        maxRotation: 0,
        maxTicksLimit: 8,
      },
      border: { display: false },
    },
    y: {
      min: props.yMin,
      max: props.yMax,
      grid: {
        color: 'rgba(99, 102, 241, 0.06)',
        drawBorder: false,
      },
      ticks: {
        color: '#475569',
        font: { size: 11 },
        callback: (val: any) => `${val}${props.yUnit}`,
      },
      border: { display: false },
    },
  },
}))

watch(
  chartData,
  () => {
    if (chartRef.value?.chart) {
      chartRef.value.chart.data = chartData.value
      chartRef.value.chart.update('none')
    }
  },
  { deep: true }
)
</script>

<template>
  <div class="line-chart-wrapper" :style="{ height: `${height}px` }">
    <Line ref="chartRef" :data="chartData" :options="chartOptions" />
  </div>
</template>

<style scoped>
.line-chart-wrapper {
  position: relative;
  width: 100%;
}
</style>
