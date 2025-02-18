import { createApp } from 'vue'
import App from './App.vue'
import router from './router'  // 导入路由配置
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import axios from 'axios'

axios.defaults.baseURL = process.env.VUE_APP_API_URL || 'https://haiad-backend.onrender.com'  
// http://localhost:5001
// https://haiad-backend.onrender.com
// 添加请求拦截器
axios.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 添加响应拦截器
axios.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      // 清除无效的 token
      localStorage.removeItem('token')
      // 重定向到登录页
      router.push('/login')
    }
    return Promise.reject(error)
  }
)

const app = createApp(App)
app.use(router)  // 使用路由
app.use(ElementPlus)
app.mount('#app')
