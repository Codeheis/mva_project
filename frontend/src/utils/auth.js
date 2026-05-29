export function getTokenFromLocalStorage() {
  return localStorage.getItem('userToken') || '';
}

export function setTokenInLocalStorage(token) {
  if (token) localStorage.setItem('userToken', token);
  else localStorage.removeItem('userToken');
}

