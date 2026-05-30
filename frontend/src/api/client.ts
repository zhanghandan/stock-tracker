/**
 * Axios HTTP客户端
 */
import axios from 'axios';
import { API_BASE } from '../utils/constants';

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API请求失败:', error.message);
    return Promise.reject(error);
  }
);

export default apiClient;
