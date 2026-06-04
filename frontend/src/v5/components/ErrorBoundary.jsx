import React from 'react';

/**
 * ErrorBoundary — catches render errors in any child widget/component
 * and shows a compact fallback with a retry button instead of blanking
 * the whole screen or emitting a white-screen React crash.
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    if (typeof console !== 'undefined' && console.error) {
      console.error('[ErrorBoundary]', error?.message || error, info?.componentStack);
    }
  }

  handleRetry = () => {
    // Call parent's onRetry (e.g., to re-fetch data) before resetting state
    if (this.props.onRetry) {
      this.props.onRetry();
    }
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.handleRetry);
      }
      return (
        <div style={{
          padding: '12px 16px',
          borderRadius: 12,
          background: 'rgba(255,107,125,0.07)',
          border: '1px solid rgba(255,107,125,0.18)',
          fontSize: 12,
          color: '#ff6b7d',
          fontFamily: 'var(--font-mono)',
        }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>Widget render error</div>
          <div style={{ marginBottom: 8, opacity: 0.8 }}>
            {this.state.error?.message || 'Something went wrong rendering this widget.'}
          </div>
          <button
            onClick={this.handleRetry}
            style={{
              padding: '4px 10px', borderRadius: 6,
              background: 'rgba(255,107,125,0.15)', border: '1px solid rgba(255,107,125,0.3)',
              color: '#ff6b7d', cursor: 'pointer', fontSize: 11, fontFamily: 'var(--font-mono)',
            }}
          >
            Retry
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
