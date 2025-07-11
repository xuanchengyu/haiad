<template>
  <div class="script-editor">
    <!-- <div v-if="loading" class="loading">Loading...</div> -->
    <!-- <div v-else-if="error" class="error">{{ error }}</div> -->
    <div class="scenes-container">
      <div v-for="scene in scenes" :key="scene._id" class="scene-block">
        <div class="scene-header">
          <div class="time-range">
            <!-- 通过 v-model 双向绑定到 scene 对象的 start_time 和 end_time 属性 -->
            <input 
              type="text" 
              v-model="scene.start_time"
              class="time-input"
              @click="$emit('seek', scene.start_time)"
            />
            <span class="time-separator">-</span>
            <input 
              type="text" 
              v-model="scene.end_time"
              class="time-input"
              @click="$emit('seek', scene.end_time)"
            />
          </div>
          <div class="scene-controls">
            <button @click="deleteScene(scene._id)" class="control-btn" title="Delete Scene">
              <span class="material-icons">delete</span>
            </button>
            <button @click="updateScene(scene)" class="control-btn" title="Save Scene">
              <span class="material-icons">save</span>
            </button>
            <button @click="addScene(scene._id, 'before')" class="control-btn" title="Add Scene Above">
              <span class="material-icons">arrow_upward</span>
            </button>
            <button @click="addScene(scene._id, 'after')" class="control-btn" title="Add Scene Below">
              <span class="material-icons">arrow_downward</span>
            </button>
            <ToggleChat 
              mode="collaborative"
              :video-id="videoId"
              :scene-id="scene._id"
              :current-text="scene.description"
              @select-description="handleDescriptionSelect"
            />
          </div>
        </div>

        <div class="scene-content">
          <textarea
            v-model="scene.description"
            class="scene-description"
            :placeholder="'Edit your script here...'"
          ></textarea>
        </div>
<!--         
        <div class="speech-rate">
          <span>Speech Rate: {{ calculateSpeechRate(scene) }} WPM</span>
        </div> -->
      </div>
    </div>
  </div>
</template>

<script>
import axios from '@/main';
import { ElMessage } from 'element-plus';
import ToggleChat from './ToggleChat.vue';

export default {
  name: 'ScriptEditor',
  components: {
    ToggleChat
  },
  props: {
    scriptData: {
      type: Array,
      default: () => []
    },
    videoId: {
      type: String,
      required: true
    },
    mode: {
      type: String,
      required: true,
      validator: value => ['collaborative', 'ai-assisted'].includes(value)
    }
  },
  data() {
    return {
      scenes: [],
      loading: false,
      error: null
    }
  },
  // mounted() {
  //   console.log('ScriptEditor mounted with:', {
  //     videoId: this.videoId,
  //     scenes: this.scenes
  //   });
  // },
  methods: {
    parseTime(timeStr) {
      if (!timeStr) return 0;
      const [hours, minutes, seconds] = timeStr.split(':');
      const [secs, ms] = (seconds || '0.0').split('.');
      return parseInt(hours || 0) * 3600 + parseInt(minutes || 0) * 60 + parseInt(secs || 0) + parseInt(ms || 0) / 1000;
    },

    handleDescriptionSelect(description, sceneId) {
  // 找到对应的场景
  const scene = this.scenes.find(s => s._id === sceneId);
  if (scene) {
    // 追加描述到现有内容（保留原有内容并在后面添加新内容）
    if (scene.description) {
      // 如果已有内容，先添加一个换行再追加新内容
      scene.description += '\n' + description;
    } else {
      // 如果原本没有内容，直接赋值
      scene.description = description;
    }
    
    // 自动保存更新
    // this.updateScene(scene);
    
    // 可选：显示成功消息
    ElMessage.success('Successfully added description!');
  }
},
    async addScene(sceneId, position) {
      try {
        const token = localStorage.getItem('token');
        if (!token) {
          this.$router.push('/login');
          return;
        }

        const newScene = {
          scene_number: `${this.scenes.length + 1}`,
          start_time: '00:00:00.000',
          end_time: '00:00:00.000',
          description: ''
        };
        
        const referenceIndex = this.scenes.findIndex(s => s._id === sceneId);
        const insertIndex = position === 'before' ? referenceIndex : referenceIndex + 1;
        
        const response = await axios.post(
          `/api/videos/${this.videoId}/scenes`,
          {
            ...newScene,
            position,
            index: insertIndex
          },
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          }
        );
        
        if (response.data.success) {
          this.scenes.splice(insertIndex, 0, response.data.scene);
          ElMessage.success('Add success');
          this.$emit('update:script', this.scenes);
        } else {
          throw new Error(response.data.error || 'Add failed');
        }
      } catch (error) {
        console.error('Add failed:', error);
        if (error.response?.status === 401) {
          this.$router.push('/login');
        } else {
          ElMessage.error(error.response?.data?.error || 'Add failed');
        }
      }
    },

    async updateScene(scene) {
      try {
        const token = localStorage.getItem('token');
        if (!token) {
          this.$router.push('/login');
          return;
        }

        const response = await axios.put(
          `/api/videos/${this.videoId}/scenes/${scene._id}`,
          {
            scene_number: scene.scene_number,
            start_time: scene.start_time,
            end_time: scene.end_time,
            description: scene.description
          },
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          }
        );
        
        if (response.data.success) {
          ElMessage.success('Update success');
          this.$emit('update:script', this.scenes);
        } else {
          throw new Error(response.data.error || 'Update failed');
        }
      } catch (error) {
        console.error('Update failed:', error);
        if (error.response?.status === 401) {
          this.$router.push('/login');
        } else {
          ElMessage.error(error.response?.data?.error || 'Update failed');
        }
      }
    },

    async deleteScene(sceneId) {
      try {
        if (!confirm('Are you sure you want to delete this line?')) {
          return;
        }

        const token = localStorage.getItem('token');
        if (!token) {
          this.$router.push('/login');
          return;
        }

        const response = await axios.delete(
          `/api/videos/${this.videoId}/scenes/${sceneId}`,
          {
            headers: {
              'Authorization': `Bearer ${token}`
            }
          }
        );
        
        if (response.data.success) {
          const index = this.scenes.findIndex(s => s._id === sceneId);
          if (index > -1) {
            this.scenes.splice(index, 1);
            ElMessage.success('Delete success');
            this.$emit('update:script', this.scenes);
          }
        } else {
          throw new Error(response.data.error || 'Delete failed');
        }
      } catch (error) {
        console.error('Delete scene failed:', error);
        if (error.response?.status === 401) {
          this.$router.push('/login');
        } else {
          ElMessage.error(error.response?.data?.error || 'Delete failed');
        }
      }
    },

    // async handleAIChat(scene, userMessage) {
    //   try {
    //     console.log('Handle AI chat:', {
    //       scene,
    //       userMessage
    //     });
        
    //     if (!scene || !scene._id) {
    //       throw new Error('Invalid scene data');
    //     }

    //     const response = await axios.post('/api/ai/scene/chat', {
    //       video_id: this.videoId,
    //       scene_id: scene._id,
    //       current_text: scene.description,
    //       user_message: userMessage
    //     }, {
    //       headers: {
    //         'Authorization': `Bearer ${localStorage.getItem('token')}`
    //       }
    //     });

    //     if (response.data.success) {
    //       return response.data.chat_history;
    //     } else {
    //       const errorMsg = response.data.error || 'AI processing failed';
    //       console.error('AI processing failed:', errorMsg);
    //       ElMessage.error(errorMsg);
    //     }
    //   } catch (error) {
    //     console.error('AI chat failed:', error);
    //     ElMessage.error(error.message || 'AI chat failed');
    //   }
    // }
  },
  
  watch: {
    scriptData: {
      immediate: true,
      handler(newValue) {
        if (Array.isArray(newValue)) {
          this.scenes = newValue.map(scene => ({
            ...scene,
            _id: scene._id || ''
          }));
        }
      }
    }
  }
}
</script>

