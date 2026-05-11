/**
 * Docker健康检查脚本
 * 用于检查API服务器是否正常运行
 */
import http from 'http';

const HOST = process.env.HOST || 'localhost';
const PORT = process.env.SERVER_PORT || 3000;

const options = {
  hostname: HOST,
  port: PORT,
  path: '/health',
  method: 'GET',
  timeout: 2000
};

const req = http.request(options, (res) => {
  if (res.statusCode === 200) {
    console.log('Health check passed');
    process.exit(0);
  } else {
    console.log(`Health check failed with status code: ${res.statusCode}`);
    process.exit(1);
  }
});

req.on('error', (e) => {
  console.error(`Health check failed: ${e.message}`);
  process.exit(1);
});

req.on('timeout', () => {
  console.error('Health check timed out');
  req.destroy();
  process.exit(1);
});

req.end();
