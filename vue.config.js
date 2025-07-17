const { defineConfig } = require('@vue/cli-service')

module.exports = defineConfig({
  transpileDependencies: true,
  devServer: {
    proxy: {
      '/api': {
        target: 'https://api.haiad.app/',  // 开发环境用本地后端
        changeOrigin: true,
        ws: true
      }
    }
  }
})
