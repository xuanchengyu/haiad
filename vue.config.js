const { defineConfig } = require('@vue/cli-service')

module.exports = defineConfig({
  transpileDependencies: true,
  devServer: {
    proxy: {
      '/api': {
        target: 'https://haiad.onrender.com',
        changeOrigin: true,
        ws: true
      }
    }
  }
})