<style scoped>
.script-editor {
  position: relative;
  overflow: visible;
  width: 100%;
  height: 100%;
  padding: 20px;
}

.scenes-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
  width: 100%;
}

.scene-block {
  width: 100%;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  background-color: #fff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.scene-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
  width: 100%;
  margin-bottom: 16px;
}

.time-range {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 1;
  min-width: 0;
}

.time-input {
  width: 120px;
  min-width: 100px;
  padding: 8px 4px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-family: 'Roboto Mono', monospace;
  font-size: 13px;
  text-align: center;
  letter-spacing: 0px;
}

.time-separator {
  padding: 0 2px;
}

.scene-content {
  margin-bottom: 8px;
}

.scene-description {
  width: 100%;
  min-height: 120px;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  resize: vertical;
  font-family: inherit;
  line-height: 1.6;
  font-size: 15px;
  color: #1f2937;
  background: #f9fafb;
  transition: all 0.2s ease;
}

.scene-description:hover {
  border-color: #d1d5db;
}

.scene-description:focus {
  outline: none;
  border-color: #3b82f6;
  background: white;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.scene-controls {
  display: flex;
  gap: 4px;
  align-items: center;
  flex-wrap: nowrap;
  flex-shrink: 0;
}

.control-btn {
  width: 32px;
  height: 32px;
  padding: 4px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background-color: white;
  color: #6b7280;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.control-btn:hover {
  background-color: #f3f4f6;
  border-color: #d1d5db;
}

/* 删除按钮 */
.control-btn:nth-child(1):hover {
  background-color: #fef2f2;
  color: #dc2626;
  border-color: #fecaca;
}

/* 保存按钮 */
.control-btn:nth-child(2):hover {
  background-color: #ecfdf5;
  color: #059669;
  border-color: #a7f3d0;
}

/* 上下箭头按钮 */
.control-btn:nth-child(3):hover,
.control-btn:nth-child(4):hover {
  background-color: #eff6ff;
  color: #3b82f6;
  border-color: #bfdbfe;
}

.material-icons {
  font-size: 20px;
}

.speech-rate {
  margin-top: 8px;
  color: #6b7280;
  font-size: 14px;
  padding: 4px 8px;
  background: #f3f4f6;
  border-radius: 4px;
  display: inline-block;
}

/* 占位符文本样式 */
.scene-description::placeholder {
  color: #9ca3af;
  font-style: italic;
}

/* 加载和错误状态 */
.loading, .error {
  padding: 40px;
  text-align: center;
  border-radius: 12px;
  background: #f9fafb;
}

.error {
  color: #dc2626;
  background: #fef2f2;
}

/* 响应式调整 */
@media (max-width: 600px) {
  .time-input {
    width: 110px;
    min-width: 90px;
    font-size: 12px;
    padding: 6px 2px;
  }
  
  .control-btn {
    width: 28px;
    height: 28px;
    padding: 3px;
  }
  
  .scene-controls {
    gap: 2px;
  }
  
  .material-icons {
    font-size: 18px;
  }
}

@media (max-width: 480px) {
  .time-input {
    width: 100px;
    min-width: 80px;
    font-size: 11px;
  }
  
  .control-btn {
    width: 26px;
    height: 26px;
  }
  
  .material-icons {
    font-size: 16px;
  }
}
</style> 
