import type { Component } from 'vue'

export interface DocItem {
  slug: string
  title: string
  category: string
  children?: DocItem[]
}

export const docTree: DocItem[] = [
  {
    slug: 'deployment',
    title: '部署指南',
    category: 'deployment',
    children: [
      { slug: 'deployment-guide', title: '部署总览', category: 'deployment' },
      { slug: 'docker-compose-dev', title: '开发环境部署', category: 'deployment' },
      { slug: 'docker-compose-prod', title: '生产环境部署', category: 'deployment' },
      { slug: 'docker-compose-gpu', title: 'GPU 环境部署', category: 'deployment' },
      { slug: 'port-reference', title: '端口参考手册', category: 'deployment' },
      { slug: 'testing-guide', title: '测试指南', category: 'deployment' },
    ],
  },
  {
    slug: 'agent',
    title: '开发约定',
    category: 'agent',
    children: [
      { slug: 'architecture', title: '架构文档', category: 'agent' },
      { slug: 'conventions', title: '编码约定', category: 'agent' },
      { slug: 'development-commands', title: '开发命令', category: 'agent' },
      { slug: 'requirement-template', title: '需求模板', category: 'agent' },
    ],
  },
  {
    slug: 'research',
    title: '研发资产',
    category: 'research',
    children: [{ slug: 'rd-assets', title: '研发资产盘点', category: 'research' }],
  },
]

const docModules: Record<string, () => Promise<{ default: Component }>> = {
  'deployment/deployment-guide': () => import('../../../docs/deployment/deployment-guide.md'),
  'deployment/docker-compose-dev': () => import('../../../docs/deployment/docker-compose-dev.md'),
  'deployment/docker-compose-prod': () => import('../../../docs/deployment/docker-compose-prod.md'),
  'deployment/docker-compose-gpu': () => import('../../../docs/deployment/docker-compose-gpu.md'),
  'deployment/port-reference': () => import('../../../docs/deployment/port-reference.md'),
  'deployment/testing-guide': () => import('../../../docs/deployment/testing-guide.md'),
  'agent/architecture': () => import('../../../docs/agent/architecture.md'),
  'agent/conventions': () => import('../../../docs/agent/conventions.md'),
  'agent/development-commands': () => import('../../../docs/agent/development_commands.md'),
  'agent/requirement-template': () => import('../../../docs/agent/requirement-template.md'),
  'research/rd-assets': () => import('../../../docs/research/rd-assets.md'),
}

export function getDocLoader(category: string, slug: string) {
  const key = `${category}/${slug}`
  return docModules[key] || null
}

export function getAllDocItems(): DocItem[] {
  const items: DocItem[] = []
  for (const group of docTree) {
    if (group.children) {
      items.push(...group.children)
    } else {
      items.push(group)
    }
  }
  return items
}

export function findDocBySlug(slug: string): DocItem | null {
  for (const group of docTree) {
    if (group.slug === slug) return group
    if (group.children) {
      for (const child of group.children) {
        if (child.slug === slug) return child
      }
    }
  }
  return null
}
