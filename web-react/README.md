# AJIN React App

Streamlit 앱 기능을 React로 이관한 프론트엔드입니다.

## 실행

```bash
cd /home/runner/work/AJIN_PROJECT/AJIN_PROJECT/web-react
cp .env.example .env
npm install
npm run dev
```

## 검증

```bash
npm run lint
npm run build
```

## 기능

- 메인 대시보드: 필터/정렬/검색/페이지네이션 + 카드/리스트/일정 탭
- 맞춤 알림: 기업 프로필 기반 공고 우선순위 목록
- 상세 페이지: 지원대상/혜택/제한/첨부/링크 확인
- 설정 페이지: 기업 프로필 + 임계값 + 알림 키워드
- 초안 페이지: 단계별 진단 + 초안 생성/수정/다운로드

## 구조(기능별 파일 분리)

```text
src/
├─ api/noticesApi.js
├─ config/{defaults.js,env.js}
├─ features/
│  ├─ layout/TopNav.jsx
│  ├─ notices/hooks/useNotices.js
│  ├─ notices/utils/{normalize.js,match.js,filtering.js,date.js}
│  └─ pages/{MainPage,NotificationPage,DetailPage,SettingsPage,DraftPage}.jsx
├─ App.jsx
└─ index.css
```

> `VITE_*` 값은 클라이언트 번들에 포함됩니다. 운영 비밀키 직접 노출은 피하세요.
