import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button, Card } from './ui'

interface Props { children: ReactNode }
interface State { hasError: boolean; message: string }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: '' }
  static getDerivedStateFromError(error: Error): State { return { hasError: true, message: error.message || 'Unexpected application error' } }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('Reloop UI error', error, info) }
  render() {
    if (!this.state.hasError) return this.props.children
    return <div className="crash-screen"><Card><div className="error-mark">!</div><h1>Reloop hit an unexpected error</h1><p>{this.state.message}</p><Button onClick={() => window.location.reload()}>Reload workspace</Button></Card></div>
  }
}
