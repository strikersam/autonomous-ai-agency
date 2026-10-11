import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getMe, login as apiLogin, logout as apiLogout } from './api';
import { clearSafeDataCache } from './v5/hooks/useSafeData';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setUser(false);
      setLoading(false);
      return;
    }
    try {
      const { data } = await getMe();
      setUser(data);
    } catch {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setUser(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { checkAuth(); }, [checkAuth]);

  const login = async (email, password) => {
    const { data } = await apiLogin(email, password);
    clearSafeDataCache();
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    setUser({ id: data.id, email: data.email, name: data.name, role: data.role });
    return data;
  };

  const logout = async () => {
    // Cached screen data belongs to this account; never show it to the next one.
    clearSafeDataCache();
    await apiLogout();
    // Again after the await: a request in flight at sign-out may have refilled it.
    clearSafeDataCache();
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
