<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, DocumentCopy, RefreshLeft } from '@element-plus/icons-vue'

const STORAGE_KEY = 'home-markdown-todos'

const defaultMarkdown = `# Todo

## 今天
- [ ] 梳理要处理的问题
- [ ] 标记优先级

## 待确认
- [ ] 补充负责人和截止时间

## 记录
> 这里可以直接写 Markdown，内容会自动保存在当前浏览器。
`

const markdown = ref(defaultMarkdown)

const todoStats = computed(() => {
  const total = markdown.value.match(/^- \[[ xX]\]/gm)?.length ?? 0
  const done = markdown.value.match(/^- \[[xX]\]/gm)?.length ?? 0

  return {
    total,
    done,
    pending: total - done
  }
})

const renderedMarkdown = computed(() => renderMarkdown(markdown.value))

onMounted(() => {
  const savedMarkdown = localStorage.getItem(STORAGE_KEY)

  if (savedMarkdown) {
    markdown.value = savedMarkdown
  }
})

watch(markdown, (value) => {
  localStorage.setItem(STORAGE_KEY, value)
})

const copyMarkdown = async () => {
  try {
    await navigator.clipboard.writeText(markdown.value)
    ElMessage.success('已复制 Markdown')
  } catch {
    ElMessage.error('复制失败，请手动选择文本复制')
  }
}

const resetMarkdown = async () => {
  try {
    await ElMessageBox.confirm('会用默认 Todo 模板覆盖当前内容，确定继续吗？', '重置内容', {
      confirmButtonText: '重置',
      cancelButtonText: '取消',
      type: 'warning'
    })
    markdown.value = defaultMarkdown
    ElMessage.success('已重置为默认模板')
  } catch {
    // User cancelled.
  }
}

const clearMarkdown = async () => {
  try {
    await ElMessageBox.confirm('会清空当前 Markdown 内容，确定继续吗？', '清空内容', {
      confirmButtonText: '清空',
      cancelButtonText: '取消',
      type: 'warning'
    })
    markdown.value = ''
    ElMessage.success('已清空')
  } catch {
    // User cancelled.
  }
}

function renderMarkdown(source: string) {
  const lines = source.split('\n')
  const html: string[] = []
  let listType: 'ul' | 'ol' | null = null
  let inCodeBlock = false
  const codeLines: string[] = []

  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`)
      listType = null
    }
  }

  for (const line of lines) {
    if (line.trim().startsWith('```')) {
      closeList()

      if (inCodeBlock) {
        html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`)
        codeLines.length = 0
        inCodeBlock = false
      } else {
        inCodeBlock = true
      }

      continue
    }

    if (inCodeBlock) {
      codeLines.push(line)
      continue
    }

    const trimmed = line.trim()

    if (!trimmed) {
      closeList()
      continue
    }

    const headingMatch = /^(#{1,4})\s+(.+)$/.exec(trimmed)
    if (headingMatch) {
      closeList()
      const level = headingMatch[1].length
      html.push(`<h${level}>${renderInline(headingMatch[2])}</h${level}>`)
      continue
    }

    const todoMatch = /^- \[([ xX])\]\s+(.+)$/.exec(trimmed)
    if (todoMatch) {
      if (listType !== 'ul') {
        closeList()
        html.push('<ul>')
        listType = 'ul'
      }

      const checked = todoMatch[1].toLowerCase() === 'x'
      html.push(`<li class="todo-item"><input type="checkbox" disabled ${checked ? 'checked' : ''}> <span>${renderInline(todoMatch[2])}</span></li>`)
      continue
    }

    const bulletMatch = /^[-*]\s+(.+)$/.exec(trimmed)
    if (bulletMatch) {
      if (listType !== 'ul') {
        closeList()
        html.push('<ul>')
        listType = 'ul'
      }

      html.push(`<li>${renderInline(bulletMatch[1])}</li>`)
      continue
    }

    const orderedMatch = /^\d+\.\s+(.+)$/.exec(trimmed)
    if (orderedMatch) {
      if (listType !== 'ol') {
        closeList()
        html.push('<ol>')
        listType = 'ol'
      }

      html.push(`<li>${renderInline(orderedMatch[1])}</li>`)
      continue
    }

    const quoteMatch = /^>\s+(.+)$/.exec(trimmed)
    if (quoteMatch) {
      closeList()
      html.push(`<blockquote>${renderInline(quoteMatch[1])}</blockquote>`)
      continue
    }

    closeList()
    html.push(`<p>${renderInline(trimmed)}</p>`)
  }

  closeList()

  if (inCodeBlock) {
    html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`)
  }

  return html.join('')
}

function renderInline(source: string) {
  return escapeHtml(source)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
}

function escapeHtml(source: string) {
  return source
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}
</script>

