<template>
  <div class="video-player">
    <video
      ref="videoRef"
      class="video-js vjs-custom-theme"
    ></video>
    <div class="custom-controls" v-if="player">
      <div class="progress-bar" 
           @click="seek"
           @mousemove="updateSeekPreview"
           @mouseenter="showSeekPreview = true"
           @mouseleave="showSeekPreview = false">
        <div class="progress-background"></div>
        <div class="progress" :style="{ width: progress + '%' }"></div>
        <div class="seek-preview" v-if="showSeekPreview" :style="{ left: seekPreviewPosition + '%' }">
          {{ seekPreviewTime }}
        </div>
      </div>
      <div class="controls-wrapper">
        <div class="left-controls">
          <button @click="play" class="control-button play-pause-button">
            <span v-if="player.paused()">⏵</span>
            <span v-else>⏸</span>
          </button>
          <button @click="skipBackward(1)" class="control-button">≪</button>
          <button @click="skipForward(1)" class="control-button">≫</button>
          <div class="time-display">
            {{ currentTimeFormatted }} / {{ durationFormatted }}
          </div>
        </div>
        <div class="right-controls">
          <button @click="toggleFullscreen" class="control-button">
            <span v-if="isFullscreen">⤓</span>
            <span v-else>⤢</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
// 使用 import 导入，如果报错可以改用 require
import videojs from 'video.js';
import 'video.js/dist/video-js.css';

export default {
  name: 'VideoPlayer',
  props: {
    videoId: {
      type: String,
      required: true
    }
  },
  data() {
    return {
      player: null,
      videoUrl: '',
      currentTimeFormatted: '00:00:00.000',
      durationFormatted: '00:00:00.000',
      isFullscreen: false,
      progress: 0,
      showSeekPreview: false,
      seekPreviewPosition: 0,
      seekPreviewTime: '00:00:00.000',
      animationFrameId: null,
      isVideoReady: false,
      isPlayerReady: false
    }
  },
  methods: {
    formatTime(seconds) {
      if (!seconds) return '00:00:00.000';
      
      const ms = Math.floor((seconds % 1) * 1000);
      seconds = Math.floor(seconds);
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      const secs = Math.floor(seconds % 60);
      
      return `${hours.toString().padStart(2, '0')}:${minutes
        .toString()
        .padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms
        .toString()
        .padStart(3, '0')}`;
    },

    updateTimeDisplay() {
      if (this.player && this.isPlayerReady && this.isVideoReady) {
        try {
          const currentTime = this.player.currentTime() || 0;
          const duration = this.player.duration() || 0;
          this.currentTimeFormatted = this.formatTime(currentTime);
          this.durationFormatted = this.formatTime(duration);
        } catch (error) {
          console.warn('更新时间显示失败:', error);
        }
      }
    },

    play() {
      if (this.player.paused()) {
        this.player.play();
      } else {
        this.player.pause();
      }
    },

    skipForward(seconds) {
      const newTime = Math.min(this.player.duration(), this.player.currentTime() + seconds);
      this.player.currentTime(newTime);
    },

    skipBackward(seconds) {
      const newTime = Math.max(0, this.player.currentTime() - seconds);
      this.player.currentTime(newTime);
    },

    toggleFullscreen() {
      if (!document.fullscreenElement) {
        this.$el.requestFullscreen();
        this.isFullscreen = true;
      } else {
        document.exitFullscreen();
        this.isFullscreen = false;
      }
    },

    handleKeydown(event) {
      if (event.key === 'Escape' && this.isFullscreen) {
        this.isFullscreen = false;
      }
    },

    updateProgress() {
      if (this.player && this.isPlayerReady && this.isVideoReady) {
        try {
          const duration = this.player.duration() || 0;
          const currentTime = this.player.currentTime() || 0;
          this.progress = duration ? (currentTime / duration) * 100 : 0;
        } catch (error) {
          console.warn('更新进度失败:', error);
        }
      }
    },

    seek(event) {
      const progressBar = event.currentTarget;
      const rect = progressBar.getBoundingClientRect();
      const ratio = (event.clientX - rect.left) / rect.width;
      const duration = this.player.duration();
      this.player.currentTime(duration * ratio);
    },

    updateSeekPreview(event) {
      const progressBar = event.currentTarget;
      const rect = progressBar.getBoundingClientRect();
      const ratio = (event.clientX - rect.left) / rect.width;
      this.seekPreviewPosition = ratio * 100;
      const previewTime = this.player.duration() * ratio;
      this.seekPreviewTime = this.formatTime(previewTime);
    },

    async initializePlayer() {
      try {
        // 初始化播放器
        this.player = videojs(this.$refs.videoRef, {
          controls: false,
          fluid: true,
          preload: 'auto'
        });

        // 等待播放器就绪
        this.player.ready(() => {
          this.isPlayerReady = true;
          
          // 添加视频加载事件监听
          this.player.on('loadedmetadata', () => {
            this.isVideoReady = true;
            this.updateTimeDisplay();
          });

          // 添加其他事件监听
          this.player.on('timeupdate', () => {
            if (this.isVideoReady) {
              this.updateTimeDisplay();
            }
          });

          this.player.on('durationchange', () => {
            if (this.isVideoReady) {
              this.updateTimeDisplay();
            }
          });

          // 开始进度更新循环
          const updateProgressLoop = () => {
            if (this.isVideoReady) {
              this.updateProgress();
            }
            this.animationFrameId = requestAnimationFrame(updateProgressLoop);
          };
          updateProgressLoop();

          // 加载视频源
          this.loadVideoSource();
        });

      } catch (error) {
        console.error('初始化播放器失败:', error);
      }
    },

    async loadVideoSource() {
      try {
        // 获取token
        const token = localStorage.getItem('token');
        if (!token) {
          throw new Error('未登录');
        }

        const response = await fetch(`/api/videos/${this.videoId}`, {
          headers: {
            'Authorization': `Bearer ${token}`  // 添加token到请求头
          }
        });

        if (!response.ok) {
          if (response.status === 401) {
            // token无效或过期
            this.$router.push('/login');
            throw new Error('请重新登录');
          }
          if (response.status === 404) {
            throw new Error('视频不存在或无权访问');
          }
          throw new Error(`加载失败 (${response.status})`);
        }
        
        const blob = await response.blob();
        if (this.videoUrl) {
          URL.revokeObjectURL(this.videoUrl);  // 清理旧的URL
        }
        this.videoUrl = URL.createObjectURL(blob);

        if (this.player && this.isPlayerReady) {
          this.player.src({
            type: response.headers.get('Content-Type') || 'video/mp4',
            src: this.videoUrl
          });
          this.player.load();
        }
      } catch (error) {
        console.error('加载视频源失败:', error);
        // 可以添加错误提示
        if (this.$notify) {
          this.$notify({
            type: 'error',
            message: error.message || '加载视频失败'
          });
        }
      }
    },

    // 添加 seekTo 方法，处理 HH:MM:SS.mmmm 格式
    seekTo(timeStr) {
      try {
        if (!this.player || !this.isPlayerReady || !this.isVideoReady) return;
        
        // 处理 HH:MM:SS.mmmm 格式
        const [time, ms] = timeStr.split('.');
        const [hours, minutes, seconds] = time.split(':').map(Number);
        
        // 计算总秒数，毫秒部分除以 10000 转换为秒
        const totalSeconds = hours * 3600 + minutes * 60 + seconds + (parseInt(ms || 0) / 10000);
        
        this.player.currentTime(totalSeconds);
      } catch (error) {
        console.error('Error seeking to time:', error);
      }
    }
  },
  mounted() {
    this.initializePlayer();
  },
  beforeUnmount() {
    if (this.player) {
      if (this.animationFrameId) {
        cancelAnimationFrame(this.animationFrameId);
      }
      
      this.player.dispose();
      if (this.videoUrl) {
        URL.revokeObjectURL(this.videoUrl);
      }
    }
  }
}
</script>

