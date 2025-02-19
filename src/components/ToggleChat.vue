<template>
  <div class="toggle-chat">
    <!-- AI 交互按钮 -->
    <button 
      v-if="mode === 'collaborative'"
      @click="toggleAIChat"
      class="control-btn"
      :class="{ 'active': isActive }"
      title="Ask AI"
    >
      <span class="material-icons">smart_toy</span>
    </button>
    
    <!-- AI 对话框 -->
    <Teleport to="body">
      <div v-if="mode === 'collaborative' && isActive" 
           class="ai-chat-dialog"
           :style="dialogPosition"
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
    </Teleport>
  </div>
</template>

<script>
import axios from '@/main'
import { ElMessage } from 'element-plus'

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
  data() {
    return {
      isActive: false,
      userMessage: '',
      chatMessages: [],
      isLoading: false,
      dialogPosition: {
        top: '0px',
        left: '0px'
      }
    }
  },
  emits: ['ai-chat'],
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
      this.isActive = !this.isActive;
      if (this.isActive) {
        this.loadSceneChatHistory();
        this.$nextTick(() => {
          const buttonEl = this.$el.querySelector('.control-btn');
          if (buttonEl) {
            const rect = buttonEl.getBoundingClientRect();
            this.dialogPosition = {
              top: `${rect.top}px`,
              left: `${rect.right + 10}px`
            };
          }
        });
        
        // 初始化对话，但不显示系统消息
        this.chatMessages = [];
      } else {
        this.chatMessages = [];
        this.userMessage = '';
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
}

.control-btn:hover {
  background-color: rgba(0, 0, 0, 0.1);
}

.control-btn.active {
  background-color: #e3f2fd;
  color: #2196f3;
  border-color: #2196f3;
}

.material-icons {
  font-size: 18px;
}

.ai-chat-dialog {
  position: absolute;
  width: 320px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  max-height: 480px;
  border: 1px solid #e5e7eb;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb;
  background: #f9fafb;
  border-radius: 12px 12px 0 0;
}

.chat-header span {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
}

.chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #ffffff;
}

.chat-message {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
  max-width: 85%;
}

.chat-message.user {
  background-color: #f3f4f6;
  color: #374151;
  margin-left: auto;
}

.chat-message.assistant {
  background-color: #e5e7eb;
  color: #374151;
  margin-right: auto;
}

.chat-message.system {
  background-color: #fff3e0;
  margin: 8px auto;
  font-style: italic;
  width: 100%;
}

.chat-input {
  padding: 12px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  gap: 8px;
  background: #f9fafb;
  border-radius: 0 0 12px 12px;
}

.chat-input input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 14px;
  color: #374151;
  background: #ffffff;
}

.chat-input input:focus {
  outline: none;
  border-color: #6b7280;
  box-shadow: 0 0 0 2px rgba(107, 114, 128, 0.1);
}

.chat-input button {
  padding: 8px 12px;
  border: none;
  border-radius: 6px;
  background-color: #6b7280;
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.chat-input button:hover {
  background-color: #4b5563;
}

.chat-input button:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
}

.close-btn {
  background: none;
  border: none;
  font-size: 20px;
  color: #666;
  cursor: pointer;
  padding: 0 4px;
}

.close-btn:hover {
  color: #f56c6c;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
</style>
