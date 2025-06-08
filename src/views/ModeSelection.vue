<template>
  <div class="mode-selection">
    <NavBar 
      :showBack="true"
    />
    <main class="main-content">
      <div class="modes-container">
        <div class="mode-card" @click="selectMode('human-only')">
          <div class="mode-icon">👤</div>
          <h2>Human-Only Writing</h2>
          <p>Write AD scripts entirely by yourself</p>
          <ul>
            <li>Complete manual control</li>
            <li>Traditional editing experience</li>
            <li>No AI assistance</li>
          </ul>
        </div>

        <div class="mode-card" @click="selectMode('collaborative')">
          <div class="mode-icon">👥</div>
          <h2>AD Copilot</h2>
          <p>Collaborate with AI to edit scripts</p>
          <ul>
            <li>AI suggestions</li>
            <li>Interactive collaboration</li>
            <li>Human in the loop</li>
          </ul>
        </div>
      </div>
    </main>
  </div>
</template>

<script>
import NavBar from '@/components/NavBar.vue'

export default {
  name: 'ModeSelection',
  components: {
    NavBar
  },
  data() {
    return {
      videoId: this.$route.params.id
    }
  },
  mounted() {
    console.log('Current Video ID:', this.videoId);
  },
  methods: {
    selectMode(mode) {
      console.log('Select Mode:', mode, 'Video ID:', this.videoId);
      try {
        let path = '';
        switch(mode) {
          case 'human-only':
            path = `/human-only/${this.videoId}`;
            break;
          case 'collaborative':
            path = `/collaborative/${this.videoId}`;
            break;
        }
        this.$router.push(path);
      } catch (error) {
        console.error('Route Navigation Failed:', error);
      }
    }
  }
}
</script>

<style scoped>
.mode-selection {
  width: 100%;
  min-height: 100vh;
  background-color: #f8f9fa;
}

.main-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
  min-height: calc(100vh - 80px);
  display: flex;
  align-items: center;
}

.modes-container {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 2rem;
  max-width: 800px;
  margin: 0 auto;
}

.mode-card {
  background: white;
  border-radius: 12px;
  padding: 2rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: transform 0.3s, box-shadow 0.3s;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.mode-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
}

.mode-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.mode-card h2 {
  margin-bottom: 1rem;
  color: #2c3e50;
  font-size: 1.5rem;
}

.mode-card p {
  color: #666;
  margin-bottom: 1rem;
}

.mode-card ul {
  margin-top: 1rem;
  padding-left: 0;
  list-style-position: inside;
  color: #666;
  text-align: left;
}

.mode-card li {
  margin-bottom: 0.5rem;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .modes-container {
    grid-template-columns: 1fr;
    padding: 1rem;
  }
  
  .mode-card {
    padding: 1.5rem;
  }
}
</style> 