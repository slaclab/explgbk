import { useQuery } from "@tanstack/react-query"

import { usersReadUserMeOptions } from "@/client/@tanstack/react-query.gen"

const useAuth = () => {
  const { data: user } = useQuery(usersReadUserMeOptions())

  return { user }
}

export default useAuth
