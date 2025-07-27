<template>
  <div class="video-player"
       @mouseenter="isPlayerActive = true"
       @mouseleave="isPlayerActive = false">
    <video
      ref="videoRef"
      class="video-js vjs-custom-theme"
      :controls="false"
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
          <button @click="togglePlay" class="control-button play-pause-button">
            <span v-if="!isPlaying">⏵</span>
            <span v-else>⏸</span>
          </button>
          <button @click="skipBackward(1)" class="control-button">≪</button>
          <button @click="skipForward(1)" class="control-button">≫</button>
          <div class="time-display">
            <span
              class="current-time-text copy-on-hover"
              @click="copyCurrentTime"
              title="Click to copy"
            >
              {{ currentTimeFormatted }}
            </span>
            <span> / {{ durationFormatted }}</span>
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
import '@videojs/http-streaming';
import 'video.js/dist/video-js.css';

export default {
  name: 'VideoPlayer',
  props: {
    videoUrl: {
      type: String,
      required: true
    }
  },
  data() {
    return {
      player: null,
      isPlaying: false,
      isFullscreen: false,
      progress: 0,
      currentTimeFormatted: '00:00:00.000',
      durationFormatted: '00:00:00.000',
      showSeekPreview: false,
      seekPreviewPosition: 0,
      seekPreviewTime: '00:00:00.000',
      animationFrameId: null,
      copied: false,
      copyTimeout: null,
      isPlayerActive: false // 新增：播放器激活状态
    }
  },
  computed: {
    videoType() {
      // 检查是否是 MP4
      if (this.videoUrl?.includes('.mp4')) {
        return 'video/mp4';
      }
      return '';
    }
  },
  methods: {
    initializePlayer() {
      if (!this.videoUrl) {
        console.error('Video URL does not exist');
        return;
      }

      try {
        if (this.player) {
          this.player.dispose();
        }

        const options = {
          sources: [{
            src: this.videoUrl,
            type: this.videoType
          }],
          fluid: true,
          controls: false,
          preload: 'auto'
        };

        this.player = videojs(this.$refs.videoRef, options, () => {
          console.log('Player initialization completed');
          this.setupEventListeners();
          this.startProgressUpdate();
        });
      } catch (error) {
        console.error('Player initialization failed:', error);
      }
    },

    setupEventListeners() {
      this.player.on('play', () => this.isPlaying = true);
      this.player.on('pause', () => this.isPlaying = false);
      this.player.on('timeupdate', () => this.updateTimeDisplay());
      this.player.on('durationchange', () => this.updateTimeDisplay());
      
      // 监听全屏变化
      document.addEventListener('fullscreenchange', this.handleFullscreenChange);
    },

    togglePlay() {
      if (this.isPlaying) {
        this.player.pause();
      } else {
        this.player.play();
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
      } else {
        document.exitFullscreen();
      }
    },

    handleFullscreenChange() {
      this.isFullscreen = !!document.fullscreenElement;
    },

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
      const currentTime = this.player.currentTime() || 0;
      const duration = this.player.duration() || 0;
      this.currentTimeFormatted = this.formatTime(currentTime);
      this.durationFormatted = this.formatTime(duration);
      this.progress = (currentTime / duration) * 100;
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

    startProgressUpdate() {
      const updateProgress = () => {
        this.updateTimeDisplay();
        this.animationFrameId = requestAnimationFrame(updateProgress);
      };
      updateProgress();
    },

    parseTime(timeStr) {
      if (typeof timeStr === 'number') return timeStr;
      
      if (!timeStr) return 0;
      
      try {
        const [hours, minutes, seconds] = timeStr.split(':');
        const [secs, ms] = (seconds || '0.0').split('.');
        
        // 更安全的毫秒处理，确保精度
        const milliseconds = ms ? parseInt(ms) : 0;
        
        const result = parseInt(hours || 0) * 3600 + 
                      parseInt(minutes || 0) * 60 + 
                      parseInt(secs || 0) + 
                      milliseconds / 1000;
        
        console.log('parseTime input:', timeStr, 'output:', result);
        return result;
      } catch (error) {
        console.error('Time parsing failed:', error);
        return 0;
      }
    },

    seekTo(time) {
      if (this.player) {
        try {
          const parsedTime = this.parseTime(time);
          console.log('Jump to time:', parsedTime); // 添加日志
          
          if (isNaN(parsedTime) || !isFinite(parsedTime)) {
            console.error('Invalid time value:', time);
            return;
          }

          const duration = this.player.duration();
          const targetTime = Math.max(0, Math.min(parsedTime, duration));
          this.player.currentTime(targetTime);
        } catch (error) {
          console.error('Jump to specified time failed:', error);
        }
      }
    },

    getCurrentTime() {
      return this.player ? this.player.currentTime() : 0;
    },

    copyCurrentTime() {
      const time = this.currentTimeFormatted;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(time);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = time;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
    },

    playSegment(start, end) {
      if (!this.player) return;
      const startSec = this.parseTime(start);
      const endSec = this.parseTime(end);
      if (isNaN(startSec) || isNaN(endSec) || endSec <= startSec) return;
      this.player.currentTime(startSec);
      this.player.play();
      if (this._segmentInterval) {
        clearInterval(this._segmentInterval);
      }
      this._segmentInterval = setInterval(() => {
        if (this.player.currentTime() >= endSec) {
          this.player.pause();
          clearInterval(this._segmentInterval);
          this._segmentInterval = null;
        }
      }, 100);
    },

    handleKeydown(e) {
      if (!this.isPlayerActive) return;
      if (e.key === 'ArrowLeft') {
        this.skipBackward(1);
        e.preventDefault();
      }
      if (e.key === 'ArrowRight') {
        this.skipForward(1);
        e.preventDefault();
      }
    }
  },
  watch: {
    videoUrl: {
      handler(newUrl) {
        if (newUrl) {
          this.initializePlayer();
        }
      },
      immediate: true
    }
  },
  mounted() {
    window.addEventListener('keydown', this.handleKeydown);
  },
  beforeUnmount() {
    window.removeEventListener('keydown', this.handleKeydown);
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }
    document.removeEventListener('fullscreenchange', this.handleFullscreenChange);
    if (this.player) {
      this.player.dispose();
    }
    clearTimeout(this.copyTimeout);
    if (this._segmentInterval) {
      clearInterval(this._segmentInterval);
      this._segmentInterval = null;
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

.copy-on-hover {
  cursor: pointer;
  user-select: all;
  border-radius: 6px;
  transition: background 0.25s, color 0.2s, box-shadow 0.25s;
  position: relative;
  z-index: 1;
  background: none;
  color: inherit;
}
.copy-on-hover:hover {
  background: #f5f5f5;
  color: #111;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
</style> 