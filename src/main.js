import axios from 'axios'
import ElementPlus, { ElMessage } from 'element-plus'
import 'element-plus/dist/index.css'
import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

// 配置 axios
const axiosInstance = axios.create({
    baseURL: 'https://haiad-backend.onrender.com',  
    // https://haiad-backend.onrender.com 
    // http://localhost:5002你的后端 API 地址
    timeout: 600000,  // 10分钟
    headers: {
        'Content-Type': 'application/json'
    }
})

// 为上传请求创建特殊的实例
const uploadInstance = axios.create({
    baseURL: 'https://haiad-backend.onrender.com',
    timeout: 3600000,  // 1小时
    headers: {
        'Content-Type': 'multipart/form-data'
    },
    maxContentLength: Infinity,
    maxBodyLength: Infinity,
    // 禁用浏览器的超时限制
    validateStatus: function (status) {
        return status >= 200 && status < 300
    }
})

// 添加请求拦截器
uploadInstance.interceptors.request.use(
    config => {
        const token = localStorage.getItem('token')
        if (token) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
    },
    error => Promise.reject(error)
)

// 添加响应拦截器
uploadInstance.interceptors.response.use(
    response => response,
    error => {
        if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
            ElMessage.error('上传超时，请检查网络连接或尝试上传小一点的文件')
        } else {
            ElMessage.error(error.response?.data?.error || '上传失败，请重试')
        }
        return Promise.reject(error)
    }
)

// 导出上传实例供组件使用
export const upload = uploadInstance

const app = createApp(App)
app.config.globalProperties.$axios = axiosInstance
app.config.globalProperties.$upload = uploadInstance

app.use(createPinia())
app.use(router)
app.use(ElementPlus)
app.mount('#app')

export default axiosInstance
