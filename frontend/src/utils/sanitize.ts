import DOMPurify from 'dompurify'

/**
 * 对不可信 HTML（如 AI 生成的 markdown 渲染结果）做消毒后再经 v-html 注入，
 * 防止 Electron 渲染进程内的 XSS。
 */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: [
      'script', 'style', 'iframe', 'form', 'input', 'button',
      'object', 'embed', 'link', 'meta', 'base',
    ],
    FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'style', 'srcset'],
  })
}
