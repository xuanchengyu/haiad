<template>
  <div class="script-editor">
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else class="scenes-container">
      <div v-for="scene in scenes" :key="scene._id" class="scene-block">
        <div class="scene-header">
          <div class="time-range">
            <input 
              type="text" 
              v-model="scene.start_time"
              class="time-input"
              @click="$emit('seek', scene.start_time)"
              style="cursor: pointer"
            />
            <span class="time-separator">-</span>
            <input 
              type="text" 
              v-model="scene.end_time"
              class="time-input"
              @click="$emit('seek', scene.end_time)"
              style="cursor: pointer"
            />
          </div>
          <div class="scene-controls">
            <button @click="deleteScene(scene._id)" class="control-btn" title="Delete Scene">
              <span class="material-icons">delete</span>
            </button>
            <button @click="updateScene(scene)" class="control-btn" title="Save Scene">
              <span class="material-icons">save_as</span>
            </button>
            <button @click="addScene(scene._id, 'before')" class="control-btn" title="Add Scene Above">
              <span class="material-icons">arrow_upward</span>
            </button>
            <button @click="addScene(scene._id, 'after')" class="control-btn" title="Add Scene Below">
              <span class="material-icons">arrow_downward</span>
            </button>
          </div>
        </div>

        <textarea
          v-model="scene.description"
          class="scene-description"
          :placeholder="'Edit your script here...'"
          @focus="$emit('seek', scene.start_time)"
        ></textarea>
        
        <div class="speech-rate">
          <span>Speech Rate: {{ calculateSpeechRate(scene) }} WPM</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';
import { ElMessage } from 'element-plus';

export default {
  name: 'ScriptEditor',
  props: {
    scriptData: {
      type: Array,
      default: () => []
    },
    videoId: {
      type: String,
      required: true
    }
  },
  data() {
    return {
      scenes: [],
      loading: false,
      error: null
    }
  },
  methods: {
    parseTime(timeStr) {
      if (!timeStr) return 0;
      const [hours, minutes, seconds] = timeStr.split(':');
      const [secs, ms] = (seconds || '0.0').split('.');
      return parseInt(hours || 0) * 3600 + parseInt(minutes || 0) * 60 + parseInt(secs || 0) + parseInt(ms || 0) / 1000;
    },
    calculateSpeechRate(scene) {
      if (!scene || !scene.description) return 0;
      
      const wordCount = scene.description.trim().split(/\s+/).length;
      const startTime = this.parseTime(scene.start_time);
      const endTime = this.parseTime(scene.end_time);
      const duration = endTime - startTime;
      
      if (duration <= 0 || wordCount === 0) return 0;
      return Math.round((wordCount / duration) * 60);
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
          ElMessage.success('添加场景成功');
          this.$emit('update:script', this.scenes);
        } else {
          throw new Error(response.data.error || '添加失败');
        }
      } catch (error) {
        console.error('添加场景失败:', error);
        if (error.response?.status === 401) {
          this.$router.push('/login');
        } else {
          ElMessage.error(error.response?.data?.error || '添加场景失败');
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
          ElMessage.success('更新场景成功');
          this.$emit('update:script', this.scenes);
        } else {
          throw new Error(response.data.error || '更新失败');
        }
      } catch (error) {
        console.error('更新场景失败:', error);
        if (error.response?.status === 401) {
          this.$router.push('/login');
        } else {
          ElMessage.error(error.response?.data?.error || '更新场景失败');
        }
      }
    },

    async deleteScene(sceneId) {
      try {
        if (!confirm('确定要删除这个场景吗？')) {
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
            ElMessage.success('删除场景成功');
            this.$emit('update:script', this.scenes);
          }
        } else {
          throw new Error(response.data.error || '删除失败');
        }
      } catch (error) {
        console.error('删除场景失败:', error);
        if (error.response?.status === 401) {
          this.$router.push('/login');
        } else {
          ElMessage.error(error.response?.data?.error || '删除场景失败');
        }
      }
    }
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
  width: 100%;
  height: 100%;
  padding: 20px;
  overflow-y: auto;
}

.scenes-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

.scene-block {
  width: 100%;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 10px;
  background-color: #fff;
}

.scene-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.time-range {
  display: flex;
  align-items: center;
  gap: 10px;
}

.time-input {
  width: 100px;
  padding: 5px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-family: monospace;
}

.time-separator {
  color: #666;
}

.scene-description {
  width: 100%;
  min-height: 100px;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  resize: vertical;
  font-family: inherit;
  line-height: 1.5;
}

.scene-description:focus {
  outline: none;
  border-color: #2196f3;
}

.scene-controls {
  display: flex;
  gap: 5px;
}

.control-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: white;
  color: #666;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.material-icons {
  font-size: 18px;
}

/* 删除按钮 */
.control-btn:nth-child(1):hover {
  background-color: #ffebee;
  color: #f44336;
  border-color: #f44336;
}

/* 保存按钮 */
.control-btn:nth-child(2):hover {
  background-color: #e8f5e9;
  color: #4caf50;
  border-color: #4caf50;
}

/* 上下箭头按钮 */
.control-btn:nth-child(3):hover,
.control-btn:nth-child(4):hover {
  background-color: #e3f2fd;
  color: #2196f3;
  border-color: #2196f3;
}

.loading, .error {
  padding: 20px;
  text-align: center;
}

.error {
  color: red;
}

.speech-rate {
  margin: 5px 0;
  color: #666;
  font-size: 0.8em;
}
</style> 