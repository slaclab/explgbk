import type { AxiosError } from "axios"

function extractErrorMessage(err: AxiosError): string {
  const errDetail = (err.response?.data as any)?.detail
  if (Array.isArray(errDetail) && errDetail.length > 0) {
    return errDetail[0].msg
  }
  return errDetail || err.message || "Something went wrong."
}

export const handleError = function (
  this: (msg: string) => void,
  err: AxiosError,
) {
  const errorMessage = extractErrorMessage(err)
  this(errorMessage)
}

export const getInitials = (name: string): string => {
  return name
    .split(" ")
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase()
}
