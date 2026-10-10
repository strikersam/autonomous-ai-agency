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

  componentDidUpdate(prevProps) {
    // React error boundaries do NOT auto-recover when child props change —
    // they stay on the fallback until explicitly reset/remounted. When the
    // caller passes a changing `resetKey` (e.g. a data version that bumps on a
    // successful refetch), clear the error so a transient render exception
    // doesn't leave the widget stuck on fallback after data later succeeds.
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false, error: null });
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
        <div role="alert" style={{
          padding: '14px 16px', borderRadius: 12,
          background: 'color-mix(in oklab, var(--danger) 7%, transparent)',
          border: '1px solid color-mix(in oklab, var(--danger) 20%, transparent)',
          fontSize: 15, color: 'var(--text-primary)',
        }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>This part of the page could not load.</div>
          <div style={{ color: 'var(--text-tertiary)', marginBottom: 10 }}>The rest of the app still works. Try again, and if it keeps happening, check System health in Settings.</div>
          <button type="button" className="app-button-secondary" onClick={this.handleRetry} style={{ minHeight: 40 }}>
            Try again
          </button>
          {this.state.error?.message && (
            <details style={{ marginTop: 10, fontSize: 13, color: 'var(--text-muted)' }}>
              <summary style={{ cursor: 'pointer' }}>Technical details</summary>
              <code style={{ display: 'block', marginTop: 6, overflowWrap: 'anywhere' }}>{this.state.error.message}</code>
            </details>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
