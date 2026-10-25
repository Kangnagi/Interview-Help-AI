import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const SITE_HOSTS = new Set(['www.neailview.com', 'neailview.com'])

// 운영 화면(vite preview)의 콘텐츠 보안 정책 — 이 사이트의 파일 · 연결만 허용 (외부 스크립트 · 다른 사이트 안에 띄우기 차단).
// React 인라인 style과 화면별 <style> 태그 때문에 style만 'unsafe-inline'. 감점 장면은 data: 이미지, 관리자 내보내기는 blob:.
// 개발 서버(npm run dev)는 Vite가 인라인 스크립트를 넣어 이 정책을 쓰지 않는다.
const CSP = [
  "default-src 'self'",
  "script-src 'self' https://static.cloudflareinsights.com",   // Cloudflare가 사이트에 자동으로 넣는 방문 통계 스크립트
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "media-src 'self' blob:",
  "font-src 'self' data:",
  "connect-src 'self' wss://www.neailview.com wss://neailview.com ws://localhost:5173 ws://127.0.0.1:5173 https://cloudflareinsights.com",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join('; ')

// 모든 화면 응답에 붙이는 보안 설정 + http → https 이동 (10/26 보안 점검)
//  - neailview.com(루트 도메인) → https://www.neailview.com 301
//  - http로 들어온 사이트 요청 → https 301 (Cloudflare 터널이 원래 접속 방식을 X-Forwarded-Proto · Cf-Visitor로 알려 줌)
//    예전엔 http 주소로도 열리고 로그인까지 돼서 비밀번호가 암호화 없이 오갈 수 있었다
//  - X-Frame-Options · frame-ancestors: 다른 사이트가 이 화면을 몰래 띄워 카메라 '허용'을 누르게 유도하는 것(클릭재킹) 차단
//  - Permissions-Policy: 카메라 · 마이크는 이 사이트만, 위치 정보는 아무도
//  로컬 개발(localhost)에는 이동 · HSTS가 적용되지 않는다
function securityMiddleware({ csp }) {
  return (req, res, next) => {
    const host = (req.headers.host || '').split(':')[0]
    const viaHttp = req.headers['x-forwarded-proto'] === 'http' || /"scheme"\s*:\s*"http"/.test(req.headers['cf-visitor'] || '')
    if (host === 'neailview.com' || (SITE_HOSTS.has(host) && viaHttp)) {
      res.writeHead(301, { Location: `https://www.neailview.com${req.url}` })
      res.end()
      return
    }
    res.setHeader('X-Content-Type-Options', 'nosniff')
    res.setHeader('X-Frame-Options', 'DENY')
    res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin')
    res.setHeader('Permissions-Policy', 'camera=(self), microphone=(self), geolocation=(), payment=(), usb=()')
    if (SITE_HOSTS.has(host)) res.setHeader('Strict-Transport-Security', 'max-age=15552000')   // 180일 동안 브라우저가 https로만 접속
    if (csp) res.setHeader('Content-Security-Policy', CSP)
    next()
  }
}

function sitePolicy() {
  return {
    name: 'site-security-policy',
    configureServer(server) {
      server.middlewares.use(securityMiddleware({ csp: false }))
    },
    configurePreviewServer(server) {
      server.middlewares.use(securityMiddleware({ csp: true }))
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
  plugins: [react(), sitePolicy()],
  server: serverOptions,
  preview: serverOptions,
  resolve: {
    alias: {
      '@': '/src',
    },
  },
})
