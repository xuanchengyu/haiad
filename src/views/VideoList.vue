<template>
  <div class="video-list-container">
    <NavBar>
      <template #left>
        <h1>AD Copilot</h1>
      </template>
    </NavBar>

    <main class="main-content">
      <div class="upload-section">
        <div class="upload-card">
          <h2>Upload Video</h2>
          <div class="upload-area" 
               :class="{ 'is-dragging': isDragging }"
               @dragover.prevent="isDragging = true"
               @dragleave.prevent="isDragging = false"
               @drop.prevent="handleFileDrop">
            <input 
              type="file" 
              ref="fileInput"
              @change="handleFileUpload" 
              accept="video/*"
              :disabled="isUploading"
              class="file-input"
            >
            <div class="upload-content">
              <i class="fas fa-cloud-upload-alt"></i>
              <p>{{ isUploading ? 'Uploading...' : 'Drag & drop video or click to browse' }}</p>
              <span class="selected-file" v-if="selectedFile">
                Selected: {{ selectedFile.name }}
              </span>
            </div>
          </div>
          <button 
            @click="uploadVideo" 
            :disabled="!selectedFile || isUploading"
            class="upload-btn"
          >
            <i class="fas fa-upload"></i>
            {{ isUploading ? 'Uploading...' : 'Upload' }}
          </button>
        </div>
      </div>

      <div class="videos-section">
        <h2>Your Projects</h2>
        <div v-if="loading" class="loading">
          <i class="fas fa-spinner fa-spin"></i>
          Loading...
        </div>
        <div v-else-if="error" class="error-message">
          <i class="fas fa-exclamation-circle"></i>
          {{ error }}
        </div>
        <div v-else class="video-grid">
          <div v-for="video in videos" 
               :key="video.id" 
               class="video-card" 
               @click="goToEdit(video.id)">
            <div class="video-thumbnail">
              <img 
                :src="video.thumbnail_url || defaultThumbnail" 
                :alt="video.original_filename"
                @error="onThumbnailError"
              />
            </div>
            <div class="video-info">
              <h3>{{ video.original_filename }}</h3>
              <div class="video-meta">
                <span class="upload-date">
                  <i class="far fa-calendar-alt"></i>
                  {{ formatDate(video.created_at) }}
                </span>
                <span class="script-status" :class="{ 'has-script': video.has_script }">
                  <i class="fas" :class="video.has_script ? 'fa-check-circle' : 'fa-clock'"></i>
                  {{ video.has_script ? 'Script Ready' : 'Pending' }}
                </span>
              </div>
            </div>
            <div class="video-actions">
              <button 
                @click.stop="deleteVideo(video.id)" 
                class="delete-btn"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script>
import axios from '@/main';
import NavBar from '@/components/NavBar.vue'
import { ElMessage } from 'element-plus';

