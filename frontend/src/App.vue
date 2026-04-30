<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Navigation -->
    <nav v-if="auth.isLoggedIn" class="bg-white shadow-sm border-b">
      <div class="max-w-7xl mx-auto px-4">
        <div class="flex items-center justify-between h-14">
          <div class="flex items-center space-x-4">
            <h1 class="text-lg font-semibold text-gray-800">AI SOP Monitor</h1>
            <router-link
              v-for="link in navLinks"
              :key="link.path"
              :to="link.path"
              class="px-3 py-1.5 text-sm rounded-md"
              :class="$route.path === link.path
                ? 'bg-blue-100 text-blue-700'
                : 'text-gray-600 hover:bg-gray-100'"
            >
              {{ link.label }}
            </router-link>
          </div>
          <div class="flex items-center space-x-3">
            <span
              class="inline-block w-2 h-2 rounded-full"
              :class="wsConnected ? 'bg-green-500' : 'bg-red-500'"
            ></span>
            <span class="text-xs text-gray-500">
              {{ wsConnected ? 'Connected' : 'Disconnected' }}
            </span>
            <span class="text-sm text-gray-600">{{ auth.user?.username }}</span>
            <button @click="handleLogout"
              class="text-sm text-gray-500 hover:text-red-600">
              Logout
            </button>
          </div>
        </div>
      </div>
    </nav>

    <!-- Main content -->
    <main :class="auth.isLoggedIn ? 'max-w-7xl mx-auto px-4 py-6' : ''">
      <router-view />
    </main>

    <!-- Global toast notifications -->
    <AlertToast v-if="auth.isLoggedIn" />
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMonitorStore } from './stores/monitor'
import { useAuthStore } from './stores/auth'
import AlertToast from './components/AlertToast.vue'

const router = useRouter()
const store = useMonitorStore()
const auth = useAuthStore()
const wsConnected = computed(() => store.wsConnected)

const navLinks = [
  { path: '/', label: 'Dashboard' },
  { path: '/training', label: 'Training' },
  { path: '/sop-editor', label: 'SOP Editor' },
  { path: '/history', label: 'History' },
]

onMounted(() => {
  if (auth.isLoggedIn) {
    auth.fetchUser()
  }
})

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>
