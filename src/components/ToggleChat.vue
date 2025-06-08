<template>
  <div class="toggle-chat">
    <!-- AI 交互按钮 -->
    <button 
      @click="toggleAIChat"
      class="control-btn"
      :class="{ 'active': isActive }"
      title="Ask AI"
    >
      <span class="material-icons">smart_toy</span>
    </button>
    
    <!-- AI 对话框 -->
    <div 
      v-show="isActive" 
      class="ai-chat-dialog"
      :class="{ 'open': isActive }"
    >
      <div class="chat-header">
        <span>How would you like to modify the script?</span>
        <button class="close-btn" @click="toggleAIChat">×</button>
      </div>
      <div class="chat-history" ref="chatHistory">
        <div v-for="(msg, index) in displayMessages" 
             :key="index"
             :class="['chat-message', msg.role]">
          <div class="sender">{{ msg.role === 'assistant' ? 'ChatGPT:' : 'You:' }}</div>
          <div class="message-content">{{ msg.content }}</div>
        </div>
      </div>
      <div class="chat-input">
        <input 
          v-model="userMessage"
          @keyup.enter="sendMessage"
          placeholder="Type your message..."
        />
        <button @click="sendMessage">Send</button>
      </div>
    </div>
  </div>
</template>

<script>
import axios from '@/main'
import { ElMessage } from 'element-plus'
import { useChatStore } from '@/store'
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

export default {
  name: 'ToggleChat',
  props: {
    mode: {
      type: String,
      required: true
    },
    videoId: {
      type: String,
      required: true
    },
    sceneId: {
      type: String,
      required: true
    },
    currentText: {
      type: String,
      required: true
    }
  },
  setup(props) {
    const store = useChatStore()
    const { activeChatId } = storeToRefs(store)
    
    const isActive = computed(() => activeChatId.value === props.sceneId)
    
    return { 
      store, 
      activeChatId,
      isActive 
    }
  },
  data() {
    return {
      userMessage: '',
      chatMessages: [],
      isLoading: false,
      dialogPosition: {
        top: '0px',
        left: '0px'
      }
    }
  },
  computed: {
    displayMessages() {
      // 过滤掉系统消息，只显示用户和助手的消息
      return this.chatMessages.filter(msg => msg.role !== 'system');
    }
  },
  methods: {
    async loadSceneChatHistory() {
      try {
        const response = await axios.get('/api/ai/scene/chat/history', {
          params: {
            video_id: this.videoId,
            scene_id: this.sceneId
          }
        });
        
        if (response.data.success && response.data.history) {
          this.chatMessages = response.data.history.messages.map(msg => ({
            role: msg.role,
            content: msg.content,
            timestamp: new Date(msg.timestamp)
          }));
        }
      } catch (error) {
        console.error('Failed to load scene chat history:', error);
        ElMessage.error('Failed to load chat history');
      }
    },
    toggleAIChat() {
      if (this.isActive) {
        this.store.setActiveChatId(null)
      } else {
        this.store.setActiveChatId(this.sceneId)
      }
      
      if (this.isActive) {
        this.loadSceneChatHistory()
      } else {
        this.chatMessages = []
        this.userMessage = ''
      }
    },
    
    async sendMessage() {
      if (!this.userMessage.trim() || this.isLoading) return;
      
      try {
        this.isLoading = true;
        
        // 验证必要参数
        const params = {
          video_id: this.videoId,
          scene_id: this.sceneId,
          current_text: this.currentText,
          user_message: this.userMessage
        };
        
        console.log('Checking parameters:', params);
        
        const missingParams = Object.entries(params)
          .filter(([, value]) => !value)
          .map(([key]) => key);
        
        if (missingParams.length > 0) {
          console.error('Missing parameters:', missingParams);
          throw new Error(`Missing required parameters: ${missingParams.join(', ')}`);
        }
        
        // 添加用户消息到聊天历史
        this.chatMessages.push({
          role: 'user',
          content: this.userMessage,
          timestamp: new Date()
        });
        
        console.log('Sending request with params:', params);  // 添加日志
        
        const response = await axios.post('/api/ai/scene/chat', params);
        
        console.log('Received response:', response.data);
        
        if (response.data.success) {
          // 添加 AI 响应到聊天历史
          this.chatMessages.push({
            role: 'assistant',
            content: response.data.message,
            timestamp: new Date()
          });
          
          // 滚动到最新消息
          this.$nextTick(() => {
            if (this.$refs.chatHistory) {
              this.$refs.chatHistory.scrollTop = this.$refs.chatHistory.scrollHeight;
            }
          });
        } else {
          throw new Error(response.data.error || 'Request failed');
        }
        
      } catch (error) {
        console.error('Send message failed:', error);
        ElMessage.error(error.message || 'Send message failed');
        this.chatMessages.push({
          role: 'system',
          content: 'Send message failed, please try again.',
          timestamp: new Date()
        });
      } finally {
        this.isLoading = false;
      }
    }
  }
}
</script>

<style scoped>
.toggle-chat {
  display: inline-block;
  position: relative;
}

.control-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  border: none;
  border-radius: 8px;
  background-color: rgba(0, 0, 0, 0.05);
  color: #1d1d1f;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1000;
}

.control-btn:hover {
  background-color: rgba(0, 0, 0, 0.1);
}

.control-btn.active {
  background-color: #e3f2fd;
  color: #2196f3;
}

.material-icons {
  font-size: 18px;
}

.ai-chat-dialog {
  position: fixed;
  top: 0;
  right: -420px; /* 初始位置在屏幕外 */
  width: 400px;
  height: 100vh;
  background: #ffffff;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  transition: right 0.3s ease;
  z-index: 999;
}

.ai-chat-dialog.open {
  right: 0; /* 显示时滑入 */
}

.chat-header {
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f9fafb;
}

.chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.chat-message {
  margin-bottom: 12px;
  padding: 10px;
  border-radius: 8px;
  max-width: 85%;
}

.chat-message.user {
  background-color: #f3f4f6;
  margin-left: auto;
}

.chat-message.assistant {
  background-color: #e5e7eb;
  margin-right: auto;
}

.chat-input {
  padding: 16px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  gap: 8px;
  background: #f9fafb;
}

.chat-input input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  outline: none;
}

.chat-input button {
  padding: 8px 16px;
  background: #2196f3;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.chat-input button:hover {
  background: #1976d2;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  color: #666;
  cursor: pointer;
  padding: 0 4px;
}

.close-btn:hover {
  color: #f56c6c;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .ai-chat-dialog {
    width: 100%;
    right: -100%;
  }
}
</style>
