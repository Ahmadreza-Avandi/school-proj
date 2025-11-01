import { createServer, IncomingMessage, ServerResponse } from 'http';
import next from 'next';

const dev = process.env.NODE_ENV !== 'production';
const app = next({ dev });
const handle = app.getRequestHandler();

const port = process.env.PORT || 3000;

app.prepare().then(() => {
  createServer((req: IncomingMessage, res: ServerResponse) => {
    handle(req, res);
  }).listen(port, () => {
    console.log(`🚀 Next.js server running on http://localhost:${port}`);
    console.log(`� Enxvironment: ${process.env.NODE_ENV}`);
  });
});
