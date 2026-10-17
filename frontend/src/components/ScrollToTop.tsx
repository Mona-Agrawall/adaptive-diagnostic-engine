import { useEffect } from 'react';
import { useLocation } from 'react-router';

/** Reset scroll on route changes (but not on in-page hash links). */
export function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo?.(0, 0);
  }, [pathname]);
  return null;
}
