export function isAbortError(error: unknown): boolean {
  if (!error || typeof error !== 'object') {
    return false
  }

  const maybeError = error as {
    name?: string
    code?: string
    message?: string
  }

  return (
    maybeError.name === 'AbortError' ||
    maybeError.name === 'CanceledError' ||
    maybeError.code === 'ERR_CANCELED' ||
    maybeError.message === 'canceled'
  )
}