export default {
  name: 'VideoList',
  components: {
    NavBar
  },
  data() {
    return {
      videos: [],
      selectedFile: null,
      loading: true,
      error: null,
      isUploading: false,
      isDragging: false,
      defaultThumbnail: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIwIiBoZWlnaHQ9IjE4MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICAgIDxyZWN0IHdpZHRoPSIzMjAiIGhlaWdodD0iMTgwIiBmaWxsPSIjZjBmMGYwIi8+CiAgICA8Y2lyY2xlIGN4PSIxNjAiIGN5PSI5MCIgcj0iNDAiIGZpbGw9IiNkZGQiLz4KICAgIDxwYXRoIGQ9Ik0xNDUgNzBMMTg1IDkwTDE0NSAxMTBaIiBmaWxsPSIjZmZmIi8+CiAgICA8dGV4dCB4PSIxNjAiIHk9IjE0MCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZmlsbD0iIzY2NiIgZm9udC1zaXplPSIxNCI+5peg57uY5Yi2PC90ZXh0Pgo8L3N2Zz4='
    }
  },
  created() {
    this.setupAxiosInterceptors();
  },
  methods: {
    setupAxiosInterceptors() {
      axios.interceptors.request.use(config => {
        const token = localStorage.getItem('token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      }, error => {
        return Promise.reject(error);
      });

      // 响应拦截器处理401错误
      axios.interceptors.response.use(
        response => response,
        error => {
          if (error.response?.status === 401) {
            this.logout();
          }
          return Promise.reject(error);
        }
      );
    },
    async fetchVideos() {
      this.loading = true;
      this.error = null;
      try {
        const response = await axios.get('/api/videos');
        if (response.data.success) {
          this.videos = response.data.videos;
        } else {
          throw new Error(response.data.error || 'Failed to fetch videos');
        }
      } catch (error) {
        console.error('Failed to fetch videos:', error);
        this.error = error.response?.data?.error || 'Failed to load videos';
        if (error.response?.status === 401) {
          this.logout();
        }
      } finally {
        this.loading = false;
      }
    },
    handleFileUpload(event) {
      const file = event.target.files[0];
      if (file) {
        if (!file.type.startsWith('video/')) {
          alert('Please select a video file');
          event.target.value = '';
          return;
        }
        this.selectedFile = file;
      }
    },
    handleFileDrop(event) {
      const file = event.dataTransfer.files[0];
      if (file) {
        if (!file.type.startsWith('video/')) {
          alert('Please select a video file');
          return;
        }
        this.selectedFile = file;
      }
    },
    async uploadVideo() {
      if (!this.selectedFile || this.isUploading) return;
      
      const formData = new FormData();
      formData.append('video', this.selectedFile);
      
      this.isUploading = true;
      try {
        const response = await axios.post('/api/upload', formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          },
          onUploadProgress: (progressEvent) => {
            const percentCompleted = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            console.log('Upload progress:', percentCompleted);
          }
        });

        if (response.data.success) {
          alert('Upload successful');
          this.selectedFile = null;
          const fileInput = document.querySelector('input[type="file"]');
          if (fileInput) fileInput.value = '';
          this.fetchVideos();
        } else {
          throw new Error(response.data.error || 'Upload failed');
        }
      } catch (error) {
        console.error('Upload failed:', error);
        alert(error.response?.data?.error || 'Upload failed, please try again');
      } finally {
        this.isUploading = false;
      }
    },
    goToEdit(videoId) {
      if (!this.isDeleting) {
        this.$router.push(`/mode-select/${videoId}`);
      }
    },
    formatDate(dateString) {
      return new Date(dateString).toLocaleString('en-GB', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    },
    async deleteVideo(videoId) {
      try {
        const response = await axios.delete(`/api/videos/${videoId}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        });

        if (response.data.success) {
          ElMessage.success('视频删除成功');
          await this.fetchVideos();
        } else {
          ElMessage.error(response.data.error || '删除失败');
        }
      } catch (error) {
        console.error('删除视频失败:', error);
        ElMessage.error(error.response?.data?.error || '删除视频失败');
      }
    },

    // async loadVideos() {
    //   try {
    //     const response = await axios.get('/api/videos', {
    //       headers: {
    //         'Authorization': `Bearer ${localStorage.getItem('token')}`
    //       }
    //     });

    //     if (response.data.success) {
    //       this.videos = response.data.videos;
    //     }
    //   } catch (error) {
    //     console.error('加载视频列表失败:', error);
    //     ElMessage.error('加载视频列表失败');
    //   }
    // },
    
    onThumbnailError(event) {
      event.target.src = this.defaultThumbnail
    }
  },
  mounted() {
    this.fetchVideos();
  }
}
</script>

<style scoped>
.video-list-container {
  min-height: 100vh;
  background-color: #f8f9fa;
}

.main-content {
  max-width: 1200px;
  margin: 2rem auto;
  padding: 0 2rem;
}

.upload-section {
  margin-bottom: 3rem;
}

.upload-card {
  background: white;
  border-radius: 8px;
  padding: 2rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.upload-area {
  border: 2px dashed #ddd;
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  position: relative;
  transition: all 0.3s;
  margin: 1rem 0;
  cursor: pointer;
}

.upload-area:hover, .upload-area.is-dragging {
  border-color: #4CAF50;
  background-color: #f8fff8;
}

.file-input {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}

.upload-content {
  color: #666;
}

.upload-content i {
  font-size: 3rem;
  color: #4CAF50;
  margin-bottom: 1rem;
}

.selected-file {
  margin-top: 1rem;
  color: #4CAF50;
  font-size: 0.9rem;
}

.upload-btn {
  width: 100%;
  padding: 1rem;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-size: 1rem;
}

.upload-btn:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.upload-btn:hover:not(:disabled) {
  background-color: #45a049;
}

.videos-section {
  background: white;
  border-radius: 8px;
  padding: 2rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
  margin-top: 1.5rem;
}

.video-card {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  transition: transform 0.3s, box-shadow 0.3s;
  cursor: pointer;
}

.video-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.video-thumbnail {
  width: 100%;
  height: 160px;
  background-color: #f8f9fa;
  position: relative;
  overflow: hidden;
}

.thumbnail-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s;
}

.video-card:hover .thumbnail-img {
  transform: scale(1.05);
}

.thumbnail-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4CAF50;
  font-size: 3rem;
}

.video-info {
  padding: 1rem;
}

.video-info h3 {
  margin: 0;
  color: #2c3e50;
  font-size: 1rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.video-meta {
  margin-top: 0.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.85rem;
  color: #666;
}

.upload-date, .script-status {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.script-status {
  padding: 0.25rem 0.5rem;
  border-radius: 12px;
  background-color: #fff3cd;
  color: #856404;
}

.script-status.has-script {
  background-color: #d4edda;
  color: #155724;
}

.loading, .error-message {
  text-align: center;
  padding: 2rem;
  color: #666;
}

.loading i, .error-message i {
  margin-right: 0.5rem;
}

.error-message {
  color: #dc3545;
}

.video-actions {
  padding: 10px;
  display: flex;
  justify-content: flex-end;
}

.delete-btn {
  padding: 5px 10px;
  background-color: #ff4444;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.delete-btn:hover {
  background-color: #cc0000;
}
</style> 