<style>
.video-player {
  width: 100%;
  height: 100%;
  position: relative;
  background: black;
  display: flex;
  flex-direction: column;
}

.video-js {
  width: 100%;
  flex: 1;
}

/* 自定义控制栏 */
.custom-controls {
  position: relative;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.8));
  padding: 0;
}

/* 控制栏布局 */
.controls-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 12px;
  height: 40px;
}

.left-controls, .right-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 控制按钮样式 */
.control-button {
  background: none;
  border: none;
  color: white;
  font-size: 16px;
  cursor: pointer;
  padding: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.9;
  transition: opacity 0.2s;
  font-family: Arial, sans-serif;
  width: 32px; /* 固定宽度 */
  height: 32px; /* 固定高度 */
}

.control-button:hover {
  opacity: 1;
}

/* 播放/暂停按钮特殊样式 */
.play-pause-button {
  font-size: 20px; /* 稍大的字体大小 */
  line-height: 1;
}

.play-pause-button span {
  width: 20px; /* 固定宽度 */
  height: 20px; /* 固定高度 */
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 时间显示样式 */
.time-display {
  color: white;
  font-family: 'Roboto', sans-serif;
  font-size: 13px;
  opacity: 0.9;
  margin-left: 8px;
}

/* 进度条样式 */
.progress-bar {
  position: relative;
  width: 100%;
  height: 3px;
  cursor: pointer;
  transition: height 0.1s;
}

.progress-bar:hover {
  height: 5px;
}

.progress-background {
  position: absolute;
  width: 100%;
  height: 100%;
  background: rgba(255, 255, 255, 0.2);
}

.progress {
  position: absolute;
  height: 100%;
  background: #ff0000;
  transition: width 0.05s linear; /* 减小过渡时间 */
}

/* 预览时间提示 */
.seek-preview {
  position: absolute;
  bottom: 100%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.8);
  color: white;
  padding: 2px 4px;
  border-radius: 2px;
  font-family: 'Roboto', sans-serif;
  font-size: 12px;
  margin-bottom: 5px;
  white-space: nowrap;
}

/* 控制栏自动隐藏 */
.video-player:not(:hover) .custom-controls {
  opacity: 0;
  transition: opacity 0.2s;
}

.video-player:hover .custom-controls {
  opacity: 1;
}

/* 全屏样式 */
.video-player:fullscreen {
  width: 100vw;
  height: 100vh;
}

.video-player:fullscreen .video-js {
  width: 100vw;
  height: 100vh;
}

.video-player:fullscreen .controls-wrapper {
  height: 50px;
  padding: 0 16px;
}

.video-player:fullscreen .control-button {
  width: 40px;
  height: 40px;
}

.video-player:fullscreen .play-pause-button {
  font-size: 24px;
}

.video-player:fullscreen .play-pause-button span {
  width: 24px;
  height: 24px;
}

.video-player:fullscreen .time-display {
  font-size: 14px;
}

.video-player:fullscreen .progress-bar {
  height: 4px;
}

.video-player:fullscreen .progress-bar:hover {
  height: 6px;
}
</style> 