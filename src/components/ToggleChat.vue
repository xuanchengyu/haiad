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
        <div class="nav-header">
          <h3>How about the description?</h3>
          <div class="tab-switcher">
            <button 
              @click="activeTab = 'request'"
              :class="{ 'active': activeTab === 'request' }"
            >
            Request AI description
            </button>
            <button 
              @click="activeTab = 'generate'"
              :class="{ 'active': activeTab === 'generate' }"
            >
            Giving your instructions
            </button>
          </div>
        </div>
        <button class="close-btn" @click="toggleAIChat">×</button>
      </div>

    <!-- 1. Request AI description -->
    <div v-if="activeTab === 'request'" class="control-panel">
      <div class="sentence-style-control">
        <h4 class="slider-title">What linguistic feature do you want?</h4>
        <div class="slider-container">
          <input
            type="range"
            v-model="sentenceStyle"
            min="0"
            max="10"
            step="1"
            class="style-slider"
          />
          <div class="slider-labels">
            <span class="label">Typical</span>
            <span class="label">Creative</span>
          </div>
        </div>

        <!-- 生成按钮 -->
        <button class="generate-btn" @click="handleRequest">
          <span class="icon-wrapper">
            <span class="material-icons">auto_awesome</span>
          </span>
          Generate descriptions
        </button>

        <!-- 显示返回的描述 -->
        <!-- <div v-if="descriptions && descriptions !== ''" class="descriptions-container">
          <h3>Generated Descriptions:</h3>
          <h4 class="slider-title" >{{ descriptions }}</h4>
        </div>-->
        
        <!-- <div v-if="description && description.length">
          <p v-for="(item, index) in descriptions" :key="index">{{ item }}</p>
        </div> -->
        <!-- 如果没有返回内容，显示加载中的提示 -->
        <!-- <div v-else>
          <p>正在加载</p>
        </div> -->

      <!-- <div class="generated-descriptions">
        <div v-if="description && description.length">
          <div v-for="(desc, index) in descriptions" :key="index" class="desc-item">
            {{ desc }}
          </div>
        </div>
        <div v-else>
          <p>正在加载.....</p>
        </div>
    </div> -->

        
        <!-- 底部说明 -->
        <p class="generate-tips">
          Press “Generate” button, forward linguistic feature,
          and current clip to AI, and recommend descriptions
        </p>
<!-- 
        <div v-for="(desc, index) in descriptions" :key="index" class="desc-item">
        <h4 class="slider-title">
          {{ desc }}
        </h4>
        </div> -->

        <!-- 替换原有的描述显示部分 -->
        <!-- <div v-if="isLoadingRequest" class="loading-indicator">
          <p>Generating...</p>
        </div> -->
        <div v-if="isLoadingRequest" class="loading-indicator">
  <div class="spinner-container">
    <div class="spinner"></div>
    <div class="spinner-blade"></div>
    <div class="spinner-blade"></div>
    <div class="spinner-blade"></div>
    <div class="spinner-blade"></div>
    <div class="spinner-blade"></div>
    <div class="spinner-blade"></div>
    <div class="spinner-blade"></div>
    <div class="spinner-blade"></div>
    <div class="spinner-blade"></div>
    <div class="spinner-blade"></div>
    <div class="spinner-blade"></div>
  </div>
  <p class="loading-text">Generating descriptions...</p>
