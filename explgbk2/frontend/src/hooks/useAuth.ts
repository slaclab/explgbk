import { useQuery } from "@tanstack/react-query"

import { type UserPublic, UsersService } from "@/client"

const useAuth = () => {
  const { data: user } = useQuery<UserPublic | null, Error>({
    queryKey: ["currentUser"],
    queryFn: UsersService.readUserMe,
  })

  return { user }
}

export default useAuth
