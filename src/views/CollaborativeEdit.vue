<!-- 人机协作模式 -->
<template>
    <div class="app-container">
      <header class="header">
        <div class="header-left">
          <button @click="goBack" class="back-btn">
            Back
          </button>
          <h1>AD Copilot (Interactive Post-editing)</h1>
        </div>
        <div class="header-buttons">
          <button 
            @click="generateScript" 
            :disabled="!videoId || isGenerating"
            class="generate-btn"
          >
            {{ isGenerating ? 'Analysing...' : 'Start Generating' }}
          </button>
          <button 
            @click="saveScript"
            :disabled="!videoId || isSaving"
            class="save-btn"
          >
            {{ isSaving ? 'Saving...' : 'Save' }}
          </button>
          <button 
            @click="downloadScript"
            :disabled="!scenes.length"
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
          <script-editor
            :video-id="videoId"
            :script-data="scenes"
            mode="collaborative"
            @update:script="updateScript"
            @seek="handleSeek"
          />
        </div>
  
        <div class="ai-chat-section">
          <ai-assistant />
        </div>
      </main>
    </div>
  </template>
  
  <script>
  import axios from '@/main'
  import VideoPlayer from '@/components/VideoPlayer.vue'
  import ScriptEditor from '@/components/ScriptEditor.vue'
  import AiAssistant from '@/components/AiAssistant.vue'
  import { ElMessage } from 'element-plus'
  
  export default {
    name: 'CollaborativeEdit',
    components: {
      VideoPlayer,
      ScriptEditor,
      AiAssistant
    },
    data() {
      return {
        videoId: this.$route.params.id,
        scenes: [],
        script: '',
        isGenerating: false,
        isSaving: false,
        hasUnsavedChanges: false,
        videoData: {
          video_url: ''
        }
      }
    },
    async created() {
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
          console.error('Load Video Failed:', error);
          ElMessage.error('Load Video Failed');
        }
      },
      async loadScript() {
        try {
          const token = localStorage.getItem('token');
          if (!token) {
            this.$router.push('/login');
            return;
          }

          const response = await axios.get(`/api/videos/${this.videoId}/scenes`, {
            headers: {
              'Authorization': `Bearer ${token}`
            }
          });

          if (response.data && response.data.scenes) {
            this.scenes = response.data.scenes;
          }
        } catch (error) {
          if (error.response?.status === 401) {
            this.$router.push('/login');
          } else {
            console.error('Failed to load script:', error);
            ElMessage.error(error.response?.data?.error || 'Failed to load script');
          }
        }
      },
      async generateScript() {
        if (!this.videoId) return;
        
        const token = localStorage.getItem('token');
        if (!token) {
          this.$router.push('/login');
          return;
        }

        this.isGenerating = true;
        try {
          const response = await axios.post(
            '/api/generatescript',
            { video_id: this.videoId },
            { 
              timeout: 300000,
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
              }
            }
          );
          
          if (response.data.success) {
            this.scenes = response.data.scenes;
            this.script = response.data.content || '';
            ElMessage.success('Script generated successfully!');
          } else {
            throw new Error(response.data.error || 'Failed to generate script');
          }
        } catch (error) {
          if (error.response?.status === 401) {
            this.$router.push('/login');
          } else {
            console.error('Failed to generate script:', error);
            ElMessage.error(error.response?.data?.error || 'Failed to generate script');
          }
        } finally {
          this.isGenerating = false;
        }
      },
      updateScript(newScenes) {
        this.scenes = newScenes;
        this.hasUnsavedChanges = true;
      },
      async downloadScript() {
        try {
          const token = localStorage.getItem('token');
          if (!token) {
            this.$router.push('/login');
            return;
          }

          const response = await axios.get(
            `/api/videos/${this.videoId}/script/download`,
            {
              headers: {
                'Authorization': `Bearer ${token}`
              },
              responseType: 'blob'
            }
          );
          
          const url = window.URL.createObjectURL(response.data);
          const link = document.createElement('a');
          link.href = url;
          link.click();
          URL.revokeObjectURL(url);
        } catch (error) {
          console.error('Download failed:', error);
          if (error.response?.status === 401) {
            this.$router.push('/login');
          } else {
            ElMessage.error('Download failed: ' + error.message);
          }
        }
      },
      async saveScript() {
        this.isSaving = true;
        try {
          const response = await axios.post(`/api/videos/${this.videoId}/script`, {
            scenes: this.scenes,
            content: this.script
          });
          
          if (response.data.success) {
            this.hasUnsavedChanges = false;
            ElMessage.success('Script saved successfully!');
          } else {
            throw new Error(response.data.error || 'Failed to save script');
          }
        } catch (error) {
          console.error('Failed to save script:', error);
          ElMessage.error('Failed to save: ' + error.message);
        } finally {
          this.isSaving = false;
        }
      },
      goBack() {
        if (this.hasUnsavedChanges) {
          const confirmed = window.confirm('You have unsaved changes. Are you sure you want to leave?');
          if (!confirmed) return;
        }
        this.$router.push('/');
      },
      handleSeek(timeStr) {
        if (this.$refs.videoPlayer) {
          this.$refs.videoPlayer.seekTo(timeStr);
        }
      },
    }
  }
  </script>
  
  <style>
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
    grid-template-columns: 35% 35% 28% !important;
    gap: 1rem;
    padding: 1rem;
    overflow: hidden;
  }
  
  .video-section,
  .script-section,
  .ai-chat-section {
    height: 100%;
    overflow-y: auto;
  }
  
  .header-buttons {
    display: flex;
    gap: 10px;
  }
  
  .generate-btn,
  .save-btn,
  .download-button {
    padding: 8px 16px;
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  
  .generate-btn:disabled {
    background-color: #cccccc;
    cursor: not-allowed;
  }
  
  .save-btn {
    margin-left: 0;
  }
  
  .save-btn:disabled {
    background-color: #cccccc;
    cursor: not-allowed;
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
  </style> 