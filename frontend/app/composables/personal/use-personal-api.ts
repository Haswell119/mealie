import { useRequests } from "~/composables/api/api-client";
import { PersonalApi } from "~/lib/api/user/personal";

/** The API of the personal edition, on the same authenticated connection as the rest of the application. */
export function usePersonalApi(): PersonalApi {
  return new PersonalApi(useRequests());
}