</div>

        <!-- <div v-else>
          <div v-for="(desc, index) in descriptions" :key="index" class="desc-item">
            <h4 class="slider-title">{{ desc }}</h4>
          </div>
        </div> -->
        
        <div v-else>
          <div v-for="(desc, index) in descriptions" :key="index" class="desc-item">
            <button 
              @click="selectDescription(desc)" 
              class="desc-btn"
            >{{ desc }}</button>
          </div>
        </div>



      </div>
    </div>



      <!-- 2. Giving your instructions -->
      <div v-if="activeTab === 'generate'" class="control-panel">
      <div class="sentence-style-control">
        <h4 class="slider-title">What linguistic feature do you want?</h4>
        <div class="slider-container">
          <input
            type="range"
            v-model="sentenceStyle"
            min="0"
            max="10"
            step="1"
            class="style-slider"
            @input="updateSlider"
          />
          <div class="slider-labels">
            <span class="label">Typical</span>
            <span class="label">Creative</span>
          </div>
        </div>

        <!-- 新增提示文字 -->
        <p class="keyword-instruction">
          Let AI know other requirements for generating the description!
        </p>

        <!-- 新增四个风格按钮 -->
        <div class="keyword-buttons">
          <button 
            v-for="(btn, index) in keywordButtons" 
            :key="index"
            class="keyword-btn"
            :class="{ active: selectedKeywords.includes(btn.value) }"
            @click="toggleKeyword(btn.value)"
          >{{ btn.label }}</button>
        </div>

        <!-- 输入框 -->
        <div class="keyword-input-wrapper">
          <input
            v-model="generateKeywords"
            class="keyword-input"
            placeholder="Additional styles that need to be included..."
          />
        </div>

        <!-- 生成按钮 -->
        <button class="generate-btn" @click="handleGenerate">
          <span class="icon-wrapper">
            <span class="material-icons">auto_awesome</span>
          </span>
          Generate sentences
        </button>
        


        <!-- 底部说明文字 -->
        <p class="generate-tips">
          Press “Generate” button, forward linguistic feature, your requirements
          and current clip to AI, and recommend descriptions

        </p>

        
        <!-- 替换原有的描述显示部分 -->
        <!-- <div v-if="isLoadingGenerate" class="loading-indicator">
          <p>Generating...</p>
        </div> -->

        <div v-if="isLoadingGenerate" class="loading-indicator">
          <div class="spinner-container">
            <div class="spinner"></div>
            <div class="spinner-blade"></div>
            <div class="spinner-blade"></div>
            <div class="spinner-blade"></div>
            <div class="spinner-blade"></div>
            <div class="spinner-blade"></div>
            <div class="spinner-blade"></div>
            <div class="spinner-blade"></div>
            <div class="spinner-blade"></div>
            <div class="spinner-blade"></div>
            <div class="spinner-blade"></div>
            <div class="spinner-blade"></div>
          </div>
          <p class="loading-text">Generating descriptions...</p>
        </div>

        <!-- <div v-else>
          <div v-for="(desc, index) in descriptions_with_instru" :key="index" class="desc-item">
            <h4 class="slider-title">{{ desc }}</h4>
          </div>
        </div> -->

        <div v-else>
          <div v-for="(desc, index) in descriptions_with_instru" :key="index" class="desc-item">
            <button 
              @click="selectDescription(desc)" 
              class="desc-btn"
            >{{ desc }}</button>
          </div>
        </div>


