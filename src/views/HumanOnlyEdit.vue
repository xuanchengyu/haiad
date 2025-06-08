<!-- 人工编辑模式 -->
<template>
  <div class="app-container">
    <header class="header">
      <div class="header-left">
        <button @click="goBack" class="back-btn">
          Back
        </button>
        <h1>Human-Only Writing</h1>
      </div>
      <div class="header-buttons">
        <button 
          @click="saveScript"
          :disabled="!videoId || isSaving"
          class="save-btn"
        >
          {{ isSaving ? 'Saving...' : 'Save' }}
        </button>
        <button 
          @click="downloadScript"
          :disabled="!script"
          class="download-button"
        >
          Download
        </button>
      </div>
    </header>

    <main class="main-content">
      <div class="video-section">
        <video-player 
          :videoUrl="videoData.video_url"
          ref="videoPlayer"
        />
      </div>

      <div class="script-section">
        <div class="script-editor">
          <textarea
            v-model="script"
            class="script-textarea"
            placeholder="Enter the audio description script here..."
            @input="handleScriptChange"
          ></textarea>
        </div>
      </div>
    </main>
  </div>
</template>

<script>
import axios from '@/main'
import VideoPlayer from '@/components/VideoPlayer.vue'
import { ElMessage } from 'element-plus'

export default {
  name: 'HumanOnlyEdit',
  components: {
    VideoPlayer
  },
  data() {
    return {
      videoId: '',
      script: '',
      isSaving: false,
      isLoading: false,
      hasUnsavedChanges: false,
      videoData: {
        video_url: ''
      }
    }
  },
  async created() {
    this.videoId = this.$route.params.id;
    await this.loadVideoData();
    await this.loadScript();
  },
  methods: {
    async loadVideoData() {
      try {
        const response = await axios.get(`/api/videos/${this.videoId}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });
        
        if (response.data.success) {
          this.videoData = {
            video_url: response.data.video_url
          };
        }
      } catch (error) {
        console.error('加载视频失败:', error);
        ElMessage.error('加载视频失败');
      }
    },
    async loadScript() {
      try {
        const token = localStorage.getItem('token');
        if (!token) {
          this.$router.push('/login');
          return;
        }

        this.isLoading = true;
        const response = await axios.get(`/api/videos/${this.videoId}/human-script`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (response.data && response.data.content) {
          this.script = response.data.content;
        }
      } catch (error) {
        if (error.response?.status === 401) {
          this.$router.push('/login');
        } else {
          console.error('Failed to load script:', error);
          ElMessage.error(error.response?.data?.error || 'Failed to load script');
        }
      } finally {
        this.isLoading = false;
      }
    },

    handleScriptChange() {
      this.hasUnsavedChanges = true;
    },

    async saveScript() {
      if (!this.videoId) return;
      
      const token = localStorage.getItem('token');
      if (!token) {
        this.$router.push('/login');
        return;
      }

      this.isSaving = true;
      try {
        const response = await axios.post(
          `/api/videos/${this.videoId}/human-script`,
          { script: this.script },
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          }
        );
        
        if (response.data.success) {
          this.hasUnsavedChanges = false;
          ElMessage.success('Script saved successfully!');
        } else {
          throw new Error(response.data.error || 'Failed to save script');
        }
      } catch (error) {
        if (error.response?.status === 401) {
          this.$router.push('/login');
        } else {
          console.error('Failed to save script:', error);
          ElMessage.error(error.response?.data?.error || 'Failed to save script');
        }
      } finally {
        this.isSaving = false;
      }
    },

    async downloadScript() {
      try {
        const token = localStorage.getItem('token');
        if (!token) {
          this.$router.push('/login');
          return;
        }

        const response = await axios.get(
          `/api/videos/${this.videoId}/human-script/download`,
          {
            headers: {
              'Authorization': `Bearer ${token}`
            },
            responseType: 'blob'
          }
        );
        
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        
        const contentDisposition = response.headers['content-disposition'];
        let filename = 'AD_script.docx';
        if (contentDisposition) {
          const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
          if (filenameMatch && filenameMatch[1]) {
            filename = filenameMatch[1];
          }
        }
        
        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      } catch (error) {
        console.error('Download failed:', error);
        if (error.response?.status === 401) {
          this.$router.push('/login');
        } else {
          ElMessage.error('Download failed: ' + error.message);
        }
      }
    },

    goBack() {
      if (this.hasUnsavedChanges) {
        const confirmed = window.confirm('You have unsaved changes. Are you sure you want to leave?');
        if (!confirmed) return;
      }
      this.$router.push('/');
    }
  }
}
</script>

<style scoped>
.app-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  padding: 1rem;
  background-color: #f5f5f5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.main-content {
  flex: 1;
  display: grid;
  grid-template-columns: 50% 50% !important;
  gap: 1rem;
  padding: 1rem;
  overflow: hidden;
}

.video-section,
.script-section {
  height: 100%;
  overflow-y: auto;
}

.header-buttons {
  display: flex;
  gap: 10px;
}

.save-btn {
  background-color: #4CAF50;
  color: white;
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.save-btn:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}

.download-button {
  background-color: #4CAF50;
  color: white;
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: opacity 0.3s;
}

.download-button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
  opacity: 0.6;
}

.download-button:hover:not(:disabled) {
  opacity: 0.9;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.back-btn {
  padding: 8px 16px;
  background-color: #666;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.back-btn:hover {
  background-color: #555;
}

.script-section {
  flex: 1;
  padding: 20px;
  overflow: hidden;
}

.script-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.script-textarea {
  flex: 1;
  width: 100%;
  min-height: 500px;
  padding: 15px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  line-height: 1.6;
  resize: none;
}

.script-textarea:focus {
  outline: none;
  border-color: #409EFF;
}
</style> 