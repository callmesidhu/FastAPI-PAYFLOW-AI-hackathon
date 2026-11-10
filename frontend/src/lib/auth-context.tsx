import { createContext, useContext, useEffect, useState, type FC, type ReactNode } from 'react';
import { apiClient, setOnUnauthorizedCallback, tokenStorage } from './api-client';

export interface UserProfile {
  id: string;
  email: string;
  name: string;
  business_name?: string | null;
  created_at: string;
  is_active: boolean;
}

interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string, businessName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(tokenStorage.getToken());
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const logout = () => {
    tokenStorage.clearToken();
    setToken(null);
    setUser(null);
  };

  useEffect(() => {
    setOnUnauthorizedCallback(logout);

    const initAuth = async () => {
      const activeToken = tokenStorage.getToken();
      if (!activeToken) {
        setIsLoading(false);
        return;
      }
      try {
        const profile = await apiClient<UserProfile>('/api/auth/me');
        setUser(profile);
        setToken(activeToken);
      } catch (err) {
        console.warn('Initial session validation failed:', err);
        logout();
      } finally {
        setIsLoading(false);
      }
    };

    void initAuth();
  }, []);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const data = await apiClient<AuthResponse>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      tokenStorage.setToken(data.access_token);
      setToken(data.access_token);
      setUser(data.user);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (email: string, password: string, name: string, businessName?: string) => {
    setIsLoading(true);
    try {
      const data = await apiClient<AuthResponse>('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          email,
          password,
          name,
          business_name: businessName || null,
        }),
      });
      tokenStorage.setToken(data.access_token);
      setToken(data.access_token);
      setUser(data.user);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user && !!token,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
