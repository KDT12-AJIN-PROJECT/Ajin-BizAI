import { useCallback, useEffect, useState } from 'react'
import { fetchAllNotices } from '../../../api/noticesApi'

export function useNotices() {
  const [notices, setNotices] = useState([])
  const [errors, setErrors] = useState([])
  const [loading, setLoading] = useState(true)

  const reload = useCallback(async ({ refresh = false } = {}) => {
    setLoading(true)
    setErrors([])
    try {
      const { notices: fetched, errors: errs } = await fetchAllNotices({ refresh })
      setNotices(fetched)
      setErrors(errs)
    } catch (err) {
      setNotices([])
      setErrors([err instanceof Error ? err.message : '알 수 없는 오류'])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = setTimeout(reload, 0)
    return () => clearTimeout(timer)
  }, [reload])

  return { notices, errors, loading, reload }
}
