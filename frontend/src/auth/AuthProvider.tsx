import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react'

export interface AuthUser {
  email: string
  name: string
}

interface AuthContextValue {
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

const TOKEN_KEY = 'declio_auth_token'
const USER_KEY = 'declio_auth_user'

const BASE_URL = import.meta.env.VITE_API_URL || '/api'
const AUTH_URL = `${BASE_URL}/auth`

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Restore session on mount
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY)
    const savedUser = localStorage.getItem(USER_KEY)
    if (token && savedUser) {
      try {
        setUser(JSON.parse(savedUser))
      } catch {
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem(USER_KEY)
      }
    }
    setIsLoading(false)
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    let res: Response
    try {
      res = await fetch(`${AUTH_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
    } catch {
      throw new Error('Impossible de contacter le serveur. Verifiez votre connexion.')
    }

    if (res.status === 401 || res.status === 403) {
      throw new Error('Email ou mot de passe incorrect.')
    }

    if (!res.ok) {
      throw new Error(`Erreur serveur (${res.status}). Reessayez plus tard.`)
    }

    const data = await res.json()
    const token: string = data.token ?? data.access_token ?? ''
    const authUser: AuthUser = {
      email: data.email ?? email,
      name: data.name ?? email.split('@')[0],
    }

    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(authUser))
    setUser(authUser)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}
