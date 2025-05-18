import { createServer } from 'https';
import { createServer as createHttpServer, IncomingMessage, ServerResponse } from 'http';
import { parse } from 'url';
import next from 'next';
import fs from 'fs';
import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';

// خطاهای TypeScript را رفع می‌کنیم
declare global {
  namespace NodeJS {
    interface ProcessEnv {
      NODE_ENV: 'development' | 'production' | 'test';
    }
  }
}

const dev = process.env.NODE_ENV !== 'production';
const app = next({ dev });
const handle = app.getRequestHandler();

// مسیر گواهینامه‌ها (با فایل‌های واقعی در archive)
const httpsOptions = {
  key: fs.existsSync('/certs/privkey1.pem') ? fs.readFileSync('/certs/privkey1.pem') : '',
  cert: fs.existsSync('/certs/fullchain1.pem') ? fs.readFileSync('/certs/fullchain1.pem') : '',
};

app.prepare().then(() => {
  const server = express();

  // تنظیم پراکسی مستقیم برای phpMyAdmin
  server.use('/phpmyadmin', createProxyMiddleware({
    target: 'http://phpmyadmin:80',
    changeOrigin: true,
    pathRewrite: {
      '^/phpmyadmin': '/'
    }
  }));

  // همه درخواست‌های دیگر را به Next.js ارسال می‌کنیم
  server.all('*', (req: express.Request, res: express.Response) => {
    return handle(req, res);
  });

  // 🚀 ریدایرکت HTTP به HTTPS
  createHttpServer((req: IncomingMessage, res: ServerResponse) => {
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
    createServer(httpsOptions, server).listen(443, () => {
      console.log('✅ HTTPS Server running on https://yourdomain.com');
    });
  } else {
    console.error('❌ SSL certificates not found! Make sure Let\'s Encrypt is configured.');
    // در صورتی که SSL موجود نباشد، سرور HTTP رو اجرا کن
    server.listen(3000, () => {
      console.log('❌ Running without SSL on http://localhost:3000');
    });
  }
});