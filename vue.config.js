const { defineConfig } = require('@vue/cli-service')

module.exports = defineConfig({
  transpileDependencies: true,
  devServer: {
    proxy: {
      '/api': {
        target: 'https://haiad-backend.onrender.com',
        changeOrigin: true,
        ws: true
      }
    }
  }
})
