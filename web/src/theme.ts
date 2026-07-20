import { useEffect } from 'react'
import { useUI } from './store'

/** Applies the selected theme to the document root. */
export function useApplyTheme() {
  const theme = useUI((s) => s.theme)
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
  }, [theme])
}
