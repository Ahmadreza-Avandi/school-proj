// CommonJS version of the server - ساده شده برای استفاده با Nginx
const next = require('next');
const express = require('express');

const dev = process.env.NODE_ENV !== 'production';
const app = next({ dev });
const handle = app.getRequestHandler();

app.prepare().then(() => {
  const server = express();

  // همه درخواست‌ها رو به Next.js می‌فرستیم
  server.all('*', (req, res) => {
    return handle(req, res);
  });

  // فقط روی پورت 3000 گوش می‌ده - Nginx مدیریت SSL و routing رو انجام می‌ده
  server.listen(3000, (err) => {
    if (err) throw err;
    console.log('✅ Next.js server running on http://localhost:3000');
    console.log('🔒 SSL and routing managed by Nginx');
  });
}); 
