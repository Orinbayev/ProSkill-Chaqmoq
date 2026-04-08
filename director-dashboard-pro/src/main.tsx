import * as React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import './index.css';

type ErrorBoundaryProps = {
  children: React.ReactNode;
};

type ErrorBoundaryState = {
  hasError: boolean;
  error: string;
};

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  declare props: ErrorBoundaryProps;
  state: ErrorBoundaryState = { hasError: false, error: '' };

  constructor(props: ErrorBoundaryProps) {
    super(props);
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error: error.message };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: '#050507', color: '#e2e8f0', fontFamily: 'system-ui, sans-serif',
          flexDirection: 'column', gap: '16px', padding: '32px', textAlign: 'center'
        }}>
          <div style={{ fontSize: '48px' }}>⚠️</div>
          <h2 style={{ fontSize: '20px', fontWeight: 700, color: '#fff', margin: 0 }}>
            Dashboard yuklanishda xatolik
          </h2>
          <p style={{ fontSize: '14px', color: '#94a3b8', maxWidth: '480px', margin: 0 }}>
            {this.state.error}
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '10px 24px', borderRadius: '12px', border: 'none',
              background: '#3b82f6', color: '#fff', fontWeight: 600,
              cursor: 'pointer', fontSize: '14px', marginTop: '8px'
            }}
          >
            Sahifani yangilash
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const rootEl = document.getElementById('root');
if (rootEl) {
  createRoot(rootEl).render(
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  );
} else {
  console.error('Root element #root not found!');
}
