<script setup lang="ts">
import { ElCard, ElButton, ElTable, ElTableColumn } from 'element-plus'
import { useRouter } from 'vue-router'

const router = useRouter()

const workflows = [
  { id: '1', name: 'Workflow 1', status: 'active', createdAt: '2024-01-01' },
  { id: '2', name: 'Workflow 2', status: 'draft', createdAt: '2024-01-02' }
]

const handleEdit = (id: string) => {
  router.push(`/workflows/${id}/edit`)
}
</script>

<template>
  <div class="workflows-view">
    <ElCard>
      <template #header>
        <div class="card-header">
          <span>Workflows</span>
          <ElButton type="primary">Create Workflow</ElButton>
        </div>
      </template>
      <ElTable :data="workflows" style="width: 100%">
        <ElTableColumn prop="name" label="Name" />
        <ElTableColumn prop="status" label="Status" />
        <ElTableColumn prop="createdAt" label="Created At" />
        <ElTableColumn label="Actions">
          <template #default="{ row }">
            <ElButton type="primary" link @click="handleEdit(row.id)">Edit</ElButton>
            <ElButton type="danger" link>Delete</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>
  </div>
</template>

<style scoped>
.workflows-view {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>