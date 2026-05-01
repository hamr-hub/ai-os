import { describe, it, expect } from 'vitest'
import { renderMarkdown } from '../useMarkdown'

describe('renderMarkdown', () => {
  it('空内容返回空字符串', () => {
    expect(renderMarkdown('')).toBe('')
  })

  it('渲染简单文本', () => {
    const result = renderMarkdown('Hello World')
    expect(result).toContain('Hello')
  })

  it('渲染粗体文本', () => {
    const result = renderMarkdown('**bold**')
    expect(result).toContain('<strong>')
  })

  it('渲染代码块', () => {
    const result = renderMarkdown('```js\nconsole.log("hi")\n```')
    expect(result).toContain('code-block')
    expect(result).toContain('hljs')
  })

  it('渲染链接', () => {
    const result = renderMarkdown('[link](https://example.com)')
    expect(result).toContain('href')
  })

  it('过滤危险标签', () => {
    const result = renderMarkdown('<script>alert(1)</script>hello')
    expect(result).not.toContain('<script')
  })
})
