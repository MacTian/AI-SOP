import { defineStore } from 'pinia'
import http from '../api/http'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: null,
  }),
  getters: {
    isLoggedIn: (state) => !!state.token,
    isAdmin: (state) => state.user?.role === 'admin',
  },
  actions: {
    async login(username, password) {
      const params = new URLSearchParams()
      params.append('username', username)
      params.append('password', password)
      const { data } = await http.post('/api/auth/login', params)
      this.token = data.access_token
      localStorage.setItem('token', data.access_token)
      await this.fetchUser()
    },
    async fetchUser() {
      try {
        const { data } = await http.get('/api/auth/me')
        this.user = data
      } catch {
        this.logout()
      }
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
    },
  },
})
