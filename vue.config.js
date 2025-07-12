const { defineConfig } = require('@vue/cli-service')

module.exports = defineConfig({
  transpileDependencies: true,
  devServer: {
    proxy: {
      '/api': {
        //target: 'https://haiad-backend.onrender.com/',
        // target: 'http://localhost:5002',
        target: 'https://api.haiad.app/',
        changeOrigin: true,
        ws: true
      }
    }
  }
})
