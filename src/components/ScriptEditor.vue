<template>
  <div class="script-editor">
    <!-- <div v-if="loading" class="loading">Loading...</div> -->
    <!-- <div v-else-if="error" class="error">{{ error }}</div> -->
    <div class="scenes-container">
      <div v-for="scene in scenes" :key="scene._id" class="scene-block">
        <div class="scene-header">
          <div class="time-range">
            <!-- 通过 v-model 双向绑定到 scene 对象的 start_time 和 end_time 属性 -->
            <div class="time-group">
              <input
                class="time-part"
                maxlength="2"
                v-model="scene.start_h"
                @input="onTimeInput($event, scene, 'start', 0); scheduleAutoSave(scene)"
                @keydown="onTimeKeydown($event, scene, 'start', 0)"
                @paste="onTimePaste($event, scene, 'start')"
                :ref="'start_h_' + scene._id"
              />
              <span class="timecode-separator">:</span>
              <input
                class="time-part"
                maxlength="2"
                v-model="scene.start_m"
                @input="onTimeInput($event, scene, 'start', 1); scheduleAutoSave(scene)"
                @keydown="onTimeKeydown($event, scene, 'start', 1)"
                :ref="'start_m_' + scene._id"
              />
              <span class="timecode-separator">:</span>
              <input
                class="time-part"
                maxlength="2"
                v-model="scene.start_s"
                @input="onTimeInput($event, scene, 'start', 2); scheduleAutoSave(scene)"
                @keydown="onTimeKeydown($event, scene, 'start', 2)"
                :ref="'start_s_' + scene._id"
              />
              <span class="timecode-separator">.</span>
              <input
                class="time-part ms"
                maxlength="3"
                v-model="scene.start_ms"
                @input="onTimeInput($event, scene, 'start', 3); scheduleAutoSave(scene)"
                @keydown="onTimeKeydown($event, scene, 'start', 3)"
                :ref="'start_ms_' + scene._id"
              />
            </div>
            <span class="time-range-separator">-</span>
            <div class="time-group">
              <input
                class="time-part"
                maxlength="2"
                v-model="scene.end_h"
                @input="onTimeInput($event, scene, 'end', 0); scheduleAutoSave(scene)"
                @keydown="onTimeKeydown($event, scene, 'end', 0)"
                @paste="onTimePaste($event, scene, 'end')"
                :ref="'end_h_' + scene._id"
              />
              <span class="timecode-separator">:</span>
              <input
                class="time-part"
                maxlength="2"
                v-model="scene.end_m"
                @input="onTimeInput($event, scene, 'end', 1); scheduleAutoSave(scene)"
                @keydown="onTimeKeydown($event, scene, 'end', 1)"
                :ref="'end_m_' + scene._id"
              />
              <span class="timecode-separator">:</span>
              <input
                class="time-part"
                maxlength="2"
                v-model="scene.end_s"
                @input="onTimeInput($event, scene, 'end', 2); scheduleAutoSave(scene)"
                @keydown="onTimeKeydown($event, scene, 'end', 2)"
                :ref="'end_s_' + scene._id"
              />
              <span class="timecode-separator">.</span>
              <input
                class="time-part ms"
                maxlength="3"
                v-model="scene.end_ms"
                @input="onTimeInput($event, scene, 'end', 3); scheduleAutoSave(scene)"
                @keydown="onTimeKeydown($event, scene, 'end', 3)"
                :ref="'end_ms_' + scene._id"
              />
            </div>
            <button class="play-btn" @click="handlePlaySegment(scene)" title="play">
              <span class="material-icons">play_arrow</span>
            </button>
          </div>
          <div class="scene-controls">
            <button @click="deleteScene(scene._id)" class="control-btn" title="Delete">
              <span class="material-icons">delete</span>
            </button>
            <button @click="updateScene(scene)" class="control-btn" title="Save">
              <span class="material-icons">save</span>
            </button>
            <button @click="addScene(scene._id, 'before')" class="control-btn" title="Insert above">
              <span class="material-icons">arrow_upward</span>
            </button>
            <button @click="addScene(scene._id, 'after')" class="control-btn" title="Insert below">
              <span class="material-icons">arrow_downward</span>
            </button>
            <ToggleChat 
              mode="collaborative"
              :video-id="videoId"
              :scene-id="scene._id"
              :current-text="scene.description"
              @select-description="handleDescriptionSelect"
              @force-save-scene="handleForceSaveScene"
              ref="toggleChat"
            />
          </div>
        </div>

        <div class="scene-content">
          <textarea
            v-model="scene.description"
            class="scene-description"
            :placeholder="'Edit your script here...'"
            @input="scheduleAutoSave(scene)"
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
      error: null,
      timeAllSelected: false, // 标记是否全选
      // 自动保存相关
      autoSaveTimer: null,
      autoSaveDelay: 2000, // 2秒后自动保存
      lastSavedData: null
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

    // 处理强制保存场景
    async handleForceSaveScene(sceneId) {
      console.log('Force saving scene:', sceneId);
      const scene = this.scenes.find(s => s._id === sceneId);
      if (scene) {
        // 清除自动保存定时器
        if (this.autoSaveTimer) {
          clearTimeout(this.autoSaveTimer);
          this.autoSaveTimer = null;
        }
        
        // 直接调用updateScene方法强制保存
        await this.updateScene(scene);
        console.log('Scene force saved successfully');
        

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
          start_h: '00', start_m: '00', start_s: '00', start_ms: '000',
          end_h: '00', end_m: '00', end_s: '00', end_ms: '000',
          description: ''
        };
        this.mergeTimeFields(newScene);
        
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
          console.log('=== New scene added ===');
          console.log('response.data.scene:', response.data.scene);
          console.log('response.data.scene._id:', response.data.scene._id);
          console.log('response.data.scene._id type:', typeof response.data.scene._id);
          
          this.scenes.splice(insertIndex, 0, response.data.scene);
          
          console.log('=== Updated scenes array ===');
          console.log('this.scenes:', this.scenes);
          console.log('scenes with IDs:', this.scenes.map(s => ({ id: s._id, type: typeof s._id })));
          
          // 强制更新DOM，确保新场景的事件绑定正确
          this.$nextTick(() => {
            console.log('=== DOM updated, checking event bindings ===');
            // 验证新场景的时间轴输入框是否存在
            const newScene = this.scenes[insertIndex];
            console.log('New scene in DOM:', newScene);
          });
          
          ElMessage.success('Insert success');
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
      console.log('=== updateScene called ===');
      this.mergeTimeFields(scene);
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
          console.log('Update success for scene:', scene._id);
          ElMessage.success('saved');
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

    // 自动保存方法
    scheduleAutoSave(scene) {
      console.log('=== scheduleAutoSave triggered ===');
      console.log('scene object:', scene);
      console.log('scene._id:', scene._id);
      console.log('scene._id type:', typeof scene._id);
      console.log('scene description:', scene.description);
      console.log('all scenes:', this.scenes.map(s => ({ id: s._id, desc: s.description })));
      
      // 验证场景对象
      if (!scene || !scene._id) {
        console.error('Invalid scene object:', scene);
        return;
      }
      
      // 清除之前的定时器
      if (this.autoSaveTimer) {
        clearTimeout(this.autoSaveTimer);
      }
      
      // 设置新的自动保存定时器
      this.autoSaveTimer = setTimeout(() => {
        this.performAutoSave(scene);
      }, this.autoSaveDelay);
    },

    async performAutoSave(scene) {
      console.log('=== performAutoSave called ===');
      this.mergeTimeFields(scene);
      
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
          console.log('Auto save successful for scene:', scene._id);
          this.lastSavedData = JSON.stringify(scene);
        } else {
          console.error('Auto save failed:', response.data.error);
        }
      } catch (error) {
        console.error('Auto save failed:', error);
        if (error.response?.status === 401) {
          this.$router.push('/login');
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
    onTimeInput(e, scene, type, idx) {
      console.log('=== onTimeInput triggered ===');
      console.log('scene:', scene);
      console.log('scene._id:', scene._id);
      console.log('type:', type, 'idx:', idx);
      console.log('event target value:', e.target.value);
      
      const fields = [`${type}_h`, `${type}_m`, `${type}_s`, `${type}_ms`];
      let val = e.target.value.replace(/\D/g, '');
      if (idx < 3) val = val.slice(0, 2);
      else val = val.slice(0, 3);
      scene[fields[idx]] = val;

      // 单框智能输入
      if (idx === 0 && val.length > 2) {
        let full = val.padStart(7, '0');
        scene[fields[0]] = full.slice(0, 2);
        scene[fields[1]] = full.slice(2, 4);
        scene[fields[2]] = full.slice(4, 6);
        scene[fields[3]] = full.slice(6, 9);
        const refEl = this.$refs[fields[3] + '_' + scene._id];
        if (Array.isArray(refEl)) {
          refEl[0] && refEl[0].focus && refEl[0].focus();
        } else if (refEl && refEl.focus) {
          refEl.focus();
        }
        // 触发自动保存
        this.scheduleAutoSave(scene);
        return;
      }

      // 自动跳转
      if ((idx < 3 && val.length === 2) || (idx === 3 && val.length === 3)) {
        if (idx < 3) {
          const refEl = this.$refs[fields[idx + 1] + '_' + scene._id];
          if (Array.isArray(refEl)) {
            refEl[0] && refEl[0].focus && refEl[0].focus();
          } else if (refEl && refEl.focus) {
            refEl.focus();
          }
        }
      }
      
      // 触发自动保存
      this.scheduleAutoSave(scene);
    },
    onTimeKeydown(e, scene, type, idx) {
      const fields = [`${type}_h`, `${type}_m`, `${type}_s`, `${type}_ms`];
      if (e.key === 'Backspace' && !scene[fields[idx]] && idx > 0) {
        const refEl = this.$refs[fields[idx - 1] + '_' + scene._id];
        if (Array.isArray(refEl)) {
          refEl[0] && refEl[0].focus && refEl[0].focus();
        } else if (refEl && refEl.focus) {
          refEl.focus();
        }
      }
      if (e.key === 'ArrowLeft' && idx > 0) {
        const refEl = this.$refs[fields[idx - 1] + '_' + scene._id];
        if (Array.isArray(refEl)) {
          refEl[0] && refEl[0].focus && refEl[0].focus();
        } else if (refEl && refEl.focus) {
          refEl.focus();
        }
        e.preventDefault();
      }
      if (e.key === 'ArrowRight' && idx < 3) {
        const refEl = this.$refs[fields[idx + 1] + '_' + scene._id];
        if (Array.isArray(refEl)) {
          refEl[0] && refEl[0].focus && refEl[0].focus();
        } else if (refEl && refEl.focus) {
          refEl.focus();
        }
        e.preventDefault();
      }
    },
    onTimePaste(e, scene, type) {
      const text = (e.clipboardData || window.clipboardData).getData('text');
      const match = text.match(/^(\d{2}):(\d{2}):(\d{2})[.,](\d{1,3})$/);
      if (match) {
        e.preventDefault();
        scene[`${type}_h`] = match[1];
        scene[`${type}_m`] = match[2];
        scene[`${type}_s`] = match[3];
        scene[`${type}_ms`] = match[4].padEnd(3, '0');
        
        // 触发自动保存
        this.scheduleAutoSave(scene);
        
        const refEl = this.$refs[`${type}_ms_${scene._id}`];
        if (Array.isArray(refEl)) {
          refEl[0] && refEl[0].focus && refEl[0].focus();
        } else if (refEl && refEl.focus) {
          refEl.focus();
        }
      }
    },
    mergeTimeFields(scene) {
      scene.start_time = `${scene.start_h}:${scene.start_m}:${scene.start_s}.${scene.start_ms}`;
      scene.end_time = `${scene.end_h}:${scene.end_m}:${scene.end_s}.${scene.end_ms}`;
    },
    handlePlaySegment(scene) {
      this.mergeTimeFields(scene);
      this.$emit('play-segment', scene.start_time, scene.end_time);
    },
  },
  
  beforeUnmount() {
    // 清理自动保存定时器
    if (this.autoSaveTimer) {
      clearTimeout(this.autoSaveTimer);
    }
  },
  
  watch: {
    scriptData: {
      immediate: true,
      handler(newValue) {
        if (Array.isArray(newValue)) {
          this.scenes = newValue.map(scene => {
            // 拆分 start_time
            let [sh, sm, ssms] = (scene.start_time || '00:00:00.000').split(':');
            let [ss, sms] = (ssms || '00.000').split('.');
            // 拆分 end_time
            let [eh, em, esms] = (scene.end_time || '00:00:00.000').split(':');
            let [es, ems] = (esms || '00.000').split('.');
            return {
              ...scene,
              start_h: sh || '00',
              start_m: sm || '00',
              start_s: ss || '00',
              start_ms: sms || '000',
              end_h: eh || '00',
              end_m: em || '00',
              end_s: es || '00',
              end_ms: ems || '000',
              _id: scene._id || ''
            };
          });
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
  position: relative;
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
}
.time-range-separator {
  color: #888;
  font-size: 12px;
  margin: 0 0.5px;
  user-select: none;
  font-family: 'Roboto Mono', 'Menlo', 'Consolas', monospace;
}

.time-group {
  display: flex;
  align-items: center;
  gap: 0;
  background: transparent;
  border-radius: 5px;
  border: 1.2px solid #e0e0e0;
  padding: 0 2px;
}

.time-part {
  width: 1.3em;
  height: 2em;
  background: transparent;
  border: none;
  color: #222;
  text-align: center;
  font-size: 12px;
  font-family: 'Roboto Mono', 'Menlo', 'Consolas', monospace;
  font-weight: 500;
  letter-spacing: 0;
  outline: none;
  margin: 0 0;
  padding: 5px 0;
  box-sizing: border-box;
}
.time-part.ms {
  width: 2em;
}

.timecode-separator {
  font-size: 12px;
  font-family: 'Roboto Mono', 'Menlo', 'Consolas', monospace;
  font-weight: 500;
  color: #aaa;
  margin: 0 0;
  user-select: none;
  letter-spacing: 0;
}

/* .time-separator {
  padding: 0 0;
} */

.scene-content {
  margin-bottom: 8px;
}

.scene-description {
  width: 100%;
  min-height: 140px;
  padding: 14px;
  border: none;                /* 去掉边框 */
  border-radius: 8px;          /* 圆角可保留 */
  background: #f7f7fa;   /* 一直有淡灰色背景 */
  font-family: inherit;
  line-height: 1.6;
  font-size: 14px;
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
  width: 28px;
  height: 28px;
  padding: 2px;
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
  font-size: 16px;
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

.play-btn {
  width: 24px;
  height: 24px;
  padding: 0;
  margin: 0 4px;
  border: none;
  background: none;
  color: #047ebf;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 50%;
  transition: background 0.2s;
}
.play-btn:hover {
  background: #e3f2fd;
}
.play-btn .material-icons {
  font-size: 16px;
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
