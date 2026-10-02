import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// neailview.com(루트 도메인)으로 들어온 요청을 www.neailview.com으로 301 리다이렉트.
// 로컬 개발(localhost)이나 www 요청에는 영향 없음.
function redirectApexToWww() {
  const middleware = (req, res, next) => {
    const host = (req.headers.host || '').split(':')[0]
    if (host === 'neailview.com') {
      res.writeHead(301, { Location: `https://www.neailview.com${req.url}` })
      res.end()
      return
    }
    next()
  }
  return {
    name: 'redirect-apex-to-www',
    configureServer(server) {
      server.middlewares.use(middleware)
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware)
    },
  }
}

// 개발 서버(npm run dev)와 운영 서버(npm run serve = 빌드 후 vite preview)가 같은 포트·프록시를 쓴다.
// Cloudflare 터널은 어느 쪽이든 5173으로 연결된다.
const serverOptions = {
  port: 5173,
  strictPort: true,
  host: true,
  allowedHosts: true,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      // rewrite: (path) => path.replace(/^\/api/, ''),
    },
    '/ws': {
      target: 'ws://localhost:8000',
      ws: true,
    },
  },
}

export default defineConfig({
  plugins: [react(), redirectApexToWww()],
  server: serverOptions,
  preview: serverOptions,
  resolve: {
    alias: {
      '@': '/src',
    },
  },
})
