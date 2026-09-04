const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const BASE_DIR = path.resolve(__dirname);
const ASSETS_DIR = path.join(BASE_DIR, 'assets');
const TEMPLATES_DIR = path.join(BASE_DIR, 'templates');
const OUTPUT_DIR = path.join(BASE_DIR, 'output', 'templates');

if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

// 1. THEPT 로고 Data URI 로드
const logoPath = path.join(ASSETS_DIR, 'logo_thept_transparent.png');
let logoDataUri = '';
if (fs.existsSync(logoPath)) {
  const buf = fs.readFileSync(logoPath);
  logoDataUri = `data:image/png;base64,${buf.toString('base64')}`;
}

// 2. 크롬 또는 엣지 브라우저 경로 탐색
function getBrowserPath() {
  const candidates = [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe'
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  throw new Error('Chrome or Edge browser not found.');
}

const browserPath = getBrowserPath();
console.log(`Using browser: ${browserPath}`);

// 공통 Head & CSS 스타일 (모바일 화면에서도 시원하게 보이는 대형 텍스트 및 닷 중앙 정렬)
const commonHead = `
  <meta charset="UTF-8">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css" />
  <link href="https://fonts.googleapis.com/css2?family=Pretendard:wght@400;500;600;700;800;900&family=Outfit:wght@700;900&display=swap" rel="stylesheet">
  <style>
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }
    body {
      font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
      overflow: hidden;
      color: #ffffff;
    }

    /* 1. 상단 바 (84px 로고, 38px 서브 타이틀, 32px 알약 뱃지) */
    .top-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2px solid rgba(255, 255, 255, 0.2);
      padding-bottom: 26px;
    }
    .brand-wrap {
      display: flex;
      align-items: center;
      gap: 22px;
    }
    .thept-logo-img {
      height: 84px;
      width: auto;
      object-fit: contain;
      filter: drop-shadow(0 4px 14px rgba(0, 0, 0, 0.7));
    }
    .brand-sub {
      font-size: 38px;
      font-weight: 900;
      letter-spacing: -0.5px;
      color: #e2e8f0;
      border-left: 3.5px solid rgba(255, 255, 255, 0.4);
      padding-left: 22px;
    }
    .category-pill {
      background: rgba(255, 255, 255, 0.15);
      border: 2px solid rgba(255, 255, 255, 0.35);
      color: #ffffff;
      padding: 12px 32px;
      border-radius: 9999px;
      font-size: 32px;
      font-weight: 800;
      backdrop-filter: blur(16px);
    }

    /* 2. 하단 네비 바 (2단 구성) */
    .bottom-nav {
      display: flex;
      flex-direction: column;
      gap: 20px;
      border-top: 2px solid rgba(255, 255, 255, 0.2);
      padding-top: 24px;
    }

    /* 1행: 채널 3종 바 (모바일 가독성 극대화: 33px 텍스트, 36px 아이콘) */
    .footer-channels-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      gap: 10px;
    }
    .footer-channel-badge {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      background: rgba(15, 23, 42, 0.78);
      border: 1.5px solid rgba(255, 255, 255, 0.22);
      border-radius: 18px;
      padding: 16px 6px;
      backdrop-filter: blur(16px);
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
    }
    .footer-channel-badge span {
      font-size: 33px;
      font-weight: 900;
      color: #ffffff;
      letter-spacing: -0.8px;
      white-space: nowrap;
    }
    .footer-icon-svg {
      width: 36px;
      height: 36px;
      fill: currentColor;
      flex-shrink: 0;
    }
    .footer-icon-stroke {
      width: 36px;
      height: 36px;
      stroke: currentColor;
      fill: none;
      stroke-width: 2.4;
      flex-shrink: 0;
    }

    /* 2행: 최하단 인디케이터 닷 가운데 정렬 및 스와이프 액션 (32px 볼드) */
    .footer-bottom-action-bar {
      position: relative;
      display: flex;
      justify-content: flex-end;
      align-items: center;
      width: 100%;
      min-height: 48px;
      padding: 0 6px;
    }
    .carousel-dots {
      position: absolute;
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      gap: 12px;
      align-items: center;
    }
    .dot {
      width: 15px;
      height: 15px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.35);
    }
    .dot.active {
      width: 44px;
      height: 15px;
      border-radius: 9999px;
      background: #facc15;
      box-shadow: 0 0 14px #facc15;
    }
    .swipe-action-text {
      font-size: 32px;
      font-weight: 900;
      color: #facc15;
      display: flex;
      align-items: center;
      gap: 10px;
      text-shadow: 0 2px 10px rgba(0, 0, 0, 0.6);
    }
  </style>
`;

// 상단 헤더 HTML
const topBarHtml = `
  <div class="top-bar">
    <div class="brand-wrap">
      <img src="${logoDataUri}" class="thept-logo-img" alt="THEPT Logo" />
      <div class="brand-sub">물리치료 LAB</div>
    </div>
    <div class="category-pill">THEPT NEWS</div>
  </div>
`;

// 하단 네비게이션 HTML
const bottomNavHtml = `
  <div class="bottom-nav">
    <div class="footer-channels-bar">
      <!-- 인스타그램 -->
      <div class="footer-channel-badge">
        <svg class="footer-icon-stroke" viewBox="0 0 24 24" style="color: #f43f5e;">
          <rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect>
          <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path>
          <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line>
        </svg>
        <span>@teamthept</span>
      </div>
      <!-- 유튜브 -->
      <div class="footer-channel-badge">
        <svg class="footer-icon-svg" viewBox="0 0 24 24" style="color: #ef4444;">
          <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
        </svg>
        <span>더피티THEPT</span>
      </div>
      <!-- 홈페이지 -->
      <div class="footer-channel-badge">
        <svg class="footer-icon-stroke" viewBox="0 0 24 24" style="color: #38bdf8;">
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
          <polyline points="9 22 9 12 15 12 15 22"></polyline>
        </svg>
        <span>thept.co.kr</span>
      </div>
    </div>
    <div class="footer-bottom-action-bar">
      <div class="carousel-dots">
        <div class="dot"></div>
        <div class="dot"></div>
        <div class="dot active"></div>
        <div class="dot"></div>
        <div class="dot"></div>
      </div>
      <div class="swipe-action-text">
        <span>다음 장으로 👉</span>
      </div>
    </div>
  </div>
`;

// 생성할 템플릿 목록 (피드 4:5 및 릴스 9:16, 상/하단 단독 분리 템플릿)
const targets = [
  // 1. 4:5 인스타 피드 투명 오버레이 (1080x1350)
  {
    name: 'thept_template_4x5_transparent',
    width: 1080,
    height: 1350,
    html: `<!DOCTYPE html>
<html lang="ko">
<head>
  ${commonHead}
  <style>
    html, body {
      width: 1080px;
      height: 1350px;
      background-color: transparent !important;
    }
    .container {
      position: relative;
      width: 1080px;
      height: 1350px;
      padding: 65px 70px 55px 70px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
  </style>
</head>
<body>
  <div class="container">
    ${topBarHtml}
    <div style="flex: 1;"></div>
    ${bottomNavHtml}
  </div>
</body>
</html>`,
    isTransparent: true
  },

  // 2. 4:5 인스타 피드 다크 배경 (1080x1350)
  {
    name: 'thept_template_4x5_dark',
    width: 1080,
    height: 1350,
    html: `<!DOCTYPE html>
<html lang="ko">
<head>
  ${commonHead}
  <style>
    body {
      width: 1080px;
      height: 1350px;
      background-color: #0b0f19;
      position: relative;
    }
    .bg-overlay-gradient {
      position: absolute;
      top: 0;
      left: 0;
      width: 1080px;
      height: 1350px;
      background: linear-gradient(
        180deg, 
        rgba(11, 15, 25, 0.94) 0%, 
        rgba(11, 15, 25, 0.76) 30%, 
        rgba(11, 15, 25, 0.72) 60%, 
        rgba(11, 15, 25, 0.92) 85%, 
        rgba(11, 15, 25, 0.98) 100%
      );
      z-index: 1;
    }
    .container {
      position: relative;
      z-index: 2;
      width: 1080px;
      height: 1350px;
      padding: 65px 70px 55px 70px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
  </style>
</head>
<body>
  <div class="bg-overlay-gradient"></div>
  <div class="container">
    ${topBarHtml}
    <div style="flex: 1;"></div>
    ${bottomNavHtml}
  </div>
</body>
</html>`,
    isTransparent: false
  },

  // 3. 9:16 릴스/쇼츠 투명 오버레이 (1080x1920)
  {
    name: 'thept_template_9x16_transparent',
    width: 1080,
    height: 1920,
    html: `<!DOCTYPE html>
<html lang="ko">
<head>
  ${commonHead}
  <style>
    html, body {
      width: 1080px;
      height: 1920px;
      background-color: transparent !important;
    }
    .container {
      position: relative;
      width: 1080px;
      height: 1920px;
      padding: 100px 80px 90px 80px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
  </style>
</head>
<body>
  <div class="container">
    ${topBarHtml}
    <div style="flex: 1;"></div>
    ${bottomNavHtml}
  </div>
</body>
</html>`,
    isTransparent: true
  },

  // 4. 9:16 릴스/쇼츠 다크 배경 (1080x1920)
  {
    name: 'thept_template_9x16_dark',
    width: 1080,
    height: 1920,
    html: `<!DOCTYPE html>
<html lang="ko">
<head>
  ${commonHead}
  <style>
    body {
      width: 1080px;
      height: 1920px;
      background-color: #0b0f19;
      position: relative;
    }
    .bg-overlay-gradient {
      position: absolute;
      top: 0;
      left: 0;
      width: 1080px;
      height: 1920px;
      background: linear-gradient(
        180deg, 
        rgba(11, 15, 25, 0.94) 0%, 
        rgba(11, 15, 25, 0.72) 20%, 
        rgba(11, 15, 25, 0.65) 50%, 
        rgba(11, 15, 25, 0.88) 80%, 
        rgba(11, 15, 25, 0.98) 100%
      );
      z-index: 1;
    }
    .container {
      position: relative;
      z-index: 2;
      width: 1080px;
      height: 1920px;
      padding: 100px 80px 90px 80px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
  </style>
</head>
<body>
  <div class="bg-overlay-gradient"></div>
  <div class="container">
    ${topBarHtml}
    <div style="flex: 1;"></div>
    ${bottomNavHtml}
  </div>
</body>
</html>`,
    isTransparent: false
  },

  // 5. 상단 헤더 바 단독 투명 템플릿 (1080 x 200)
  {
    name: 'thept_header_only',
    width: 1080,
    height: 200,
    html: `<!DOCTYPE html>
<html lang="ko">
<head>
  ${commonHead}
  <style>
    html, body {
      width: 1080px;
      height: 200px;
      background-color: transparent !important;
    }
    .header-container {
      width: 1080px;
      padding: 48px 70px 24px 70px;
    }
  </style>
</head>
<body>
  <div class="header-container">
    ${topBarHtml}
  </div>
</body>
</html>`,
    isTransparent: true
  },

  // 6. 하단 네비 바 단독 투명 템플릿 (1080 x 260)
  {
    name: 'thept_footer_only',
    width: 1080,
    height: 260,
    html: `<!DOCTYPE html>
<html lang="ko">
<head>
  ${commonHead}
  <style>
    html, body {
      width: 1080px;
      height: 260px;
      background-color: transparent !important;
    }
    .footer-container {
      width: 1080px;
      padding: 24px 70px 52px 70px;
    }
  </style>
</head>
<body>
  <div class="footer-container">
    ${bottomNavHtml}
  </div>
</body>
</html>`,
    isTransparent: true
  },

  // 7. 상단 헤더 바 단독 다크 템플릿 (1080 x 200)
  {
    name: 'thept_header_dark',
    width: 1080,
    height: 200,
    html: `<!DOCTYPE html>
<html lang="ko">
<head>
  ${commonHead}
  <style>
    body {
      width: 1080px;
      height: 200px;
      background-color: #0b0f19;
    }
    .header-container {
      width: 1080px;
      padding: 48px 70px 24px 70px;
    }
  </style>
</head>
<body>
  <div class="header-container">
    ${topBarHtml}
  </div>
</body>
</html>`,
    isTransparent: false
  },

  // 8. 하단 네비 바 단독 다크 템플릿 (1080 x 260)
  {
    name: 'thept_footer_dark',
    width: 1080,
    height: 260,
    html: `<!DOCTYPE html>
<html lang="ko">
<head>
  ${commonHead}
  <style>
    body {
      width: 1080px;
      height: 260px;
      background-color: #0b0f19;
    }
    .footer-container {
      width: 1080px;
      padding: 24px 70px 52px 70px;
    }
  </style>
</head>
<body>
  <div class="footer-container">
    ${bottomNavHtml}
  </div>
</body>
</html>`,
    isTransparent: false
  }
];

// 브라우저 헤드리스 스크린샷 일괄 실행
for (const item of targets) {
  const htmlFilePath = path.join(TEMPLATES_DIR, `${item.name}.html`);
  const pngFilePath = path.join(OUTPUT_DIR, `${item.name}.png`);

  fs.writeFileSync(htmlFilePath, item.html, 'utf8');
  console.log(`Saved HTML: ${htmlFilePath}`);

  const chromeArgs = [
    '--headless=new',
    '--disable-gpu',
    '--force-device-scale-factor=1',
    `--window-size=${item.width},${item.height}`,
    '--hide-scrollbars',
    '--run-all-compositor-stages-before-draw',
    '--virtual-time-budget=3000'
  ];

  if (item.isTransparent) {
    chromeArgs.push('--default-background-color=00000000');
  }

  chromeArgs.push(`--screenshot=${pngFilePath}`);
  chromeArgs.push(htmlFilePath);

  console.log(`Rendering PNG (${item.width}x${item.height}): ${pngFilePath}...`);
  const result = spawnSync(browserPath, chromeArgs, { stdio: 'inherit' });

  if (fs.existsSync(pngFilePath)) {
    const stats = fs.statSync(pngFilePath);
    console.log(`=> Success: ${path.basename(pngFilePath)} (${stats.size} bytes)`);
  } else {
    console.error(`=> Failed to create ${pngFilePath}`);
  }
}

console.log('\nAll templates generated successfully with mobile-optimized font sizes!');
