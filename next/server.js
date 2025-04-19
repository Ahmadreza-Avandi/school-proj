// CommonJS version of the server
const https = require('https');
const http = require('http');
const { parse } = require('url');
const next = require('next');
const fs = require('fs');
const express = require('express');

const dev = process.env.NODE_ENV !== 'production';
const app = next({ dev });
const handle = app.getRequestHandler();

// مسیر گواهینامه‌ها
const httpsOptions = {
  key: fs.existsSync('/certs/privkey.pem') ? fs.readFileSync('/certs/privkey.pem') : '',
  cert: fs.existsSync('/certs/fullchain.pem') ? fs.readFileSync('/certs/fullchain.pem') : '',
};

app.prepare().then(() => {
  const server = express();

  // 🚀 ریدایرکت HTTP به HTTPS
  http.createServer((req, res) => {
    // در صورتی که گواهینامه SSL موجود نباشد، ریدایرکت به پورت 3000 انجام می‌شود.
    if (!httpsOptions.key || !httpsOptions.cert) {
      res.writeHead(301, { Location: `http://${req.headers.host}${req.url}` });
      res.end();
    } else {
      res.writeHead(301, { Location: `https://${req.headers.host}${req.url}` });
      res.end();
    }
  }).listen(80, () => {
    console.log('🚀 HTTP Server running on port 80 (Redirecting to HTTPS)');
  });

  // 🚀 اگر گواهینامه‌ها وجود داشت، سرور HTTPS رو اجرا کن
  if (httpsOptions.key && httpsOptions.cert) {
    https.createServer(httpsOptions, (req, res) => {
      const parsedUrl = parse(req.url || '', true);
      handle(req, res, parsedUrl);
    }).listen(443, () => {
      console.log('✅ HTTPS Server running on https://yourdomain.com');
    });
  } else {
    console.error('❌ SSL certificates not found! Make sure Let\'s Encrypt is configured.');
    // در صورتی که SSL موجود نباشد، سرور HTTP رو اجرا کن
    http.createServer((req, res) => {
      const parsedUrl = parse(req.url || '', true);
      handle(req, res, parsedUrl);
    }).listen(3000, () => {
      console.log('❌ Running without SSL on http://localhost:3000');
    });
  }
}); 