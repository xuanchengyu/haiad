import { defineStore } from 'pinia'

export const useChatStore = defineStore('chat', {
  state: () => ({
    activeChatId: null
  }),
  actions: {
    setActiveChatId(id) {
      this.activeChatId = id
    }
  }
}) 