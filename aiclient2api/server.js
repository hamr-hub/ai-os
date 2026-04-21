const express = require('express');
const http = require('http');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const TARGET_URL = 'http://localhost:35000';

app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true }));

app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  next();
});

function proxyRequest(req, res) {
  const options = {
    hostname: 'localhost',
    port: 35000,
    path: req.path,
    method: req.method,
    headers: {
      ...req.headers,
      host: 'localhost:35000',
      'content-length': req.body ? Buffer.byteLength(JSON.stringify(req.body)) : 0
    }
  };

  const proxy = http.request(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res, { end: true });
  });

  proxy.on('error', (err) => {
    console.error('Proxy error:', err);
    res.status(503).json({ error: 'Service unavailable', message: err.message });
  });

  if (req.body) {
    proxy.write(JSON.stringify(req.body));
  }
  proxy.end();
}

app.all('/*', (req, res) => {
  console.log(`${new Date().toISOString()} - ${req.method} ${req.path}`);
  proxyRequest(req, res);
});

app.listen(PORT, () => {
  console.log(`AIClient Proxy Server running on http://localhost:${PORT}`);
  console.log(`Proxying requests to: ${TARGET_URL}`);
});