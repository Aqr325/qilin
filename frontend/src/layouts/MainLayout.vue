<template>
  <div class="app-layout">
    <!-- 粒子背景 -->
    <canvas id="particle-bg"></canvas>

    <!-- 侧边栏 -->
    <Sidebar />

    <!-- 主区域 -->
    <div class="main-area">
      <TopBar />
      <main class="content-area">
        <router-view v-slot="{ Component }">
          <keep-alive :exclude="['Dashboard']">
            <transition name="page-fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </keep-alive>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import Sidebar from '@/components/Sidebar.vue'
import TopBar from '@/components/TopBar.vue'
import { initParticleBg } from '@/services/particles'

let cleanupParticles: (() => void) | null = null

onMounted(() => {
  cleanupParticles = initParticleBg()
})

onUnmounted(() => {
  if (cleanupParticles) cleanupParticles()
})
</script>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  width: 100%;
}

#particle-bg {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
  opacity: 0.5;
}

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.content-area {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6);
  max-width: var(--layout-content-max);
  width: 100%;
  margin: 0 auto;
  position: relative;
  z-index: 1;
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>