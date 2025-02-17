<template>
  <div class="chat-interface">
    <!-- 对话历史区域 -->
    <div class="interaction-history">
      <div class="zone-title">Interaction History:</div>
      <div class="messages-container" ref="messagesContainer">
        <div v-for="(msg, index) in messages" :key="index" class="message-box">
          <!-- 发送者标识 -->
          <div class="sender">{{ msg.role === 'assistant' ? 'ChatGPT:' : 'You:' }}</div>
          
          <!-- 消息内容 -->
          <div class="message-content" :class="msg.role">
            <!-- 如果有图片则显示 -->
            <div v-if="msg.image" class="image-preview">
              <img :src="msg.image" alt="Uploaded image" />
            </div>
            <div class="text">{{ msg.content }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="instruction-zone">
      <div class="zone-title">Your Instruction:</div>
      <div class="input-area">
        <!-- 图片上传按钮 -->
        <div class="image-upload">
          <input 
            type="file" 
            accept="image/*" 
            @change="handleImageUpload"
            ref="fileInput"
            class="file-input"
          >
          <button v-if="selectedImage" @click="clearImage" class="clear-button">
            Clear Image
          </button>
        </div>

        <!-- 文本输入和发送按钮 -->
        <div class="message-input">
          <textarea 
            v-model="currentMessage" 
            @keyup.enter="sendMessage"
            placeholder="Type your message..."
            :disabled="isLoading"
            rows="3"
          ></textarea>
          <button 
            @click="sendMessage" 
            :disabled="isLoading || !currentMessage.trim()"
            class="send-button"
          >
            send
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'AiAssistant',
  
  data() {
    return {
      messages: [],
      currentMessage: '',
      selectedImage: null,
      isLoading: false
    }
  },

  created() {
    // 组件创建时加载聊天历史
    this.loadChatHistory()
  },

  methods: {
    async loadChatHistory() {
      try {
        const response = await axios.get('/api/chat/history')
        if (response.data.success) {
          // 将历史记录转换为消息格式
          const allMessages = []
          response.data.history.forEach(chat => {
            chat.messages.forEach(msg => {
              allMessages.push({
                role: msg.role,
                content: msg.content,
                image: msg.image,
                timestamp: new Date(msg.timestamp)
              })
            })
          })
          // 按时间排序
          this.messages = allMessages.sort((a, b) => a.timestamp - b.timestamp)
        }
      } catch (error) {
        console.error('Failed to load chat history:', error)
      }
    },

    async handleImageUpload(event) {
      const file = event.target.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
          this.selectedImage = e.target.result;
        };
        reader.readAsDataURL(file);
      }
    },

    clearImage() {
      this.selectedImage = null;
      if (this.$refs.fileInput) {
        this.$refs.fileInput.value = '';
      }
    },

    async sendMessage() {
      if (!this.currentMessage.trim() && !this.selectedImage) return;

      try {
        this.isLoading = true;
        
        // 添加用户消息到对话
        const userMessage = {
          role: 'user',
          content: this.currentMessage,
          image: this.selectedImage,
          timestamp: new Date()
        }
        this.messages.push(userMessage)

        // 发送请求到后端
        const response = await axios.post('/api/chat', {
          message: this.currentMessage,
          image: this.selectedImage
        })

        // 添加AI响应到对话
        if (response.data.success) {
          const assistantMessage = {
            role: 'assistant',
            content: response.data.response,
            timestamp: new Date()
          }
          this.messages.push(assistantMessage)
        }

        // 清空输入
        this.currentMessage = ''
        this.clearImage()
        
        // 滚动到底部
        this.$nextTick(() => {
          const container = this.$refs.messagesContainer
          container.scrollTop = container.scrollHeight
        })

      } catch (error) {
        console.error('Chat error:', error)
        alert('Failed to send message. Please try again.')
      } finally {
        this.isLoading = false
      }
    }
  }
}
</script>

<style scoped>
.chat-interface {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.zone-title {
  padding: 12px 16px;
  font-weight: 500;
  color: #333;
  background: #f8f9fa;
  border-bottom: 1px solid #e0e0e0;
}

.interaction-history {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.message-box {
  margin-bottom: 1rem;
}

.sender {
  font-weight: 500;
  margin-bottom: 4px;
  color: #666;
}

.message-content {
  background: #f8f9fa;
  padding: 12px;
  border-radius: 8px;
  white-space: pre-wrap;
}

.message-content.assistant {
  background: #f0f7ff;
  border: 1px solid #e3f2fd;
}

.message-content.user {
  background: #f5f5f5;
  border: 1px solid #eeeeee;
}

.image-preview {
  margin-bottom: 8px;
}

.image-preview img {
  max-width: 200px;
  max-height: 200px;
  border-radius: 4px;
}

.instruction-zone {
  border-top: 1px solid #e0e0e0;
  background: white;
}

.input-area {
  padding: 16px;
}

.image-upload {
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-input {
  padding: 8px;
}

.no-file {
  color: #666;
}

.message-input {
  display: flex;
  gap: 12px;
}

textarea {
  flex: 1;
  padding: 12px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  resize: vertical;
  min-height: 60px;
  font-family: inherit;
  font-size: 14px;
}

textarea:focus {
  outline: none;
  border-color: #2196f3;
}

.send-button {
  align-self: flex-end;
  padding: 8px 24px;
  background: #2196f3;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  height: 40px;
  transition: background-color 0.2s;
}

.send-button:hover {
  background: #1976d2;
}

.send-button:disabled {
  background: #e0e0e0;
  cursor: not-allowed;
}

.clear-button {
  padding: 4px 12px;
  background: #f5f5f5;
  color: #666;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.clear-button:hover {
  background: #eeeeee;
}

/* 滚动条样式 */
.messages-container::-webkit-scrollbar {
  width: 6px;
}

.messages-container::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.messages-container::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: #999;
}

/* 添加时间戳样式 */
.message-timestamp {
  font-size: 0.8em;
  color: #666;
  margin-top: 4px;
}
</style> 