<!-- 
        原来的
        <div v-for="(desc, index) in descriptions_with_instru" :key="index" class="desc-item">
        <h4 class="slider-title">
          {{ desc }}
        </h4>
        </div> -->

        <!-- <div v-if="description && description.length">
          <p v-for="(item, index) in descriptions" :key="index">{{ item }}</p>
        </div> -->
        <!-- 如果没有返回内容，显示加载中的提示 -->
        <!-- <div v-else>
          <p>正在加载</p>
        </div> -->

      </div>
    </div>

      <!-- <div v-for="(desc, index) in descriptions" :key="index" class="desc-item">
        <h4 class="slider-title">
          {{ desc }}
        </h4>
      </div> -->




      <!-- 聊天记录区（待删除） -->
      <div class="chat-history" ref="chatHistory">
        <div 
          v-for="(msg, index) in displayMessages" 
          :key="index"
          :class="['chat-message', msg.role]"
        >
          <div class="sender">{{ msg.role === 'assistant' ? 'ChatGPT:' : 'You:' }}</div>
          <div class="message-content">{{ msg.content }}</div>
        </div>
      </div>

      <!-- 消息输入区 -->
      <!-- <div class="chat-input">
        <input 
          v-model="userMessage"
          @keyup.enter="sendMessage"
          placeholder="Type your message..."
        />
        <button @click="sendMessage">Send</button>
      </div> -->
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
      isLoadingRequest: false, // 请求标签页加载状态
      isLoadingGenerate: false, // 指令标签页加载状态
      activeTab: 'generate',
      descriptions: '',
      userMessage: '',
      chatMessages: [],
      keywords: '',
      isLoading: false,
      sentenceStyle: 5,
      dialogPosition: {
        top: '0px',
        left: '0px'},
      selectedKeywords: [], // 存储选中关键词
      keywordButtons: [
        { label: 'Objective', value: 'Objective' },
        { label: 'Subjective', value: 'Subjective' },
        { label: 'Professional', value: 'Professional' },
        { label: 'Concise', value: 'Concise' }]
    }
  },
  computed: {
    displayMessages() {
      // 过滤掉系统消息，只显示用户和助手的消息
      return this.chatMessages.filter(msg => msg.role !== 'system');
    }
  },
  methods: {
      selectDescription(description) {
        // 触发事件并传递描述内容
        this.$emit('select-description', description, this.sceneId);
      },
    toggleKeyword(keyword) {
    const index = this.selectedKeywords.indexOf(keyword)
    if (index > -1) {
      this.selectedKeywords.splice(index, 1)
    } else {
      this.selectedKeywords.push(keyword)
    }
    this.updateKeywordsInput()
  },
  updateKeywordsInput() {
    this.generateKeywords = this.selectedKeywords.join(', ')
  },
        // 新增滑动条更新处理
        updateSlider(event) {
      this.sentenceStyle = parseInt(event.target.value);
    },
    // async loadSceneChatHistory() {
    //   try {
    //     const response = await axios.get('/api/ai/scene/chat/history', {
    //       params: {
    //         video_id: this.videoId,
    //         scene_id: this.sceneId
    //       }
    //     });
        
    //     if (response.data.success && response.data.history) {
    //       this.chatMessages = response.data.history.messages.map(msg => ({
    //         role: msg.role,
    //         content: msg.content,
    //         timestamp: new Date(msg.timestamp)
    //       }));
    //     }
    //   } catch (error) {
    //     console.error('Failed to load scene chat history:', error);
    //     ElMessage.error('Failed to load chat history');
    //   }
    // },
    toggleAIChat() {
      if (this.isActive) {
        this.store.setActiveChatId(null)
      } else {
        this.store.setActiveChatId(this.sceneId)
      }
      
      // if (this.isActive) {
      //   this.loadSceneChatHistory()
      // } else {
      //   this.chatMessages = []
      //   this.userMessage = ''
      // }
    },


    // 点击1. "generate description"
      async handleRequest() {
        try {
          this.isLoadingRequest = true; // 开始加载
          this.descriptions = []; // 清空之前的结果

          const sceneData = this.$parent.$parent.scenes.find(s => s._id === this.sceneId);
          const response = await axios.post('/api/ai/scene/description', {
            video_id: this.videoId,
            start_time: sceneData.start_time,
            end_time: sceneData.end_time,
            creativity: this.sentenceStyle // 0-10数值
          }, {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
          });
          
        if (response.data.success) {
          this.descriptions = response.data.descriptions;
        } else {
          this.descriptions = 'Error generating description';
        }
      } catch (error) {
        console.error('Error during API request:', error);
        this.description = 'Error generating description';
      }finally {
    this.isLoadingRequest = false; // 结束加载
      }
    },

    // 点击2. "generate description"
      async handleGenerate() {
        try {
          this.isLoadingGenerate = true; // 开始加载
          this.descriptions_with_instru = []; // 清空之前的结果

          const sceneData = this.$parent.$parent.scenes.find(s => s._id === this.sceneId);
          const response = await axios.post('/api/ai/scene/description2', {
            video_id: this.videoId,
            start_time: sceneData.start_time,
            end_time: sceneData.end_time,
            creativity: this.sentenceStyle,
            selected_keywords: this.selectedKeywords, // 用户选择的风格按钮
            additional_instructions: this.generateKeywords // 用户输入框内容
          }, {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
          });
          
          if (response.data.success) {
            this.descriptions_with_instru = response.data.descriptions;
          } else {
            this.descriptions_with_instru = ['Error generating description'];
          }
        } catch (error) {
          console.error('Error during API request:', error);
          this.descriptions_with_instru = ['Error generating description'];
        }finally {
    this.isLoadingGenerate = false; // 结束加载
  }
      },


    async sendMessage() {
      if ((!this.userMessage.trim() && !this.keywords.trim()) || this.isLoading) return;
      
      try {
        this.isLoading = true;
        
        // 验证必要参数
        const params = {
          video_id: this.videoId,
          scene_id: this.sceneId,
          current_text: this.currentText,
          user_message: this.userMessage,
          keywords: this.keywords, // 添加关键词参数
          style_level: this.sentenceStyle // 添加风格参数
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


.desc-btn {
  width: 100%;
  padding: 8px 12px;
  margin: 4px 0;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  background: #f8f9fa;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s;
}

   .desc-btn.selected {
     background: #2196f3;
     color: white;
     border-color: #2196f3;
   }


.desc-btn:hover {
  background: #e3f2fd;
  border-color: #2196f3;
}

/* 添加按钮样式 */
.keyword-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 12px 0;
}

.keyword-btn {
  padding: 6px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 16px;
  background: #f5f5f5;
  color: #333;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.keyword-btn:hover {
  background: #e0f2fe;
}

.keyword-btn.active {
  background: #2196f3;
  color: white;
  border-color: #2196f3;
}

/* 新增样式 */
.keyword-instruction {
  color: #666;
  font-size: 13px;
  margin: 16px 0 8px;
  line-height: 1.4;
}

.keyword-input-wrapper {
  margin: 12px 0;
}

.keyword-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  color: #333;
  transition: border-color 0.2s;
}

.keyword-input:focus {
  outline: none;
  border-color: #2196f3;
  box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.1);
}

.keyword-input::placeholder {
  color: #999;
}

.generate-btn {
  width: 100%;
  padding: 12px;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.generate-btn:hover {
  background: #f8f9fa;
  border-color: #2196f3;
}

.icon-wrapper {
  margin-right: 8px;
  display: flex;
  align-items: center;
}

.material-icons {
  font-size: 18px;
  color: #2196f3;
}

.generate-tips {
  text-align: center;
  color: #999;
  font-size: 12px;
  line-height: 1.5;
  margin: 16px 0 0;
  padding: 8px;
}
/* 新增核心控制区样式 */
.control-panel {
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
}

.sentence-style-control {
  margin-bottom: 20px;
}

.slider-title {
  color: #1d1d1f;
  font-size: 14px;
  margin: 0 0 12px 0;
  font-weight: 500;
}

.slider-container {
  position: relative;
  padding: 8px 0;
  margin: 16px 0 8px;

}

.style-slider {
  -webkit-appearance: none;
  width: 100%;
  height: 4px;
  background: #e5e7eb;
  border-radius: 2px;
  outline: none;
}

.style-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #2196f3;
  cursor: pointer;
  transition: transform 0.2s ease;
}

.style-slider::-webkit-slider-thumb:hover {
  transform: scale(1.1);
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
}

.slider-labels .label {
  color: #666;
  font-size: 12px;
  font-weight: 400;
}

/* 关键词输入样式 */
.keyword-input input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 14px;
  color: #1d1d1f;
}

