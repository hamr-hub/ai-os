<script setup lang="ts">
/* eslint-disable @typescript-eslint/no-explicit-any */
import { watch, ref } from 'vue'
import { Line } from 'vue-chartjs'
import type { ChartData, ChartOptions } from 'chart.js'
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
    title: '',
  }
)

const chartRef = ref<any>(null)

const chartData = ref<ChartData<'line'>>({
  labels: [],
  datasets: [],
})

const chartOptions = ref<ChartOptions<'line'>>({
  responsive: true,
  maintainAspectRatio: false,
  animation: props.animate ? { duration: 300 } : false,
  interaction: {
    mode: 'nearest',
    axis: 'xy',
    intersect: true,
  },
  plugins: {
    legend: {
      display: props.showLegend,
      position: 'top',
      align: 'end',
      labels: {
        color: '#94a3b8',
        font: { size: 11 },
        boxWidth: 8,
        boxHeight: 8,
        usePointStyle: true,
        pointStyle: 'circle',
        pointStyleWidth: 8,
        padding: 8,
      },
    },
    title: {
      display: !!props.title,
      text: props.title,
      color: '#f1f5f9',
      font: { size: 13, weight: 600 },
      padding: { bottom: 8 },
    },
    tooltip: {
      enabled: true,
      backgroundColor: 'rgba(17, 24, 39, 0.95)',
      titleColor: '#f1f5f9',
      bodyColor: '#cbd5e1',
      borderColor: 'rgba(99, 102, 241, 0.4)',
      borderWidth: 1,
      cornerRadius: 8,
      padding: 10,
      titleFont: { size: 11, weight: 600 },
      bodyFont: { size: 11 },
      displayColors: true,
      boxPadding: 4,
      caretPadding: 8,
      caretSize: 6,
      position: 'average',
      filter: (tooltipItem: any) => {
        return tooltipItem.parsed.y !== null && tooltipItem.parsed.y !== undefined
      },
      callbacks: {
        label: (ctx: any) => {
          const val = ctx.parsed.y
          if (val === null || val === undefined) return ''
          const label = ctx.dataset.label || ''
          return `${label}: ${Number(val).toFixed(1)}${props.yUnit}`
        },
        title: (items: any) => {
          if (items && items.length > 0) {
            return items[0].label
          }
          return ''
        },
      },
    },
  },
  scales: {
    x: {
      grid: {
        color: 'rgba(99, 102, 241, 0.08)',
        lineWidth: 0.5,
      },
      ticks: {
        color: '#64748b',
        font: { size: 10 },
        maxRotation: 0,
        maxTicksLimit: 6,
        padding: 4,
      },
      border: { 
        display: false 
      },
    },
    y: {
      min: props.yMin,
      max: props.yMax,
      grid: {
        color: 'rgba(99, 102, 241, 0.08)',
        lineWidth: 0.5,
      },
      ticks: {
        color: '#64748b',
        font: { size: 10 },
        padding: 8,
        maxTicksLimit: 5,
        callback: (val: any) => `${val}${props.yUnit}`,
      },
      border: { display: false },
    },
  },
  layout: {
    padding: {
      top: 8,
      right: 4,
      bottom: 4,
      left: 4,
    },
  },
})

const updateChartData = () => {
  chartData.value = {
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
  }
}

watch(
  () => [props.labels, props.datasets, props.yMin, props.yMax, props.showLegend] as const,
  () => {
    updateChartData()

    chartOptions.value = {
      ...chartOptions.value,
      animation: props.animate ? { duration: 300 } : false,
      plugins: {
        ...chartOptions.value.plugins,
        legend: {
          ...chartOptions.value.plugins?.legend,
          display: props.showLegend,
        },
      },
      scales: {
        ...chartOptions.value.scales,
        y: {
          ...chartOptions.value.scales?.y,
          min: props.yMin,
          max: props.yMax,
        },
      },
    }

    if (chartRef.value?.chart) {
      const labels = chartData.value.labels || []
      chartRef.value.chart.data.labels = labels.slice()
      chartData.value.datasets.forEach((ds, i) => {
        if (chartRef.value.chart.data.datasets[i]) {
          chartRef.value.chart.data.datasets[i].data = ds.data.slice()
          chartRef.value.chart.data.datasets[i].borderColor = ds.borderColor
          chartRef.value.chart.data.datasets[i].backgroundColor = ds.backgroundColor
        }
      })
      chartRef.value.chart.update('none')
    }
  },
  { deep: true, immediate: true }
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