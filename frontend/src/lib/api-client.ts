/**
 * Frontend API Client with safe session-scoped token management and 401 handling.
 */

// In-memory token holder to prevent persistent token exposure
let memoryToken: string | null = null;

const SESSION_KEY = 'payflow_session_token';

export const tokenStorage = {
  getToken(): string | null {
    if (memoryToken) return memoryToken;
    try {
      // Session storage automatically purges when the tab or window closes
      const stored = sessionStorage.getItem(SESSION_KEY);
      if (stored) {
        memoryToken = stored;
        return stored;
      }
    } catch {
      // Handle environments where sessionStorage is unavailable
    }
    return null;
  },

  setToken(token: string | null): void {
    memoryToken = token;
    try {
      if (token) {
        sessionStorage.setItem(SESSION_KEY, token);
      } else {
        sessionStorage.removeItem(SESSION_KEY);
      }
    } catch {
      // Handle environments where sessionStorage is unavailable
    }
  },

  clearToken(): void {
    memoryToken = null;
    try {
      sessionStorage.removeItem(SESSION_KEY);
    } catch {
      // Handle environments where sessionStorage is unavailable
    }
  },
};

export class ApiError extends Error {
  public status: number;
  public detail: string;
  public data?: unknown;

  constructor(status: number, detail: string, data?: unknown) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.data = data;
  }
}

let onUnauthorizedCallback: (() => void) | null = null;

export const setOnUnauthorizedCallback = (callback: () => void) => {
  onUnauthorizedCallback = callback;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ? import.meta.env.VITE_API_BASE_URL.replace(/\/+$/, '') : '';

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = tokenStorage.getToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${normalizedEndpoint}`;

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    tokenStorage.clearToken();
    if (onUnauthorizedCallback) {
      onUnauthorizedCallback();
    }
    throw new ApiError(401, 'Session expired or unauthenticated. Please log in.');
  }

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    let errJson: any = undefined;
    try {
      errJson = await response.json();
      if (errJson?.detail) {
        if (typeof errJson.detail === 'string') {
          errorDetail = errJson.detail;
        } else if (Array.isArray(errJson.detail)) {
          errorDetail = errJson.detail
            .map((d: any) => {
              const field = Array.isArray(d?.loc) ? d.loc.slice(-1)[0] : '';
              return field ? `${field}: ${d?.msg || 'Invalid value'}` : d?.msg || JSON.stringify(d);
            })
            .join('; ');
        } else {
          errorDetail = JSON.stringify(errJson.detail);
        }
      } else if (typeof errJson?.message === 'string') {
        errorDetail = errJson.message;
      } else if (typeof errJson?.error?.message === 'string') {
        errorDetail = errJson.error.message;
      }
    } catch {
      // Non-JSON error body
    }
    throw new ApiError(response.status, errorDetail, errJson);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return (await response.json()) as T;
}
