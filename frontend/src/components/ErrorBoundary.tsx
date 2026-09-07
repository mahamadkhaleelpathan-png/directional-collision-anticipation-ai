import { Component } from 'react';
import type { ReactNode } from 'react';

interface Props {
  section: string;
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Backstop only: the root cause of the post-completion blank page
 * (completed-without-result + NaN payload) is fixed at the source.
 * This boundary merely guarantees one bad section can never again
 * unmount the entire dashboard; the header/shell always stay visible.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error(`[ErrorBoundary:${this.props.section}]`, error);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          Unable to display {this.props.section}. Technical details available in console.
        </div>
      );
    }
    return this.props.children;
  }
}