<template>
  <div class="home-view">
    <section class="markdown-header">
      <div>
        <p class="eyebrow">Markdown Todo</p>
        <h1>事项记录</h1>
        <p class="description">直接编辑 Markdown，内容会自动保存在当前浏览器。</p>
      </div>

      <div class="toolbar">
        <el-button :icon="DocumentCopy" @click="copyMarkdown">复制</el-button>
        <el-button :icon="RefreshLeft" @click="resetMarkdown">重置模板</el-button>
        <el-button :icon="Delete" type="danger" plain @click="clearMarkdown">清空</el-button>
      </div>
    </section>

    <section class="stats-row" aria-label="Todo 统计">
      <div class="stat-card">
        <span>全部事项</span>
        <strong>{{ todoStats.total }}</strong>
      </div>
      <div class="stat-card">
        <span>已完成</span>
        <strong>{{ todoStats.done }}</strong>
      </div>
      <div class="stat-card">
        <span>待处理</span>
        <strong>{{ todoStats.pending }}</strong>
      </div>
    </section>

    <section class="editor-grid">
      <div class="editor-panel">
        <div class="panel-title">编辑</div>
        <el-input
          v-model="markdown"
          type="textarea"
          resize="none"
          spellcheck="false"
          placeholder="# Todo"
          class="markdown-input"
        />
      </div>

      <div class="preview-panel">
        <div class="panel-title">预览</div>
        <article class="markdown-preview" v-html="renderedMarkdown"></article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home-view {
  min-height: 100%;
  color: #303133;
}

.markdown-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.eyebrow {
  margin-bottom: 4px;
  font-size: 10px;
  font-weight: 600;
  color: #3b82f6;
}

.markdown-header h1 {
  margin: 0;
  font-size: 20px;
  line-height: 1.2;
  color: #1e293b;
}

.description {
  margin-top: 6px;
  color: #64748b;
  line-height: 1.6;
  font-size: 12px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.stat-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #f8fafc;
}

.stat-card span {
  color: #64748b;
  font-size: 12px;
}

.stat-card strong {
  color: #1e293b;
  font-size: 18px;
}

.editor-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  min-height: 480px;
}

.editor-panel,
.preview-panel {
  display: flex;
  min-width: 0;
  min-height: 480px;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
}

.panel-title {
  padding: 8px 12px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}

.markdown-input {
  flex: 1;
}

.markdown-input :deep(.el-textarea__inner) {
  height: 100%;
  min-height: 0 !important;
  padding: 12px;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  color: #1e293b;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
  line-height: 1.6;
}

.markdown-preview {
  flex: 1;
  overflow: auto;
  padding: 14px 16px 20px;
  line-height: 1.6;
}

.markdown-preview :deep(h1),
.markdown-preview :deep(h2),
.markdown-preview :deep(h3),
.markdown-preview :deep(h4) {
  margin: 0 0 10px;
  color: #1e293b;
  line-height: 1.35;
}

.markdown-preview :deep(h1) {
  font-size: 20px;
}

.markdown-preview :deep(h2) {
  margin-top: 16px;
  padding-bottom: 4px;
  border-bottom: 1px solid #e2e8f0;
  font-size: 16px;
}

.markdown-preview :deep(h3) {
  margin-top: 14px;
  font-size: 14px;
}

.markdown-preview :deep(h4) {
  margin-top: 12px;
  font-size: 12px;
}

.markdown-preview :deep(p),
.markdown-preview :deep(ul),
.markdown-preview :deep(ol),
.markdown-preview :deep(blockquote),
.markdown-preview :deep(pre) {
  margin: 0 0 10px;
}

.markdown-preview :deep(ul),
.markdown-preview :deep(ol) {
  padding-left: 20px;
}

.markdown-preview :deep(li) {
  margin-bottom: 4px;
  font-size: 12px;
}

.markdown-preview :deep(.todo-item) {
  list-style: none;
  margin-left: -22px;
}

.markdown-preview :deep(.todo-item input) {
  margin-right: 8px;
}

.markdown-preview :deep(blockquote) {
  padding: 8px 12px;
  border-left: 3px solid #3b82f6;
  border-radius: 4px;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
}

.markdown-preview :deep(code) {
  padding: 1px 4px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #ef4444;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.9em;
}

.markdown-preview :deep(pre) {
  overflow: auto;
  padding: 10px;
  border-radius: 6px;
  background: #1f2937;
}

.markdown-preview :deep(pre code) {
  padding: 0;
  background: transparent;
  color: #f9fafb;
}

.markdown-preview :deep(a) {
  color: #3b82f6;
  text-decoration: none;
}

.markdown-preview :deep(a:hover) {
  text-decoration: underline;
}

@media (max-width: 960px) {
  .markdown-header {
    flex-direction: column;
  }

  .toolbar {
    justify-content: flex-start;
  }

  .editor-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .stats-row {
    grid-template-columns: 1fr;
  }

  .toolbar {
    width: 100%;
  }

  .toolbar .el-button {
    flex: 1;
    margin-left: 0;
  }
}
</style>
