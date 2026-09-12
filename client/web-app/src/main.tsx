import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import './index.css';
import { AppErrorBoundary } from './components/ui/AppErrorBoundary.tsx';
import { AppUpdateBanner } from './components/ui/AppUpdateBanner.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppErrorBoundary>
      <App />
      {/* Ngoài <App/> chứ không lồng bên trong: banner phải sống sót qua mọi
          thay đổi route, và không được phụ thuộc vào provider nào của app —
          nó tồn tại đúng cho lúc app đang chạy bản cũ. */}
      <AppUpdateBanner />
    </AppErrorBoundary>
  </StrictMode>,
);
