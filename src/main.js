import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'  // 导入路由配置
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import axios from 'axios'
import { ElMessage } from 'element-plus'

// 配置 axios
const axiosInstance = axios.create({
    baseURL: 'https://haiad-backend.onrender.com',  
    // https://haiad-backend.onrender.com 
    // http://localhost:5002你的后端 API 地址
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json'
    }
})

// 添加请求拦截器
axiosInstance.interceptors.request.use(
    config => {
        const token = localStorage.getItem('token')
        if (token) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
    },
    error => {
        console.error('请求拦截器错误:', error)
        return Promise.reject(error)
    }
)

// 添加响应拦截器
axiosInstance.interceptors.response.use(
    response => response,
    error => {
        console.error('响应拦截器错误:', error)
        if (error.response?.status === 401) {
            ElMessage.error('请重新登录')
            // 可以在这里处理登录过期的逻辑
            localStorage.removeItem('token')
            window.location.href = '/login'
        } else {
            ElMessage.error(error.response?.data?.error || '请求失败')
        }
        return Promise.reject(error)
    }
)

// 全局注册 axios
const app = createApp(App)
app.config.globalProperties.$axios = axiosInstance
// 也可以设置为全局变量
window.axios = axiosInstance

app.use(router)  // 使用路由
app.use(ElementPlus)
app.use(ElMessage)
app.use(createPinia())
app.mount('#app')

// 导出配置好的 axios 实例
export default axiosInstance