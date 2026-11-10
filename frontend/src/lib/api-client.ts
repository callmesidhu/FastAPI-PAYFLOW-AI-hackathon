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

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

let onUnauthorizedCallback: (() => void) | null = null;

export const setOnUnauthorizedCallback = (callback: () => void) => {
  onUnauthorizedCallback = callback;
};

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

  const response = await fetch(endpoint, {
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
    try {
      const errJson = await response.json();
      if (errJson && errJson.detail) {
        errorDetail = errJson.detail;
      }
    } catch {
      // Non-JSON error body
    }
    throw new ApiError(response.status, errorDetail);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return (await response.json()) as T;
}
