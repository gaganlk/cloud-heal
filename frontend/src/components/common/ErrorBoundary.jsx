import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[Global Error Boundary] Caught exception:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#0d0d18] flex items-center justify-center p-8">
          <div className="glass-premium rounded-[2.5rem] p-12 max-w-2xl w-full text-center border-rose-500/20">
            <div className="w-20 h-20 bg-rose-500/10 rounded-3xl flex items-center justify-center mx-auto mb-8">
              <span className="text-4xl">⚠️</span>
            </div>
            <h1 className="text-3xl font-black text-white tracking-tighter mb-4">
              System Fault Detected
            </h1>
            <p className="text-slate-400 font-medium mb-8">
              The application encountered a critical runtime error. This has been logged and our autonomous healing engine is investigating.
            </p>
            <div className="bg-black/40 rounded-2xl p-4 text-left mb-8 overflow-hidden">
              <code className="text-rose-400 text-xs font-mono break-all">
                {this.state.error?.toString()}
              </code>
            </div>
            <button 
              onClick={() => window.location.href = '/'}
              className="btn-primary-glow px-8"
            >
              Restart Session
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
