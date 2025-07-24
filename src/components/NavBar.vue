<template>
  <header class="header">
    <div class="header-content">
      <div class="header-left">
        <button v-if="showBack" @click="goBack" class="back-btn">
          <i class="fas fa-arrow-left"></i> Back
        </button>
      </div>
      <div class="header-center">
        <h1>{{ title }}</h1>
      </div>
      <div class="user-info">
        <span class="username">{{ username }}</span>
        <button @click="goToDemo" class="demo-btn">Help</button><!-- 新增的Demo按钮 -->
        <button @click="logout" class="logout-btn">Logout</button>
      </div>
    </div>
  </header>
</template>

<script>
export default {
  name: 'NavBar',
  props: {
    showBack: {
      type: Boolean,
      default: false
    },
    title: {
      type: String,
      default: 'AD Copilot'
    }
  },
  data() {
    return {
      username: '',
      demoLink: "https://haiad.app/help.mp4" // 待替换为实际的使用说明书链接
    }
  },
  created() {
    this.loadUserInfo();
  },
  methods: {
    loadUserInfo() {
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const user = JSON.parse(userStr);
        this.username = user.username;
      } else {
        this.logout();
      }
    },
    logout() {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      this.$router.push('/login');
    },
    goBack() {
      this.$router.push('/');
    },
    // 新增的Demo按钮点击方法
    goToDemo() {
      window.open(this.demoLink, '_blank');
    }
  }
}
</script>

<style scoped>
.header {
  background-color: white;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 1rem 2rem;
  width: 100%;
}

.header-content {
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 200px 1fr 450px; /* 三列布局 */
  align-items: center;
}

.header-left {
  grid-column: 1;
  display: flex;
  align-items: center;
}

.header-center {
  grid-column: 2;
  display: flex;
  justify-content: center; /* 居中显示 */
  align-items: center;
}

.back-btn {
  padding: 0;
  width: 80px;
  height: 32px;
  background-color: #6c757d;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  font-size: 14px;
  flex-shrink: 0;
}

.back-btn i {
  font-size: 12px;
  margin-right: -2px;
}

.back-btn:hover {
  background-color: #5a6268;
}

.header h1 {
  color: #2c3e50;
  margin: 0;
  font-size: 1.8rem;
  white-space: nowrap;
  flex-shrink: 0;
}

.user-info {
  grid-column: 3;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  justify-content: flex-end;
}

.username {
  color: #666;
  font-weight: 500;
  white-space: nowrap;
}

.logout-btn {
  padding: 0;
  width: 80px;
  height: 32px;
  background-color: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  line-height: 1;
  flex-shrink: 0;
}

.logout-btn:hover {
  background-color: #c82333;
}


/* 新增的Demo按钮样式 */
.demo-btn {
  padding: 0;
  width: 80px;
  height: 32px;
  background-color: white; /* 白色背景 */
  color: #495057; /* 深灰色文字 */
  border: 1px solid #ced4da; /* 浅灰色边框 */
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  line-height: 1;
  flex-shrink: 0;
}

.demo-btn:hover {
  background-color: #f8f9fa; /* 悬停时浅灰色背景 */
  border-color: #adb5bd; /* 悬停时深一点的边框 */
}

</style>