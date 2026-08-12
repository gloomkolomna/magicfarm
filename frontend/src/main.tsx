import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { VkBridgeProvider } from './context/VkBridgeContext';
import { SessionProvider } from './context/SessionContext';
import App from './App';
import './styles/theme.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter basename="/magicfarm" future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <VkBridgeProvider>
        <SessionProvider>
          <App />
        </SessionProvider>
      </VkBridgeProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
