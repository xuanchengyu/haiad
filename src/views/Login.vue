<template>
  <div class="auth-container">
    <div class="auth-box">
      <h2>Sign In</h2>
      <form @submit.prevent="handleLogin" class="auth-form">
        <div class="form-group">
          <label for="username">Username</label>
          <input 
            type="text" 
            id="username"
            v-model="username"
            required
            placeholder="Enter your username"
          >
        </div>
        
        <div class="form-group">
          <label for="password">Password</label>
          <input 
            type="password" 
            id="password"
            v-model="password"
            required
            placeholder="Enter your password"
          >
        </div>

        <div class="error-message" v-if="error">
          {{ error }}
        </div>

        <button type="submit" class="auth-button">
          <span v-if="isLoading">Signing in...</span>
          <span v-else>Sign In</span>
        </button>
        
        <div class="auth-links">
          <router-link to="/register">New to AD Copilot? Create an account</router-link>
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'LoginPage',
  data() {
    return {
      username: '',
      password: '',
      error: '',
      isLoading: false
    }
  },
  methods: {
    async handleLogin() {
      this.error = '';
      this.isLoading = true;
      
      try {
        const response = await axios.post('/api/auth/login', {
          username: this.username,
          password: this.password
        });

        if (response.data.token) {
          // Store token
          localStorage.setItem('token', response.data.token);
          // Store user info
          localStorage.setItem('user', JSON.stringify(response.data.user));
          // Redirect to home page
          this.$router.push('/');
        }
      } catch (error) {
        this.error = error.response?.data?.message || 'Failed to sign in. Please try again.';
      } finally {
        this.isLoading = false;
      }
    }
  }
}
</script>

<style scoped>
.auth-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f8f9fa;
}

.auth-box {
  background: white;
  padding: 2.5rem;
  border-radius: 12px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  width: 100%;
  max-width: 400px;
}

h2 {
  color: #2c3e50;
  text-align: center;
  margin-bottom: 2rem;
  font-size: 1.75rem;
  font-weight: 600;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

label {
  font-size: 0.9rem;
  color: #4a5568;
  font-weight: 500;
}

input {
  padding: 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 1rem;
  transition: all 0.3s ease;
}

input:focus {
  outline: none;
  border-color: #2196f3;
  box-shadow: 0 0 0 3px rgba(33, 150, 243, 0.1);
}

.auth-button {
  background: #2196f3;
  color: white;
  padding: 0.875rem;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.auth-button:hover {
  background: #1976d2;
  transform: translateY(-1px);
}

.auth-button:active {
  transform: translateY(0);
}

.error-message {
  color: #e53e3e;
  font-size: 0.875rem;
  padding: 0.5rem;
  background-color: #fff5f5;
  border-radius: 4px;
  text-align: center;
}

.auth-links {
  text-align: center;
  font-size: 0.9rem;
  margin-top: 0.5rem;
}

.auth-links a {
  color: #2196f3;
  text-decoration: none;
  transition: color 0.2s;
}

.auth-links a:hover {
  color: #1976d2;
  text-decoration: underline;
}

/* Loading state styles */
.auth-button:disabled {
  background-color: #90caf9;
  cursor: not-allowed;
}
</style> 