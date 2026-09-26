import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { clearSession, getSession, login as apiLogin, register as apiRegister } from '../api'
import type { Role, SessionData } from '../types'

interface AuthContextValue {
  session: SessionData | null
  login: (email: string, password: string, role?: Role) => Promise<SessionData>
  register: (payload: Record<string, unknown>) => Promise<SessionData>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionData | null>(() => getSession())
  useEffect(() => {
    const onExpired = () => setSession(null)
    window.addEventListener('reloop-session-expired', onExpired)
    return () => window.removeEventListener('reloop-session-expired', onExpired)
  }, [])
  const value = useMemo<AuthContextValue>(() => ({
    session,
    login: async (email, password, role) => { const next = await apiLogin(email, password, role); setSession(next); return next },
    register: async payload => { const next = await apiRegister(payload); setSession(next); return next },
    logout: () => { clearSession(); setSession(null) }
  }), [session])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
