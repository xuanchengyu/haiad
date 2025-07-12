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
          <div class="wpm-bottom">
            <span 
              class="wpm-icon-label"
              :class="{
                'normal-rate': calculateSpeechRate(scene) <= 160, 
                'high-rate': calculateSpeechRate(scene) > 160
              }"
            >
              <span class="material-icons wpm-icon">speed</span>
              {{ calculateSpeechRate(scene) }} wpm
            </span>
          </div>
        </div>
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
    calculateSpeechRate(scene) {
      // 计算时间差（秒）
      const startSeconds = this.parseTime(scene.start_time);
      const endSeconds = this.parseTime(scene.end_time);
      const durationSeconds = endSeconds - startSeconds;
      
      if (durationSeconds <= 0) return 0;  // 避免除以0
      
      // 计算字数（按空格分割单词）
      const wordCount = scene.description.trim().split(/\s+/).length;
      
      // 计算每分钟字数（WPM）
      const minutes = durationSeconds / 60;
      const wpm = Math.round(wordCount / minutes);
      
      return isFinite(wpm) ? wpm : 0;  // 处理无效值
    },
    parseTime(timeStr) {
      if (!timeStr) return 0;
      const [hours, minutes, seconds] = timeStr.split(':');
      const [secs, ms] = (seconds || '0.0').split('.');
      return parseInt(hours || 0) * 3600 + parseInt(minutes || 0) * 60 + parseInt(secs || 0) + parseInt(ms || 0) / 1000;
    },

    handleDescriptionSelect(description, sceneId) {
      const scene = this.scenes.find(s => s._id === sceneId);
      if (scene) {
        // 追加描述
        if (scene.description) {
          scene.description += '\n' + description;
        } else {
          scene.description = description;
        }
        
        // // 计算语速（WPM）
        // const wordCount = description.trim().split(/\s+/).length;
        // const minutes = generationTime / (1000 * 60); // 毫秒转分钟
        // const wpm = Math.round(wordCount / minutes);
        
        // // 更新场景的语速信息（如果需要保存）
        // // 这里可以添加逻辑将wpm保存到场景对象中
        
        // ElMessage.success('Successfully added description!');
        
        // // 强制更新视图以显示新计算的语速
        // this.$forceUpdate();
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
          ElMessage.success('successfully saved');
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
.wpm-bottom {
  text-align: right;
  margin-top: 4px;
  min-height: 18px;
}
.wpm-icon-label {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 500;
  color: #10b981;
  gap: 3px;
  background: none;
  border-radius: 8px;
  padding: 0 4px;
  transition: color 0.2s;
}
.wpm-icon {
  font-size: 14px;
  vertical-align: middle;
  margin-right: 2px;
}
.wpm-icon-label.normal-rate {
  color: #10b981;
}
.wpm-icon-label.high-rate {
  color: #ef4444;
}


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
  border: none;                /* 去掉边框 */
  border-radius: 8px;          /* 圆角可保留 */
  background: #f7f7fa;   /* 一直有淡灰色背景 */
  font-family: inherit;
  line-height: 1.6;
  font-size: 15px;
  color: #1f2937;
  box-shadow: none;            /* 去掉阴影 */
  resize: vertical;
  transition: background 0.2s, box-shadow 0.2s;
  outline: none;               /* 去掉默认高亮 */
}
.scene-description:focus {
  background: #f7f7fa;   /* 保持一致 */
  box-shadow: 0 0 0 2px #e3e8f0;
}
.scene-description::placeholder {
  color: #b0b8c9;
  font-style: italic;
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