.keyword-input input::placeholder {
  color: #999;
}

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


/* 新增样式 */
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
  background: #f9fafb;
  width: 100%;
}

.nav-header {
  flex-grow: 1;
}

h3 {
  margin: 0 0 8px 0;
  font-size: 16px;
  color: #1d1d1f;
  font-weight: 600;
}

.tab-switcher {
  display: flex;
  gap: 20px;
}

.tab-switcher button {
  border: none;
  background: none;
  padding: 8px 0;
  color: #666;
  cursor: pointer;
  font-size: 14px;
  position: relative;
  transition: color 0.2s ease;
}

.tab-switcher button.active {
  color: #1d1d1f;
  font-weight: 500;
}

.tab-switcher button.active::after {
  content: '';
  position: absolute;
  bottom: -4px;
  left: 0;
  right: 0;
  height: 2px;
  background-color: #2196f3;
  animation: underline 0.3s ease;
}

@keyframes underline {
  from { transform: scaleX(0); }
  to { transform: scaleX(1); }
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



.loading-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 0;
  margin: 20px 0;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.spinner-container {
  position: relative;
  width: 50px;
  height: 50px;
  margin-bottom: 16px;
}

.spinner {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 3px solid rgba(33, 150, 243, 0.1);
  border-radius: 50%;
}

.spinner-blade {
  position: absolute;
  top: 0;
  left: 50%;
  width: 6px;
  height: 15px;
  margin-left: -3px;
  background: #2196f3;
  border-radius: 4px;
  opacity: 0;
  animation: spinner-fade 1s linear infinite;
}

.spinner-blade:nth-child(2) { transform: rotate(30deg); animation-delay: -0.916s; }
.spinner-blade:nth-child(3) { transform: rotate(60deg); animation-delay: -0.833s; }
.spinner-blade:nth-child(4) { transform: rotate(90deg); animation-delay: -0.75s; }
.spinner-blade:nth-child(5) { transform: rotate(120deg); animation-delay: -0.666s; }
.spinner-blade:nth-child(6) { transform: rotate(150deg); animation-delay: -0.583s; }
.spinner-blade:nth-child(7) { transform: rotate(180deg); animation-delay: -0.5s; }
.spinner-blade:nth-child(8) { transform: rotate(210deg); animation-delay: -0.416s; }
.spinner-blade:nth-child(9) { transform: rotate(240deg); animation-delay: -0.333s; }
.spinner-blade:nth-child(10) { transform: rotate(270deg); animation-delay: -0.25s; }
.spinner-blade:nth-child(11) { transform: rotate(300deg); animation-delay: -0.166s; }
.spinner-blade:nth-child(12) { transform: rotate(330deg); animation-delay: -0.083s; }

@keyframes spinner-fade {
  0% { opacity: 0.1; }
  50% { opacity: 1; }
  100% { opacity: 0.1; }
}

.loading-text {
  font-size: 14px;
  color: #2196f3;
  font-weight: 500;
  letter-spacing: 0.5px;
  text-align: center;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0% { opacity: 0.6; }
  50% { opacity: 1; }
  100% { opacity: 0.6; }
}

</style>
