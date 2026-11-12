import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode; fallbackTitle?: string };
type State = { error: Error | null };

/**
 * Catches render-time failures so one broken panel cannot blank the dashboard.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("[RouteGrid] UI error boundary", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="p-6" role="alert">
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-5">
            <p className="font-semibold text-rose-200">
              {this.props.fallbackTitle ?? "This section failed to render"}
            </p>
            <p className="mt-1 text-sm text-rose-100/80">{this.state.error.message}</p>
            <button
              className="btn mt-3"
              onClick={() => this.setState({ error: null })}
            >
              Try again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
